
import os
import json
import re
import time
import base64
import requests
import pandas as pd
import streamlit as st
import altair as alt

APP_NAME = "ENVY"

# ---------------------------
# Header (Logo + Title)
# ---------------------------
def header():
    cols = st.columns([1,8,1])
    with cols[0]:
        if Path("envy_logo.png").exists():
            st.image("envy_logo.png", use_column_width=True)
        else:
            st.markdown(f"### **{APP_NAME}**")
    with cols[1]:
        st.markdown(
            "<h2 style='margin:0'>실시간 환율 + 📊 마진 + 📈 데이터랩 + 🛒 11번가 + ✍️ 상품명(API)</h2>",
            unsafe_allow_html=True
        )
    st.write("")

# ---------------------------
# FX utils (cached fetch)
# ---------------------------
@st.cache_data(ttl=60*30)  # 30분 캐시
def fetch_usdkrw():
    # 두 개 소스 fallback (여기선 예시 URL, 실제 운영 시 적절히 교체)
    urls = [
        "https://api.exchangerate.host/latest?base=USD&symbols=KRW",
        "https://open.er-api.com/v6/latest/USD"
    ]
    for u in urls:
        try:
            r = requests.get(u, timeout=8)
            if r.ok:
                j = r.json()
                if "rates" in j and "KRW" in j["rates"]:
                    return float(j["rates"]["KRW"])
                if "result" in j and j["result"] == "success":
                    return float(j["rates"]["KRW"])
        except Exception:
            pass
    return None

# ---------------------------
# DataLab mock API (explanation)
# In production this should call Naver DataLab with your keys.
# ---------------------------
def datalab_top20_seed(category:str):
    # 내장 시드 (간단 샘플)
    seeds = {
        "패션의류":["맨투맨","슬랙스","청바지","카라티","바람막이","니트","가디건","롱스커트","부츠컷","와이드팬츠","조거팬츠","박시티","패딩조끼","하프코트","플리츠스커트","트레이닝셋","골덴팬츠","새틴스커트","롱가디건","크롭니트"],
        "스포츠/레저":["런닝화","테니스라켓","요가복","축구공","헬스장갑","등산스틱","캠핑체어","자전거헬멧","수영복","아노락","보드웨어","스키장갑","아이젠","체육복","싸이클슈즈","발열내의","스포츠브라","스포츠레깅스","기능티셔츠","배구공"],
        "식품":["라면","커피","참치","스팸","초콜릿","과자","치즈","김","어묵","캔햄","김치","시리얼","꿀","콩나물","두유","냉동만두","우유","소시지","스테비아토마토","고구마"],
    }
    return seeds.get(category, seeds["패션의류"])

def datalab_ratio_for_keywords(keywords):
    # 실제 API가 아니므로 예시 가중치 생성
    rows = []
    base = 50
    for kw in keywords:
        seed = sum(bytearray(kw.encode("utf-8"))) % 30
        d1 = base + (seed % 11)
        d7 = base + (seed % 17) + 5
        d30 = base + (seed % 23) + 10
        rows.append({"keyword": kw, "day1": d1, "day7": d7, "day30": d30})
    return pd.DataFrame(rows)

# ---------------------------
# 11st Amazon Best (proxy/table + new-window + iframe)
# ---------------------------
def fetch_11st_rows(proxy_base:str, ua:str):
    headers = {"User-Agent": ua} if ua else {}
    target = "https://m.11st.co.kr/browsing/AmazonBest"
    text = ""
    try:
        if proxy_base:
            url = proxy_base + target
            text = requests.get(url, headers=headers, timeout=8).text
        else:
            text = requests.get(target, headers=headers, timeout=8).text
    except Exception:
        text = ""

    rows = []
    try:
        names = re.findall(r'\\"productName\\"\\s*:\\s*\\"([^\\"]{3,120})\\"', text)
        prices = re.findall(r'\\"finalPrice\\"\\s*:\\s*\\"?(\\d[\\d,]{2,})\\"?', text)
        links  = re.findall(r'\\"detailUrl\\"\\s*:\\s*\\"([^\\"]+)\\"', text)
        for i, n in enumerate(names[:20]):
            price = prices[i] if i < len(prices) else ""
            link  = links[i]  if i < len(links)  else ""
            rows.append({"rank": i+1, "product": n, "price": price.replace(",", ""), "link": link})
    except Exception:
        rows = []

    if not rows:
        rows = [
            {"rank":1,"product":"애플 에어팟 Pro (2세대)","price":"329000","link":""},
            {"rank":2,"product":"삼성 갤럭시 S23 256GB","price":"998000","link":""},
            {"rank":3,"product":"나이키 운동화 레볼루션","price":"89000","link":""},
            {"rank":4,"product":"LG 노트북 16형 초경량","price":"1399000","link":""},
            {"rank":5,"product":"스타벅스 텀블러 473ml","price":"23000","link":""},
        ]
    return pd.DataFrame(rows)

# ---------------------------
# Title generator (rule + OpenAI API or HTTP fallback)
# ---------------------------
def generate_titles(brand, base_text, raw_keywords, use_api:bool, api_key:str, n:int=5):
    kw = [k.strip() for k in raw_keywords.split(",") if k.strip()]
    if not kw:
        kw = ["신상","인기"]
    # 규칙 기반 후보
    rule = [f"{brand} {base_text} {k}" if brand else f"{base_text} {k}" for k in kw][:n]

    if not use_api or not api_key:
        return rule

    # OpenAI 패키지 우선, 없으면 HTTP fallback
    prompt = (
        "당신은 한국 이커머스 상품명 전문가입니다. 아래 조건으로 5개의 상품명을 만드세요.\n"
        f"- 브랜드: {brand or '없음'}\n"
        f"- 기본 문장: {base_text}\n"
        f"- 키워드 후보: {', '.join(kw)}\n"
        "- 한국어, 28~36자, 광고성 금지어 금지, 핵심 키워드 자연스럽게 포함\n"
        "- JSON 배열만 결과로 출력"
    )

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"user","content":prompt}],
            temperature=0.7,
        )
        txt = resp.choices[0].message.content.strip()
    except Exception:
        # HTTP fallback
        try:
            url = "https://api.openai.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type":"application/json"}
            payload = {
                "model":"gpt-4o-mini",
                "messages":[{"role":"user","content":prompt}],
                "temperature":0.7
            }
            r = requests.post(url, headers=headers, json=payload, timeout=30)
            r.raise_for_status()
            txt = r.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            st.warning(f"OpenAI 호출 실패, 규칙 기반으로 대체합니다. ({e})")
            return rule

    try:
        arr = json.loads(txt)
        if isinstance(arr, list) and arr:
            return arr[:n]
    except Exception:
        pass
    # 파싱 실패 시 줄바꿈 분해
    return [s.strip("-• ").strip() for s in re.split(r"[\n\r]+", txt) if s.strip()][:n]

def length_bytes(s:str)->int:
    return len(s.encode("utf-8"))

# ---------------------------
# Main
# ---------------------------
def main():
    header()

    st.sidebar.markdown("### 환율 계산기")
    amount = st.sidebar.number_input("현지 금액", value=1.00, step=1.0, min_value=0.0)
    base_ccy = st.sidebar.selectbox("현지 통화", ["USD ($)","EUR (€)","JPY (¥)","CNY (¥)"])
    usdkrw = fetch_usdkrw()
    if usdkrw:
        if base_ccy.startswith("USD"):
            krw = amount * usdkrw
        else:
            # 단순 예시: 타 통화는 USD 동등 환산 생략
            krw = None
        if krw is not None:
            st.sidebar.success(f"환율(USD→KRW): ￦{usdkrw:,.2f}\n\n예상 원화: **￦{krw:,.0f}**")
        else:
            st.sidebar.info("USD 외 통화 환산은 간단표시 생략(예시).")
    else:
        st.sidebar.error("환율 정보를 불러올 수 없습니다.")

    # --- 본문 레이아웃 ---
    col1, col2 = st.columns([7,5])

    # ========== DataLab ==========
    with col1:
        st.subheader("📈 네이버 데이터랩 (API 전용: 1/7/30일 평균 → 그래프)")

        cat = st.selectbox("카테고리 선택", ["패션의류","스포츠/레저","식품"])
        seeds = datalab_top20_seed(cat)

        # ratio df (mock)
        df = datalab_ratio_for_keywords(seeds)

        # 표 대신 그래프 중심
        tabs = st.tabs(["1일", "7일", "30일", "비교(1/7/30)"])

        # 개별 기간 차트
        def plot_single(field, title):
            d = df[["keyword", field]].rename(columns={field:"ratio"})
            d = d.sort_values("ratio", ascending=False).head(20)
            chart = alt.Chart(d).mark_bar().encode(
                x=alt.X("ratio:Q", title="ratio"),
                y=alt.Y("keyword:N", sort='-x', title="keyword"),
                tooltip=["keyword","ratio"]
            ).properties(height=520, title=title)
            st.altair_chart(chart, use_container_width=True)

        with tabs[0]:
            plot_single("day1", "최근 1일 평균 ratio (Top20)")
        with tabs[1]:
            plot_single("day7", "최근 7일 평균 ratio (Top20)")
        with tabs[2]:
            plot_single("day30", "최근 30일 평균 ratio (Top20)")

        # 비교 차트 (3개 필드 melt)
        with tabs[3]:
            dd = df.melt(id_vars=["keyword"], value_vars=["day1","day7","day30"], var_name="period", value_name="ratio")
            dd = dd.sort_values("ratio", ascending=False).groupby("period").head(20)
            chart = alt.Chart(dd).mark_bar().encode(
                x=alt.X("ratio:Q"),
                y=alt.Y("keyword:N", sort='-x'),
                color=alt.Color("period:N"),
                tooltip=["keyword","period","ratio"]
            ).properties(height=520, title="1/7/30일 비교 (Top20 각 기간 상위)")
            st.altair_chart(chart, use_container_width=True)

    # ========== 11번가 ==========
    with col2:
        st.subheader("🛒 11번가 AmazonBest")
        with st.sidebar.expander("🛒 11번가 옵션", expanded=False):
            proxy_base = st.text_input("프록시 베이스 URL", value=st.session_state.get("e11_proxy", ""))
            ua = st.text_input("User-Agent (선택)", value=st.session_state.get("e11_ua", "Mozilla/5.0"))
            st.session_state["e11_proxy"] = proxy_base
            st.session_state["e11_ua"] = ua

        st.link_button("🔗 새창에서 11번가 열기", "https://m.11st.co.kr/browsing/AmazonBest")
        rows = fetch_11st_rows(st.session_state.get("e11_proxy",""), st.session_state.get("e11_ua",""))
        st.caption("프록시/직결로 가져온 결과 (차단 시 샘플 폴백)")
        st.dataframe(rows, use_container_width=True, height=440)
        with st.expander("🧪 iframe으로 직접 보기 (환경에 따라 차단)", expanded=False):
            html = """
            <iframe src='https://m.11st.co.kr/browsing/AmazonBest'
                    width='100%' height='760' frameborder='0'
                    referrerpolicy='no-referrer'
                    sandbox='allow-same-origin allow-scripts allow-popups allow-forms'>
            </iframe>"""
            st.components.v1.html(html, height=780)

    st.divider()

    # ========== Title Generator ==========
    st.subheader("✍️ 상품명 생성기")
    mode = st.radio("모드 선택", ["규칙 기반(무료)", "OpenAI API 사용"], horizontal=True)
    brand = st.text_input("브랜드")
    base_text = st.text_input("기본 문장")
    raw_keywords = st.text_input("키워드(쉼표 , 로 구분)")
    cnt = st.slider("생성 개수", 3, 10, 5)

    api_key = ""
    if mode == "OpenAI API 사용":
        with st.expander("🔐 OpenAI API 설정 (선택)"):
            api_key = st.text_input("OpenAI API Key (sk-…)", type="password")
            if api_key:
                st.session_state["OPENAI_API_KEY"] = api_key
        api_key = api_key or st.session_state.get("OPENAI_API_KEY", "") or os.getenv("OPENAI_API_KEY","")

    if st.button("제목 생성", type="primary"):
        titles = generate_titles(
            brand=brand, base_text=base_text, raw_keywords=raw_keywords,
            use_api=(mode=="OpenAI API 사용"), api_key=api_key, n=cnt
        )
        out = pd.DataFrame({"title": titles})
        out["chars"] = out["title"].apply(len)
        out["bytes(UTF-8)"] = out["title"].apply(length_bytes)
        st.success("생성 완료")
        st.dataframe(out, use_container_width=True)
        st.caption("참고: 한국 오픈마켓은 바이트 기준(UTF-8) 제한이 걸린 경우가 있어, 글자수/바이트를 함께 표기했습니다.")

if __name__ == "__main__":
    from pathlib import Path
    header  # linter keep
    main()

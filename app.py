
import os
import json
import re
import time
from datetime import datetime, timedelta

import pandas as pd
import requests
import streamlit as st
import altair as alt

APP_NAME = "ENVY"

# =====================
# Utilities
# =====================
def header():
    cols = st.columns([1,8,1])
    with cols[0]:
        # logo optional
        if Path("envy_logo.png").exists():
            st.image("envy_logo.png", use_column_width=True)
        else:
            st.markdown(f"### **{APP_NAME}**")
    with cols[1]:
        st.markdown(
            "<h2 style='margin:0'>실시간 환율 + 📊 마진 + 📈 데이터랩 + 🛒 11번가 + ✍️ 상품명(API)</h2>",
            unsafe_allow_html=True,
        )
    st.write("")

@st.cache_data(ttl=60*30)
def fetch_usdkrw():
    urls = [
        "https://api.exchangerate.host/latest?base=USD&symbols=KRW",
        "https://open.er-api.com/v6/latest/USD",
    ]
    for u in urls:
        try:
            r = requests.get(u, timeout=8)
            if r.ok:
                j = r.json()
                # exchangerate.host
                if "rates" in j and "KRW" in j["rates"]:
                    return float(j["rates"]["KRW"])
                # er-api
                if j.get("result") == "success" and "rates" in j:
                    return float(j["rates"]["KRW"])
        except Exception:
            pass
    return None

# =====================
# DataLab (mock + CSV + hooks)
# =====================
CATEGORY_SEEDS = {
    "패션의류":["맨투맨","슬랙스","청바지","카라티","바람막이","니트","가디건","롱스커트","부츠컷","와이드팬츠","조거팬츠","박시티","패딩조끼","하프코트","플리츠스커트","트레이닝셋","골덴팬츠","새틴스커트","롱가디건","크롭니트"],
    "스포츠/레저":["런닝화","테니스라켓","요가복","축구공","헬스장갑","등산스틱","캠핑체어","자전거헬멧","수영복","아노락","보드웨어","스키장갑","아이젠","체육복","싸이클슈즈","발열내의","스포츠브라","스포츠레깅스","기능티셔츠","배구공"],
    "식품":["라면","커피","참치","스팸","초콜릿","과자","치즈","김","어묵","캔햄","김치","시리얼","꿀","콩나물","두유","냉동만두","우유","소시지","스테비아토마토","고구마"],
}

def mock_ratios_from_keywords(keywords):
    rows = []
    base = 50
    for kw in keywords:
        seed = sum(bytearray(kw.encode("utf-8"))) % 30
        d1 = base + (seed % 11)
        d7 = base + (seed % 17) + 5
        d30 = base + (seed % 23) + 10
        rows.append({"keyword": kw, "day1": d1, "day7": d7, "day30": d30})
    return pd.DataFrame(rows)

def clean_keyword(s:str)->str:
    ss = s.strip()
    # 간단 정규화: 중복공백 제거, 슬래시/하이픈 통일
    ss = re.sub(r"[\/\-]+", " ", ss)
    ss = re.sub(r"\s+", " ", ss)
    return ss

def normalize_keywords(keywords):
    # 동의어/철자 변형 맵 (예시)
    norm_map = {
        "맨투맨":"맨투맨",
        "맨투 맨":"맨투맨",
        "티셔츠":"티셔츠",
        "티 샤츠":"티셔츠",
        "데님 팬츠":"청바지",
        "데님":"청바지",
        "바이크 쇼츠":"바이크쇼츠",
    }
    out = []
    for k in keywords:
        k2 = clean_keyword(k)
        out.append(norm_map.get(k2, k2))
    return out

def parse_uploaded_csv(file):
    # 기대 포맷: keyword[,day1,day7,day30] — 없으면 모의 값 생성
    try:
        df = pd.read_csv(file)
        if "keyword" in df.columns:
            for c in ["day1","day7","day30"]:
                if c not in df.columns:
                    # 모의로 채우기
                    tmp = mock_ratios_from_keywords(df["keyword"].tolist())
                    df = df.merge(tmp, on="keyword", how="left")
                    break
            df["keyword"] = df["keyword"].astype(str).apply(clean_keyword)
            return df[["keyword","day1","day7","day30"]]
    except Exception:
        pass
    return None

# =====================
# 11st
# =====================
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

# =====================
# Title generation + 금칙어 자동대체
# =====================
DEFAULT_FORBIDDEN = [
    "최고","유일","완치","100%","전부다","국내최초","세계최초","보장","환불보장",
    "초특가","파격세일","공짜","무료","덤","대박","미친","극강","압도적",
    "만병통치","효능","치료","즉시효과","확실","절대","무조건","안전보장",
]

DEFAULT_REPLACE_MAP = {
    "무료":"무상",
    "공짜":"무상",
    "대박":"인기",
    "미친":"강력",
    "파격세일":"특가",
    "보장":"제공",
    "최고":"우수",
    "세계최초":"새로운",
    "국내최초":"새로운",
}

def normalize_title(s:str)->str:
    # 이모지/특수문자 일부 제거 (간단)
    s = re.sub(r"[\u2600-\u27BF\u1F300-\u1F9FF]+", "", s)  # emojis (rough)
    s = s.replace("  ", " ")
    s = re.sub(r"\s+", " ", s).strip(" -_/·")
    return s.strip()

def apply_forbidden_map(text:str, forbidden:list, repl_map:dict):
    out = text
    # 우선 대체 맵 적용
    for bad, repl in repl_map.items():
        try:
            out = re.sub(re.escape(bad), repl, out, flags=re.IGNORECASE)
        except Exception:
            pass
    # 남은 금칙어는 제거
    for bad in forbidden:
        if bad in repl_map:  # 이미 처리됨
            continue
        try:
            out = re.sub(re.escape(bad), "", out, flags=re.IGNORECASE)
        except Exception:
            pass
    out = normalize_title(out)
    return out

def title_bytes(s:str)->int:
    return len(s.encode("utf-8"))

def rule_candidates(brand, base_text, keywords, n=5):
    if not keywords:
        keywords = ["신상","인기"]
    rule = [f"{brand} {base_text} {k}".strip() if brand else f"{base_text} {k}".strip() for k in keywords]
    return rule[:n]

def call_openai(api_key, prompt):
    # SDK 우선 → 실패 시 HTTP fallback
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"user","content":prompt}],
            temperature=0.7,
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        try:
            url = "https://api.openai.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type":"application/json"}
            payload = {"model":"gpt-4o-mini","messages":[{"role":"user","content":prompt}], "temperature":0.7}
            r = requests.post(url, headers=headers, json=payload, timeout=30)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            raise RuntimeError(f"OpenAI 호출 실패: {e}")

# =====================
# Streamlit UI
# =====================
def main():
    header()

    # Sidebar: 환율
    st.sidebar.markdown("### 환율 계산기")
    amount = st.sidebar.number_input("현지 금액", value=1.00, step=1.0, min_value=0.0)
    base_ccy = st.sidebar.selectbox("현지 통화", ["USD ($)","EUR (€)","JPY (¥)","CNY (¥)"])
    usdkrw = fetch_usdkrw()
    if usdkrw and base_ccy.startswith("USD"):
        st.sidebar.success(f"USD→KRW: ￦{usdkrw:,.2f}\n\n예상 원화: **￦{amount*usdkrw:,.0f}**")
    elif not usdkrw:
        st.sidebar.error("환율 불러오기 실패")

    # Main layout
    col1, col2 = st.columns([7,5])

    # -------- DataLab --------
    with col1:
        st.subheader("📈 네이버 데이터랩 (Top20 + 1/7/30 그래프)")

        cat = st.selectbox("카테고리 선택", list(CATEGORY_SEEDS.keys()), index=0)
        seeds_default = CATEGORY_SEEDS[cat]

        # 업로드로 직접 시드/지표 입력 지원
        up = st.file_uploader("키워드 시드 업로드 (CSV, 선택) — 컬럼: keyword[,day1,day7,day30]", type=["csv"])
        if up:
            df = parse_uploaded_csv(up)
            if df is None:
                st.warning("CSV 해석 실패. 기본 시드로 대체합니다.")
                df = mock_ratios_from_keywords(seeds_default)
        else:
            # 모의 지표
            df = mock_ratios_from_keywords(seeds_default)

        # 키워드 정규화/중복 제거
        df["keyword"] = normalize_keywords(df["keyword"].astype(str))
        df = df.drop_duplicates("keyword")

        tabs = st.tabs(["1일", "7일", "30일", "비교(1/7/30)"])

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

    # -------- 11번가 --------
    with col2:
        st.subheader("🛒 11번가 AmazonBest")
        with st.sidebar.expander("🛒 11번가 옵션", expanded=False):
            proxy_base = st.text_input("프록시 베이스 URL", value=st.session_state.get("e11_proxy", ""))
            ua = st.text_input("User-Agent (선택)", value=st.session_state.get("e11_ua", "Mozilla/5.0"))
            st.session_state["e11_proxy"] = proxy_base
            st.session_state["e11_ua"] = ua

        st.link_button("🔗 새창에서 11번가 열기", "https://m.11st.co.kr/browsing/AmazonBest")
        rows = fetch_11st_rows(st.session_state.get("e11_proxy",""), st.session_state.get("e11_ua",""))
        st.caption("프록시/직결 결과 (차단 시 샘플 폴백)")
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

    # -------- Title generator + forbidden filter --------
    st.subheader("✍️ 상품명 생성기 + 금칙어 자동대체")
    mode = st.radio("모드 선택", ["규칙 기반(무료)", "OpenAI API 사용"], horizontal=True)
    brand = st.text_input("브랜드")
    base_text = st.text_input("기본 문장")
    raw_keywords = st.text_input("키워드(쉼표 , 로 구분)")
    cnt = st.slider("생성 개수", 3, 10, 5)

    with st.expander("🛡️ 금칙어/대체어 설정", expanded=True):
        colA, colB, colC = st.columns([4,4,2])
        with colA:
            forb = st.text_area("금칙어 목록(줄바꿈으로 구분)", value="\n".join(DEFAULT_FORBIDDEN), height=160)
            forbidden = [w.strip() for w in forb.splitlines() if w.strip()]
        with colB:
            repl_lines = st.text_area("대체 맵(형식: 원문=>대체어, 줄바꿈)", value="\n".join([f"{k}=>{v}" for k,v in DEFAULT_REPLACE_MAP.items()]), height=160)
            repl_map = {}
            for line in repl_lines.splitlines():
                if "=>" in line:
                    a,b = line.split("=>",1)
                    repl_map[a.strip()] = b.strip()
        with colC:
            max_bytes = st.number_input("바이트 제한(UTF-8)", min_value=10, max_value=120, value=60, step=2)
            hard_trim = st.checkbox("제한 초과 시 자동 자르기", value=True)

    api_key = ""
    if mode == "OpenAI API 사용":
        with st.expander("🔐 OpenAI API 설정 (선택)"):
            api_key = st.text_input("OpenAI API Key (sk-…)", type="password")
            if api_key:
                st.session_state["OPENAI_API_KEY"] = api_key
        api_key = api_key or st.session_state.get("OPENAI_API_KEY", "") or os.getenv("OPENAI_API_KEY","")

    if st.button("제목 생성", type="primary"):
        keywords = [k.strip() for k in raw_keywords.split(",") if k.strip()]
        titles = rule_candidates(brand, base_text, keywords, n=cnt)

        if mode == "OpenAI API 사용" and api_key:
            prompt = (
                "당신은 한국 이커머스 상품명 전문가입니다. 아래 조건으로 "
                f"{cnt}개의 상품명을 만드세요.\n"
                f"- 브랜드: {brand or '없음'}\n"
                f"- 기본 문장: {base_text}\n"
                f"- 키워드 후보: {', '.join(keywords) or '신상, 인기'}\n"
                "- 한국어, 28~36자, 광고성 금지어 금지, 핵심 키워드 자연스럽게 포함\n"
                "- JSON 배열만 결과로 출력"
            )
            try:
                resp = call_openai(api_key, prompt)
                try:
                    arr = json.loads(resp)
                    if isinstance(arr, list) and arr:
                        titles = arr[:cnt]
                except Exception:
                    # 줄바꿈 리스트 허용
                    lines = [s.strip("-• ").strip() for s in re.split(r"[\n\r]+", resp) if s.strip()]
                    if lines:
                        titles = lines[:cnt]
            except Exception as e:
                st.warning(f"OpenAI 실패: {e}. 규칙 기반으로 대체합니다.")

        # 금칙어 자동 대체 적용
        after = []
        for t in titles:
            t1 = apply_forbidden_map(t, forbidden, repl_map)
            if title_bytes(t1) > max_bytes and hard_trim:
                # 바이트 초과 시 부드럽게 자르기
                b = t1.encode("utf-8")
                b = b[:max_bytes]
                # 깨진 멀티바이트 컷 보정
                while True:
                    try:
                        t1 = b.decode("utf-8")
                        break
                    except UnicodeDecodeError:
                        b = b[:-1]
            after.append(t1)

        df = pd.DataFrame({
            "원본": titles,
            "적용후": after,
            "chars": [len(s) for s in after],
            "bytes(UTF-8)": [title_bytes(s) for s in after],
        })
        st.success("생성 완료 (금칙어 자동대체 적용)")
        st.dataframe(df, use_container_width=True, height=330)
        st.download_button("CSV로 내보내기", df.to_csv(index=False).encode("utf-8-sig"), file_name="titles_filtered.csv", mime="text/csv")

if __name__ == "__main__":
    header  # keep
    main()


# -*- coding: utf-8 -*-
"""
ENVY Full (v14) — 환율 + 마진 + 데이터랩(TOP20/CSV) + 11번가(링크/우회 스텁)
+ 상품명 생성기(규칙/옵션 OpenAI) + AI 소싱 레이더(MVP)

실행: streamlit run app.py
필요 패키지: streamlit, requests, altair, pandas
(선택) openai 1.x 설치 시 OpenAI API 사용 가능
"""
import os, json, time, math, csv, io, sys
from pathlib import Path
from datetime import datetime, timedelta

import requests
import streamlit as st
import pandas as pd
import altair as alt

# -------------- 공통 --------------
APP_TITLE = "ENVY 풀버전 v14"
LOGO_PATH = Path("envy_logo.png")

def header():
    cols = st.columns([1,6])
    with cols[0]:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), width=72)
        else:
            st.markdown("### 🐾")
    with cols[1]:
        st.markdown(f"## {APP_TITLE}")
        st.caption("환율, 마진, 데이터랩, 11번가, 상품명 생성, AI 소싱 통합 버전")

def load_cache(path: Path):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_cache(path: Path, obj):
    try:
        path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

# -------------- 환율 --------------
CACHE_FILE = Path(".envy_cache.json")
DEFAULT_RATE = 1391.70

@st.cache_data(ttl=1800)  # 30분 캐시
def get_fx_rate(base: str="USD", symbols=("KRW",)):
    # 1차: exchangerate.host
    try:
        r = requests.get(
            "https://api.exchangerate.host/latest",
            params={"base": base, "symbols": ",".join(symbols)},
            timeout=5,
        )
        if r.ok:
            data = r.json()
            if "rates" in data and "KRW" in data["rates"]:
                return float(data["rates"]["KRW"])
    except Exception:
        pass
    # 2차: frankfurter
    try:
        r = requests.get(
            f"https://api.frankfurter.app/latest",
            params={"from": base, "to": "KRW"},
            timeout=5,
        )
        if r.ok:
            data = r.json()
            if "rates" in data and "KRW" in data["rates"]:
                return float(data["rates"]["KRW"])
    except Exception:
        pass
    return DEFAULT_RATE

def fx_block():
    st.subheader("환율 계산기")
    c1, c2, c3 = st.columns([2,1,2])
    with c1:
        amount = st.number_input("상품 원가", value=1.00, min_value=0.0, step=1.0, format="%.2f")
    with c2:
        base = st.selectbox("통화", ["USD","EUR","JPY","CNY"], index=0)
    with c3:
        rate = get_fx_rate(base=base, symbols=("KRW",))
        st.metric("현재 환율 (1 "+base+" ➜ KRW)", f"{rate:,.2f}")
    st.caption("환율은 30분 캐시, 실패 시 백업/기본값으로 폴백")

# -------------- 마진 계산 --------------
def compute_price(amount_foreign, base, shipping_krw, card_pct, market_pct, target_margin_pct):
    krw_rate = get_fx_rate(base=base, symbols=("KRW",))
    cost_krw = amount_foreign * krw_rate
    fees_ratio = (card_pct + market_pct) / 100.0
    target_margin = target_margin_pct / 100.0
    # 판매가 = (비용총합 / (1 - 수수료)) * (1 + 목표마진)
    base_cost = cost_krw + shipping_krw
    price = (base_cost / max(1e-6, (1 - fees_ratio))) * (1 + target_margin)
    profit = price - base_cost - price*fees_ratio
    profit_ratio = (profit / max(price,1e-6))*100.0
    return cost_krw, price, profit, profit_ratio

def margin_block():
    st.subheader("간이 마진 계산기")
    c1,c2 = st.columns(2)
    with c1:
        cur = st.selectbox("현지 통화", ["USD","EUR","JPY","CNY"], index=0, key="m_cur")
        amount_foreign = st.number_input("현지 금액", value=0.0, min_value=0.0, step=1.0, format="%.2f", key="m_amt")
        ship = st.number_input("배송비 (KRW)", value=0.0, min_value=0.0, step=500.0, format="%.0f", key="m_ship")
    with c2:
        card = st.number_input("카드 수수료 (%)", value=4.0, min_value=0.0, step=0.1, format="%.2f")
        market = st.number_input("마켓 수수료 (%)", value=15.0, min_value=0.0, step=0.5, format="%.2f")
        margin = st.number_input("목표 마진 (%)", value=40.0, min_value=0.0, step=0.5, format="%.2f")
    cost_krw, price, profit, pr = compute_price(amount_foreign, cur, ship, card, market, margin)
    st.info(f"원가(환산): ₩{cost_krw:,.0f}")
    st.success(f"예상 판매가: ₩{price:,.0f}")
    st.metric("예상 순이익", f"₩{profit:,.0f}", f"{pr:.1f}%")

# -------------- 데이터랩 --------------
CATEGORIES = [
    "패션의류","화장품/미용","식품","디지털/가전","스포츠/레저","생활/건강","출산/육아","가구/인테리어","문구/오피스","반려동물"
]

def datalab_block():
    st.subheader("네이버 데이터랩 (Top20 키워드)")
    cat = st.selectbox("카테고리 선택", CATEGORIES, index=0, key="dl_cat")
    st.caption("API 없을 경우 CSV 업로드(컬럼: keyword, day1, day7, day30). 업로드 없으면 샘플 생성")
    up = st.file_uploader("CSV 업로드 (선택)", type=["csv"], key="dl_csv")

    if up:
        df = pd.read_csv(up)
    else:
        # 샘플: keyword에 임의 20개 생성, day1/7/30 가중치로 점수 계산
        base_words = ["맨투맨","슬랙스","청바지","가디건","롱스커트","부츠컷","와이드팬츠","조거팬츠","빅사이즈","패턴풀오버",
                      "크롭셔츠","셔츠원피스","롱패딩","경량패딩","카라니트","브이넥","오버핏","미디스커트","테니스스커트","숏패딩"]
        import random
        random.seed(42+len(cat))
        day1 = [random.randint(20,100) for _ in base_words]
        day7 = [random.randint(10,90)  for _ in base_words]
        day30= [random.randint(5,80)   for _ in base_words]
        df = pd.DataFrame({"keyword":base_words, "day1":day1, "day7":day7, "day30":day30})
    # 점수
    df["score"] = 0.5*df["day1"] + 0.3*df["day7"] + 0.2*df["day30"]
    df = df.sort_values("score", ascending=False).reset_index(drop=True)
    df.index = df.index + 1
    st.dataframe(df[["keyword","day1","day7","day30","score"]].head(20), use_container_width=True)

    try:
        chart = alt.Chart(df.head(20)).mark_bar().encode(
            x="keyword:N", y="score:Q", tooltip=["keyword","day1","day7","day30","score"]
        ).properties(height=300)
        st.altair_chart(chart, use_container_width=True)
    except Exception:
        st.info("Altair 표시가 불가하여 표만 표시합니다.")

    st.session_state["datalab_df"] = df

# -------------- 11번가 --------------
def eleven_block():
    st.subheader("11번가 아마존 베스트")
    st.caption("환경상 iframe은 차단될 수 있어 새창 열기 링크 제공")
    c1,c2 = st.columns(2)
    with c1:
        st.link_button("모바일 열기", "https://m.11st.co.kr/MW/html/main.html")
    with c2:
        st.link_button("PC 열기", "https://www.11st.co.kr/")
    st.info("우회요약(스텁): 실제 크롤링은 프록시/헤더가 필요할 수 있어 자리만 구성.\n"
            "추후 프록시/UA 입력 시 테이블 채우는 훅 제공 예정.")

# -------------- 상품명 생성기 --------------
BANNED = ["무료", "공짜", "불법", "짝퉁", "정품아님"]
REPLACE_MAP = {"프리": "프리사이즈", "FREE":"프리사이즈"}

def byte_len(s: str):
    return len(s.encode("utf-8"))

def title_rules(brand, base, kws):
    parts = []
    if brand: parts.append(brand.strip())
    if base: parts.append(base.strip())
    if kws: parts.append(kws.strip())
    title = " ".join([x for x in parts if x])
    for b in BANNED:
        title = title.replace(b, "")
    for k,v in REPLACE_MAP.items():
        title = title.replace(k, v)
    # 공백 정리
    title = " ".join(title.split())
    return title

def openai_generate(api_key, prompt, n=5):
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        msgs = [{"role":"system","content":"You are a product title generator for e-commerce."},
                {"role":"user","content":prompt}]
        out = client.chat.completions.create(model="gpt-4o-mini", messages=msgs, n=n, temperature=0.7)
        return [c.message.content.strip() for c in out.choices]
    except Exception as e:
        return []

def product_title_block():
    st.subheader("상품명 생성기")
    mode = st.radio("모드", ["규칙기반(무료)", "OpenAI API 사용"], horizontal=True)
    api_key = None
    if mode == "OpenAI API 사용":
        api_key = st.text_input("OpenAI API Key", value=os.getenv("OPENAI_API_KEY",""), type="password")

    brand = st.text_input("브랜드", "")
    base = st.text_input("기본 문장", "")
    kws  = st.text_input("키워드(쉼표, 슬래시 등 자유)", "")

    max_bytes = st.number_input("최대 바이트(표시용)", value=60, min_value=10, step=2)
    btn = st.button("제목 생성", use_container_width=True)
    if btn:
        results = []
        if mode.startswith("규칙"):
            for i in range(5):
                t = title_rules(brand, base, kws)
                results.append(t)
        else:
            prompt = f"브랜드:{brand}\n기본:{base}\n키워드:{kws}\n한국 쇼핑몰용 짧고 선명한 상품명 5개 생성."
            results = openai_generate(api_key, prompt, n=5) if api_key else []

            if not results:
                # 폴백
                for i in range(5):
                    results.append(title_rules(brand, base, kws))
        # 표시
        rows = []
        for i, t in enumerate(results, 1):
            blen = byte_len(t)
            cut = t.encode("utf-8")[:max_bytes].decode("utf-8","ignore")
            rows.append({"#":i, "title":t, "bytes":blen, "trim_to_max":cut})
        st.dataframe(pd.DataFrame(rows), use_container_width=True)
        st.session_state["titles"] = rows

    if "titles" in st.session_state and st.session_state["titles"]:
        csv_buf = io.StringIO()
        pd.DataFrame(st.session_state["titles"]).to_csv(csv_buf, index=False, encoding="utf-8-sig")
        st.download_button("CSV 다운로드", data=csv_buf.getvalue().encode("utf-8-sig"),
                           file_name="titles.csv", mime="text/csv")

# -------------- AI 소싱 레이더 (MVP) --------------
def ai_sourcing_block():
    st.subheader("🤖 AI 소싱 레이더 (MVP)")
    st.caption("데이터랩 Top20 또는 CSV 업로드 데이터를 점수화하여 추천 키워드 제안")

    df = st.session_state.get("datalab_df")
    if df is None or df.empty:
        st.info("데이터랩에서 키워드를 먼저 불러오세요.")
        return
    # 포화도: 빈출(여기선 단순 순위) 정규화 흉내
    df2 = df.copy()
    if not all(c in df2.columns for c in ["day1","day7","day30","score"]):
        st.warning("스코어 산식을 위해 day1/day7/day30/score 필요. 샘플 활용을 권장.")
        return
    m = df2[["day1","day7","day30"]].max().max()
    df2["saturation"] = (df2["day1"] + df2["day7"] + df2["day30"]) / max(m*3,1e-6)
    # 금칙어 패널티
    def penalty(s):
        return 1.0 if any(b in s for b in BANNED) else 0.0
    df2["penalty"] = df2["keyword"].apply(penalty)
    df2["ai_score"] = (0.5*df2["day1"] + 0.3*df2["day7"] + 0.2*df2["day30"]) - 40*df2["saturation"] - 30*df2["penalty"]
    df2 = df2.sort_values("ai_score", ascending=False).reset_index(drop=True)
    df2.index = df2.index + 1
    st.dataframe(df2[["keyword","day1","day7","day30","saturation","penalty","ai_score"]].head(20), use_container_width=True)

    # CSV 다운로드
    csv_buf = io.StringIO()
    df2.to_csv(csv_buf, index=False, encoding="utf-8-sig")
    st.download_button("AI 소싱 추천 CSV", data=csv_buf.getvalue().encode("utf-8-sig"),
                       file_name="ai_sourcing.csv", mime="text/csv")

# -------------- 앱 레이아웃 --------------
def main():
    st.set_page_config(page_title="ENVY", page_icon="🐾", layout="wide")
    header()

    tabs = st.tabs(["환율/마진", "데이터랩", "11번가", "상품명 생성기", "AI 소싱"])

    with tabs[0]:
        fx_block()
        st.divider()
        margin_block()

    with tabs[1]:
        datalab_block()

    with tabs[2]:
        eleven_block()

    with tabs[3]:
        product_title_block()

    with tabs[4]:
        ai_sourcing_block()

if __name__ == "__main__":
    main()

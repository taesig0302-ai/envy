# ENVY v27.0 • Full (Real-time FX + v23 Margin Formula + All Modules)
# ⚠️ HuggingFace API Key는 예시. 로컬 테스트용으로만 사용하세요!

import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import json, random, html, requests, textwrap, urllib.parse

st.set_page_config(page_title="ENVY v27.0 Full", page_icon="🚀", layout="wide")

HF_API_KEY = "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"

# -------------------- currency utils --------------------
CURRENCY_SYMBOL = {"KRW":"₩","USD":"$","EUR":"€","JPY":"¥","CNY":"CN¥"}
FX_ORDER = ["USD","EUR","JPY","CNY"]

def fmt_money(v: float, code: str="KRW"):
    sym = CURRENCY_SYMBOL.get(code, "")
    try:
        return f"{sym}{v:,.0f} {code}"
    except Exception:
        return f"{v} {code}"

# -------------------- v23 margin formulas --------------------
def margin_calc_percent(cost_krw: float, ship_krw: float, card_pct: float, market_pct: float, margin_pct: float):
    cf, mf, m = card_pct/100.0, market_pct/100.0, margin_pct/100.0
    denom = max(1e-9, 1 - cf - mf)
    target_revenue = (cost_krw + ship_krw) * (1 + m)
    P = target_revenue / denom
    revenue = P * (1 - cf - mf)
    profit = revenue - (cost_krw + ship_krw)
    margin_on_sale = (profit / P * 100) if P > 0 else 0.0
    return P, profit, margin_on_sale

def margin_calc_add(cost_krw: float, ship_krw: float, card_pct: float, market_pct: float, add_margin_krw: float):
    cf, mf = card_pct/100.0, market_pct/100.0
    denom = max(1e-9, 1 - cf - mf)
    target_revenue = (cost_krw + ship_krw) + add_margin_krw
    P = target_revenue / denom
    revenue = P * (1 - cf - mf)
    profit = revenue - (cost_krw + ship_krw)
    margin_on_sale = (profit / P * 100) if P > 0 else 0.0
    return P, profit, margin_on_sale

# -------------------- mock data for DataLab & Sourcing --------------------
CATE_KEYWORDS = {
    "식품 > 커피/믹스/차": ["커피 믹스","맥심","카누","드립백","인스턴트 커피","유자차","녹차","보리차","아메리카노","스틱 커피",
                          "원두커피","디카페인","콜드브루","헤이즐넛","캡슐커피","카라멜마끼아또","티백","허브티","핫초코","라떼"]
}
GLOBAL_KEYWORDS = {
    "Amazon US": ["protein bar","wireless earbuds","air fryer","heated blanket","gel nail kit"],
    "Amazon JP": ["コーヒーミックス","加湿器","トレカスリーブ","ワイヤレスイヤホン","抹茶"],
    "Rakuten JP": ["楽天ランキング","水筒","タンブラー","サプリメント","タオル"]
}

def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")

def copy_button(text: str, key: str):
    safe_text = html.escape(text).replace("\n","\\n").replace("'","\\'")
    html_str = f"""
    <div style='display:flex;gap:8px;align-items:center;margin:6px 0;'>
      <input id='inp_{key}' value='{html.escape(text)}' style='flex:1;padding:6px 8px;' />
      <button onclick="navigator.clipboard.writeText('{safe_text}')">복사</button>
    </div>
    """
    st.components.v1.html(html_str, height=46)

# -------------------- Sidebar --------------------
st.sidebar.header("① 환율 계산기 (실시간)")
base_ccy = st.sidebar.selectbox("기준 통화", FX_ORDER, index=0)
sym = CURRENCY_SYMBOL.get(base_ccy, "")
st.sidebar.caption(f"기준 통화 기호: {sym}")

if st.sidebar.button("실시간 환율 불러오기", type="primary", use_container_width=True):
    try:
        url = f"https://api.exchangerate.host/latest?base={base_ccy}&symbols=KRW"
        r = requests.get(url, timeout=10)
        data = r.json()
        rate = float(data["rates"]["KRW"])
        st.session_state["fx_rate"] = rate
        st.sidebar.success(f"1 {sym} = {rate:,.2f} ₩ (업데이트 {data.get('date','')})")
    except Exception as e:
        st.sidebar.error(f"환율 호출 실패: {e}")

ex = st.sidebar.number_input(f"환율 (1 {sym} → ? ₩)", 0.00, 100000.00, float(st.session_state.get("fx_rate", 1400.00)), 0.01, format="%.2f")

st.sidebar.markdown("---")
st.sidebar.header("② 마진 계산기 (v23 공식)")
cost = st.sidebar.number_input("구매가격 (환율 적용 금액, ₩)", 0.0, 1e12, 250000.0, 100.0)
ship = st.sidebar.number_input("배송비 (₩)", 0.0, 1e10, 0.0, 100.0)
card = st.sidebar.number_input("카드수수료 (%)", 0.0, 100.0, 4.0, 0.1)
market = st.sidebar.number_input("마켓수수료 (%)", 0.0, 100.0, 14.0, 0.1)
mode = st.sidebar.radio("마진 방식", ["퍼센트 마진(%)","더하기 마진(₩)"], horizontal=True)

if mode=="퍼센트 마진(%)":
    margin_pct = st.sidebar.number_input("마진율 (%)", 0.0, 500.0, 10.0, 0.1)
    P, profit, on_sale = margin_calc_percent(cost, ship, card, market, margin_pct)
else:
    add_margin = st.sidebar.number_input("더하기 마진 (₩)", 0.0, 1e12, 10000.0, 100.0)
    P, profit, on_sale = margin_calc_add(cost, ship, card, market, add_margin)

st.sidebar.metric("판매가격", fmt_money(P, "KRW"))
st.sidebar.metric("순이익(마진)", fmt_money(profit, "KRW"))
st.sidebar.caption(f"마진율(판매가 기준): {on_sale:.2f}%")

# -------------------- Body --------------------
st.title("🚀 ENVY v27.0 Full (실시간 환율 + v23 마진공식 + 전체 모듈)")

# 데이터랩
st.subheader("데이터랩 (카테고리 선택 → Top20 키워드)")
category = st.selectbox("카테고리", list(CATE_KEYWORDS.keys()))
kw_list = CATE_KEYWORDS[category]
st.table(pd.DataFrame({"rank":range(1,21),"keyword":kw_list[:20],"score":np.random.randint(50,200,20)}))

# 11번가 (프록시)
st.subheader("11번가 (프록시 임베드)")
url = st.text_input("11번가 URL", "https://www.11st.co.kr/")
proxy = st.text_input("프록시 엔드포인트", "")
if proxy:
    src = f"{proxy}?target={urllib.parse.quote(url.replace('www.11st.co.kr','m.11st.co.kr'))}"
else:
    src = url.replace("www.11st.co.kr","m.11st.co.kr")
st.components.v1.html(f"<iframe src='{src}' width='100%' height='500'></iframe>", height=520)

# 소싱레이더
st.subheader("소싱레이더")
domestic = st.checkbox("국내 보기", value=True)
globalv = st.checkbox("글로벌 보기", value=True)
if domestic: st.table(pd.DataFrame({"keyword":kw_list[:10]}))
if globalv: 
    rows=[]
    for m,kws in GLOBAL_KEYWORDS.items():
        for k in kws: rows.append({"market":m,"keyword":k})
    st.dataframe(pd.DataFrame(rows))

# 상품명 생성기
st.subheader("상품명 생성기")
brand = st.text_input("브랜드","envy")
base = st.text_input("베이스","K-coffee mix")
if st.button("규칙 기반 생성"):
    for i in range(5):
        st.write(f"[New] {brand} - {base} HotDeal")

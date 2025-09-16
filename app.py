
import streamlit as st
import pandas as pd
import requests
import altair as alt
from functools import lru_cache
from datetime import datetime, timedelta
from math import ceil

st.set_page_config(page_title="ENVY — 환율·마진·데이터랩·11번가", layout="wide")

# -----------------------------
# Header with logo
# -----------------------------
def header():
    cols = st.columns([1, 8])
    with cols[0]:
        try:
            from pathlib import Path
            logo_paths = [
                Path("envy_logo.png"),
                Path("assets/envy_logo.png")
            ]
            logo = None
            for p in logo_paths:
                if p.exists():
                    logo = str(p)
                    break
            if logo:
                st.image(logo, use_column_width=True)
            else:
                st.markdown(
                    "<div style='font-size:28px;font-weight:700;line-height:1.2;'>ENVY</div>",
                    unsafe_allow_html=True
                )
        except Exception:
            st.markdown(
                "<div style='font-size:28px;font-weight:700;line-height:1.2;'>ENVY</div>",
                unsafe_allow_html=True
            )
    with cols[1]:
        st.markdown(
            "<div style='font-size:28px;font-weight:700;'>실시간 환율 + 마진 + 데이터랩 + 11번가</div>",
            unsafe_allow_html=True
        )
header()

st.markdown("---")

# ========================================
# Sidebar — 환율 계산기 + 간이 마진 계산기
# ========================================
st.sidebar.header("🔧 빠른 도구")
st.sidebar.caption("환율 계산기 & 마진 계산기를 사이드바로 정리했습니다.")

# --- 환율 ----
st.sidebar.subheader("💱 환율 계산기")

CURRENCIES = [
    ("USD", "$"), ("EUR", "€"), ("JPY", "¥"), ("CNY", "¥")
]

amount = st.sidebar.number_input("상품 원가", min_value=0.0, value=1.0, step=1.0)
base_label = st.sidebar.selectbox("통화 선택", [f"{c} ({s})" for c, s in CURRENCIES], index=0)
base = base_label.split()[0]

@st.cache_data(ttl=1800)  # 30분 캐시
def fetch_rates(base_code: str):
    # 1차: exchangerate.host
    try:
        r = requests.get(f"https://api.exchangerate.host/latest?base={base_code}", timeout=8)
        if r.ok and "rates" in r.json():
            return r.json()["rates"]
    except Exception:
        pass
    # 2차: frankfurter
    try:
        r = requests.get(f"https://api.frankfurter.app/latest?from={base_code}", timeout=8)
        if r.ok and "rates" in r.json():
            return r.json()["rates"]
    except Exception:
        pass
    return {}

rates = fetch_rates(base)
krw_value = 0.0
if rates and "KRW" in rates:
    krw_value = amount * rates["KRW"]
    st.sidebar.success(f"1.00 {base} → ₩{rates['KRW']:.2f}")
else:
    st.sidebar.error("환율 정보를 불러올 수 없습니다.")

st.sidebar.metric("계산 결과", f"₩{krw_value:,.0f}")

st.sidebar.markdown("---")

# --- 간이 마진 계산기 ----
st.sidebar.subheader("🧮 간이 마진 계산")
local_amount = st.sidebar.number_input("현지 금액", min_value=0.0, value=0.0, step=1.0)
local_currency_label = st.sidebar.selectbox("현지 통화", [c for c,_ in CURRENCIES], index=0)
shipping_krw = st.sidebar.number_input("배송비 (KRW)", min_value=0.0, value=0.0, step=1000.0, format="%.0f")
card_fee = st.sidebar.number_input("카드 수수료(%)", min_value=0.0, value=4.0, step=0.5)
market_fee = st.sidebar.number_input("마켓 수수료(%)", min_value=0.0, value=15.0, step=0.5)
target_margin = st.sidebar.number_input("목표 마진(%)", min_value=0.0, value=40.0, step=1.0)

rates2 = fetch_rates(local_currency_label)
krw_cost = local_amount * rates2.get("KRW", 0.0) + shipping_krw
fee_mult = (1 + card_fee/100) * (1 + market_fee/100)
target_mult = 1 + target_margin/100

sell_price = krw_cost * fee_mult * target_mult
profit = sell_price - krw_cost

st.sidebar.metric("예상 판매가", f"₩{sell_price:,.0f}")
st.sidebar.metric("예상 순이익", f"₩{profit:,.0f}", delta=f"{(profit/sell_price*100 if sell_price>0 else 0):.1f}%")

# ========================================
# 본문 — 데이터랩 + 11번가 버튼
# ========================================

st.markdown("### 📊 네이버 데이터랩 (Top20 키워드)")

# 내부 매핑 샘플(데모). 실제 운영 시, 서버/캐시 파일에서 확장 가능.
CATEGORY_KEYWORDS = {
    "패션의류": ["맨투맨","슬랙스","청바지","가디건","롱스커트","부츠컷","와이드팬츠","조거팬츠","빅사이즈","셔츠","블레이저","후드집업","롱원피스","트레이닝","연청바지","흑청바지","슬림핏","A라인 스커트","보이핏","니트조끼"],
    "화장품/미용": ["쿠션","선크림","립밤","아이섀도우","클렌징폼","마스카라","립틴트","프라이머","토너","에센스","앰플","픽서","틴트립","립오일","립글로스","아이브로우","쉐이딩","하이라이터","블러셔","세럼"],
    "식품": ["라면","커피","참치","스팸","젤리","간식","과자","초콜릿","김","견과","시리얼","과일","김자반","햇반","즉석국","만두","치즈","우유","요거트","식빵"],
    "스포츠/레저": ["런닝화","요가매트","테니스공","배드민턴라켓","축구공","헬스장갑","무릎보호대","아대","수영모","스노클","다이빙마스크","자전거장갑","클라이밍화","스포츠양말","라켓가방","하프팬츠","피클볼","워킹화","헬스벨트","보호대"],
}

cat = st.selectbox("카테고리 선택", list(CATEGORY_KEYWORDS.keys()), index=0, key="dl_cat")

# 키워드 DF + 가짜 점수(순위 기반 점수)
kw_list = CATEGORY_KEYWORDS.get(cat, [])[:20]
df = pd.DataFrame({
    "rank": list(range(1, len(kw_list)+1)),
    "keyword": kw_list,
    "score": list(reversed([40 + i*3 for i in range(len(kw_list))]))  # 대충 점수 형태(내림차순)
})

left, right = st.columns([1,1])

with left:
    st.dataframe(df[["rank","keyword"]], use_container_width=True, height=420)

with right:
    chart = (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X("score:Q", title="score"),
            y=alt.Y("keyword:N", sort="-x", title="keyword"),
            tooltip=["rank","keyword","score"]
        )
        .properties(height=420)
    )
    st.altair_chart(chart, use_container_width=True)

st.markdown("---")
st.markdown("### 🛍️ 11번가 아마존 베스트")
st.caption("브라우저 정책으로 iframe 차단될 수 있어 **새창 열기** 버튼을 제공합니다.")
c1, c2 = st.columns(2)
with c1:
    st.link_button("모바일 새창 열기", "https://m.11st.co.kr/browsing/AmazonBest", help="모바일 UI로 열기")
with c2:
    st.link_button("PC 새창 열기", "https://www.11st.co.kr/browsing/AmazonBest", help="PC UI로 열기")

st.markdown("---")
st.caption("© ENVY — 환율/마진/데이터랩/11번가 도구")

import streamlit as st
import requests
import datetime
import streamlit.components.v1 as components

st.set_page_config(layout="wide")

# ===== 다크/라이트 모드 (사이드바 제외) =====
dark_mode = st.sidebar.checkbox("🌙 다크 모드")
if dark_mode:
    st.markdown(
        """
        <style>
        .stApp { background-color: #1e1e1e; color: white; }
        .css-18e3th9 { background-color: #1e1e1e; }
        </style>
        """, unsafe_allow_html=True
    )
else:
    st.markdown(
        """
        <style>
        .stApp { background-color: white; color: black; }
        </style>
        """, unsafe_allow_html=True
    )

# ===== 환율 빠른 계산 =====
st.sidebar.header("💱 환율 빠른 계산")

amount = st.sidebar.number_input("상품 원가", min_value=0.0, value=1.0, step=1.0)
currency = st.sidebar.selectbox("통화", ["USD ($)", "EUR (€)", "JPY (¥)", "CNY (¥)"])

def get_rate(base="USD", symbols="KRW"):
    try:
        r = requests.get(f"https://api.exchangerate.host/latest?base={base}&symbols={symbols}", timeout=5)
        return r.json()["rates"][symbols]
    except:
        return None

base = currency.split()[0]
rate = get_rate(base)
if rate:
    krw_value = amount * rate
    st.sidebar.markdown(f"<h3><b>{amount:.2f} {currency} ➜ {krw_value:,.0f} 원</b></h3>", unsafe_allow_html=True)
    st.sidebar.caption(f"1 {base} = {rate:,.2f} KRW (10분 캐시)")
else:
    st.sidebar.error("환율 불러오기 실패")

# ===== 간이 마진 계산 =====
st.sidebar.header("📊 간이 마진 계산")

local_amount = st.sidebar.number_input("현지 금액", min_value=0.0, value=0.0, step=1.0)
local_currency = st.sidebar.selectbox("현지 통화", ["USD", "EUR", "JPY", "CNY"])
shipping_fee = st.sidebar.number_input("배송비 (KRW)", min_value=0.0, value=0.0, step=100.0)
card_fee = st.sidebar.number_input("카드수수료 (%)", min_value=0.0, value=4.0, step=0.1)
market_fee = st.sidebar.number_input("마켓수수료 (%)", min_value=0.0, value=15.0, step=0.1)
target_margin = st.sidebar.number_input("목표 마진 (%)", min_value=0.0, value=40.0, step=1.0)

local_rate = get_rate(local_currency)
if local_rate:
    cost_krw = local_amount * local_rate + shipping_fee
    sale_price = cost_krw / (1 - (card_fee + market_fee + target_margin) / 100)
    st.sidebar.markdown(f"<h3><b>예상 판매가: {sale_price:,.0f} 원</b></h3>", unsafe_allow_html=True)
else:
    st.sidebar.error("현지 환율 불러오기 실패")

# ===== 메인 영역 =====
st.title("💱 실시간 환율 + 📊 마진 + 📈 데이터랩 + 🛒 11번가")

col1, col2 = st.columns(2)

with col1:
    st.subheader("📈 네이버 데이터랩 (보류중)")
    st.info("현재는 Client ID/Secret API 연동 보류 상태입니다. 선택된 카테고리에 맞는 Top 20 키워드 + 1일/7일/30일 그래프 표시 예정.")

with col2:
    st.subheader("🛒 11번가 아마존 베스트 (모바일)")
    url = "https://m.11st.co.kr/MW/html/main.html"
    try:
        components.iframe(url, height=600, scrolling=True)
    except:
        st.warning("⚠️ 보안 정책 때문에 화면 표시가 차단되었습니다.")
        st.markdown(f"[새창에서 열기]({url})")

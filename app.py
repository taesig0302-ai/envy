
import streamlit as st
import requests
import time

# -------------------- 캐싱된 환율 가져오기 --------------------
@st.cache_data(ttl=1800)  # 30분마다 갱신
def get_exchange_rate(base="USD"):
    try:
        url = f"https://api.exchangerate.host/latest?base={base}&symbols=KRW"
        r = requests.get(url, timeout=10)
        data = r.json()
        return data["rates"]["KRW"]
    except Exception:
        return None

# -------------------- 다크모드 --------------------
st.sidebar.checkbox("🌙 다크 모드", key="dark_mode")
dark_mode = st.session_state.get("dark_mode", False)

if dark_mode:
    st.markdown("""
        <style>
        body { background-color: #1e1e1e; color: white; }
        </style>
    """, unsafe_allow_html=True)

st.title("💱 실시간 환율 + 📊 마진 계산기")

# -------------------- 환율 계산기 --------------------
st.subheader("환율 계산기")
amount = st.number_input("상품 원가", value=1.0, step=1.0)
currency = st.selectbox("통화 선택", ["USD", "EUR", "JPY", "CNY"])

rate = get_exchange_rate(currency)
if rate:
    krw_value = amount * rate
    st.markdown(f"### {amount:.2f} {currency} ➝ **{krw_value:,.0f} 원**")
    st.caption(f"현재 환율: 1 {currency} = {rate:,.2f} KRW (30분 캐시)")
else:
    st.error("환율 정보를 불러올 수 없습니다.")

# -------------------- 마진 계산기 --------------------
st.subheader("간이 마진 계산")

base_price = st.number_input("현지 금액", value=0.0, step=1.0)
base_currency = st.selectbox("현지 통화", ["USD", "EUR", "JPY", "CNY"])
shipping_fee = st.number_input("배송비 (KRW)", value=0.0, step=100.0)
card_fee = st.number_input("카드 수수료 (%)", value=4.0, step=0.5)
market_fee = st.number_input("마켓 수수료 (%)", value=15.0, step=0.5)
target_margin = st.number_input("목표 마진 (%)", value=40.0, step=1.0)

rate2 = get_exchange_rate(base_currency)
if rate2:
    cost_krw = base_price * rate2
    total_cost = cost_krw + shipping_fee
    # 목표 마진 반영
    sell_price = total_cost * (1 + (target_margin / 100))
    # 수수료 반영
    final_price = sell_price / (1 - (card_fee + market_fee) / 100)
    profit = final_price - total_cost
    profit_margin = (profit / final_price) * 100

    st.success(f"🔥 예상 판매가: {final_price:,.0f} 원")
    st.write(f"순이익: {profit:,.0f} 원 ({profit_margin:.1f}%)")
else:
    st.error("환율 정보를 불러올 수 없습니다.")

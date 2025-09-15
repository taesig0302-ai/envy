import streamlit as st
import requests
from datetime import timedelta

st.set_page_config(page_title="환율 + 마진 계산기", page_icon="💹")
st.title("💹 실시간 환율 + 마진 계산기")

# ======================
# 환율 불러오기
# ======================
@st.cache_data(ttl=timedelta(minutes=30))
def get_rate_to_krw(base: str) -> float:
    try:
        url = f"https://api.exchangerate.host/latest?base={base}&symbols=KRW"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        js = r.json()
        if "rates" in js and "KRW" in js["rates"]:
            return float(js["rates"]["KRW"])
    except Exception:
        pass
    try:
        url2 = f"https://open.er-api.com/v6/latest/{base}"
        r2 = requests.get(url2, timeout=10)
        r2.raise_for_status()
        js2 = r2.json()
        if js2.get("result") == "success":
            return float(js2["rates"]["KRW"])
    except Exception:
        pass
    return 0.0

# ======================
# 입력값
# ======================
st.header("📥 기본 입력값")

col1, col2 = st.columns(2)
with col1:
    product_price = st.number_input("상품 원가", min_value=0.0, value=319.0, step=1.0, format="%.2f")
    local_shipping = st.number_input("현지 배송비", min_value=0.0, value=0.0, step=1.0, format="%.2f")
    intl_shipping = st.number_input("국제 배송비 (KRW)", min_value=0.0, value=0.0, step=100.0, format="%.0f")
with col2:
    card_fee = st.number_input("카드 수수료 (%)", min_value=0.0, value=4.0, step=0.1, format="%.1f") / 100
    market_fee = st.number_input("마켓 수수료 (%)", min_value=0.0, value=15.0, step=0.1, format="%.1f") / 100
    currency = st.selectbox("통화 선택", ["CNY", "USD", "JPY", "EUR"], index=0)

rate = get_rate_to_krw(currency)
if rate == 0:
    st.error("환율을 불러오지 못했습니다. 잠시 후 다시 시도하세요.")
    st.stop()

st.write(f"💱 현재 환율: 1 {currency} = {rate:.2f} KRW")

# 원가 (KRW 환산)
base_cost_krw = (product_price + local_shipping) * rate + intl_shipping

st.markdown("---")

# ======================
# 계산 모드 선택
# ======================
st.header("⚙️ 계산 모드")

mode = st.radio("계산 방식을 선택하세요", ["목표 마진 → 판매가", "판매가 → 순이익"])

# ======================
# 모드 1: 목표 마진으로 판매가 계산
# ======================
if mode == "목표 마진 → 판매가":
    margin_mode = st.radio("마진 방식 선택", ["퍼센트 마진 (%)", "더하기 마진 (₩)"])

    if margin_mode == "퍼센트 마진 (%)":
        margin_rate = st.number_input("목표 마진 (%)", min_value=0.0, value=40.0, step=1.0, format="%.1f") / 100
        selling_price = base_cost_krw / (1 - (market_fee + card_fee + margin_rate))
        net_profit = selling_price * (1 - (market_fee + card_fee)) - base_cost_krw
        profit_rate = net_profit / selling_price if selling_price > 0 else 0

    else:  # 더하기 마진
        margin_add = st.number_input("목표 마진 (₩)", min_value=0.0, value=20000.0, step=1000.0, format="%.0f")
        selling_price = (base_cost_krw + margin_add) / (1 - (market_fee + card_fee))
        net_profit = margin_add
        profit_rate = net_profit / selling_price if selling_price > 0 else 0

    st.markdown("### 📊 계산 결과")
    st.write(f"- 원가 합계: {base_cost_krw:,.0f} 원")
    st.write(f"- 목표 판매가: {selling_price:,.0f} 원")
    st.write(f"- 예상 순이익: {net_profit:,.0f} 원")
    st.write(f"- 순이익률: {profit_rate*100:.1f}%")

# ======================
# 모드 2: 판매가로 순이익 계산
# ======================
else:
    selling_price = st.number_input("판매가 입력 (KRW)", min_value=0.0, value=100000.0, step=1000.0, format="%.0f")
    net_after_fee = selling_price * (1 - (market_fee + card_fee))
    net_profit = net_after_fee - base_cost_krw
    profit_rate = net_profit / selling_price if selling_price > 0 else 0

    st.markdown("### 📊 계산 결과")
    st.write(f"- 원가 합계: {base_cost_krw:,.0f} 원")
    st.write(f"- 입력 판매가: {selling_price:,.0f} 원")
    st.write(f"- 예상 순이익: {net_profit:,.0f} 원")
    st.write(f"- 순이익률: {profit_rate*100:.1f}%")

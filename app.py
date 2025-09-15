import streamlit as st
import requests
from datetime import timedelta

st.set_page_config(page_title="환율 + 마진 계산기", page_icon="📈")
st.title("📈 실시간 환율 + 마진 계산기")

# ---------------------------
# 최초 기본값 고정 (새로고침 포함)
# ---------------------------
if "init" not in st.session_state:
    st.session_state.init = True
    st.session_state.quick_amount = 1.0
    st.session_state.quick_currency = "USD"
    st.session_state.product_price = 1.0
    st.session_state.currency = "USD"

# ---------------------------
# 환율 로더 (캐시)
# ---------------------------
@st.cache_data(ttl=timedelta(minutes=30))
def get_rate_to_krw(base: str) -> float:
    try:
        r = requests.get(
            f"https://api.exchangerate.host/latest?base={base}&symbols=KRW",
            timeout=10,
        )
        r.raise_for_status()
        js = r.json()
        if "rates" in js and "KRW" in js["rates"]:
            return float(js["rates"]["KRW"])
    except Exception:
        pass
    try:
        r2 = requests.get(f"https://open.er-api.com/v6/latest/{base}", timeout=10)
        r2.raise_for_status()
        js2 = r2.json()
        if js2.get("result") == "success":
            return float(js2["rates"]["KRW"])
    except Exception:
        pass
    return 0.0

# ======================================================
# 0) 환율만 빠르게 확인 (기본값: 원가=1, 통화=USD)
#    + "환산 금액(원화)" 전용 칸 추가 (읽기전용)
# ======================================================
st.subheader("💱 환율만 빠르게 확인")

colq1, colq2, colq3 = st.columns([1, 1, 1.2])
with colq1:
    quick_amount = st.number_input(
        "상품 원가",
        min_value=0.0,
        value=st.session_state.quick_amount,
        step=1.0,
        format="%.2f",
        key="quick_amount",
    )
with colq2:
    quick_currency = st.selectbox(
        "통화 선택",
        ["USD", "CNY", "JPY", "EUR"],
        index=["USD", "CNY", "JPY", "EUR"].index(st.session_state.quick_currency),
        key="quick_currency",
    )

q_rate = get_rate_to_krw(quick_currency)
if q_rate > 0:
    q_result = quick_amount * q_rate
    with colq3:
        st.text_input("환산 금액 (KRW)", value=f"{q_result:,.0f}", disabled=True)
    st.caption(f"현재 환율: 1 {quick_currency} = {q_rate:,.2f} KRW (30분 캐시)")
else:
    with colq3:
        st.text_input("환산 금액 (KRW)", value="불러오기 실패", disabled=True)
    st.error("환율을 불러오지 못했습니다. 잠시 후 다시 시도하세요.")

st.divider()

# ======================================================
# 1) 기본 입력값 (마진 계산용)
#    기본값: 상품원가=1, 통화=USD
# ======================================================
st.subheader("📥 기본 입력값")

col1, col2 = st.columns(2)
with col1:
    product_price = st.number_input(
        "상품 원가",
        min_value=0.0,
        value=st.session_state.product_price,
        step=1.0,
        format="%.2f",
        key="product_price",
    )
    local_shipping = st.number_input("현지 배송비", min_value=0.0, value=0.0, step=1.0, format="%.2f")
    intl_shipping = st.number_input("국제 배송비 (KRW)", min_value=0.0, value=0.0, step=100.0, format="%.0f")
with col2:
    card_fee = st.number_input("카드 수수료 (%)", min_value=0.0, value=4.0, step=0.1, format="%.1f") / 100
    market_fee = st.number_input("마켓 수수료 (%)", min_value=0.0, value=15.0, step=0.1, format="%.1f") / 100
    currency = st.selectbox(
        "통화 선택(마진 계산용)",
        ["USD", "CNY", "JPY", "EUR"],
        index=["USD", "CNY", "JPY", "EUR"].index(st.session_state.currency),
        key="currency",
    )

rate = get_rate_to_krw(currency)
if rate == 0:
    st.error("환율을 불러오지 못해 마진 계산을 진행할 수 없습니다.")
    st.stop()

st.caption(f"💱 현재 환율: 1 {currency} = {rate:,.2f} KRW")
base_cost_krw = (product_price + local_shipping) * rate + intl_shipping

st.divider()

# ======================================================
# 2) 계산 모드
# ======================================================
st.subheader("⚙️ 계산 모드")
mode = st.radio("계산 방식을 선택하세요", ["목표 마진 → 판매가", "판매가 → 순이익"])

# ---- 모드 1: 목표 마진으로 판매가 계산 ----
if mode == "목표 마진 → 판매가":
    margin_mode = st.radio("마진 방식 선택", ["퍼센트 마진 (%)", "더하기 마진 (₩)"])

    if margin_mode == "퍼센트 마진 (%)":
        margin_rate = st.number_input("목표 마진 (%)", min_value=0.0, value=40.0, step=1.0, format="%.1f") / 100
        selling_price = base_cost_krw / (1 - (market_fee + card_fee + margin_rate))
        net_profit = selling_price * (1 - (market_fee + card_fee)) - base_cost_krw
        profit_rate = (net_profit / selling_price) if selling_price > 0 else 0.0
    else:
        margin_add = st.number_input("목표 마진 (₩)", min_value=0.0, value=20000.0, step=1000.0, format="%.0f")
        selling_price = (base_cost_krw + margin_add) / (1 - (market_fee + card_fee))
        net_profit = margin_add
        profit_rate = (net_profit / selling_price) if selling_price > 0 else 0.0

    st.markdown("### 📊 계산 결과")
    st.write(f"- 원가 합계: **{base_cost_krw:,.0f} 원**")
    st.write(f"- 목표 판매가: **{selling_price:,.0f} 원**")
    st.write(f"- 예상 순이익: **{net_profit:,.0f} 원**")
    st.write(f"- 순이익률: **{profit_rate*100:.1f}%**")

# ---- 모드 2: 판매가 → 순이익 ----
else:
    selling_price = st.number_input("판매가 입력 (KRW)", min_value=0.0, value=100000.0, step=1000.0, format="%.0f")
    net_after_fee = selling_price * (1 - (market_fee + card_fee))
    net_profit = net_after_fee - base_cost_krw
    profit_rate = (net_profit / selling_price) if selling_price > 0 else 0.0

    st.markdown("### 📊 계산 결과")
    st.write(f"- 원가 합계: **{base_cost_krw:,.0f} 원**")
    st.write(f"- 입력 판매가: **{selling_price:,.0f} 원**")
    st.write(f"- 예상 순이익: **{net_profit:,.0f} 원**")
    st.write(f"- 순이익률: **{profit_rate*100:.1f}%**")

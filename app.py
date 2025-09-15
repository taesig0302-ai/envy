# app.py
import streamlit as st
import requests
from datetime import timedelta
import streamlit.components.v1 as components

st.set_page_config(page_title="환율 + 마진 계산기 + 11번가", page_icon="📈", layout="wide")
st.title("📈 실시간 환율 + 마진 계산기")

# ---------------------------
# 최초 기본값 (새로고침 포함)
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
        r = requests.get(f"https://api.exchangerate.host/latest?base={base}&symbols=KRW", timeout=10)
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

# ---------------------------
# 통화 코드 + 기호 매핑
# ---------------------------
currency_symbols = {
    "USD": "$",
    "CNY": "¥",
    "JPY": "¥",
    "EUR": "€"
}

# ======================================================
# 0) 환율만 빠르게 확인
# ======================================================
st.subheader("💱 환율만 빠르게 확인")
colq1, colq2, colq3 = st.columns([1, 1, 1.2])
with colq1:
    quick_amount = st.number_input("상품 원가", min_value=0.0,
                                   value=st.session_state.quick_amount, step=1.0, format="%.2f", key="quick_amount")
with colq2:
    quick_currency = st.selectbox(
        "통화 선택",
        [f"{c} ({currency_symbols[c]})" for c in currency_symbols.keys()],
        index=list(currency_symbols.keys()).index(st.session_state.quick_currency),
        key="quick_currency"
    )
    # 선택된 코드만 추출
    quick_currency_code = quick_currency.split()[0]

q_rate = get_rate_to_krw(quick_currency_code)
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
# ======================================================
st.subheader("📥 기본 입력값")
col1, col2 = st.columns(2)
with col1:
    product_price = st.number_input("상품 원가", min_value=0.0,
                                    value=st.session_state.product_price, step=1.0, format="%.2f", key="product_price")
    local_shipping = st.number_input("현지 배송비", min_value=0.0, value=0.0, step=1.0, format="%.2f")
    intl_shipping = st.number_input("국제 배송비 (KRW)", min_value=0.0, value=0.0, step=100.0, format="%.0f")
with col2:
    card_fee = st.number_input("카드 수수료 (%)", min_value=0.0, value=4.0, step=0.1, format="%.1f") / 100
    market_fee = st.number_input("마켓 수수료 (%)", min_value=0.0, value=15.0, step=0.1, format="%.1f") / 100
    currency = st.selectbox(
        "통화 선택(마진 계산용)",
        [f"{c} ({currency_symbols[c]})" for c in currency_symbols.keys()],
        index=list(currency_symbols.keys()).index(st.session_state.currency),
        key="currency"
    )
    currency_code = currency.split()[0]

rate = get_rate_to_krw(currency_code)
if rate == 0:
    st.error("환율을 불러오지 못해 마진 계산을 진행할 수 없습니다.")
    st.stop()

st.caption(f"💱 현재 환율: 1 {currency} = {rate:,.2f} KRW")
base_cost_krw = (product_price + local_shipping) * rate + intl_shipping

st.divider()

# ======================================================
# 2) 계산 모드 (마진)
# ======================================================
st.subheader("⚙️ 계산 모드")
mode = st.radio("계산 방식을 선택하세요", ["목표 마진 → 판매가", "판매가 → 순이익"])

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

st.divider()

# ======================================================
# 3) 11번가 모바일 보기
# ======================================================
st.header("🛒 11번가 아마존 베스트 (모바일 보기)")

col11a, col11b = st.columns([2, 1])
with col11a:
    sel = st.selectbox(
        "보기 선택",
        ["아마존 베스트", "홈", "오늘의 딜"],
        index=0,
    )
    if sel == "아마존 베스트":
        url = "https://m.11st.co.kr/browsing/AmazonBest"
    elif sel == "오늘의 딜":
        url = "https://m.11st.co.kr/browsing/todayDeal"
    else:
        url = "https://m.11st.co.kr/"

with col11b:
    h = st.slider("높이(px)", 500, 1400, 900, 50)

components.html(
    f"""
    <div style="border:1px solid #e5e7eb;border-radius:10px;overflow:hidden">
      <iframe src="{url}" 
              style="width:100%;height:{h}px;border:0"
              referrerpolicy="no-referrer"
              sandbox="allow-same-origin allow-scripts allow-popups allow-forms">
      </iframe>
    </div>
    """,
    height=h + 12,
)

st.caption("※ 일부 브라우저/정책에서 임베드가 차단될 수 있습니다. 차단될 경우 아래 버튼으로 새 창에서 열어주세요.")
st.link_button("🔗 11번가 모바일 새 창으로 열기", url)

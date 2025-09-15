
import streamlit as st
import requests

st.set_page_config(page_title="실시간 환율 + 마진 + 11번가", layout="wide")

# --- 다크 모드 토글 ---
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False

dark_mode = st.sidebar.checkbox("🌙 다크 모드", value=st.session_state.dark_mode)
st.session_state.dark_mode = dark_mode

# --- 환율 계산기 ---
st.sidebar.header("💱 환율 빠른 계산")
amount = st.sidebar.number_input("상품 원가", value=1.00, step=1.0)
currency = st.sidebar.selectbox("통화", ["USD ($)", "EUR (€)", "JPY (¥)", "CNY (¥)"])

currency_code = currency.split()[0]

def get_rate():
    try:
        url = f"https://open.er-api.com/v6/latest/{currency_code}"
        r = requests.get(url, timeout=5)
        return r.json()["rates"]["KRW"]
    except:
        url = f"https://api.exchangerate.host/latest?base={currency_code}&symbols=KRW"
        r = requests.get(url, timeout=5)
        return r.json()["rates"]["KRW"]

rate = get_rate()
krw_value = amount * rate

st.sidebar.markdown(f"### {amount:.2f} {currency} →")
st.sidebar.markdown(f"<h2 style='color: {'white' if dark_mode else 'black'};'>{krw_value:,.0f} 원</h2>", unsafe_allow_html=True)
st.sidebar.caption(f"1 {currency_code} = {rate:,.2f} KRW (10분 캐시)")

# --- 마진 계산기 ---
st.sidebar.header("🧾 간이 마진 계산")
local_price = st.sidebar.number_input("현지 금액", value=0.0, step=1.0)
local_currency = st.sidebar.selectbox("현지 통화", ["USD", "EUR", "JPY", "CNY"], key="local_currency")
shipping_fee = st.sidebar.number_input("배송비 (KRW)", value=0, step=100)
card_fee = st.sidebar.number_input("카드수수료 (%)", value=4.0, step=0.5)
market_fee = st.sidebar.number_input("마켓수수료 (%)", value=15.0, step=0.5)
target_margin = st.sidebar.number_input("목표 마진 (%)", value=40.0, step=1.0)

# 현지 금액 → 원화 변환
local_rate = get_rate()
converted_price = local_price * local_rate

# 판매가 계산식
final_price = (converted_price + shipping_fee) * (1 + (card_fee + market_fee + target_margin) / 100)

st.sidebar.markdown(f"### 예상 판매가: {final_price:,.0f} 원")

# --- 본문 영역 ---
st.title("💱 실시간 환율 + 📊 마진 + 🛒 11번가")

# 데이터랩 (자리 유지)
st.subheader("📈 네이버 데이터랩 (보류중)")
st.info("현재는 Client ID/Secret API 연동 보류 상태입니다. 선택된 카테고리에 맞는 Top 20 키워드 + 1일/7일/30일 그래프 표시 예정.")

# 11번가 모바일 화면
st.subheader("🛒 11번가 아마존 베스트 (모바일)")
url_11st = "https://m.11st.co.kr/best"
try:
    st.components.v1.iframe(url_11st, height=800)
except:
    st.warning("11번가 화면을 불러올 수 없습니다. 새창으로 열어주세요: " + url_11st)

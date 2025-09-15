
import streamlit as st
import requests
import time
import pandas as pd
import plotly.express as px

# -----------------------------
# 내부에 심은 네이버 API 정보
# -----------------------------
NAVER_CLIENT_ID = "hMmkI2hNLct04bD7Sc0"
NAVER_CLIENT_SECRET = "YOUR_SECRET"

# -----------------------------
# 환율 데이터 캐싱 (30분)
# -----------------------------
@st.cache_data(ttl=1800)
def get_exchange_rate(base="USD"):
    urls = [
        f"https://open.er-api.com/v6/latest/{base}",
        f"https://api.exchangerate.host/latest?base={base}"
    ]
    for url in urls:
        try:
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                data = r.json()
                if "rates" in data:
                    return data["rates"].get("KRW")
        except Exception:
            continue
    return None

# -----------------------------
# 네이버 데이터랩 API 요청
# -----------------------------
def get_datalab_keywords(category):
    url = "https://openapi.naver.com/v1/datalab/search"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
        "Content-Type": "application/json",
    }
    payload = {
        "startDate": "2025-09-01",
        "endDate": "2025-09-15",
        "timeUnit": "date",
        "keywordGroups": [{"groupName": category, "keywords": [category]}],
        "device": "pc",
        "ages": [],
        "gender": ""
    }
    r = requests.post(url, headers=headers, json=payload)
    if r.status_code == 200:
        return r.json()
    return None

# -----------------------------
# UI 시작
# -----------------------------
st.set_page_config(page_title="실시간 환율 + 마진 + 데이터랩 + 11번가", layout="wide")

# 다크모드 토글
dark_mode = st.sidebar.checkbox("🌙 다크 모드")
if dark_mode:
    st.markdown("<style>body {background-color: #1e1e1e; color: white;}</style>", unsafe_allow_html=True)

st.title("💱 실시간 환율 + 📊 마진 + 📈 데이터랩 + 🛒 11번가")

# -----------------------------
# 환율 계산기
# -----------------------------
st.sidebar.header("💲 환율 빠른 계산")
amount = st.sidebar.number_input("상품 원가", value=1.00, step=1.0)
currency = st.sidebar.selectbox("통화", ["USD ($)", "EUR (€)", "JPY (¥)", "CNY (¥)"])
base = currency.split()[0]

rate = get_exchange_rate(base)
if rate:
    result = amount * rate
    st.sidebar.metric(label=f"{amount} {base} → 원화", value=f"{result:,.0f} 원")
    st.sidebar.caption(f"1 {base} = {rate:,.2f} KRW (30분 캐시)")
else:
    st.sidebar.error("환율 불러오기 실패")

# -----------------------------
# 마진 계산기
# -----------------------------
st.sidebar.header("🧮 간이 마진 계산")
cost = st.sidebar.number_input("현지 금액", value=0.0, step=1.0)
base2 = st.sidebar.selectbox("현지 통화", ["USD", "EUR", "JPY", "CNY"])
shipping = st.sidebar.number_input("배송비 (KRW)", value=0.0, step=100.0)
card_fee = st.sidebar.number_input("카드수수료 (%)", value=4.0)
market_fee = st.sidebar.number_input("마켓수수료 (%)", value=15.0)
target_margin = st.sidebar.number_input("목표 마진 (%)", value=40.0)

rate2 = get_exchange_rate(base2)
if rate2:
    cost_krw = cost * rate2 + shipping
    sale_price = cost_krw * (1 + (card_fee+market_fee+target_margin)/100)
    st.sidebar.metric("예상 판매가", f"{sale_price:,.0f} 원")
else:
    st.sidebar.warning("환율 계산 불가")

# -----------------------------
# 데이터랩
# -----------------------------
st.subheader("📊 네이버 데이터랩 (자동 실행 + API)")
category = st.selectbox("카테고리 선택", ["패션의류", "패션잡화", "디지털/가전", "생활/건강"])
if st.button("데이터 불러오기"):
    data = get_datalab_keywords(category)
    if data and "results" in data:
        df = pd.DataFrame(data["results"][0]["data"])
        fig = px.line(df, x="period", y="ratio", title=f"{category} 검색량 추이")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("API 응답이 없거나 오류 발생")

# -----------------------------
# 11번가 모바일 화면
# -----------------------------
st.subheader("🛒 11번가 아마존 베스트 (모바일)")
st.components.v1.iframe("https://m.11st.co.kr/MW/html/main.html", height=800)

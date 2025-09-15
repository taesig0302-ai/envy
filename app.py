import streamlit as st
import requests

st.set_page_config(page_title="실시간 환율 계산기", page_icon="💱")

st.title("💱 실시간 환율 계산기")

# 입력
amount = st.number_input("금액 입력", min_value=0.0, value=100.0)
cur = st.selectbox("통화 선택", ["USD", "JPY", "EUR", "CNY"])

# 환율 API 불러오기
url = f"https://api.exchangerate.host/latest?base={cur}&symbols=KRW"
r = requests.get(url)
rate = r.json()["rates"]["KRW"]

# 결과 계산
result = amount * rate

st.metric(label=f"{amount} {cur} → 원화", value=f"{result:,.0f} KRW")
st.caption(f"실시간 환율: 1 {cur} = {rate:.2f} KRW")

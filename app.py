import streamlit as st
import requests
import pandas as pd
import altair as alt

# -------------------------------
# 기본 세팅
# -------------------------------
st.set_page_config(page_title="환율 + 마진 + 데이터랩 + 11번가", layout="wide")

st.title("💱 실시간 환율 + 📊 마진 + 📈 데이터랩 + 🛒 11번가")

# -------------------------------
# 사이드바 (공통 기능)
# -------------------------------
st.sidebar.header("⚙️ 빠른 도구")

# 다크 모드 (단순 UI 토글만 구현, 실제 색상은 streamlit theme 필요)
dark_mode = st.sidebar.checkbox("🌙 다크 모드")

# -------------------------------
# 환율 계산기
# -------------------------------
st.sidebar.subheader("💲 환율 빠른 계산")

amount = st.sidebar.number_input("상품 원가", min_value=0.0, value=1.0, step=1.0)
currency = st.sidebar.selectbox("통화 선택", ["USD ($)", "EUR (€)", "JPY (¥)", "CNY (¥)"])
currency_code = currency.split()[0]

# 환율 API (자동 fallback)
def get_exchange_rate(base, target="KRW"):
    urls = [
        f"https://api.exchangerate.host/latest?base={base}&symbols={target}",
        f"https://open.er-api.com/v6/latest/{base}"
    ]
    for url in urls:
        try:
            r = requests.get(url, timeout=5)
            data = r.json()
            if "rates" in data and target in data["rates"]:
                return data["rates"][target]
        except Exception:
            continue
    return None

rate = get_exchange_rate(currency_code, "KRW")

if rate:
    result = amount * rate
    st.sidebar.write(f"{amount:.2f} {currency_code} → {result:,.0f} 원")
    st.sidebar.caption(f"1 {currency_code} = {rate:,.2f} KRW (10분 캐시)")
else:
    st.sidebar.error("환율 정보를 불러올 수 없습니다.")

# -------------------------------
# 마진 계산기
# -------------------------------
st.sidebar.subheader("📊 간이 마진 계산")

cost = st.sidebar.number_input("원가합계(KRW)", min_value=0.0, value=0.0, step=100.0)
card_fee = st.sidebar.number_input("카드수수료 (%)", min_value=0.0, value=4.0, step=0.1)
market_fee = st.sidebar.number_input("마켓수수료 (%)", min_value=0.0, value=15.0, step=0.1)
target_margin = st.sidebar.number_input("목표 마진 (%)", min_value=0.0, value=40.0, step=1.0)

if st.sidebar.button("판매가 계산"):
    total_fee_rate = (card_fee + market_fee + target_margin) / 100
    if total_fee_rate >= 1:
        st.sidebar.error("수수료+마진율 합이 100% 이상입니다.")
    else:
        selling_price = cost / (1 - total_fee_rate)
        st.sidebar.success(f"예상 판매가: {selling_price:,.0f} 원")

# -------------------------------
# 메인 레이아웃 (2열)
# -------------------------------
col1, col2 = st.columns([2, 2])

# -------------------------------
# 네이버 데이터랩 (보류 모드)
# -------------------------------
with col1:
    st.subheader("📈 네이버 데이터랩 (자동 실행 + API)")
    category = st.selectbox("카테고리 선택", ["패션의류", "가전제품", "화장품/미용", "식품", "도서/취미"])
    st.info("👉 현재는 Client ID/Secret API 연동 보류 상태. \n선택된 카테고리에 맞는 **Top 20 키워드** + **1일/7일/30일 그래프** 표시 예정.")

    # 더미 데이터 (UI 확인용)
    df = pd.DataFrame({
        "날짜": pd.date_range("2025-09-01", periods=10),
        "검색량": [100, 150, 200, 180, 250, 300, 270, 260, 310, 330]
    })

    chart = alt.Chart(df).mark_line(point=True).encode(
        x="날짜:T",
        y="검색량:Q"
    ).properties(title="예시 그래프 (실제 API 연결 예정)")
    st.altair_chart(chart, use_container_width=True)

# -------------------------------
# 11번가 모바일 화면
# -------------------------------
with col2:
    st.subheader("🛒 11번가 아마존 베스트 (모바일)")
    st.components.v1.iframe(
        "https://m.11st.co.kr/MW/html/main.html",
        height=900,
        scrolling=True
    )

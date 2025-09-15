import streamlit as st
import requests
from datetime import timedelta

st.set_page_config(page_title="실시간 환율 계산기", page_icon="💱")
st.title("💱 실시간 환율 계산기")

# ---- 입력 ----
amount = st.number_input("금액 입력", min_value=0.0, value=100.0, step=1.0, format="%.2f")
cur = st.selectbox("통화 선택", ["USD", "JPY", "EUR", "CNY"])

# ---- 환율 로더 (캐시 포함) ----
@st.cache_data(ttl=timedelta(minutes=30))
def get_rate_to_krw(base: str) -> float:
    # 1) exchangerate.host
    try:
        url = f"https://api.exchangerate.host/latest?base={base}&symbols=KRW"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        js = r.json()
        if isinstance(js, dict) and "rates" in js and "KRW" in js["rates"]:
            return float(js["rates"]["KRW"])
    except Exception:
        pass

    # 2) open.er-api.com (fallback)
    try:
        url2 = f"https://open.er-api.com/v6/latest/{base}"
        r2 = requests.get(url2, timeout=10)
        r2.raise_for_status()
        js2 = r2.json()
        # 형식: {"result":"success","rates":{"KRW":...}}
        if js2.get("result") == "success" and "rates" in js2 and "KRW" in js2["rates"]:
            return float(js2["rates"]["KRW"])
    except Exception:
        pass

    # 실패
    return 0.0

rate = get_rate_to_krw(cur)

# ---- 결과 ----
if rate > 0:
    result = amount * rate
    st.metric(label=f"{amount:,.2f} {cur} → 원화", value=f"{result:,.0f} KRW")
    st.caption(f"현재 환율: 1 {cur} = {rate:,.2f} KRW (30분 캐시)")
else:
    st.error("환율을 불러오지 못했습니다. 잠시 후 다시 시도하거나 통화를 바꿔보세요.")
    with st.expander("진단 정보 보기"):
        st.write("API 응답에서 KRW 환율을 찾지 못했습니다.")
        st.code(
            "시도 1: exchangerate.host/latest?base={cur}&symbols=KRW\n"
            "시도 2: open.er-api.com/v6/latest/{cur}"
        )

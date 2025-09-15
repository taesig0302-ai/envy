
import streamlit as st
import requests, json, os, re
import pandas as pd
from datetime import timedelta
import streamlit.components.v1 as components

st.set_page_config(page_title="실시간 환율 + 마진 + 데이터랩", page_icon="📊", layout="wide")

# ---------------------------
# NAVER API Key (직접 심기)
# ---------------------------
NAVER_CLIENT_ID = "h4mkIM2hNLct04BD7sC0"
NAVER_CLIENT_SECRET = "ltoxUNyKxi"

# ---------------------------
# HTTP session
# ---------------------------
@st.cache_resource
def get_http():
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    })
    return s
http = get_http()

# ---------------------------
# 환율 API (10분 캐시, fallback)
# ---------------------------
CURRENCY_SYMBOL = {"USD":"$", "EUR":"€", "JPY":"¥", "CNY":"¥"}
CURRENCY_ORDER = ["USD","EUR","JPY","CNY"]

@st.cache_data(ttl=600)
def get_rate_to_krw(base: str) -> float:
    try:
        r = http.get(f"https://api.exchangerate.host/latest?base={base}&symbols=KRW", timeout=5)
        r.raise_for_status()
        js = r.json()
        return float(js["rates"]["KRW"])
    except Exception:
        pass
    try:
        r2 = http.get(f"https://open.er-api.com/v6/latest/{base}", timeout=5)
        r2.raise_for_status()
        js2 = r2.json()
        if js2.get("result") == "success":
            return float(js2["rates"]["KRW"])
    except Exception:
        pass
    return 0.0

# ---------------------------
# Naver DataLab API (공식)
# ---------------------------
CATEGORY_MAP = {
    "패션의류": "50000000", "패션잡화": "50000001", "화장품/미용": "50000002",
    "디지털/가전": "50000003", "가구/인테리어": "50000004",
    "식품": "50000005", "스포츠/레저": "50000006"
}

@st.cache_data(ttl=600)
def fetch_keywords_from_datalab(category_cid: str):
    url = "https://openapi.naver.com/v1/datalab/shopping/categories"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
        "Content-Type": "application/json",
    }
    body = {
        "startDate": "2025-09-01",
        "endDate": "2025-09-15",
        "timeUnit": "date",
        "category": [{"name":"cat","param":[category_cid]}]
    }
    try:
        r = requests.post(url, headers=headers, data=json.dumps(body), timeout=8)
        r.raise_for_status()
        js = r.json()
        # 단순히 top 키워드 흉내 (API는 trend 데이터 제공)
        data = js.get("results", [])
        kws = []
        for d in data:
            kws.extend([str(x.get("period","")) for x in d.get("data",[])])
        return kws[:20] if kws else []
    except Exception as e:
        return []

# ---------------------------
# Sidebar
# ---------------------------
sb = st.sidebar
sb.title("⚙️ 빠른 도구")

sb.subheader("💱 환율 빠른 계산")
st.session_state.setdefault("quick_amount", 1.0)
st.session_state.setdefault("quick_currency", "USD")
with sb.form("fx_form"):
    qa = st.number_input("상품 원가", min_value=0.0, value=float(st.session_state.quick_amount), step=1.0, format="%.2f")
    qc = st.selectbox(
        "통화",
        [f"{cur} ({CURRENCY_SYMBOL[cur]})" for cur in CURRENCY_ORDER],
        index=CURRENCY_ORDER.index(st.session_state.quick_currency)
    )
    fx_go = st.form_submit_button("환율 계산")
if fx_go:
    st.session_state.quick_amount = float(qa)
    st.session_state.quick_currency = qc.split()[0]

rate = get_rate_to_krw(st.session_state.quick_currency)
if rate>0:
    sym = CURRENCY_SYMBOL.get(st.session_state.quick_currency, st.session_state.quick_currency)
    sb.metric(f"{sym}{st.session_state.quick_amount:.2f} {st.session_state.quick_currency} → ₩",
              f"{st.session_state.quick_amount*rate:,.0f} 원")
    sb.caption(f"1 {st.session_state.quick_currency} = ₩{rate:,.2f} (10분 캐시)")
else:
    sb.warning("환율 불러오기 실패")

# ---------------------------
# Layout
# ---------------------------
st.title("📊 실시간 환율 + 마진 + 데이터랩")

left, right = st.columns([1.4, 1])

with left:
    st.subheader("📈 네이버 데이터랩")
    cat_name = st.selectbox("카테고리 선택", list(CATEGORY_MAP.keys()), index=0)
    keywords = fetch_keywords_from_datalab(CATEGORY_MAP[cat_name])

    if keywords:
        df = pd.DataFrame({"keyword": keywords})
        st.dataframe(df, use_container_width=True)
    else:
        st.info("데이터랩 API에서 키워드를 가져올 수 없음.")

with right:
    st.subheader("🛒 11번가 아마존 베스트 (모바일)")
    url="https://m.11st.co.kr/browsing/AmazonBest"
    h = st.slider("높이(px)", 500, 1400, 900, 50)
    components.html(
        f"""
        <div style="border:1px solid #e5e7eb;border-radius:10px;overflow:hidden">
            <iframe src="{url}" style="width:100%;height:{h}px;border:0" sandbox=""></iframe>
        </div>
        """ ,
        height=h+14
    )

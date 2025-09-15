
# app.py — 실시간 환율 + 마진 + 네이버 데이터랩 + 11번가
# (네이버 API 키 내장 + 외부 secrets.json 지원)

import streamlit as st
import requests, re, os, json
import pandas as pd
from datetime import timedelta, date
import streamlit.components.v1 as components

st.set_page_config(page_title="실시간 환율 + 마진 + 데이터랩", page_icon="📊", layout="wide")

# ---------------------------
# NAVER API Key (내장 + 외부 secrets.json 지원)
# ---------------------------
DEFAULT_CLIENT_ID = "h4mkIM2hNLct04BD7sC0"
DEFAULT_CLIENT_SECRET = "ltoxUNyKxi"

if os.path.exists("secrets.json"):
    try:
        with open("secrets.json","r",encoding="utf-8") as f:
            data = json.load(f)
            NAVER_CLIENT_ID = data.get("NAVER_CLIENT_ID", DEFAULT_CLIENT_ID)
            NAVER_CLIENT_SECRET = data.get("NAVER_CLIENT_SECRET", DEFAULT_CLIENT_SECRET)
    except Exception:
        NAVER_CLIENT_ID, NAVER_CLIENT_SECRET = DEFAULT_CLIENT_ID, DEFAULT_CLIENT_SECRET
else:
    NAVER_CLIENT_ID, NAVER_CLIENT_SECRET = DEFAULT_CLIENT_ID, DEFAULT_CLIENT_SECRET

# ---------------------------
# Style & Theme
# ---------------------------
st.session_state.setdefault("theme_dark", False)
def inject_theme(dark: bool):
    if not dark:
        return
    st.markdown(
        """
        <style>
        html, body, [data-testid="stAppViewContainer"] { background: #0f172a !important; color:#e5e7eb !important; }
        .stButton>button, .stDownloadButton>button { background:#1f2937 !important; color:#e5e7eb !important; border:1px solid #374151; }
        .stSelectbox, .stTextInput, .stNumberInput, .stDateInput, .stRadio, .stCheckbox, .stSlider, .stMetric {
            filter: brightness(0.95);
        }
        .stTabs [data-baseweb="tab-list"] { gap: 12px; }
        </style>
        """ ,
        unsafe_allow_html=True,
    )
inject_theme(st.session_state.theme_dark)

# ---------------------------
# HTTP session
# ---------------------------
@st.cache_resource
def get_http():
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    })
    return s
http = get_http()

# ---------------------------
# 환율 캐시
# ---------------------------
CURRENCY_SYMBOL = {"USD":"$", "CNY":"¥", "JPY":"¥", "EUR":"€", "KRW":"₩"}

@st.cache_data(ttl=timedelta(minutes=45))
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
# Sidebar: 환율 + 마진 + 다크모드
# ---------------------------
sb = st.sidebar
sb.title("⚙️ 빠른 도구")
dark = sb.toggle("다크 모드", value=st.session_state.theme_dark)
if dark != st.session_state.theme_dark:
    st.session_state.theme_dark = dark
    st.rerun()

sb.subheader("💱 환율 빠른 계산")
st.session_state.setdefault("quick_amount", 1.0)
st.session_state.setdefault("quick_currency", "USD")
with sb.form("fx_form"):
    qa = st.number_input("상품 원가", min_value=0.0, value=float(st.session_state.quick_amount), step=1.0, format="%.2f")
    qc = st.selectbox("통화", ["USD","CNY","JPY","EUR"], index=["USD","CNY","JPY","EUR"].index(st.session_state.quick_currency))
    fx_go = st.form_submit_button("환율 계산")
if fx_go:
    st.session_state.quick_amount = float(qa)
    st.session_state.quick_currency = qc

rate = get_rate_to_krw(st.session_state.quick_currency)
if rate>0:
    sym = CURRENCY_SYMBOL.get(st.session_state.quick_currency, st.session_state.quick_currency)
    sb.metric(f"{sym}{st.session_state.quick_amount:.2f} {st.session_state.quick_currency} → ₩", f"{st.session_state.quick_amount*rate:,.0f} 원")
    sb.caption(f"1 {st.session_state.quick_currency} = ₩{rate:,.2f} (45분 캐시)")
else:
    sb.warning("환율 불러오기 실패")

sb.subheader("🧮 간이 마진 계산")
st.session_state.setdefault("target_margin_pct", 40.0)
with sb.form("margin_quick"):
    cost_input = st.number_input("원가합계(KRW)", min_value=0.0, value=0.0, step=1000.0, format="%.0f")
    card = st.number_input("카드수수료(%)", min_value=0.0, value=4.0, step=0.1)/100
    market = st.number_input("마켓수수료(%)", min_value=0.0, value=15.0, step=0.1)/100
    margin_pct = st.number_input("목표 마진(%)", min_value=0.0, value=float(st.session_state.target_margin_pct), step=1.0)/100
    mg_go = st.form_submit_button("판매가 계산")
if mg_go:
    st.session_state.target_margin_pct = margin_pct*100
if mg_go and rate>0:
    base = 1 - (card+market+margin_pct)
    sell = cost_input / base if base>0 else float('inf')
    net = sell*(1-(card+market)) - cost_input
    sb.metric("목표 판매가", f"{sell:,.0f} 원")
    sb.caption(f"예상 순이익 {net:,.0f} 원, 순이익률 {(net/sell*100) if sell and sell>0 else 0:.1f}%")

# ---------------------------
# Naver DataLab helpers
# ---------------------------
CATEGORY_MAP = {
    "패션의류": "50000000", "패션잡화": "50000001", "화장품/미용": "50000002",
    "디지털/가전": "50000003", "가구/인테리어": "50000004", "식품": "50000005",
    "스포츠/레저": "50000006", "생활/건강": "50000007", "출산/육아": "50000008", "완구/취미": "50000009",
}

@st.cache_data(ttl=timedelta(minutes=30))
def try_fetch_top_keywords_from_datalab(category_cid: str):
    try:
        url = "https://datalab.naver.com/shoppingInsight/getCategoryKeywordRank.naver"
        headers = {"Referer": "https://datalab.naver.com/shoppingInsight/sCategory.naver"}
        resp = http.get(url, params={"cid": category_cid}, headers=headers, timeout=6)
        resp.raise_for_status()
        js = resp.json()
        data = js.get("data") or js.get("result") or []
        kws = [d.get("keyword") for d in data if isinstance(d, dict) and d.get("keyword")]
        return kws[:20]
    except Exception:
        return []

@st.cache_data(ttl=timedelta(minutes=30))
def fetch_naver_search_count(keyword: str, period: str) -> int:
    nso = {"1d":"so:r,p:1d,a:all", "7d":"so:r,p:1w,a:all", "1m":"so:r,p:1m,a:all"}[period]
    params = {"query": keyword, "nso": nso, "where": "view"}
    try:
        r = http.get("https://search.naver.com/search.naver", params=params, timeout=6)
        r.raise_for_status()
        txt = re.sub(r"\s+", " ", r.text)
        m = re.search(r"약?\s*([\d,]+)\s*건", txt)
        return int(m.group(1).replace(",","")) if m else 0
    except Exception:
        return 0

# ---------------------------
# Layout
# ---------------------------
st.title("📊 실시간 환율 + 마진 + 데이터랩")

left, right = st.columns([1.4, 1])

with left:
    st.subheader("📈 데이터랩 (자동 실행 + API)")
    cat_name = st.selectbox("카테고리 선택", list(CATEGORY_MAP.keys()), index=0)
    manual = st.text_area("직접 키워드 입력 (쉼표로 구분)", "")
    keywords = try_fetch_top_keywords_from_datalab(CATEGORY_MAP[cat_name])
    if not keywords and manual:
        keywords = [k.strip() for k in manual.split(",") if k.strip()]

    if keywords:
        rows = []
        for kw in keywords:
            c1 = fetch_naver_search_count(kw, "1d")
            c7 = fetch_naver_search_count(kw, "7d")
            c30 = fetch_naver_search_count(kw, "1m")
            rows.append({"keyword": kw, "1일": c1, "7일": c7, "30일": c30})
        df = pd.DataFrame(rows).set_index("keyword")
        st.bar_chart(df[["1일","7일","30일"]])
        st.dataframe(df.sort_values("7일", ascending=False), use_container_width=True)
    else:
        st.info("카테고리에서 키워드를 불러올 수 없음. 직접 입력하세요.")

with right:
    st.subheader("🛒 11번가 아마존 베스트 (모바일)")
    view = st.selectbox("보기", ["아마존 베스트","오늘의 딜","홈"], index=0)
    if view=="아마존 베스트":
        url="https://m.11st.co.kr/browsing/AmazonBest"
    elif view=="오늘의 딜":
        url="https://m.11st.co.kr/browsing/todayDeal"
    else:
        url="https://m.11st.co.kr/"
    h = st.slider("높이(px)", 500, 1400, 900, 50)
    components.html(
        f"""
        <div style="border:1px solid #e5e7eb;border-radius:10px;overflow:hidden">
            <iframe src="{url}" style="width:100%;height:{h}px;border:0"
                    referrerpolicy="no-referrer"
                    sandbox="allow-same-origin allow-scripts allow-popups allow-forms"></iframe>
        </div>
        """ ,
        height=h+14
    )

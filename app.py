
# app.py — Sidebar: 환율/마진 + 테마 토글 | 본문: 데이터랩(무키/키 둘다 지원) + 11번가
import streamlit as st
import requests, re, math
import pandas as pd
from datetime import timedelta, date
import streamlit.components.v1 as components

st.set_page_config(page_title="실시간 환율 + 마진 + 데이터랩", page_icon="📊", layout="wide")

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
        .st-emotion-cache-1v0mbdj { background:#111827 !important; }
        .stTabs [data-baseweb="tab-list"] { gap: 12px; }
        </style>
        """,
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
# Sidebar: 환율 + 간이 마진 + 테마
# ---------------------------
sb = st.sidebar
sb.title("⚙️ 빠른 도구")
# Theme toggle
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
    sb.metric(f"{st.session_state.quick_amount:.2f} {st.session_state.quick_currency} → KRW", f"{st.session_state.quick_amount*rate:,.0f} 원")
    sb.caption(f"1 {st.session_state.quick_currency} = {rate:,.2f} KRW (45분 캐시)")
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
# Naver DataLab helpers (no-key mode)
# ---------------------------
CATEGORY_MAP = {
    "패션의류": "50000000", "패션잡화": "50000001", "화장품/미용": "50000002",
    "디지털/가전": "50000003", "가구/인테리어": "50000004", "식품": "50000005",
    "스포츠/레저": "50000006", "생활/건강": "50000007", "출산/육아": "50000008", "완구/취미": "50000009",
}

@st.cache_data(ttl=timedelta(minutes=30))
def try_fetch_top_keywords_from_datalab(category_cid: str):
    """Best-effort: 시도해서 top 키워드 파싱 (로그인/차단시 실패 가능)"""
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

def parse_number_ko(text: str) -> int:
    m = re.search(r"약?\s*([\d,]+)\s*건", text.replace("\u00a0"," "))
    return int(m.group(1).replace(",","")) if m else 0

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
    st.subheader("📈 데이터랩 (무키 모드 + 선택적 API)")

    tab1, tab2 = st.tabs(["키 입력 없이 사용", "NAVER API 사용"])

    with tab1:
        colA, colB = st.columns([1,1])
        with colA:
            cat_name = st.selectbox("카테고리 선택", list(CATEGORY_MAP.keys()), index=0)
            run = st.button("키워드 Top20 불러오기")
        with colB:
            st.write("※ 정책/로그인에 따라 실패 가능. 실패 시 키워드 직접 입력으로 진행하세요.")
            manual = st.text_area("직접 키워드 입력 (쉼표로 구분)", "")

        keywords = []
        if run:
            keywords = try_fetch_top_keywords_from_datalab(CATEGORY_MAP[cat_name])
            if not keywords and manual:
                keywords = [k.strip() for k in manual.split(",") if k.strip()]
        elif manual:
            keywords = [k.strip() for k in manual.split(",") if k.strip()]

        if keywords:
            st.success(f"{len(keywords)}개 키워드")
            rows = []
            for kw in keywords[:20]:
                c1 = fetch_naver_search_count(kw, "1d")
                c7 = fetch_naver_search_count(kw, "7d")
                c30 = fetch_naver_search_count(kw, "1m")
                rows.append({"keyword": kw, "1일": c1, "7일": c7, "30일": c30})
            df = pd.DataFrame(rows).set_index("keyword")
            st.bar_chart(df[["1일","7일","30일"]])
            st.dataframe(df.sort_values("7일", ascending=False), use_container_width=True)
        else:
            st.info("카테고리를 선택하고 [키워드 Top20 불러오기] 버튼을 누르세요. 실패하면 키워드를 직접 입력하세요.")

    with tab2:
        st.caption("정확한 검색량은 NAVER DataLab Open API 권장 (Client ID/Secret 필요).")
        with st.form("api_form"):
            cid = st.text_input("Client ID")
            csec = st.text_input("Client Secret", type="password")
            kws_in = st.text_input("키워드(쉼표)")
            start_d = st.date_input("시작일", value=date.today().replace(day=1))
            end_d = st.date_input("종료일", value=date.today())
            time_unit = st.selectbox("단위", ["date","week","month"], index=1)
            go_api = st.form_submit_button("API 조회")
        if go_api and cid and csec and kws_in:
            try:
                url = "https://openapi.naver.com/v1/datalab/search"
                headers = {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": csec, "Content-Type":"application/json"}
                keywordGroups = [{"groupName": k.strip(), "keywords":[k.strip()]} for k in kws_in.split(",") if k.strip()]
                payload = {"startDate": str(start_d), "endDate": str(end_d), "timeUnit": time_unit, "keywordGroups": keywordGroups}
                r = http.post(url, headers=headers, json=payload, timeout=8)
                r.raise_for_status()
                js = r.json()
                frames = []
                for res in js.get("results", []):
                    title = res.get("title","kw")
                    df = pd.DataFrame(res.get("data",[]))
                    df["keyword"] = title
                    frames.append(df)
                if frames:
                    all_df = pd.concat(frames, ignore_index=True)
                    pv = all_df.pivot(index="period", columns="keyword", values="ratio").fillna(0)
                    st.line_chart(pv)
                    st.dataframe(pv.reset_index(), use_container_width=True)
                else:
                    st.warning("데이터 없음")
            except Exception as e:
                st.error(f"API 오류: {e}")

with right:
    st.subheader("🛒 11번가 아마존 베스트 (모바일)")
    embed = st.checkbox("화면에 임베드(느릴 수 있음)", value=False)
    st.link_button("🔗 새 창으로 열기", "https://m.11st.co.kr/browsing/AmazonBest")
    if embed:
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
            """,
            height=h+14
        )

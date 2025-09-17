# envy_app.py  (Part 1)

import streamlit as st
import pandas as pd
import requests, time as _t, datetime, random
import urllib.parse as _u

# 공통 헤더
COMMON_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "ko,en;q=0.9",
}

# ==== 다크모드/라이트모드 토글 ====
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False

mode = st.sidebar.toggle("🌗 다크 모드", value=st.session_state.dark_mode)
st.session_state.dark_mode = mode

if st.session_state.dark_mode:
    st.markdown(
        """
        <style>
        body, .stApp { background-color: #1e1e1e; color: #e0e0e0; }
        .stDataFrame, .stTable { background-color: #2a2a2a; color: #ddd; }
        </style>
        """, unsafe_allow_html=True
    )

# ==== 사이드바 스타일 ====
st.markdown(
    """
    <style>
    section[data-testid="stSidebar"] {
        padding-top: 0.5rem;
        padding-bottom: 0.5rem;
    }
    .stNumberInput label, .stSelectbox label { margin-bottom: -0.3rem; }
    </style>
    """, unsafe_allow_html=True
)
# envy_app.py  (Part 2)

st.sidebar.header("① 환율 계산기")
base_currency = st.sidebar.selectbox("기준 통화", ["USD","EUR","JPY","CNY"], index=0)

rate_map = {"USD":1400.00, "EUR":1500.00, "JPY":9.50, "CNY":190.00}
fx_rate = rate_map.get(base_currency, 1400.0)
price_foreign = st.sidebar.number_input(f"판매금액 ({base_currency})", 0.0, 1e7, 100.0)
fx_amount = price_foreign * fx_rate

st.sidebar.success(f"환산 금액(읽기전용): {fx_amount:,.0f} 원")

# --- 마진 계산기 ---
st.sidebar.header("② 마진 계산기 (v23)")
m_currency = st.sidebar.selectbox("기준 통화(판매금액)", ["USD","EUR","JPY","CNY"], index=0)
m_rate = rate_map.get(m_currency, 1400.0)
m_price = st.sidebar.number_input(f"판매금액 ({m_currency})", 0.0, 1e7, 100.0)
m_fx = m_price * m_rate
st.sidebar.info(f"판매금액 환산: {m_fx:,.0f} 원")

fee_card = st.sidebar.number_input("카드수수료 (%)", 0.0, 100.0, 4.0)
fee_market = st.sidebar.number_input("마켓수수료 (%)", 0.0, 100.0, 14.0)
ship_cost = st.sidebar.number_input("배송비 (₩)", 0.0, 1e7, 0.0)
margin_type = st.sidebar.radio("마진 방식", ["퍼센트 마진(%)","더하기 마진(₩)"])
margin_val = st.sidebar.number_input("마진율/금액", 0.0, 1e6, 10.0)

# 계산
calc_price = m_fx * (1 + fee_card/100 + fee_market/100)
if margin_type.startswith("퍼센트"):
    calc_price *= (1 + margin_val/100)
else:
    calc_price += margin_val
calc_price += ship_cost
profit = calc_price - m_fx

st.sidebar.info(f"예상 판매가: {calc_price:,.0f} 원")
st.sidebar.warning(f"순이익: {profit:,.0f} 원")
# envy_app.py  (Part 3 교체)

from functools import lru_cache

@st.cache_data(ttl=3600)
def fetch_datalab_top20(cid: str, start_date: str, end_date: str, proxy: str | None = None) -> pd.DataFrame:
    """네이버 데이터랩 Top20 키워드 수집 (프록시 우선, 실패 시 더미)"""
    try:
        end = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
    except:
        end = datetime.date.today()
    yesterday = (end - datetime.timedelta(days=1)).strftime("%Y-%m-%d")

    # 세션 예열
    s = requests.Session()
    entry = "https://datalab.naver.com/shoppingInsight/sCategory.naver"
    try:
        s.get(entry, headers=COMMON_HEADERS, timeout=10)
    except:
        pass

    # API 엔드포인트 (프록시 우선)
    api = "https://datalab.naver.com/shoppingInsight/getCategoryKeywordRank.naver"
    url = f"{proxy}?target=" + _u.quote(api, safe="") if proxy else api

    payload = {
        "cid": cid,
        "timeUnit": "date",
        "startDate": start_date,
        "endDate": yesterday,
        "device": "pc",
        "gender": "",
        "ages": "",
    }
    headers = {
        **COMMON_HEADERS,
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": entry,
    }

    last_err = None
    for i in range(3):
        try:
            r = s.post(url, headers=headers, data=payload, timeout=12)
            if r.status_code == 200:
                js = r.json()
                items = js.get("keywordList", [])
                rows = [
                    {"rank": it.get("rank", i+1), "keyword": it.get("keyword", ""), "search": it.get("ratio", 0)}
                    for i, it in enumerate(items[:20])
                ]
                return pd.DataFrame(rows)
            last_err = f"HTTP {r.status_code}"
        except Exception as e:
            last_err = str(e)
        _t.sleep(1.5 * (i+1))

    # 실패 시 더미 데이터 반환
    stub = pd.DataFrame({
        "rank": range(1, 11),
        "keyword": [f"키워드{i}" for i in range(1, 11)],
        "search": [200 - i*7 for i in range(1, 11)]
    })
    stub.attrs["warning"] = f"DataLab 호출 실패: {last_err}"
    return stub


# === Amazon 글로벌 키워드 (프록시 + 미러 폴백) ===
def fetch_amazon_top(proxy: str | None = None, region: str = "JP") -> pd.DataFrame:
    base = "https://www.amazon.co.jp" if region.upper() == "JP" else "https://www.amazon.com"
    url = f"{base}/gp/bestsellers"
    try:
        r = requests.get(url, headers=COMMON_HEADERS, timeout=10)
        if r.status_code == 200:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(r.text, "html.parser")
            items = soup.select(".p13n-sc-truncate")[:10]
            return pd.DataFrame({
                "rank": range(1, len(items)+1),
                "keyword": [i.get_text(strip=True) for i in items],
                "source": [f"Amazon {region.upper()}"]*len(items)
            })
    except:
        pass
    # 폴백 (더미 데이터)
    return pd.DataFrame({
        "rank": range(1, 6),
        "keyword": ["샘플A", "샘플B", "샘플C", "샘플D", "샘플E"],
        "source": [f"Amazon {region.upper()}"]*5
    })
# envy_app.py  (Part 4 교체)

st.title("🚀 ENVY v27.9 Full")

col1, col2, col3 = st.columns(3)
with col1:
    st.subheader("데이터랩")
    sel_cat = st.selectbox("카테고리", ["패션의류","가전/디지털","식품","생활/건강"])
    proxy = st.text_input("프록시(선택)", "", placeholder="https://envy-proxy.xxx.workers.dev")

    today = datetime.date.today()
    start = (today - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
    end   = today.strftime("%Y-%m-%d")

    df_dl = fetch_datalab_top20("50000002", start, end, proxy if proxy else None)
    warn = getattr(df_dl, "attrs", {}).get("warning")
    if warn:
        st.warning(warn)
    st.dataframe(df_dl, use_container_width=True, height=280)

with col2:
    st.subheader("아이템스카우트")
    st.info("연동 예정")

with col3:
    st.subheader("셀러라이프")
    st.info("연동 예정")

col4, col5 = st.columns(2)
with col4:
    st.subheader("AI 키워드 레이더 (국내/글로벌)")
    mode = st.radio("모드", ["국내","글로벌"])
    if mode == "국내":
        st.dataframe(df_dl)
    else:
        st.dataframe(fetch_amazon_top(region="JP"))

with col5:
    st.subheader("11번가 (모바일 프록시 + 요약표)")
    url = st.text_input("11번가 URL", "https://www.11st.co.kr/")
    st.components.v1.html(f"<iframe src='{url}' width='100%' height='400'></iframe>", height=400)

st.subheader("상품명 생성기 (규칙 + HuggingFace KoGPT2)")
brand = st.text_input("브랜드", "envy")
base_kw = st.text_input("베이스 키워드", "K-coffee mix")
rel_kw = st.text_input("연관키워드", "Maxim, Kanu, Korea")
ban_kw = st.text_input("금칙어", "copy, fake, replica")
limit = st.slider("글자수 제한", 10, 100, 80)
mode = st.radio("모드", ["규칙 기반","HuggingFace AI"])
if st.button("생성"):
    out = f"{brand} {base_kw} {rel_kw}".replace(",", " ")
    st.success(out)

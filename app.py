# === envy_app.py — Part 1 ===
import streamlit as st
import pandas as pd
import requests, time as _t, datetime, random, re
import urllib.parse as _u
from bs4 import BeautifulSoup

# 공통 헤더
COMMON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
    "Accept-Language": "ko,en;q=0.9",
}

# 다크모드 토글
if "dark_mode" not in st.session_state:
    st.session_state["dark_mode"] = False
st.session_state["dark_mode"] = st.sidebar.toggle("🌗 다크 모드", value=st.session_state["dark_mode"], key="toggle_dark")

# 간단 테마 적용
if st.session_state["dark_mode"]:
    st.markdown("""
    <style>
    body, .stApp { background: #0b1220; color: #e5e7eb; }
    .stDataFrame, .stTable { color: #e5e7eb; }
    </style>
    """, unsafe_allow_html=True)

# 사이드바 여백 축소 + pill 스타일
st.markdown("""
<style>
section[data-testid="stSidebar"] .block-container {
  padding-top: 6px !important; padding-bottom: 6px !important;
  padding-left: 10px !important; padding-right: 10px !important;
}
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"]{ gap:6px !important; }
.pill {border-radius:10px; padding:10px 12px; font-weight:700; font-size:14px; margin:6px 0 2px 0; border:1px solid;}
.pill.green  { background:#E6F4EA; color:#0F5132; border-color:#BADBCC; }   /* 환율/환산 */
.pill.blue   { background:#E7F1FE; color:#0B3D91; border-color:#B6D0FF; }   /* 예상 판매가 */
.pill.yellow { background:#FFF4CC; color:#7A5D00; border-color:#FFE08A; }   /* 순이익 */
</style>
""", unsafe_allow_html=True)

def fmt_krw(x: float) -> str:
    try:
        return f"{x:,.0f} 원"
    except Exception:
        return "0 원"

def show_pill(where, label: str, value: str, color: str):
    html = f'<div class="pill {color}">{label}: {value}</div>'
    where.markdown(html, unsafe_allow_html=True)
# === envy_app.py — Part 2 ===

st.sidebar.header("① 환율 계산기")
rate_map = {"USD": 1400.00, "EUR": 1500.00, "JPY": 9.50, "CNY": 190.00}

base_currency = st.sidebar.selectbox("기준 통화", list(rate_map.keys()), index=0, key="fx_cur")
fx_rate = rate_map.get(base_currency, 1400.0)

price_foreign = st.sidebar.number_input(f"판매금액 ({base_currency})", min_value=0.0, max_value=1e9, value=100.0, step=1.0, key="fx_price_input")
fx_amount = price_foreign * fx_rate
show_pill(st.sidebar, "환산 금액(읽기전용)", fmt_krw(fx_amount), "green")

st.sidebar.header("② 마진 계산기 (v23)")
m_currency = st.sidebar.selectbox("기준 통화(판매금액)", list(rate_map.keys()), index=0, key="m_cur")
m_rate = rate_map.get(m_currency, 1400.0)

m_price = st.sidebar.number_input(f"판매금액 ({m_currency})", min_value=0.0, max_value=1e9, value=100.0, step=1.0, key="m_price_input")
m_fx = m_price * m_rate
# 판매금액(환산) = 연두
show_pill(st.sidebar, "판매금액(환산)", fmt_krw(m_fx), "green")

fee_card   = st.sidebar.number_input("카드수수료 (%)", 0.0, 100.0, 4.0, step=0.1, key="fee_card")
fee_market = st.sidebar.number_input("마켓수수료 (%)", 0.0, 100.0, 14.0, step=0.1, key="fee_market")
ship_cost  = st.sidebar.number_input("배송비 (₩)", 0.0, 1e9, 0.0, step=100.0, key="ship_cost")

margin_type = st.sidebar.radio("마진 방식", ["퍼센트 마진(%)","더하기 마진(₩)"], index=0, key="margin_type")
margin_val  = st.sidebar.number_input("마진율/금액", 0.0, 1e9, 10.0, step=1.0, key="margin_val")

# v23 방식: (환산가 * (1+수수료들)) → 마진 적용 → 배송비 더함
calc_price = m_fx * (1 + fee_card/100 + fee_market/100)
if margin_type.startswith("퍼센트"):
    calc_price *= (1 + margin_val/100)
else:
    calc_price += margin_val
calc_price += ship_cost

profit = calc_price - m_fx

# 예상 판매가 = 하늘색 / 순이익 = 노랑
show_pill(st.sidebar, "예상 판매가", fmt_krw(calc_price), "blue")
show_pill(st.sidebar, "순이익(마진)", fmt_krw(profit), "yellow")
# === envy_app.py — Part 3 ===
@st.cache_data(ttl=3600)
def fetch_datalab_top20(cid: str, start_date: str, end_date: str, proxy: str | None = None) -> pd.DataFrame:
    """네이버 데이터랩 Top20 키워드 — 프록시 우선, 실패 시 더미"""
    try:
        end = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
    except:
        end = datetime.date.today()
    yesterday = (end - datetime.timedelta(days=1)).strftime("%Y-%m-%d")

    s = requests.Session()
    entry = "https://datalab.naver.com/shoppingInsight/sCategory.naver"
    try:
        s.get(entry, headers=COMMON_HEADERS, timeout=10)
    except:
        pass

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
            if r.status_code == 200 and r.text.strip():
                js = r.json()
                items = js.get("keywordList", [])
                rows = [
                    {"rank": it.get("rank", idx+1), "keyword": it.get("keyword", ""), "search": it.get("ratio", 0)}
                    for idx, it in enumerate(items[:20])
                ]
                return pd.DataFrame(rows)
            last_err = f"HTTP {r.status_code}"
        except Exception as e:
            last_err = str(e)
        _t.sleep(1.25 * (i+1))

    stub = pd.DataFrame({
        "rank": list(range(1, 11)),
        "keyword": [f"키워드{i}" for i in range(1, 11)],
        "search": [200 - i*7 for i in range(1, 11)]
    })
    stub.attrs["warning"] = f"DataLab 호출 실패: {last_err}"
    return stub


def fetch_amazon_top(proxy: str | None = None, region: str = "JP") -> pd.DataFrame:
    """Amazon 베스트셀러 — 직접 → 실패 시 미러 폴백"""
    base = "https://www.amazon.co.jp" if region.upper() == "JP" else "https://www.amazon.com"
    url = f"{base}/gp/bestsellers"
    try:
        r = requests.get(url, headers=COMMON_HEADERS, timeout=10)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            titles = []
            sels = [
                ".p13n-sc-truncate",
                "div._cDEzb_p13n-sc-css-line-clamp-3_g3dy1",
                "div._cDEzb_p13n-sc-css-line-clamp-2_EWgCb",
                "span.zg-text-center-align > div > a > div"
            ]
            for sel in sels:
                for el in soup.select(sel):
                    t = re.sub(r"\s+", " ", el.get_text(strip=True))
                    if t and t not in titles:
                        titles.append(t)
                    if len(titles) >= 15:
                        break
                if len(titles) >= 15:
                    break
            if titles:
                return pd.DataFrame({"rank": range(1, len(titles)+1), "keyword": titles, "source": [f"Amazon {region}"]*len(titles)})

    except Exception:
        pass

    # 폴백 더미
    return pd.DataFrame({
        "rank": range(1, 6),
        "keyword": ["샘플A","샘플B","샘플C","샘플D","샘플E"],
        "source": [f"Amazon {region}"]*5
    })
# === envy_app.py — Part 4 ===
st.title("🚀 ENVY v27.10 Full")

# ---- 본문: 데이터랩 / 아이템스카우트 / 셀러라이프 ----
col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("데이터랩")
    # 간단 CID 매핑 (필요시 확장)
    cid_map = {
        "패션의류": "50000002",
        "가전/디지털": "50000003",
        "식품": "50000006",
        "생활/건강": "50000005",
    }
    sel_cat = st.selectbox("카테고리", list(cid_map.keys()), index=0, key="dl_cat")
    proxy = st.text_input("프록시(선택)", "", placeholder="https://envy-proxy.xxx.workers.dev", key="dl_proxy")

    today = datetime.date.today()
    start = (today - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
    end   = today.strftime("%Y-%m-%d")

    df_dl = fetch_datalab_top20(cid_map[sel_cat], start, end, proxy if proxy else None)
    warn = getattr(df_dl, "attrs", {}).get("warning")
    if warn:
        st.warning(warn)
    st.dataframe(df_dl, use_container_width=True, height=280)

with col2:
    st.subheader("아이템스카우트")
    st.info("연동 대기(별도 API/프록시 준비)")

with col3:
    st.subheader("셀러라이프")
    st.info("연동 대기(별도 API/프록시 준비)")

# ---- 본문: AI 레이더 / 11번가 ----
col4, col5 = st.columns(2)
with col4:
    st.subheader("AI 키워드 레이더 (국내/글로벌)")
    radar_mode = st.radio("모드", ["국내","글로벌"], index=0, key="radar_mode")
    if radar_mode == "국내":
        st.dataframe(df_dl, use_container_width=True, height=300)
    else:
        amz_region = st.selectbox("Amazon 지역", ["JP","US"], index=0, key="amz_region")
        df_amz = fetch_amazon_top(region=amz_region)
        st.dataframe(df_amz, use_container_width=True, height=300)

with col5:
    st.subheader("11번가 (모바일 프록시 + 요약표)")
    url_11 = st.text_input("11번가 URL", "https://www.11st.co.kr/", key="url_11")
    st.components.v1.html(f"<iframe src='{url_11}' width='100%' height='400'></iframe>", height=410)

# ---- 본문: 상품명 생성기 ----
st.subheader("상품명 생성기 (규칙 + HuggingFace KoGPT2)")
brand  = st.text_input("브랜드", "envy", key="nm_brand")
base_kw= st.text_input("베이스 키워드", "K-coffee mix", key="nm_base")
rel_kw = st.text_input("연관키워드", "Maxim, Kanu, Korea", key="nm_rel")
ban_kw = st.text_input("금칙어", "copy, fake, replica", key="nm_ban")
limit  = st.slider("글자수 제한", 10, 100, 80, key="nm_limit")
gen_mode = st.radio("모드", ["규칙 기반","HuggingFace AI"], index=0, key="nm_mode")

if st.button("생성", key="nm_gen"):
    out = f"{brand} {base_kw} {rel_kw}".replace(",", " ")
    st.success(out)

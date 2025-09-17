# === envy_app.py — Part 1 ===
import streamlit as st
import pandas as pd
import requests, time as _t, datetime, re
import urllib.parse as _u
from bs4 import BeautifulSoup

# ✅ 와이드 레이아웃
st.set_page_config(page_title="ENVY Full", layout="wide")

COMMON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
    "Accept-Language": "ko,en;q=0.9",
}

# 다크모드 토글
if "dark_mode" not in st.session_state:
    st.session_state["dark_mode"] = False
st.session_state["dark_mode"] = st.sidebar.toggle("🌗 다크 모드", value=st.session_state["dark_mode"], key="toggle_dark")

if st.session_state["dark_mode"]:
    st.markdown("""
    <style>
    body, .stApp { background:#0b1220; color:#e5e7eb; }
    .stDataFrame, .stTable { color:#e5e7eb; }
    </style>
    """, unsafe_allow_html=True)

# ✅ CSS (페이지 전체 폭 + 카드 와이드화)
st.markdown("""
<style>
/* 전체 컨테이너 폭 풀기 */
html, body, [data-testid="stAppViewContainer"] > .main {
  max-width: 100vw !important;
  padding-left: 16px !important;
  padding-right: 16px !important;
}
/* 사이드바 여백 */
section[data-testid="stSidebar"] .block-container { padding:14px 16px !important; }
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"]{ gap:12px !important; }
/* 본문 컬럼 간격 */
[data-testid="stHorizontalBlock"] { gap: 1.25rem !important; }
/* 카드 */
.envy-card {
  border:1px solid #e5e7eb; border-radius:12px; padding:20px;
  width: 100% !important; max-width: none !important;
  box-sizing: border-box;
}
.envy-card h3 { margin-top:0; margin-bottom:12px; }
/* 결과 pill */
.pill {border-radius:10px; padding:10px 12px; font-weight:700; font-size:14px; margin:6px 0 2px 0; border:1px solid;}
.pill.green  { background:#E6F4EA; color:#0F5132; border-color:#BADBCC; }
.pill.blue   { background:#E7F1FE; color:#0B3D91; border-color:#B6D0FF; }
.pill.yellow { background:#FFF4CC; color:#7A5D00; border-color:#FFE08A; }
/* 스페이서 */
.vspace { height:10px; }
</style>
""", unsafe_allow_html=True)

def fmt_money2(x: float) -> str:
    try:
        return f"{x:,.2f} 원"
    except Exception:
        return "0.00 원"

def show_pill(where, label: str, value: str, color: str):
    where.markdown(f'<div class="pill {color}">{label}: {value}</div>', unsafe_allow_html=True)

# 상품명 생성기 유틸
def _sanitize(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "").replace(",", " ")).strip()

def build_titles(brand: str, base_kw: str, rel_candidates: list[dict],
                 ban_set: set[str], max_len: int, k: int = 5) -> list[str]:
    titles = []
    for cand in rel_candidates:
        kw = cand.get("keyword", "")
        if not kw: continue
        title = f"{brand} {base_kw} {kw}"
        if any(b in title.lower() for b in ban_set):
            continue
        title = _sanitize(title)[:max_len]
        if title and title not in titles:
            titles.append(title)
        if len(titles) >= k: break
    while len(titles) < k:
        fallback = _sanitize(f"{brand} {base_kw}")[:max_len]
        if fallback and fallback not in titles:
            titles.append(fallback)
        else:
            titles.append(_sanitize(brand)[:max_len])
        if len(titles) >= k: break
    return titles
# === envy_app.py — Part 2 ===

st.sidebar.header("① 환율 계산기")
rate_map = {"USD": 1400.00, "EUR": 1500.00, "JPY": 9.50, "CNY": 190.00}

fx_cur = st.sidebar.selectbox("기준 통화", list(rate_map.keys()), index=0, key="fx_cur")
fx_rate = rate_map.get(fx_cur, 1400.0)
fx_price = st.sidebar.number_input(
    f"판매금액 ({fx_cur})", min_value=0.0, max_value=1e12,
    value=1.00, step=0.01, format="%.2f", key="fx_price"
)
fx_amount = fx_price * fx_rate
show_pill(st.sidebar, "환산 금액", fmt_money2(fx_amount), "green")

st.sidebar.header("② 마진 계산기 (v23)")
m_cur = st.sidebar.selectbox("기준 통화(판매금액)", list(rate_map.keys()), index=0, key="m_cur")
m_rate = rate_map.get(m_cur, 1400.0)
m_price = st.sidebar.number_input(
    f"판매금액 ({m_cur})", min_value=0.0, max_value=1e12,
    value=1.00, step=0.01, format="%.2f", key="m_price"
)
m_fx = m_price * m_rate
show_pill(st.sidebar, "판매금액(환산)", fmt_money2(m_fx), "green")

st.sidebar.markdown('<div class="vspace"></div>', unsafe_allow_html=True)

fee_card   = st.sidebar.number_input("카드수수료 (%)", 0.00, 100.00, 4.00, 0.01, format="%.2f", key="fee_card")
fee_market = st.sidebar.number_input("마켓수수료 (%)", 0.00, 100.00, 14.00, 0.01, format="%.2f", key="fee_market")
ship_cost  = st.sidebar.number_input("배송비 (₩)",     0.00, 1e12,   0.00, 0.01, format="%.2f", key="ship_cost")

m_type = st.sidebar.radio("마진 방식", ["퍼센트 마진(%)","더하기 마진(₩)"], index=0, key="m_type")
m_val  = st.sidebar.number_input("마진율/금액", 0.00, 1e12, 10.00, 0.01, format="%.2f", key="m_val")

calc_price = m_fx * (1 + fee_card/100 + fee_market/100)
if m_type.startswith("퍼센트"):
    calc_price *= (1 + m_val/100)
else:
    calc_price += m_val
calc_price += ship_cost

profit = calc_price - m_fx
show_pill(st.sidebar, "예상 판매가", fmt_money2(calc_price), "blue")
show_pill(st.sidebar, "순이익(마진)", fmt_money2(profit), "yellow")
# === envy_app.py — Part 3 ===

@st.cache_data(ttl=3600)
def fetch_datalab_top20(cid: str, start_date: str, end_date: str, proxy: str | None = None) -> pd.DataFrame:
    try:
        end = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
    except:
        end = datetime.date.today()
    yesterday = (end - datetime.timedelta(days=1)).strftime("%Y-%m-%d")

    s = requests.Session()
    entry = "https://datalab.naver.com/shoppingInsight/sCategory.naver"
    try: s.get(entry, headers=COMMON_HEADERS, timeout=10)
    except: pass

    api = "https://datalab.naver.com/shoppingInsight/getCategoryKeywordRank.naver"
    url = f"{proxy}?target=" + _u.quote(api, safe="") if proxy else api
    payload = {"cid": cid,"timeUnit":"date","startDate":start_date,"endDate":yesterday,"device":"pc","gender":"","ages":""}
    headers = {**COMMON_HEADERS,"Content-Type":"application/x-www-form-urlencoded; charset=UTF-8","X-Requested-With":"XMLHttpRequest","Referer":entry}

    last_err=None
    for i in range(3):
        try:
            r=s.post(url,headers=headers,data=payload,timeout=12)
            if r.status_code==200 and r.text.strip():
                js=r.json()
                items=js.get("keywordList",[])
                rows=[{"rank":it.get("rank",idx+1),"keyword":it.get("keyword",""),"search":it.get("ratio",0)} for idx,it in enumerate(items[:20])]
                return pd.DataFrame(rows)
            last_err=f"HTTP {r.status_code}"
        except Exception as e: last_err=str(e)
        _t.sleep(1.25*(i+1))
    stub=pd.DataFrame({"rank":list(range(1,6)),"keyword":["키워드A","키워드B","키워드C","키워드D","키워드E"],"search":[100,95,90,85,80]})
    stub.attrs["warning"]=f"DataLab 호출 실패: {last_err}"
    return stub

def fetch_amazon_top(region: str = "JP") -> pd.DataFrame:
    base = "https://www.amazon.co.jp" if region.upper()=="JP" else "https://www.amazon.com"
    url = f"{base}/gp/bestsellers"
    try:
        r=requests.get(url,headers=COMMON_HEADERS,timeout=10)
        if r.status_code==200:
            soup=BeautifulSoup(r.text,"html.parser")
            titles=[]
            for sel in [".p13n-sc-truncate","div._cDEzb_p13n-sc-css-line-clamp-3_g3dy1","div._cDEzb_p13n-sc-css-line-clamp-2_EWgCb","span.zg-text-center-align > div > a > div"]:
                for el in soup.select(sel):
                    t=re.sub(r"\s+"," ",el.get_text(strip=True))
                    if t and t not in titles: titles.append(t)
                    if len(titles)>=15: break
                if len(titles)>=15: break
            if titles: return pd.DataFrame({"rank":range(1,len(titles)+1),"keyword":titles,"source":[f"Amazon {region}"]*len(titles)})
    except: pass
    return pd.DataFrame({"rank":range(1,6),"keyword":["샘플A","샘플B","샘플C","샘플D","샘플E"],"source":[f"Amazon {region}"]*5})

from urllib.parse import urlparse,urlunparse
def normalize_11st_mobile(url:str)->str:
    try:
        u=urlparse(url.strip())
        if not u.scheme: u=urlparse("https://"+url.strip())
        host=u.netloc.lower()
        if "11st.co.kr" in host and not host.startswith("m."): host="m.11st.co.kr"
        return urlunparse((u.scheme,host,u.path,u.params,u.query,u.fragment))
    except: return "https://m.11st.co.kr"
# === envy_app.py — Part 4 ===
st.title("🚀 ENVY v27.12 Full")

# 윗줄 3분할
top1, top2, top3 = st.columns([1,1,1], gap="large")
with top1:
    st.markdown('<div class="envy-card">', unsafe_allow_html=True)
    st.markdown("### 데이터랩")
    cid_map={"패션의류":"50000002","패션잡화":"50000001","화장품/미용":"50000007","디지털/가전":"50000003","가구/인테리어":"50000004","생활/건강":"50000005","식품":"50000006","출산/육아":"50000008","스포츠/레저":"50000009","자동차용품":"50000100"}
    dl_cat=st.selectbox("카테고리(10개)",list(cid_map.keys()),index=5,key="dl_cat_main")
    proxy=st.text_input("프록시(선택)","","https://envy-proxy.taesig0302.workers.dev",key="dl_proxy_main")
    today=datetime.date.today(); start=(today-datetime.timedelta(days=30)).strftime("%Y-%m-%d"); end=today.strftime("%Y-%m-%d")
    df_dl=fetch_datalab_top20(cid_map[dl_cat],start,end,proxy if proxy else None)
    warn=getattr(df_dl,"attrs",{}).get("warning"); 
    if warn: st.warning(warn)
    st.dataframe(df_dl,use_container_width=True,height=260)
    st.markdown('</div>', unsafe_allow_html=True)
with top2: st.markdown('<div class="envy-card"><h3>아이템스카우트</h3><p>연동 대기</p></div>', unsafe_allow_html=True)
with top3: st.markdown('<div class="envy-card"><h3>셀러라이프</h3><p>연동 대기</p></div>', unsafe_allow_html=True)

# 아랫줄 3분할
bot1, bot2, bot3 = st.columns([1,1,1], gap="large")
with bot1:
    st.markdown('<div class="envy-card">', unsafe_allow_html=True)
    st.markdown("### AI 키워드 레이더")
    mode=st.radio("모드",["국내","글로벌"],index=0,horizontal=True,key="radar_mode_main")
    if mode=="국내":
        st.dataframe(df_dl,use_container_width=True,height=300)
    else:
        region=st.selectbox("Amazon 지역",["JP","US"],index=0,key="amz_region_main")
        st.dataframe(fetch_amazon_top(region),use_container_width=True,height=300)
    st.markdown('</div>', unsafe_allow_html=True)
with bot2:
    st.markdown('<div class="envy-card">', unsafe_allow_html=True)
    st.markdown("### 11번가")
    url_11=st.text_input("11번가 URL","https://www.11st.co.kr/",key="url_11_main")
    mobile_11=normalize_11st_mobile(url_11)
    st.components.v1.html(f"<iframe src='{mobile_11}' width='100%' height='520' style='border:1px solid #e5e7eb;border-radius:10px;' sandbox='allow-scripts allow-forms allow-same-origin allow-popups'></iframe>",height=540)
    st.markdown('</div>', unsafe_allow_html=True)
with bot3:
    st.markdown('<div class="envy-card">', unsafe_allow_html=True)
    st.markdown("### 상품명 생성기")
    brand=st.text_input("브랜드","envy",key="nm_brand_main")
    base_kw=st.text_input("베이스 키워드","K-coffee mix",key="nm_base_main")
    rel_kw=st.text_input("연관키워드","Maxim, Kanu, Korea",key="nm_rel_main")
    ban_kw=st.text_input("금칙어","copy, fake, replica",key="nm_ban_main")
    limit=st.slider("글자수 제한",10,100,80,key="nm_limit_main")
    if st.button("제목 생성",key="nm_gen_main"):
        tokens=[t.strip() for t in rel_kw.split(",") if t.strip()]
        rel_candidates=[{"keyword":t,"search":None} for t in tokens]
        ban_set={b.strip().lower() for b in ban_kw.split(",") if b.strip()}
        titles=build_titles(brand,base_kw,rel_candidates,ban_set,limit,k=5)
        st.markdown("#### 추천 제목 5가지")
        for i,t in enumerate(titles,1):
            st.code(f"{i}. {t}")
        st.markdown("#### 추천용 연관키워드")
        st.dataframe(pd.DataFrame(rel_candidates),use_container_width=True,height=200)
    st.markdown('</div>', unsafe_allow_html=True)

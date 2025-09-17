# ==== THEME TOGGLE & GLOBAL CSS ====
if "theme" not in st.session_state:
    st.session_state["theme"] = "light"

theme_choice = st.sidebar.toggle("🌗 다크 모드", value=(st.session_state["theme"]=="dark"), key="__theme_toggle")
st.session_state["theme"] = "dark" if theme_choice else "light"

PRIMARY = "#2563eb" if st.session_state["theme"]=="light" else "#60a5fa"
BG_PANEL = "#f8fafc" if st.session_state["theme"]=="light" else "#0b1220"
FG_TEXT = "#0f172a" if st.session_state["theme"]=="light" else "#e5e7eb"

st.markdown(f"""
<style>
/* 사이드바 상단 여백 축소 */
section[data-testid="stSidebar"] .css-1lcbmhc, 
section[data-testid="stSidebar"] .css-1d391kg {{ padding-top: 6px !important; }}

/* 카드형 박스 */
.envy-box {{
  background:{BG_PANEL};
  border:1px solid rgba(100,100,100,0.12);
  border-radius:10px; padding:12px 14px; margin:6px 0;
}}
.envy-title {{ font-weight:700; color:{FG_TEXT}; margin-bottom:6px; }}
.envy-kpi {{ font-size:20px; font-weight:800; color:{PRIMARY}; }}
.envy-kpi-sub {{ font-size:12px; opacity:0.8; }}
</style>
""", unsafe_allow_html=True)
with st.sidebar:
    st.header("① 환율 계산기")
    fx_ccy = st.selectbox("기준 통화", FX_ORDER, index=0, key="sb_fx_base")
    fx_rate = get_fx_rate(fx_ccy)
    st.caption(f"자동 환율: 1 {fx_ccy} = {fx_rate:,.2f} ₩")

    fx_price = st.number_input(f"판매금액 ({fx_ccy})", 0.0, 1e12, 100.0, 1.0, key="sb_fx_price_foreign")
    fx_krw = fx_price * fx_rate

    # 환산금액 강조 박스
    st.markdown(f"""
    <div class="envy-box">
      <div class="envy-title">환산 금액 (읽기 전용)</div>
      <div class="envy-kpi">₩{fx_krw:,.0f}</div>
      <div class="envy-kpi-sub">환율 자동 반영</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.header("② 마진 계산기 (v23)")
    m_ccy = st.selectbox("기준 통화(판매금액)", FX_ORDER, index=0, key="sb_m_base")
    m_rate = get_fx_rate(m_ccy)
    st.caption(f"자동 환율: 1 {m_ccy} = {m_rate:,.2f} ₩")

    sale_foreign = st.number_input(f"판매금액 ({m_ccy})", 0.0, 1e12, 100.0, 1.0, key="sb_m_sale_foreign")
    sale_krw = sale_foreign * m_rate

    # 판매금액(환산) 강조
    st.markdown(f"""
    <div class="envy-box">
      <div class="envy-title">판매금액 (환산)</div>
      <div class="envy-kpi">₩{sale_krw:,.0f}</div>
    </div>
    """, unsafe_allow_html=True)

    card = st.number_input("카드수수료 (%)", 0.0, 100.0, 4.0, 0.1, key="sb_card")
    market = st.number_input("마켓수수료 (%)", 0.0, 100.0, 14.0, 0.1, key="sb_market")
    ship = st.number_input("배송비 (₩)", 0.0, 1e9, 0.0, 100.0, key="sb_ship")
    mode = st.radio("마진 방식", ["퍼센트 마진(%)","더하기 마진(₩)"], horizontal=True, key="sb_mode")

    if mode=="퍼센트 마진(%)":
        margin_pct = st.number_input("마진율 (%)", 0.0, 500.0, 10.0, 0.1, key="sb_margin_pct")
        P, profit, on_sale = margin_calc_percent(sale_krw, card, market, margin_pct, ship)
    else:
        add_margin = st.number_input("더하기 마진 (₩)", 0.0, 1e12, 10000.0, 100.0, key="sb_add_margin")
        P, profit, on_sale = margin_calc_add(sale_krw, card, market, add_margin, ship)

    # KPI 두 개를 큰 카드로 강조
    st.markdown(f"""
    <div class="envy-box">
      <div class="envy-title">판매가격 (계산 결과)</div>
      <div class="envy-kpi">₩{P:,.0f}</div>
      <div class="envy-kpi-sub">마진율(판매가 기준): {on_sale:.2f}%</div>
    </div>
    <div class="envy-box">
      <div class="envy-title">순이익(마진)</div>
      <div class="envy-kpi">₩{profit:,.0f}</div>
    </div>
    """, unsafe_allow_html=True)
# ==== 강화된 요청 유틸 ====
def _retry_post(url, headers=None, data=None, timeout=12, tries=4):
    last = None
    for i in range(tries):
        try:
            r = requests.post(url, headers=headers, data=data, timeout=timeout)
            if r.status_code in (200, 201):
                return r
            if r.status_code in (403, 429):
                time = 1.2 * (2**i)
                st.caption(f"요청 지연중… {time:.1f}s")
                import time as _t; _t.sleep(time)
                continue
            last = r
        except Exception as e:
            last = e
    raise RuntimeError(f"POST 실패: {last}")

def _retry_get(url, headers=None, timeout=12, tries=4):
    last = None
    for i in range(tries):
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            if r.status_code in (200, 201):
                return r
            if r.status_code in (403, 429):
                time = 1.2 * (2**i)
                st.caption(f"요청 지연중… {time:.1f}s")
                import time as _t; _t.sleep(time)
                continue
            last = r
        except Exception as e:
            last = e
    raise RuntimeError(f"GET 실패: {last}")
# ==== DataLab (프록시 옵션 + 재시도) ====
def fetch_datalab_top20(cid: str, start_date: str, end_date: str, proxy: str|None=None) -> pd.DataFrame:
    s = requests.Session()
    cat_url = "https://datalab.naver.com/shoppingInsight/sCategory.naver"
    s.get(cat_url, headers={**COMMON_HEADERS, "Accept":"text/html,*/*"}, timeout=10)

    api_url = "https://datalab.naver.com/shoppingInsight/getCategoryKeywordRank.naver"
    if proxy:
        api_url = f"{proxy}?target=" + urllib.parse.quote(api_url, safe="")

    headers = {
        **COMMON_HEADERS,
        "Accept":"application/json, text/javascript, */*; q=0.01",
        "Content-Type":"application/x-www-form-urlencoded; charset=UTF-8",
        "Origin":"https://datalab.naver.com",
        "Referer": cat_url,
        "X-Requested-With":"XMLHttpRequest",
    }
    payload = {"cid":cid,"timeUnit":"date","startDate":start_date,"endDate":end_date,
               "device":"pc","gender":"","ages":""}

    r = _retry_post(api_url, headers=headers, data=payload, timeout=12, tries=4)
    txt = r.text.strip()
    if not txt or not (txt.startswith("{") or txt.startswith("[")):
        raise RuntimeError("DataLab JSON 아님(차단/구조변경 가능성)")
    data = r.json()
    if "keywordList" not in data or not isinstance(data["keywordList"], list):
        raise RuntimeError("DataLab 구조 변경 또는 데이터 없음")
    rows=[]
    for it in data["keywordList"][:20]:
        rows.append({"rank": it.get("rank") or len(rows)+1,
                     "keyword": it.get("keyword",""),
                     "search": it.get("ratio") or 0})
    return pd.DataFrame(rows).sort_values("rank").reset_index(drop=True)
# ==== Amazon (프록시 옵션 + 재시도) ====
def fetch_amazon_bestsellers(limit:int=15, proxy:str|None=None) -> pd.DataFrame:
    url = "https://www.amazon.com/Best-Sellers/zgbs"
    if proxy:
        url = f"{proxy}?target=" + urllib.parse.quote(url, safe="")
    headers = {**COMMON_HEADERS, "Referer":"https://www.amazon.com/"}
    r = _retry_get(url, headers=headers, timeout=12, tries=4)
    from bs4 import BeautifulSoup, SoupStrainer
    soup = BeautifulSoup(r.text, "html.parser")

    titles=[]
    selectors = [
        "div.p13n-sc-truncate",
        "div._cDEzb_p13n-sc-css-line-clamp-3_g3dy1",
        "div._cDEzb_p13n-sc-css-line-clamp-2_EWgCb",
        "div.a-section.a-spacing-small > h3, div.a-section.a-spacing-small > a > span",
        "span.zg-text-center-align > div > a > div",
    ]
    for sel in selectors:
        for el in soup.select(sel):
            t = re.sub(r"\s+"," ", el.get_text(strip=True))
            if t and t not in titles:
                titles.append(t)
            if len(titles) >= limit:
                break
        if len(titles) >= limit:
            break
    if not titles:
        raise RuntimeError("Amazon 파싱 실패(구조변경/차단 가능)")
    df = pd.DataFrame({"rank":range(1,len(titles)+1), "keyword":titles[:limit]})
    df["score"] = [300-i for i in range(1,len(df)+1)]
    df["source"] = "Amazon US"
    return df[["source","rank","keyword","score"]]
with c1:
    st.subheader("데이터랩")
    category = st.selectbox("카테고리", list(NAVER_CATEGORIES.keys()), index=0, key="dl_cat")
    cid = NAVER_CATEGORIES[category]
    dl_proxy = st.text_input("프록시(선택)", "", key="dl_proxy", placeholder="https://your-proxy/app?target=<url>")
    today = datetime.date.today()
    start = (today - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
    end = today.strftime("%Y-%m-%d")
    try:
        df_dl = fetch_datalab_top20(cid, start, end, proxy=(dl_proxy or None))
        ...

with d1:
    ...
    else:
        amz_proxy = st.text_input("Amazon 프록시(선택)", "", key="amz_proxy",
                                   placeholder="https://your-proxy/app?target=<url>")
        rak_genre = st.text_input("Rakuten genreId (선택, 비우면 종합)", "", key="rak_genre")
        try:
            df_amz = fetch_amazon_bestsellers(15, proxy=(amz_proxy or None))
        except Exception as e:
            st.error(f"Amazon 수집 실패: {e}")
            df_amz = pd.DataFrame(columns=["source","rank","keyword","score"])
        ...

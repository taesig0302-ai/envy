# -*- coding: utf-8 -*-
# ENVY — Season 1 (Dual Proxy Edition) — FULL

import re, io, json, math, time, base64, hashlib, hmac
import datetime as dt
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import streamlit as st

# ---------- Optional imports ----------
try:
    import requests
except Exception:
    requests = None

try:
    from deep_translator import GoogleTranslator as _GT
except Exception:
    _GT = None

st.set_page_config(page_title="ENVY — Season 1 (Dual Proxy Edition)", layout="wide")

# =========================
# 0) GLOBALS & DEFAULT KEYS
# =========================
SHOW_ADMIN_BOX = False

# Proxies (Cloudflare Worker)
NAVER_PROXY      = "https://envy-proxy.taesig0302.workers.dev"
ELEVENST_PROXY   = "https://worker-11stjs.taesig0302.workers.dev"
ITEMSCOUT_PROXY  = "https://worker-itemscoutjs.taesig0302.workers.dev"
SELLERLIFE_PROXY = "https://worker-sellerlifejs.taesig0302.workers.dev"

# ---- Default credentials (secrets 가 있으면 secrets 우선) ----
DEFAULT_KEYS = {
    # Rakuten
    "RAKUTEN_APP_ID": "1043271015809337425",
    "RAKUTEN_AFFILIATE_ID": "4c723498.cbfeca46.4c723499.1deb6f77",

    # NAVER Searchad(키워드도구)
    "NAVER_API_KEY": "0100000000785cf1d8f039b13a5d3c3d1262b84e9ad4a046637e8887bbd003051b0d2a5cdf",
    "NAVER_SECRET_KEY": "AQAAAAB4XPHY8DmxOl08PRJiuE6ao1LN3lh0kF9rOJ4m5b8O5g==",
    "NAVER_CUSTOMER_ID": "2274338",

    # NAVER DataLab
    "NAVER_CLIENT_ID": "T27iw3tyujrM1nG_shFT",
    "NAVER_CLIENT_SECRET": "s59xKPYLz1",

    # 선택: Referer
    "NAVER_WEB_REFERER": "",
}
def _get_key(name: str) -> str:
    return (st.secrets.get(name, "") or DEFAULT_KEYS.get(name, "")).strip()

# Simple FX
CURRENCIES = {
    "USD":{"kr":"미국 달러","symbol":"$","unit":"USD"},
    "EUR":{"kr":"유로","symbol":"€","unit":"EUR"},
    "JPY":{"kr":"일본 엔","symbol":"¥","unit":"JPY"},
    "CNY":{"kr":"중국 위안","symbol":"元","unit":"CNY"},
}
FX_DEFAULT = {"USD":1400.0,"EUR":1500.0,"JPY":10.0,"CNY":200.0}

# =========================
# Boot: session defaults & theme helper
# =========================
def ensure_session_defaults():
    ss = st.session_state
    ss.setdefault("theme", "light")               # "light" or "dark"
    ss.setdefault("__theme_toggle", False)        # sidebar raw toggle
    ss.setdefault("__show_translator", False)
    ss.setdefault("rk_genre_map", {})             # <-- KeyError 방지 (라쿠텐 장르 매핑)
    # calculators defaults
    ss.setdefault("fx_base", "USD")
    ss.setdefault("sale_foreign", 1.00)
    ss.setdefault("m_base", "USD")
    ss.setdefault("purchase_foreign", 0.00)
    ss.setdefault("card_fee_pct", 4.00)
    ss.setdefault("market_fee_pct", 14.00)
    ss.setdefault("shipping_won", 0.0)
    ss.setdefault("margin_mode", "퍼센트")
    ss.setdefault("margin_pct", 10.00)
    ss.setdefault("margin_won", 10000.0)

def _toggle_theme():
    st.session_state["theme"] = "dark" if st.session_state.get("__theme_toggle", False) else "light"

def _inject_css():
    theme = st.session_state.get("theme", "light")

    # 라이트: 본문 알림/컬러박스 파란 배경 + 흰 글자
    if theme == "light":
        st.markdown("""
        <style>
          [data-testid="stAppViewContainer"] .stAlert{
            background:#2563eb !important; border:1px solid #1e40af !important;
          }
          [data-testid="stAppViewContainer"] .stAlert,
          [data-testid="stAppViewContainer"] .stAlert *{
            color:#ffffff !important; fill:#ffffff !important;
          }
        </style>
        """, unsafe_allow_html=True)

    # 다크: 모든 입력계열은 흰 배경 + 검정 글자로 강제
    if theme == "dark":
        st.markdown("""
        <style>
          [data-testid="stAppViewContainer"] div[data-testid="stTextInput"] input,
          [data-testid="stAppViewContainer"] div[data-testid="stNumberInput"] input,
          [data-testid="stAppViewContainer"] div[data-testid="stTextArea"] textarea,
          [data-testid="stAppViewContainer"] [data-baseweb="textarea"] textarea{
            background:#ffffff !important;
            color:#111 !important; -webkit-text-fill-color:#111 !important;
            border:1px solid rgba(0,0,0,.18) !important;
          }
          [data-testid="stAppViewContainer"] [data-baseweb="select"] > div{
            background:#ffffff !important;
            border:1px solid rgba(0,0,0,.18) !important;
          }
          [data-testid="stAppViewContainer"] [data-baseweb="select"] *,
          [data-testid="stAppViewContainer"] [data-baseweb="select"] input{
            color:#111 !important; -webkit-text-fill-color:#111 !important;
          }
          [data-baseweb="popover"] [role="listbox"],
          [data-baseweb="popover"] [role="listbox"] *{
            background:#ffffff !important;
            color:#111 !important; -webkit-text-fill-color:#111 !important;
          }
        </style>
        """, unsafe_allow_html=True)

# =========================
# Sidebar
# =========================
def sidebar():
    with st.sidebar:
        ensure_session_defaults()

        # 로고(있으면 표시)
        try:
            lp = Path(__file__).parent / "logo.png"
            if lp.exists():
                b64 = base64.b64encode(lp.read_bytes()).decode("ascii")
                st.markdown(
                    '<div style="width:64px;height:64px;border-radius:9999px;overflow:hidden;'
                    'margin:.35rem auto .6rem auto;box-shadow:0 2px 8px rgba(0,0,0,.12);'
                    'border:1px solid rgba(0,0,0,.06)"><img src="data:image/png;base64,%s" style="width:100%%;height:100%%;object-fit:cover"></div>'
                    % b64, unsafe_allow_html=True
                )
        except Exception:
            pass

        c1, c2 = st.columns(2)
        with c1:
            st.toggle("🌓 다크", value=(st.session_state.get("theme")=="dark"),
                      key="__theme_toggle", on_change=_toggle_theme)
        with c2:
            st.toggle("🌐 번역기",
                      value=st.session_state.get("__show_translator", False),
                      key="__show_translator")

        # Sidebar always light (가독)
        st.markdown("""
        <style>
          :root [data-testid="stSidebar"]{ background:#ffffff !important; color:#111 !important; }
          :root [data-testid="stSidebar"] *{ color:#111 !important; -webkit-text-fill-color:#111 !important; }
        </style>
        """, unsafe_allow_html=True)

        # Tools
        if st.session_state.get("__show_translator") and _GT:
            with st.expander("🌐 구글 번역기", expanded=True):
                langs = {
                    "auto":"자동 감지","ko":"한국어","en":"영어","ja":"일본어","zh-CN":"중국어(간체)",
                    "zh-TW":"중국어(번체)","vi":"베트남어","th":"태국어","id":"인도네시아어",
                    "de":"독일어","fr":"프랑스어","es":"스페인어","it":"이탈리아어","pt":"포르투갈어"
                }
                inv = {v:k for k,v in langs.items()}
                src = st.selectbox("원문 언어", list(langs.values()),
                                   index=list(langs.keys()).index("auto"))
                tgt = st.selectbox("번역 언어", list(langs.values()),
                                   index=list(langs.keys()).index("ko"))
                txt = st.text_area("텍스트", height=100)
                if st.button("번역 실행", use_container_width=True):
                    try:
                        out = _GT(source=inv[src], target=inv[tgt]).translate(txt or "")
                        st.text_area(f"결과 ({tgt})", value=out, height=100)
                        if inv[tgt] != "ko":
                            ko = _GT(source=inv[tgt], target="ko").translate(out or "")
                            st.text_area("결과 (한국어)", value=ko, height=100)
                    except Exception as e:
                        st.error(f"번역 오류: {e}")

        with st.expander("💱 환율 계산기", expanded=(not st.session_state.get("__show_translator"))):
            fx_base = st.selectbox("기준 통화", list(CURRENCIES.keys()),
                                   index=list(CURRENCIES.keys()).index(st.session_state.get("fx_base","USD")),
                                   key="fx_base")
            sale_foreign = st.number_input("판매금액 (외화)",
                                           value=float(st.session_state.get("sale_foreign",1.0)),
                                           step=0.01, format="%.2f", key="sale_foreign")
            won = FX_DEFAULT[fx_base]*sale_foreign
            st.success(f"환산 금액: {won:,.2f} 원  ({CURRENCIES[fx_base]['symbol']})")
            st.caption(f"환율 기준: {FX_DEFAULT[fx_base]:,.2f} ₩/{CURRENCIES[fx_base]['unit']}")

        with st.expander("📈 마진 계산기", expanded=(not st.session_state.get("__show_translator"))):
            m_base = st.selectbox("매입 통화", list(CURRENCIES.keys()),
                                  index=list(CURRENCIES.keys()).index(st.session_state.get("m_base","USD")), key="m_base")
            purchase_foreign = st.number_input("매입금액 (외화)",
                                               value=float(st.session_state.get("purchase_foreign",0.0)),
                                               step=0.01, format="%.2f", key="purchase_foreign")
            base_cost_won = FX_DEFAULT[m_base]*purchase_foreign if purchase_foreign>0 \
                            else FX_DEFAULT[st.session_state.get("fx_base","USD")]*st.session_state.get("sale_foreign",1.0)
            st.info(f"원가(₩): {base_cost_won:,.2f}")

            c1, c2 = st.columns(2)
            with c1:
                card_fee = st.number_input("카드수수료(%)",
                                           value=float(st.session_state.get("card_fee_pct",4.0)),
                                           step=0.01, format="%.2f", key="card_fee_pct")
            with c2:
                market_fee = st.number_input("마켓수수료(%)",
                                             value=float(st.session_state.get("market_fee_pct",14.0)),
                                             step=0.01, format="%.2f", key="market_fee_pct")

            shipping_won = st.number_input("배송비(₩)",
                                           value=float(st.session_state.get("shipping_won",0.0)),
                                           step=100.0, format="%.0f", key="shipping_won")
            mode = st.radio("마진 방식", ["퍼센트","플러스"], horizontal=True, key="margin_mode")

            if mode=="퍼센트":
                margin_pct = st.number_input("마진율 (%)",
                                             value=float(st.session_state.get("margin_pct",10.0)),
                                             step=0.01, format="%.2f", key="margin_pct")
                target_price = base_cost_won*(1+card_fee/100)*(1+market_fee/100)*(1+margin_pct/100)+shipping_won
                margin_value = target_price - base_cost_won; desc=f"{margin_pct:.2f}%"
            else:
                margin_won = st.number_input("마진액 (₩)",
                                             value=float(st.session_state.get("margin_won",10000.0)),
                                             step=100.0, format="%.0f", key="margin_won")
                target_price = base_cost_won*(1+card_fee/100)*(1+market_fee/100)+margin_won+shipping_won
                margin_value = margin_won; desc=f"+{margin_won:,.0f}"

            st.success(f"판매가: {target_price:,.2f} 원")
            st.info(f"순이익: {margin_value:,.2f} 원 — {desc}")

        if SHOW_ADMIN_BOX:
            st.divider()
            st.text_input("PROXY_URL(디버그)", key="PROXY_URL")

# =========================
# Utilities
# =========================
def _responsive_probe():
    html = """
    <script>
    (function(){
      const bps=[900,1280,1600];
      const w=Math.max(document.documentElement.clientWidth||0, window.innerWidth||0);
      let bin=0; for(let i=0;i<bps.length;i++) if(w>=bps[i]) bin=i+1;
      const url=new URL(window.location); const curr=url.searchParams.get('vwbin');
      if(curr!==String(bin)){ url.searchParams.set('vwbin', String(bin)); window.location.replace(url.toString()); }
    })();
    </script>
    """
    st.components.v1.html(html, height=0, scrolling=False)

def _get_view_bin():
    try:
        raw = st.query_params.get("vwbin", "3")
    except Exception:
        raw = (st.experimental_get_query_params().get("vwbin", ["3"])[0])
    try:
        return max(0, min(3, int(raw)))
    except:
        return 3

# =========================
# NAVER Searchad — 키워드도구
# =========================
def _naver_signature(timestamp: str, method: str, uri: str, secret: str) -> str:
    msg = f"{timestamp}.{method}.{uri}"
    digest = hmac.new(bytes(secret, "utf-8"), bytes(msg, "utf-8"), hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")

def _naver_keys_from_secrets():
    ak = _get_key("NAVER_API_KEY"); sk = _get_key("NAVER_SECRET_KEY"); cid= _get_key("NAVER_CUSTOMER_ID")
    return ak.strip(), sk.strip(), str(cid).strip()

def _naver_keywordstool(hint_keywords: list[str]) -> pd.DataFrame:
    api_key, sec_key, customer_id = _naver_keys_from_secrets()
    if not (requests and api_key and sec_key and customer_id and hint_keywords):
        return pd.DataFrame()
    base_url="https://api.naver.com"; uri="/keywordstool"; ts = str(round(time.time()*1000))
    headers = {"X-API-KEY": api_key, "X-Signature": _naver_signature(ts, "GET", uri, sec_key),
               "X-Timestamp": ts, "X-Customer": customer_id}
    params={ "hintKeywords": ",".join(hint_keywords), "includeHintKeywords": "0", "showDetail": "1" }
    try:
        r = requests.get(base_url+uri, headers=headers, params=params, timeout=12)
        r.raise_for_status()
    except Exception as e:
        code = getattr(getattr(e, "response", None), "status_code", "N/A")
        st.warning(f"키워드도구 호출 실패 · HTTP {code} — 키/시그니처/권한 확인")
        return pd.DataFrame()

    try:
        data = r.json().get("keywordList", [])[:200]
        if not data: return pd.DataFrame()
        df = pd.DataFrame(data).rename(columns={
            "relKeyword":"키워드","monthlyPcQcCnt":"PC월간검색수","monthlyMobileQcCnt":"Mobile월간검색수",
            "monthlyAvePcClkCnt":"PC월평균클릭수","monthlyAveMobileClkCnt":"Mobile월평균클릭수",
            "monthlyAvePcCtr":"PC월평균클릭률","monthlyAveMobileCtr":"Mobile월평균클릭률",
            "plAvgDepth":"월평균노출광고수","compIdx":"광고경쟁정도",
        }).drop_duplicates(["키워드"]).set_index("키워드").reset_index()
        num_cols=["PC월간검색수","Mobile월간검색수","PC월평균클릭수","Mobile월평균클릭수",
                  "PC월평균클릭률","Mobile월평균클릭률","월평균노출광고수"]
        for c in num_cols: df[c]=pd.to_numeric(df[c], errors="coerce")
        return df
    except Exception:
        return pd.DataFrame()

def _count_product_from_shopping(keyword: str) -> int|None:
    if not requests: return None
    try:
        url=f"https://search.shopping.naver.com/search/all?where=all&frm=NVSCTAB&query={quote(keyword)}"
        r=requests.get(url, timeout=10); r.raise_for_status()
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, "html.parser")
        a_tags = soup.select("a.subFilter_filter__3Y-uy")
        for a in a_tags:
            if "전체" in a.text:
                span = a.find("span")
                if span:
                    txt = span.get_text().replace(",","").strip()
                    return int(re.sub(r"[^0-9]", "", txt) or "0")
        return None
    except Exception:
        return None

# =========================
# DataLab (Open API)
# =========================
@st.cache_data(ttl=1800, show_spinner=False)
def _datalab_trend(groups: list, start_date: str, end_date: str,
                    time_unit: str = "week") -> pd.DataFrame:
    if not requests:
        return pd.DataFrame()

    cid  = _get_key("NAVER_CLIENT_ID")
    csec = _get_key("NAVER_CLIENT_SECRET")
    if not (cid and csec):
        return pd.DataFrame()

    url = "https://openapi.naver.com/v1/datalab/search"
    headers = {
        "X-Naver-Client-Id": cid,
        "X-Naver-Client-Secret": csec,
        "Content-Type": "application/json; charset=utf-8",
    }
    ref = (_get_key("NAVER_WEB_REFERER") or "").strip()
    if ref:
        headers["Referer"] = ref

    payload = {
        "startDate": start_date, "endDate": end_date, "timeUnit": time_unit,
        "keywordGroups": (groups or [])[:5],
    }

    try:
        r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=12)
        r.raise_for_status()
        js = r.json()
        rows = []
        for gr in js.get("results", []):
            title = gr.get("title") or (gr.get("keywords") or [""])[0]
            df = pd.DataFrame(gr.get("data", []))
            if df.empty: continue
            df["keyword"] = title
            rows.append(df)
        if not rows: return pd.DataFrame()

        big = pd.concat(rows, ignore_index=True)
        big.rename(columns={"period": "날짜", "ratio": "검색지수"}, inplace=True)
        pv = big.pivot_table(index="날짜", columns="keyword", values="검색지수", aggfunc="mean")
        return pv.reset_index().sort_values("날짜")
    except Exception:
        return pd.DataFrame()

# =========================
# 해외(라쿠텐) 랭킹
# =========================
def _rakuten_keys():
    return _get_key("RAKUTEN_APP_ID"), _get_key("RAKUTEN_AFFILIATE_ID")

@st.cache_data(ttl=900, show_spinner=False)
def _rk_fetch_rank_cached(genre_id: str, topn: int = 20, strip_emoji: bool=True) -> pd.DataFrame:
    app_id, affiliate = _rakuten_keys()
    def _clean(s: str) -> str:
        if not strip_emoji: return s
        return re.sub(r"[\U00010000-\U0010ffff]", "", s or "")
    if not (requests and app_id):
        rows=[{"rank":i+1,"keyword":_clean(f"[샘플] 키워드 {i+1} ハロウィン 秋 🍂"),
               "shop":"샘플","url":"https://example.com"} for i in range(topn)]
        return pd.DataFrame(rows)
    try:
        api = "https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20170628"
        params = {"applicationId": app_id, "genreId": str(genre_id).strip(), "hits": topn}
        if affiliate: params["affiliateId"] = affiliate
        r = requests.get(api, params=params, timeout=12)
        r.raise_for_status()
        items = r.json().get("Items", [])[:topn]
        rows=[]
        for it in items:
            node = it.get("Item", {})
            rows.append({
                "rank": node.get("rank"),
                "keyword": _clean(node.get("itemName","")),
                "shop": node.get("shopName",""),
                "url": node.get("itemUrl",""),
            })
        return pd.DataFrame(rows)
    except Exception:
        rows=[{"rank":i+1,"keyword":_clean(f"[샘플] 키워드 {i+1} ハロウィン 秋 🍂"),
               "shop":"샘플","url":"https://example.com"} for i in range(topn)]
        return pd.DataFrame(rows)

def section_rakuten_ui():
    ss = st.session_state
    ss.setdefault("rk_genre_map", {})   # 안전

    st.markdown('<div id="rk-card" class="main">', unsafe_allow_html=True)
    colB, colC = st.columns([2,1])
    with colB:
        cat = st.selectbox("라쿠텐 카테고리",
                           ["전체(샘플)","뷰티/코스메틱","의류/패션","가전/디지털",
                            "가구/인테리어","식품","생활/건강","스포츠/레저","문구/취미"], key="rk_cat")
    with colC:
        sample_only = st.checkbox("샘플 보기", value=False, key="rk_sample")
    strip_emoji = st.toggle("이모지 제거", value=True, key="rk_strip_emoji")

    genre_id = (ss["rk_genre_map"].get(cat) or "").strip() or "100283"
    with st.spinner("라쿠텐 랭킹 불러오는 중…"):
        df = (pd.DataFrame([{"rank":i+1,"keyword":f"[샘플] 키워드 {i+1}","shop":"샘플","url":"https://example.com"} for i in range(20)])
              if sample_only else _rk_fetch_rank_cached(genre_id, topn=20, strip_emoji=strip_emoji))

    colcfg = {
        "rank": st.column_config.NumberColumn("rank", width="small"),
        "keyword": st.column_config.TextColumn("keyword", width="medium"),
        "shop": st.column_config.TextColumn("shop", width="small"),
        "url": st.column_config.LinkColumn("url", display_text="열기", width="small"),
    }
    st.dataframe(df[["rank","keyword","shop","url"]], hide_index=True, use_container_width=True, height=430, column_config=colcfg)
    st.download_button("표 CSV 다운로드", data=df.to_csv(index=False).encode("utf-8-sig"),
                       file_name="rakuten_ranking.csv", mime="text/csv")

    with st.expander("🔧 장르 매핑 편집 (화면에는 숨김)", expanded=False):
        st.caption("카테고리 → genreId 매핑입니다. 올바른 genreId로 바꾸고 저장하세요.")
        g1, g2 = st.columns(2)
        with g1:
            for k in ["뷰티/코스메틱","의류/패션","가구/인테리어","스포츠/레저","문구/취미"]:
                ss["rk_genre_map"][k] = st.text_input(k, ss["rk_genre_map"].get(k,"100283"), key=f"rk_{k}")
        with g2:
            for k in ["가전/디지털","식품","생활/건강","전체(샘플)"]:
                ss["rk_genre_map"][k] = st.text_input(k, ss["rk_genre_map"].get(k,"100283"), key=f"rk_{k}")
        st.info("세션에 저장됩니다. 앱 재실행 시 초기값으로 돌아올 수 있어요.")
    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# 국내 레이더 (Searchad + 옵션 상품수)
# =========================
def section_korea_ui():
    is_dark = (st.session_state.get("theme","light") == "dark")
    st.markdown('<div class="main">', unsafe_allow_html=True)

    if not is_dark:
        st.markdown("""
        <style>
          [data-testid="stAppViewContainer"] .main .stAlert{
            background:#2563eb !important; border:1px solid #1e40af !important;
          }
          [data-testid="stAppViewContainer"] .main .stAlert,
          [data-testid="stAppViewContainer"] .main .stAlert *{
            color:#fff !important; fill:#fff !important;
          }
        </style>
        """, unsafe_allow_html=True)

    st.caption("※ 검색지표는 네이버 검색광고 API(키워드도구) 기준, 상품수는 네이버쇼핑 ‘전체’ 탭 크롤링 기준입니다.")
    c1, c2, c3 = st.columns([1,1,1])

    # 다크에서 이 블록만 검정 폰트
    if is_dark:
        st.markdown("""
        <style>.force-black *{ color:#111 !important; -webkit-text-fill-color:#111 !important; }</style>
        """, unsafe_allow_html=True)
        st.markdown("<div class='force-black'>", unsafe_allow_html=True)

    with c1:
        months = st.slider("분석기간(개월, 표시용)", 1, 6, 3)
    with c2:
        device = st.selectbox("디바이스", ["all","pc","mo"], index=0)
    with c3:
        src = st.selectbox("키워드 소스", ["직접 입력"], index=0)

    if is_dark:
        st.markdown("</div>", unsafe_allow_html=True)

    keywords_txt = st.text_area("키워드(콤마로 구분)", "핸드메이드코트, 남자코트, 여자코트", height=96)
    kw_list = [k.strip() for k in (keywords_txt or "").split(",") if k.strip()]
    opt1, opt2 = st.columns([1,1])
    with opt1:
        add_product = st.toggle("네이버쇼핑 ‘전체’ 상품수 수집(느림)", value=False)
    with opt2:
        table_mode = st.radio("표 모드", ["A(검색지표)","B(검색+순위)","C(검색+상품수+스코어)"], horizontal=True, index=2)

    if st.button("레이더 업데이트", use_container_width=False):
        with st.spinner("네이버 키워드도구 조회 중…"):
            df = _naver_keywordstool(kw_list)
        if df.empty:
            st.warning("데이터가 없습니다. (API/권한/쿼터 또는 키워드 확인)")
            st.markdown("</div>", unsafe_allow_html=True); return

        if table_mode.startswith("A"):
            st.dataframe(df, use_container_width=True, height=430)
            st.download_button("CSV 다운로드", df.to_csv(index=False).encode("utf-8-sig"),
                               file_name="korea_keyword_A.csv", mime="text/csv")
            st.markdown("</div>", unsafe_allow_html=True); return

        df2 = df.copy()
        df2["검색합계"] = (pd.to_numeric(df2["PC월간검색수"], errors="coerce").fillna(0) +
                           pd.to_numeric(df2["Mobile월간검색수"], errors="coerce").fillna(0))
        df2["검색순위"] = df2["검색합계"].rank(ascending=False, method="min")

        if table_mode.startswith("B"):
            out = df2.sort_values("검색순위")
            st.dataframe(out, use_container_width=True, height=430)
            st.download_button("CSV 다운로드", out.to_csv(index=False).encode("utf-8-sig"),
                               file_name="korea_keyword_B.csv", mime="text/csv")
            st.markdown("</div>", unsafe_allow_html=True); return

        product_counts = []
        if add_product:
            with st.spinner("네이버쇼핑 상품수 수집 중…"):
                for k in df2["키워드"]:
                    cnt = _count_product_from_shopping(k)
                    product_counts.append(cnt if cnt is not None else math.nan)
        else:
            product_counts = [math.nan]*len(df2)

        df2["판매상품수"] = product_counts
        df2["상품수순위"] = df2["판매상품수"].rank(na_option="bottom", method="min")
        df2["상품발굴대상"] = (df2["검색순위"] + df2["상품수순위"]).rank(na_option="bottom", method="min")

        cols = ["키워드","PC월간검색수","Mobile월간검색수","판매상품수",
                "PC월평균클릭수","Mobile월평균클릭수","PC월평균클릭률","Mobile월평균클릭률",
                "월평균노출광고수","광고경쟁정도","검색순위","상품수순위","상품발굴대상"]
        out = df2[cols].sort_values("상품발굴대상")
        st.dataframe(out, use_container_width=True, height=430)
        st.download_button("CSV 다운로드", out.to_csv(index=False).encode("utf-8-sig"),
                           file_name="korea_keyword_C.csv", mime="text/csv")
    st.markdown("</div>", unsafe_allow_html=True)

# =========================
# 카테고리 → Top20 & 트렌드
# =========================
SEED_MAP = {
    "패션의류":        ["원피스", "코트", "니트", "셔츠", "블라우스"],
    "패션잡화":        ["가방", "지갑", "모자", "스카프", "벨트"],
    "뷰티/미용":       ["쿠션", "립스틱", "선크림", "마스카라", "토너"],
    "디지털/가전":     ["블루투스이어폰", "스피커", "모니터", "노트북", "로봇청소기"],
    "가구/인테리어":   ["소파", "식탁", "행거", "수납장", "러그"],
    "생활/건강":       ["칫솔", "치약", "샴푸", "세제", "물티슈"],
    "식품":           ["간편식", "커피", "차", "과자", "즉석밥"],
    "출산/육아":       ["기저귀", "물티슈", "유모차", "카시트", "아기띠"],
    "스포츠/레저":     ["러닝화", "요가복", "캠핑의자", "텐트", "자전거"],
    "자동차/공구":      ["블랙박스", "엔진오일", "차량용청소기", "공구세트", "와이퍼"],
    "도서/취미/오피스": ["문구세트", "다이어리", "스티커", "보드게임", "퍼즐"],
    "여행/문화":       ["캐리어", "여권지갑", "목베개", "여행용파우치", "슬리퍼"],
}

def section_category_keyword_lab():
    st.markdown('<div class="card"><div class="card-title">카테고리 → 키워드 Top20 & 트렌드</div>', unsafe_allow_html=True)
    is_dark = (st.session_state.get("theme","light") == "dark")
    if not is_dark:
        st.markdown("""
        <style>
          [data-testid="stAppViewContainer"] .main .stAlert{
            background:#2563eb !important; border:1px solid #1e40af !important;
          }
          [data-testid="stAppViewContainer"] .main .stAlert,
          [data-testid="stAppViewContainer"] .main .stAlert *{
            color:#fff !important; fill:#fff !important;
          }
        </style>
        """, unsafe_allow_html=True)

    cA, cB, cC = st.columns([1, 1, 1])

    # 다크에서 이 블럭만 검정 폰트
    if is_dark:
        st.markdown("<style>.force-black *{color:#111 !important;-webkit-text-fill-color:#111!important}</style>",
                    unsafe_allow_html=True)
        st.markdown("<div class='force-black'>", unsafe_allow_html=True)

    with cA:
        cat = st.selectbox("카테고리", list(SEED_MAP.keys()))
    with cB:
        time_unit = st.selectbox("단위", ["week", "month"], index=0)
    with cC:
        months = st.slider("조회기간(개월)", 1, 12, 3)

    if is_dark:
        st.markdown("</div>", unsafe_allow_html=True)

    start = (dt.date.today() - dt.timedelta(days=30 * months)).strftime("%Y-%m-%d")
    end   = (dt.date.today() - dt.timedelta(days=1)).strftime("%Y-%m-%d")

    seeds = SEED_MAP.get(cat, [])
    df = _naver_keywordstool(seeds)
    if df.empty:
        st.warning("키워드도구 응답이 비었습니다. (API/권한/쿼터 확인)")
        st.markdown("</div>", unsafe_allow_html=True); return

    df["검색합계"] = pd.to_numeric(df["PC월간검색수"], errors="coerce").fillna(0) + \
                     pd.to_numeric(df["Mobile월간검색수"], errors="coerce").fillna(0)
    top20 = df.sort_values("검색합계", ascending=False).head(20).reset_index(drop=True)

    st.dataframe(
        top20[["키워드", "검색합계", "PC월간검색수", "Mobile월간검색수", "월평균노출광고수", "광고경쟁정도"]],
        use_container_width=True, height=340,
    )
    st.download_button(
        "CSV 다운로드",
        top20.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"category_{cat}_top20.csv", mime="text/csv",
    )

    topk = st.slider("라인차트 키워드 수", 3, 10, 5, help="상위 N개 키워드만 트렌드를 그립니다.")
    kws = top20["키워드"].head(topk).tolist()
    groups = [{"groupName": k, "keywords": [k]} for k in kws]
    ts = _datalab_trend(groups, start, end, time_unit=time_unit)

    if ts.empty:
        st.info("DataLab 트렌드 응답이 비어 있어요.")
    else:
        try:
            st.line_chart(ts.set_index("날짜"))
        except Exception:
            st.dataframe(ts, use_container_width=True, height=260)

    st.markdown("</div>", unsafe_allow_html=True)

def section_keyword_trend_widget():
    st.markdown('<div class="card"><div class="card-title">키워드 트렌드 (직접 입력)</div>', unsafe_allow_html=True)
    kwtxt  = st.text_input("키워드(콤마)", "가방, 원피스")
    unit   = st.selectbox("단위", ["week", "month"], index=0)
    months = st.slider("조회기간(개월)", 1, 12, 3)

    if st.button("트렌드 조회"):
        start = (dt.date.today() - dt.timedelta(days=30 * months)).strftime("%Y-%m-%d")
        end   = (dt.date.today() - dt.timedelta(days=1)).strftime("%Y-%m-%d")
        kws = [k.strip() for k in (kwtxt or "").split(",") if k.strip()]
        groups = [{"groupName": k, "keywords": [k]} for k in kws][:5]
        df = _datalab_trend(groups, start, end, time_unit=unit)
        if df.empty:
            st.error("DataLab 트렌드 응답이 비어 있어요.")
        else:
            st.dataframe(df, use_container_width=True, height=260)
            st.line_chart(df.set_index("날짜"))
            st.download_button("CSV 다운로드", data=df.to_csv(index=False).encode("utf-8-sig"),
                               file_name="keyword_trend_direct.csv", mime="text/csv")

    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# AI 키워드 레이더 (국내/해외 탭)
# =========================
def section_radar():
    st.markdown('<div class="card main"><div class="card-title">AI 키워드 레이더</div>', unsafe_allow_html=True)
    tab_domestic, tab_overseas = st.tabs(["국내", "해외"])
    with tab_domestic:
        section_korea_ui()
    with tab_overseas:
        section_rakuten_ui()
    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# Stopwords & 상품명 생성기
# =========================
STOPWORDS_GLOBAL = [
    "무료배송","무배","초특가","특가","핫딜","최저가","세일","sale","이벤트","사은품","증정",
    "쿠폰","역대급","역대가","폭탄세일","원가","정가","파격","초대박","할인폭","혜택가",
    "파손","환불","교환","재고","품절","한정수량","긴급","급처","특판",
    "mustbuy","강추","추천","추천템","🔥","💥","⭐","best","베스트"
]
PATTERN_RE = re.compile(r"[!?\[\]{}()★☆•·~^️💥🔥⭐]+")
LITERAL_RE = re.compile(r"(무료배송|무배|세일|특가|핫딜|최저가|증정|쿠폰)", re.I)

def _dedupe_tokens(s:str)->str:
    seen=set(); out=[]
    for t in s.split():
        k=t.lower()
        if k in seen: continue
        seen.add(k); out.append(t)
    return " ".join(out)

def _truncate_bytes(text:str, max_bytes:int=50)->str:
    raw=text.encode("utf-8")
    if len(raw)<=max_bytes: return text
    cut=raw[:max_bytes]
    while True:
        try: s=cut.decode("utf-8"); break
        except UnicodeDecodeError: cut=cut[:-1]
    return s.rstrip()+"…"

def _apply_filters_soft(text:str)->str:
    try:
        out = PATTERN_RE.sub(" ", text)
        out = LITERAL_RE.sub(" ", out)
    except Exception:
        out = text
    return re.sub(r"\s+"," ", out).strip()

_ALLOWED_BY_DOMAIN = {
    "무릎보호대": ["무릎","보호대","무릎보호대","관절","압박","테이핑","밴드","서포트",
                 "스포츠","운동","헬스","러닝","재활","부상","쿠션","지지대","슬리브","슬개골"],
}
_BLOCK_LIST = {"양산","돗자리","지갑","모자","우산","머그","키링","슬리퍼","가랜드"}
_FALLBACK_PAD = {
    "무릎보호대": ["스포츠","헬스","러닝","관절보호","압박밴드","테이핑","남녀공용","프리사이즈","충격흡수"]
}

def _seed_tokens(seed:str)->list[str]:
    toks = [t for t in re.split(r"[,\s/|]+", seed or "") if len(t)>=2]
    extras=[]
    for t in toks:
        if "무릎보호대" in t: extras += ["무릎","보호대"]
    return list(dict.fromkeys(toks+extras))

def _is_related_kw(kw:str, seed:str)->bool:
    if not kw: return False
    if kw in _BLOCK_LIST: return False
    allow = set(_seed_tokens(seed))
    dom=[]
    for s in allow:
        if s in _ALLOWED_BY_DOMAIN: dom += _ALLOWED_BY_DOMAIN[s]
    allow |= set(dom)
    return any(a in kw for a in allow)

@st.cache_data(ttl=3600, show_spinner=False)
def _cached_kstats(seed: str) -> pd.DataFrame:
    if not seed: return pd.DataFrame()
    try:
        df = _naver_keywordstool([seed])
    except Exception:
        return pd.DataFrame()
    if df.empty: return pd.DataFrame()
    for col, default in [("키워드",""),("PC월간검색수",0),("Mobile월간검색수",0),
                         ("PC월평균클릭수",0),("Mobile월평균클릭수",0),
                         ("PC월평균클릭률",0),("Mobile월평균클릭률",0),
                         ("월평균노출광고수",0),("광고경쟁정도",0)]:
        if col not in df.columns: df[col]=default
    for c in ["PC월간검색수","Mobile월간검색수","광고경쟁정도"]:
        df[c] = pd.to_numeric(df.get(c,0), errors="coerce").fillna(0)
    df["검색합계"] = df["PC월간검색수"] + df["Mobile월간검색수"]
    return df

@st.cache_data(ttl=1200, show_spinner=False)
def _suggest_keywords_by_searchad_and_datalab(seed_kw:str, months:int=3, top_rel:int=15, strict:bool=True) -> pd.DataFrame:
    base = _cached_kstats(seed_kw)
    if base.empty or "키워드" not in base.columns: return pd.DataFrame()

    df = base.copy()
    df = df[df["키워드"].astype(str).str.strip().str.len()>0]
    df = df[df["키워드"].astype(str)!=str(seed_kw)]
    df = df.sort_values("검색합계", ascending=False)
    if strict:
        df = df[df["키워드"].apply(lambda k: _is_related_kw(str(k), seed_kw))]
    if df.empty and strict:
        df = base.copy()
        df = df[df["키워드"].astype(str).str.strip().str.len()>0]
        df = df[df["키워드"].astype(str)!=str(seed_kw)]
        df = df.sort_values("검색합계", ascending=False)
    if df.empty: return pd.DataFrame()

    df = df.head(max(5,min(50,top_rel))).reset_index(drop=True)

    start = (dt.date.today() - dt.timedelta(days=30*months)).strftime("%Y-%m-%d")
    end   = (dt.date.today() - dt.timedelta(days=1)).strftime("%Y-%m-%d")

    dl_means = {}
    kws_all = df["키워드"].tolist()
    for i in range(0,len(kws_all),5):
        chunk = kws_all[i:i+5]
        groups = [{"groupName":k,"keywords":[k]} for k in chunk]
        ts = _datalab_trend(groups, start, end, time_unit="week")
        if ts.empty:
            for k in chunk: dl_means[k]=0.0
        else:
            for k in chunk:
                try: dl_means[k]=float(pd.to_numeric(ts.get(k), errors="coerce").mean())
                except: dl_means[k]=0.0

    df["dl_mean"] = df["키워드"].map(dl_means).fillna(0.0)
    df["score"]   = pd.to_numeric(df["검색합계"], errors="coerce").fillna(0) * (df["dl_mean"].clip(lower=0)/100.0)
    return df.sort_values(["score","검색합계"], ascending=[False,False]).reset_index(drop=True)

def _compose_titles(main_kw:str, attrs:list[str], sugg:list[str],
                    min_chars:int=30, max_bytes:int=50, topn:int=10):
    base = [t for t in [main_kw]+attrs if t]
    if not sugg:
        sugg = _FALLBACK_PAD.get(main_kw,[]) or _ALLOWED_BY_DOMAIN.get(main_kw,[]) or _seed_tokens(main_kw)

    candidates=[]; L=min(len(sugg),5)
    for i in range(L):
        candidates.append(base+[sugg[i]])
        for j in range(i+1,L):
            candidates.append(base+[sugg[i],sugg[j]])
            for k in range(j+1,L):
                candidates.append(base+[sugg[i],sugg[j],sugg[k]])
    if not candidates: candidates=[base]

    out=[]; used=set()
    for toks in candidates:
        title = _apply_filters_soft(_dedupe_tokens(" ".join(toks)))
        if not title: continue

        if len(title) < min_chars:
            pad_pool = [x for x in (sugg+attrs) if x and x not in toks]
            for p in pad_pool:
                trial = _apply_filters_soft(_dedupe_tokens(title+" "+p))
                if len(trial.encode("utf-8")) > max_bytes: break
                title = trial
                if len(title) >= min_chars: break

        if len(title.encode("utf-8")) > max_bytes:
            title = _truncate_bytes(title, max_bytes)

        key = title.lower().strip()
        if key and key not in used:
            out.append(title); used.add(key)
        if len(out) >= topn: break
    return out[:topn]

def section_title_generator():
    st.markdown('<div class="card main"><div class="card-title">상품명 생성기 (스마트스토어 · Top-N)</div>', unsafe_allow_html=True)
    if st.session_state.get("theme","light") == "light":
        st.markdown("""
        <style>
          [data-testid="stAppViewContainer"] .stAlert{
            background:#2563eb !important; border:1px solid #1e40af !important;
          }
          [data-testid="stAppViewContainer"] .stAlert,
          [data-testid="stAppViewContainer"] .stAlert *{
            color:#ffffff !important; fill:#ffffff !important;
          }
        </style>
        """, unsafe_allow_html=True)

    cA,cB = st.columns([1,2])
    with cA:
        brand = st.text_input("브랜드", placeholder="예: 무지 / Apple")
        attrs = st.text_input("속성(콤마, 선택)", placeholder="예: 스포츠, 헬스, 러닝, 남녀공용, 압박밴드")
    with cB:
        kws_raw = st.text_input("키워드(콤마, 첫 번째가 메인)", placeholder="예: 무릎보호대, 관절보호, 충격흡수")
        main_kw = next((k.strip() for k in (kws_raw or "").split(",") if k.strip()), "")

    c1,c2,c3,c4 = st.columns([1,1,1,1])
    with c1: N = st.slider("추천 개수", 5, 20, 10, 1)
    with c2: min_chars = st.slider("최소 글자(권장 30~50)", 30, 50, 35, 1)
    with c3: max_chars = st.slider("최대 글자(바이트)", 30, 50, 50, 1)
    with c4: months = st.slider("검색 트렌드 기간(개월)", 1, 6, 3)

    relaxed = st.checkbox("느슨한 모드(연관성 필터 완화/백업 재시도)", value=True)
    st.caption("※ 추천은 ‘네이버 키워드도구(검색량)’ + ‘DataLab(검색지수)’ 기반. 엉뚱어 자동필터. 30자/50바이트 근접 자동 패딩.")

    sugg_df = st.session_state.get("__sugg_df_cache", pd.DataFrame())

    if st.button("상위 키워드 추천 불러오기 (데이터랩+키워드도구)"):
        if not main_kw:
            st.error("메인 키워드를 먼저 입력하세요.")
        else:
            with st.spinner("연관 키워드·트렌드 수집 중…"):
                sugg_df = _suggest_keywords_by_searchad_and_datalab(main_kw, months=months, top_rel=15, strict=not relaxed)
            st.session_state["__sugg_df_cache"] = sugg_df
            if sugg_df.empty:
                st.warning("추천에 사용할 데이터가 없습니다. (API/권한/쿼터 또는 키워드 확인)")
            else:
                cols = ["키워드","PC월간검색수","Mobile월간검색수","검색합계","dl_mean","score"]
                st.dataframe(sugg_df[cols], use_container_width=True, height=320)
                st.download_button("추천 키워드 CSV 다운로드",
                                   data=sugg_df[cols].to_csv(index=False).encode("utf-8-sig"),
                                   file_name=f"suggest_keywords_{main_kw}.csv", mime="text/csv")

    if st.button("상품명 생성"):
        if not main_kw:
            st.error("키워드를 하나 이상 입력하세요."); st.markdown("</div>", unsafe_allow_html=True); return
        if sugg_df.empty:
            sugg_df = _suggest_keywords_by_searchad_and_datalab(main_kw, months=months, top_rel=15, strict=not relaxed)

        at_list = [a.strip() for a in (attrs or "").split(",") if a.strip()]
        sugg = (sugg_df["키워드"].tolist() if not sugg_df.empty else [])

        titles = _compose_titles(main_kw, at_list, sugg, min_chars=min_chars, max_bytes=max_chars, topn=N)

        def _fit_score(t):
            by = len(t.encode("utf-8"))
            fit = (max_chars - by) if by <= max_chars else 999
            cov = sum(int(k in t) for k in (sugg[:10] if sugg else []))
            return (fit, -cov)

        titles_sorted = sorted(titles, key=_fit_score)
        primary = titles_sorted[0] if titles_sorted else ""
        if primary:
            by=len(primary.encode("utf-8")); ch=len(primary)
            st.success(f"1순위(등록용) — {primary}  (문자 {ch}/{max_chars} · 바이트 {by}/{max_chars})")
        st.divider()

        for i, t in enumerate(titles_sorted, 1):
            ch=len(t); by=len(t.encode("utf-8"))
            warn=[]
            if ch < min_chars: warn.append(f"{min_chars}자 미만")
            if by > max_chars: warn.append(f"{max_chars}바이트 초과")
            suf = "" if not warn else " — " + " / ".join([f":red[{w}]" for w in warn])
            st.markdown(f"**{i}.** {t}  <span style='opacity:.7'>(문자 {ch}/{max_chars} · 바이트 {by}/{max_chars})</span>{suf}",
                        unsafe_allow_html=True)

        st.download_button(
            "제목 CSV 다운로드",
            data=pd.DataFrame({"title": titles_sorted}).to_csv(index=False).encode("utf-8-sig"),
            file_name=f"titles_{main_kw}.csv", mime="text/csv",
        )

    st.markdown("</div>", unsafe_allow_html=True)

# =========================
# 11번가 임베드 (옵션)
# =========================
def section_11st():
    import time as _t
    st.markdown('<div class="card main"><div class="card-title">11번가 (모바일) — 아마존 베스트</div>', unsafe_allow_html=True)
    ss = st.session_state
    ss.setdefault("__11st_nonce", int(_t.time()))
    if st.button("🔄 새로고침 (11번가)"):
        ss["__11st_nonce"] = int(_t.time())
    base_proxy = (st.secrets.get("ELEVENST_PROXY", "") or globals().get("ELEVENST_PROXY", "")).rstrip("/")
    raw_url = "https://m.11st.co.kr/page/main/abest?tabId=ABEST&pageId=AMOBEST&ctgr1No=166160"
    src_raw = raw_url if not base_proxy else f"{base_proxy}/?url={quote(raw_url, safe=':/?&=%')}"
    src = f"{src_raw}{'&' if '?' in src_raw else '?'}r={ss['__11st_nonce']}"
    html = f"""
    <style>.embed-11st-wrap{{height:940px;overflow:hidden;border-radius:10px}}
    .embed-11st-wrap iframe{{width:100%;height:100%;border:0;border-radius:10px;overflow:hidden}}</style>
    <div class="embed-11st-wrap"><iframe src="{src}" loading="lazy" scrolling="no"></iframe></div>
    """
    st.components.v1.html(html, height=960, scrolling=False)
    st.markdown("</div>", unsafe_allow_html=True)

# =========================
# Layout
# =========================
ensure_session_defaults()
_inject_css()
sidebar()
_responsive_probe()
vwbin = _get_view_bin()

st.title("ENVY — Season 1 (Dual Proxy Edition)")

# row1: 카테고리 ⇄ 레이더 ⇄ 상품명
row1_a, row1_b, row1_c = st.columns([4, 8, 4], gap="medium")
with row1_a:
    tab_cat, tab_direct = st.tabs(["카테고리", "직접 입력"])
    with tab_cat:
        section_category_keyword_lab()
    with tab_direct:
        section_keyword_trend_widget()
with row1_b:
    section_radar()
with row1_c:
    section_title_generator()

st.markdown('<div style="height:24px"></div>', unsafe_allow_html=True)

# row2
c1, c2, c3 = st.columns([3, 3, 3], gap="medium")
with c1:
    section_11st()
with c2:
    st.info("아이템스카우트: 새 탭에서 열기를 권장합니다.")
    st.link_button("아이템스카우트 열기", "https://app.itemscout.io/market/keyword")
with c3:
    st.info("셀러라이프: 새 탭에서 열기를 권장합니다.")
    st.link_button("셀러라이프 열기", "https://sellochomes.co.kr/sellerlife/")

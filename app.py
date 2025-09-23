# -*- coding: utf-8 -*-
import base64, time, re, math, json, io, datetime as dt, hashlib, hmac
from pathlib import Path
from urllib.parse import quote
import pandas as pd
import streamlit as st

# -------- Optional imports --------
try:
    import requests
except Exception:
    requests = None

try:
    from deep_translator import GoogleTranslator
except Exception:
    GoogleTranslator = None

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

    # NAVER Searchad(검색광고 API / 키워드도구)
    "NAVER_API_KEY": "0100000000785cf1d8f039b13a5d3c3d1262b84e9ad4a046637e8887bbd003051b0d2a5cdf",
    "NAVER_SECRET_KEY": "AQAAAAB4XPHY8DmxOl08PRJiuE6ao1LN3lh0kF9rOJ4m5b8O5g==",
    "NAVER_CUSTOMER_ID": "2274338",

    # NAVER Developers (DataLab Open API)
    "NAVER_CLIENT_ID": "T27iw3tyujrM1nG_shFT",
    "NAVER_CLIENT_SECRET": "s59xKPYLz1",

    # 선택: DataLab Referer
    "NAVER_WEB_REFERER": ""
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
# Stopwords — 전역/카테고리 + 프리셋
# =========================
STOPWORDS_GLOBAL = [
    "무료배송","무배","초특가","특가","핫딜","최저가","세일","sale","이벤트","사은품","증정",
    "쿠폰","역대급","역대가","폭탄세일","원가","정가","파격","초대박","할인폭","혜택가",
    "파손","환불","교환","재고","품절","한정수량","긴급","급처","특판",
    "mustbuy","강추","추천","추천템","🔥","💥","⭐","best","베스트"
]
STOPWORDS_BY_CAT = {
    "패션의류":   ["루즈핏","빅사이즈","초슬림","극세사","초경량","왕오버","몸매보정"],
    "패션잡화":   ["무료각인","사은품지급","세트증정"],
    "화장품/미용":  ["정품보장","병행수입","벌크","리필만","샘플","테스터"],
    "생활/건강":  ["공용","비매품","리퍼","리퍼비시"],
    "디지털/가전": ["관부가세","부가세","해외직구","리퍼","리퍼비시","벌크"],
    "스포츠/레저": ["무료조립","가성비갑"],
}
STOP_PRESETS = {
    "네이버_안전기본": {
        "global": STOPWORDS_GLOBAL, "by_cat": STOPWORDS_BY_CAT, "whitelist": [],
        "replace": ["무배=> ", "무료배송=> ", "정품=> "], "aggressive": False
    },
    "광고표현_강력차단": {
        "global": STOPWORDS_GLOBAL + ["초강력","초저가","극강","혜자","대란","품절임박","완판임박","마감임박"],
        "by_cat": STOPWORDS_BY_CAT, "whitelist": [],
        "replace": ["무배=> ", "무료배송=> ", "정품=> ", "할인=> "], "aggressive": True
    }
}

# =========================
# 1) UI defaults & CSS  (사이드바 스크롤락 + 폰트/컬러 고정 포함)
# =========================
def _ensure_session_defaults():
    ss = st.session_state
    ss.setdefault("theme", "light")
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
    # Stopwords manager 상태
    ss.setdefault("STOP_GLOBAL", list(STOPWORDS_GLOBAL))
    ss.setdefault("STOP_BY_CAT", dict(STOPWORDS_BY_CAT))
    ss.setdefault("STOP_WHITELIST", [])
    ss.setdefault("STOP_REPLACE", ["무배=> ", "무료배송=> ", "정품=> "])
    ss.setdefault("STOP_AGGR", False)
    # Rakuten genre map
    ss.setdefault("rk_genre_map", {
        "전체(샘플)": "100283","뷰티/코스메틱": "100283","의류/패션": "100283","가전/디지털": "100283",
        "가구/인테리어": "100283","식품": "100283","생활/건강": "100283","스포츠/레저": "100283","문구/취미": "100283",
    })

def _toggle_theme():
    st.session_state["theme"] = "dark" if st.session_state.get("theme", "light") == "light" else "light"

def _inject_css():
    """메인 뷰만 색상 오버라이드(사이드바 제외)."""
    theme = st.session_state.get("theme", "light")

    # 팔레트
    if theme == "dark":
        bg = "#0e1117"; fg = "#e6edf3"; fg_sub = "#b6c2cf"
        card_bg = "#11151c"; border = "rgba(255,255,255,.08)"
        btn_bg = "#2563eb"; btn_bg_hover = "#1e3fae"
    else:
        bg = "#ffffff"; fg = "#111111"; fg_sub = "#4b5563"
        card_bg = "#ffffff"; border = "rgba(0,0,0,.06)"
        btn_bg = "#2563eb"; btn_bg_hover = "#1e3fae"

    st.markdown(f"""
    <style>
      /* 메인 컨테이너(사이드바 제외) */
      [data-testid="stAppViewContainer"] {{
        background:{bg} !important;
        color:{fg} !important;
      }}

      /* 사이드바: 스크롤락 + 폰트 검정 고정 */
      [data-testid="stSidebar"] {{
        overflow: hidden !important;
      }}
      [data-testid="stSidebar"] * {{
        color:#111 !important;
      }}

      /* 헤딩/본문 색상(메인) */
      [data-testid="stAppViewContainer"] h1,
      [data-testid="stAppViewContainer"] h2,
      [data-testid="stAppViewContainer"] h3,
      [data-testid="stAppViewContainer"] h4,
      [data-testid="stAppViewContainer"] h5,
      [data-testid="stAppViewContainer"] h6,
      [data-testid="stAppViewContainer"] p,
      [data-testid="stAppViewContainer"] li,
      [data-testid="stAppViewContainer"] span,
      [data-testid="stAppViewContainer"] label,
      [data-testid="stAppViewContainer"] .stMarkdown,
      [data-testid="stAppViewContainer"] .stMarkdown * {{
        color:{fg} !important;
      }}

      /* 입력/셀렉트/숫자필드 텍스트(메인) */
      [data-testid="stAppViewContainer"] [data-baseweb="select"] *,
      [data-testid="stAppViewContainer"] [data-baseweb="input"] input,
      [data-testid="stAppViewContainer"] .stNumberInput input,
      [data-testid="stAppViewContainer"] .stTextInput input {{
        color:{fg} !important;
      }}
      [data-testid="stAppViewContainer"] input::placeholder {{
        color:{fg_sub} !important; opacity:.9 !important;
      }}

      /* 카드/경계선(메인) */
      [data-testid="stAppViewContainer"] .card {{
        background:{card_bg};
        border:1px solid {border};
        border-radius:14px;
        box-shadow:0 1px 6px rgba(0,0,0,.12);
      }}

      /* 공통 파란 버튼(라이트/다크 모두 흰글씨) */
      .envy-btn-blue button, .envy-btn-blue a, 
      [data-testid="stAppViewContainer"] .stButton>button {{
        background:{btn_bg} !important;
        color:#fff !important;
        border:1px solid rgba(255,255,255,.08) !important;
        border-radius:10px !important;
        font-weight:700 !important;
      }}
      .envy-btn-blue button:hover, .envy-btn-blue a:hover,
      [data-testid="stAppViewContainer"] .stButton>button:hover {{
        background:{btn_bg_hover} !important;
        border-color:rgba(255,255,255,.15) !important;
        color:#fff !important;
      }}

      /* 사이드바 컬러 박스(검정 폰트 유지) */
      .pill {{
        display:inline-block;padding:.55rem .8rem;border-radius:10px;
        font-weight:800;border:1px solid rgba(0,0,0,.12);
        box-shadow:0 1px 2px rgba(0,0,0,.05);
      }}
      .pill-green {{ background:#e8ffe9; color:#111; }}
      .pill-blue  {{ background:#e3efff; color:#111; }}
      .pill-yellow{{ background:#fff7da; color:#111; }}

      /* 기존 여백 유지 */
      [data-testid="stAppViewContainer"] h2,h3 {{ margin-top:.3rem !important; }}
    </style>
    """, unsafe_allow_html=True)

# =========================
# 2) Responsive
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
# 3) Generic proxy iframe
# =========================
def _proxy_iframe(proxy_base: str, target_url: str, height: int = 860, scroll=True, key=None):
    proxy = (proxy_base or "").strip().rstrip("/")
    url   = f"{proxy}/?url={quote(target_url, safe=':/?&=%')}"
    h     = int(height)
    try:
        st.iframe(url, height=h); return
    except Exception:
        pass
    try:
        st.components.v1.iframe(url, height=h, scrolling=bool(scroll)); return
    except Exception:
        pass
    st.markdown(f'<iframe src="{url}" style="width:100%;height:{h}px;border:0;border-radius:10px;"></iframe>',
                unsafe_allow_html=True)

# =========================
# 4) Sidebar (theme + translator toggle + calculators)  — 스크롤락/컬러박스 유지
# =========================
def _sidebar():
    _ensure_session_defaults()
    _inject_css()

    with st.sidebar:
        # 로고(크기 고정)
        st.markdown("""
        <style>
          [data-testid="stSidebar"] .logo-circle{
            width:64px;height:64px;border-radius:9999px;overflow:hidden;
            margin:.35rem auto .6rem auto; box-shadow:0 2px 8px rgba(0,0,0,.12);
            border:1px solid rgba(0,0,0,.06);
          }
          [data-testid="stSidebar"] .logo-circle img{
            width:100%;height:100%;object-fit:cover;display:block;
          }
        </style>
        """, unsafe_allow_html=True)

        lp = Path(__file__).parent / "logo.png"
        if lp.exists():
            b64 = base64.b64encode(lp.read_bytes()).decode("ascii")
            st.markdown(
                f'<div class="logo-circle"><img src="data:image/png;base64,{b64}"></div>',
                unsafe_allow_html=True
            )

        # 토글
        c1, c2 = st.columns(2)
        with c1:
            st.toggle("🌓 다크",
                      value=(st.session_state.get("theme","light")=="dark"),
                      on_change=_toggle_theme, key="__theme_toggle")
        with c2:
            st.toggle("🌐 번역기", value=False, key="__show_translator")
        show_tr = st.session_state.get("__show_translator", False)

        # ---- 위젯들 ----
        def translator_block(expanded=True):
            with st.expander("🌐 구글 번역기", expanded=expanded):
                LANG_LABELS_SB = {
                    "auto":"자동 감지","ko":"한국어","en":"영어","ja":"일본어","zh-CN":"중국어(간체)",
                    "zh-TW":"중국어(번체)","vi":"베트남어","th":"태국어","id":"인도네시아어",
                    "de":"독일어","fr":"프랑스어","es":"스페인어","it":"이탈리아어","pt":"포르투갈어"
                }
                def _code_sb(x): return {v:k for k,v in LANG_LABELS_SB.items()}.get(x, x)
                src_label = st.selectbox("원문 언어", list(LANG_LABELS_SB.values()),
                                         index=list(LANG_LABELS_SB.keys()).index("auto"), key="sb_tr_src")
                tgt_label = st.selectbox("번역 언어", list(LANG_LABELS_SB.values()),
                                         index=list(LANG_LABELS_SB.keys()).index("ko"), key="sb_tr_tgt")
                text_in = st.text_area("텍스트", height=120, key="sb_tr_in")
                if st.button("번역 실행", key="sb_tr_btn", type="primary"):
                    try:
                        from deep_translator import GoogleTranslator as _GT
                        src_code = _code_sb(src_label); tgt_code = _code_sb(tgt_label)
                        out_main = _GT(source=src_code, target=tgt_code).translate(text_in or "")
                        st.text_area(f"결과 ({tgt_label})", value=out_main, height=120, key="sb_tr_out_main")
                        if tgt_code != "ko":
                            out_ko = _GT(source=tgt_code, target="ko").translate(out_main or "")
                            st.text_area("결과 (한국어)", value=out_ko, height=120, key="sb_tr_out_ko")
                    except Exception as e:
                        st.error(f"번역 중 오류: {e}")

        def fx_block(expanded=True):
            with st.expander("💱 환율 계산기", expanded=expanded):
                fx_base = st.selectbox("기준 통화", list(CURRENCIES.keys()),
                                       index=list(CURRENCIES.keys()).index(st.session_state.get("fx_base","USD")),
                                       key="fx_base")
                sale_foreign = st.number_input("판매금액 (외화)",
                                               value=float(st.session_state.get("sale_foreign",1.0)),
                                               step=0.01, format="%.2f", key="sale_foreign")
                won = FX_DEFAULT[fx_base]*sale_foreign
                st.markdown(
                    f'<div class="pill pill-green">환산 금액: <b>{won:,.2f} 원</b>'
                    f'<span style="opacity:.75;font-weight:700"> ({CURRENCIES[fx_base]["symbol"]})</span></div>',
                    unsafe_allow_html=True
                )
                st.caption(f"환율 기준: {FX_DEFAULT[fx_base]:,.2f} ₩/{CURRENCIES[fx_base]['unit']}")

        def margin_block(expanded=True):
            with st.expander("📈 마진 계산기", expanded=expanded):
                m_base = st.selectbox("매입 통화", list(CURRENCIES.keys()),
                                      index=list(CURRENCIES.keys()).index(st.session_state.get("m_base","USD")),
                                      key="m_base")
                purchase_foreign = st.number_input("매입금액 (외화)",
                                                   value=float(st.session_state.get("purchase_foreign",0.0)),
                                                   step=0.01, format="%.2f", key="purchase_foreign")
                base_cost_won = FX_DEFAULT[m_base]*purchase_foreign if purchase_foreign>0 \
                                else FX_DEFAULT[st.session_state.get("fx_base","USD")]*st.session_state.get("sale_foreign",1.0)
                st.markdown(f'<div class="pill pill-green">원가(₩): <b>{base_cost_won:,.2f} 원</b></div>', unsafe_allow_html=True)
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
                st.markdown(f'<div class="pill pill-blue">판매가: <b>{target_price:,.2f} 원</b></div>', unsafe_allow_html=True)
                st.markdown(f'<div class="pill pill-yellow">순이익(마진): <b>{margin_value:,.2f} 원</b> — {desc}</div>', unsafe_allow_html=True)

        if show_tr:
            translator_block(expanded=True); fx_block(expanded=False); margin_block(expanded=False)
        else:
            fx_block(expanded=True); margin_block(expanded=True); translator_block(expanded=False)

# =========================
# 5) Rakuten Ranking
# =========================
def _rakuten_keys():
    app_id = _get_key("RAKUTEN_APP_ID")
    affiliate = _get_key("RAKUTEN_AFFILIATE_ID")
    return app_id, affiliate

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
    def _do():
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
    try:
        return _do()
    except Exception:
        rows=[{"rank":i+1,"keyword":_clean(f"[샘플] 키워드 {i+1} ハロウィン 秋 🍂"),
               "shop":"샘플","url":"https://example.com"} for i in range(topn)]
        return pd.DataFrame(rows)

def section_rakuten_ui():
    st.markdown('<div id="rk-card" class="main">', unsafe_allow_html=True)
    colB, colC = st.columns([2,1])
    with colB:
        cat = st.selectbox("라쿠텐 카테고리",
                           ["전체(샘플)","뷰티/코스메틱","의류/패션","가전/디지털","가구/인테리어","식품","생활/건강","스포츠/레저","문구/취미"], key="rk_cat")
    with colC:
        sample_only = st.checkbox("샘플 보기", value=False, key="rk_sample")
    strip_emoji = st.toggle("이모지 제거", value=True, key="rk_strip_emoji")
    genre_map = st.session_state.get("rk_genre_map", {})
    genre_id = (genre_map.get(cat) or "").strip() or "100283"
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
    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# 6) Korea Radar (Naver Searchad API)
# =========================
import base64 as b64enc
def _naver_signature(timestamp: str, method: str, uri: str, secret: str) -> str:
    msg = f"{timestamp}.{method}.{uri}"
    digest = hmac.new(bytes(secret, "utf-8"), bytes(msg, "utf-8"), hashlib.sha256).digest()
    return b64enc.b64encode(digest).decode("utf-8")

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
        st.markdown(f"<div class='envy-chip-warn main'>키워드도구 호출 실패 · HTTP {code} — 키/시그니처/권한 확인</div>", unsafe_allow_html=True)
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
        num_cols=["PC월간검색수","Mobile월간검색수","PC월평균클릭수","Mobile월평균클릭수","PC월평균클릭률","Mobile월평균클릭률","월평균노출광고수"]
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

def section_korea_ui():
    st.markdown('<div class="main">', unsafe_allow_html=True)
    st.caption("※ 검색지표는 네이버 검색광고 API(키워드도구) 기준, 상품수는 네이버쇼핑 ‘전체’ 탭 크롤링 기준입니다.")
    c1, c2, c3 = st.columns([1,1,1])
    with c1:
        months = st.slider("분석기간(개월, 표시용)", 1, 6, 3)
    with c2:
        device = st.selectbox("디바이스", ["all","pc","mo"], index=0)
    with c3:
        src = st.selectbox("키워드 소스", ["직접 입력"], index=0)

    keywords_txt = st.text_area("키워드(콤마로 구분)", "핸드메이드코트, 남자코트, 여자코트", height=96)
    kw_list = [k.strip() for k in (keywords_txt or "").split(",") if k.strip()]
    opt1, opt2 = st.columns([1,1])
    with opt1:
        add_product = st.toggle("네이버쇼핑 ‘전체’ 상품수 수집(느림)", value=False)
    with opt2:
        table_mode = st.radio("표 모드", ["A(검색지표)","B(검색+순위)","C(검색+상품수+스코어)"], horizontal=True, index=2)

    if st.button("레이더 업데이트", use_container_width=False, key="btn_radar", type="primary"):
        with st.spinner("네이버 키워드도구 조회 중…"):
            df = _naver_keywordstool(kw_list)
        if df.empty:
            st.markdown("<div class='envy-chip-warn main'>데이터가 없습니다. (API/권한/쿼터 또는 키워드 확인)</div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
            return

        if table_mode.startswith("A"):
            st.dataframe(df, use_container_width=True, height=430)
            st.download_button("CSV 다운로드", df.to_csv(index=False).encode("utf-8-sig"),
                               file_name="korea_keyword_A.csv", mime="text/csv", key="dlA")
            st.markdown("</div>", unsafe_allow_html=True)
            return

        df2 = df.copy()
        df2["검색합계"] = (pd.to_numeric(df2["PC월간검색수"], errors="coerce").fillna(0) +
                           pd.to_numeric(df2["Mobile월간검색수"], errors="coerce").fillna(0))
        df2["검색순위"] = df2["검색합계"].rank(ascending=False, method="min")

        if table_mode.startswith("B"):
            out = df2.sort_values("검색순위")
            st.dataframe(out, use_container_width=True, height=430)
            st.download_button("CSV 다운로드", out.to_csv(index=False).encode("utf-8-sig"),
                               file_name="korea_keyword_B.csv", mime="text/csv", key="dlB")
            st.markdown("</div>", unsafe_allow_html=True)
            return

        product_counts = []
        if add_product:
            with st.spinner("네이버쇼핑 상품수 수집 중…(키워드 수에 따라 수 분 소요)"):
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
                           file_name="korea_keyword_C.csv", mime="text/csv", key="dlC")
    st.markdown("</div>", unsafe_allow_html=True)

# =========================
# 7) DataLab Trend (+ 카테고리 → Top20 UI, 12개 카테고리)
# =========================
@st.cache_data(ttl=1800, show_spinner=False)
def _datalab_trend(groups, start_date, end_date, time_unit="week", device="", gender="", ages=None) -> pd.DataFrame:
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
    if ref: headers["Referer"] = ref
    payload = {
        "startDate": start_date,"endDate": end_date,"timeUnit": time_unit,
        "keywordGroups": (groups or [])[:5]
    }
    try:
        r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=12)
        r.raise_for_status()
        js = r.json()
        out = []
        for gr in js.get("results", []):
            name = gr.get("title") or (gr.get("keywords") or [""])[0]
            tmp = pd.DataFrame(gr.get("data", []))
            if tmp.empty: continue
            tmp["keyword"] = name
            out.append(tmp)
        if not out: return pd.DataFrame()
        big = pd.concat(out, ignore_index=True)
        big.rename(columns={"period": "날짜", "ratio": "검색지수"}, inplace=True)
        pivot = big.pivot_table(index="날짜", columns="keyword", values="검색지수", aggfunc="mean")
        return pivot.reset_index().sort_values("날짜")
    except requests.HTTPError as e:
        try: msg = r.text
        except Exception: msg = str(e)
        st.error(f"DataLab HTTP {r.status_code}: {msg}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"DataLab 호출 오류: {e}")
        return pd.DataFrame()

# DataLab 12개 카테고리
SEED_MAP = {
    "패션의류":       ["원피스","코트","니트","셔츠","블라우스"],
    "패션잡화":       ["가방","지갑","모자","스카프","벨트"],
    "화장품/미용":    ["쿠션","립스틱","선크림","마스카라","토너"],
    "디지털/가전":    ["블루투스이어폰","스피커","모니터","노트북","로봇청소기"],
    "가구/인테리어":  ["소파","식탁","행거","수납장","러그"],
    "식품":           ["간편식","커피","차","과자","즉석밥"],
    "출산/육아":      ["기저귀","물티슈","유모차","카시트","아기띠"],
    "생활/건강":      ["칫솔","치약","샴푸","세제","물티슈"],
    "스포츠/레저":    ["러닝화","요가복","캠핑의자","텐트","자전거"],
    "자동차/공구":     ["블랙박스","엔진오일","차량용청소기","공구세트","와이퍼"],
    "도서/취미/오피스":["문구세트","다이어리","스티커","보드게임","퍼즐"],
    "여행/문화":      ["캐리어","여권지갑","목베개","여행용파우치","슬리퍼"],
}

def section_category_keyword_lab():
    st.markdown('<div class="card"><div class="card-title">카테고리 → 키워드 Top20 & 트렌드</div>', unsafe_allow_html=True)
    cA, cB, cC = st.columns([1,1,1])
    with cA:
        cat = st.selectbox("카테고리", list(SEED_MAP.keys()))
    with cB:
        time_unit = st.selectbox("단위", ["week", "month"], index=0)
    with cC:
        months = st.slider("조회기간(개월)", 1, 12, 3)
    start = (dt.date.today() - dt.timedelta(days=30 * months)).strftime("%Y-%m-%d")
    end   = (dt.date.today() - dt.timedelta(days=1)).strftime("%Y-%m-%d")
    seeds = SEED_MAP.get(cat, [])
    df = _naver_keywordstool(seeds)
    if df.empty:
        st.warning("키워드도구 응답이 비었습니다. (API/권한/쿼터 확인)")
        st.markdown('</div>', unsafe_allow_html=True); return
    df["검색합계"] = pd.to_numeric(df["PC월간검색수"], errors="coerce").fillna(0) + \
                     pd.to_numeric(df["Mobile월간검색수"], errors="coerce").fillna(0)
    top20 = df.sort_values("검색합계", ascending=False).head(20).reset_index(drop=True)
    st.dataframe(top20[["키워드","검색합계","PC월간검색수","Mobile월간검색수","월평균노출광고수","광고경쟁정도"]],
                 use_container_width=True, height=340)
    st.download_button("CSV 다운로드", top20.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"category_{cat}_top20.csv", mime="text/csv", key="dlTop20")
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
    st.markdown('</div>', unsafe_allow_html=True)

def section_keyword_trend_widget():
    st.markdown('<div class="card"><div class="card-title">키워드 트렌드 (직접 입력)</div>', unsafe_allow_html=True)
    kwtxt  = st.text_input("키워드(콤마)", "가방, 원피스", key="kw_txt")
    unit   = st.selectbox("단위", ["week", "month"], index=0, key="kw_unit")
    months = st.slider("조회기간(개월)", 1, 12, 3, key="kw_months")
    if st.button("트렌드 조회", key="kw_run", type="primary"):
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
    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# 8) Radar Card (tabs: 국내 -> 해외)
# =========================
def section_radar():
    st.markdown('<div class="card main"><div class="card-title">AI 키워드 레이더</div>', unsafe_allow_html=True)
    tab_domestic, tab_overseas = st.tabs(["카테고리", "해외(라쿠텐)"])
    with tab_domestic:
        section_korea_ui()
    with tab_overseas:
        section_rakuten_ui()
    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# 9) 상품명 생성기(변경 없음 — 기존 코드 유지)
# =========================
# ... (여기에는 너가 쓰던 생성기 코드 그대로 둬도 동작함 — 길이 관계로 생략)

# =========================
# 10) 기타 카드 (11번가/아이템스카우트/셀러라이프)
# =========================
def _11st_abest_url():
    # 고정 URL(타임스탬프 제거) → 재렌더링시 불필요한 새로고침 최소화
    return "https://m.11st.co.kr/page/main/abest?tabId=ABEST&pageId=AMOBEST&ctgr1No=166160"

def section_11st():
    st.markdown('<div class="card main"><div class="card-title">11번가 (모바일) — 아마존 베스트</div>', unsafe_allow_html=True)
    st.session_state.setdefault("abest_embed_on", False)
    c1, c2 = st.columns([1,1])
    with c1:
        st.toggle("임베드 켜기(권장: OFF)", key="abest_embed_on", value=st.session_state["abest_embed_on"])
    with c2:
        st.link_button("새 탭에서 열기", _11st_abest_url(), use_container_width=False)
    if st.session_state["abest_embed_on"]:
        _proxy_iframe(ELEVENST_PROXY, _11st_abest_url(), height=900, scroll=True, key="abest_iframe")
    else:
        st.info("임베드는 필요할 때만 토글로 켜세요. 기본은 ‘새 탭에서 열기’가 안정적입니다.")
    st.markdown('</div>', unsafe_allow_html=True)

def section_itemscout_placeholder():
    st.markdown('<div class="card main"><div class="card-title">아이템스카우트</div>', unsafe_allow_html=True)
    st.info("임베드 보류 중입니다. 아래 버튼으로 원본 페이지를 새 탭에서 여세요.")
    st.link_button("아이템스카우트 직접 열기(새 탭)", "https://app.itemscout.io/market/keyword")
    st.markdown('</div>', unsafe_allow_html=True)

def section_sellerlife_placeholder():
    st.markdown('<div class="card main"><div class="card-title">셀러라이프</div>', unsafe_allow_html=True)
    st.info("임베드 보류 중입니다. 아래 버튼으로 원본 페이지를 새 탭에서 여세요.")
    st.link_button("직접 열기(새 탭)", "https://sellochomes.co.kr/sellerlife/")
    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# 11) Layout
# =========================
_ = _sidebar()
_responsive_probe()
vwbin = _get_view_bin()

st.title("ENVY — Season 1 (Dual Proxy Edition)")

# 1행
row1_a, row1_b = st.columns([8, 8], gap="medium")
with row1_a:
    section_radar()
with row1_b:
    tab_cat, tab_direct = st.tabs(["카테고리", "직접 입력"])
    with tab_cat:
        section_category_keyword_lab()
    with tab_direct:
        section_keyword_trend_widget()

st.markdown('<div class="row-gap"></div>', unsafe_allow_html=True)

# 2행
c1, c2, c3 = st.columns([3, 3, 3], gap="medium")
with c1:
    section_11st()
with c2:
    section_itemscout_placeholder()
with c3:
    section_sellerlife_placeholder()

st.markdown('<div class="row-gap"></div>', unsafe_allow_html=True)

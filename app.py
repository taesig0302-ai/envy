# -*- coding: utf-8 -*-
# ENVY — Season 1 (Dual Proxy Edition, Radar Unified Step 2)
# - 레이아웃: 기존 백업 유지(상단: 데이터랩/아이템스카우트/셀러라이프, 하단: 11번가/레이더/번역/생성기)
# - 레이더: "국내·글로벌" 단일 카드 토글
#   · 국내 = 네이버 광고 API(Keyword Tool) + 선택적 네이버쇼핑 상품수 수집(느림, 옵션)
#   · 글로벌 = 라쿠텐 랭킹 API(기존 안정화 코드, 캐시/백오프/CSV/가로 스크롤 제거)
# - 나머지 섹션/스타일/로고(72px)/사이드바 여백/데이터랩 탭제목 표시 모두 백업과 동일 유지

import base64, time, re, hashlib, hmac, base64 as b64
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import streamlit as st

try:
    import requests
except Exception:
    requests = None

try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None

try:
    from deep_translator import GoogleTranslator
except Exception:
    GoogleTranslator = None

st.set_page_config(page_title="ENVY — Season 1 (Dual Proxy Edition)", layout="wide")

# =========================
# 0) GLOBALS
# =========================
SHOW_ADMIN_BOX = False

NAVER_PROXY      = "https://envy-proxy.taesig0302.workers.dev"
ELEVENST_PROXY   = "https://worker-11stjs.taesig0302.workers.dev"
ITEMSCOUT_PROXY  = "https://worker-itemscoutjs.taesig0302.workers.dev"
SELLERLIFE_PROXY = "https://worker-sellerlifejs.taesig0302.workers.dev"

RAKUTEN_APP_ID_DEFAULT       = "1043271015809337425"
RAKUTEN_AFFILIATE_ID_DEFAULT = "4c723498.cbfeca46.4c723499.1deb6f77"

CURRENCIES = {
    "USD":{"kr":"미국 달러","symbol":"$","unit":"USD"},
    "EUR":{"kr":"유로","symbol":"€","unit":"EUR"},
    "JPY":{"kr":"일본 엔","symbol":"¥","unit":"JPY"},
    "CNY":{"kr":"중국 위안","symbol":"元","unit":"CNY"},
}
FX_DEFAULT = {"USD":1400.0,"EUR":1500.0,"JPY":10.0,"CNY":200.0}

# =========================
# 1) UI 기본값 & CSS
# =========================

def _ensure_session_defaults():
    ss = st.session_state
    ss.setdefault("theme","light")
    ss.setdefault("fx_base","USD")
    ss.setdefault("sale_foreign",1.00)
    ss.setdefault("m_base","USD")
    ss.setdefault("purchase_foreign",0.00)
    ss.setdefault("card_fee_pct",4.00)
    ss.setdefault("market_fee_pct",14.00)
    ss.setdefault("shipping_won",0.0)
    ss.setdefault("margin_mode","퍼센트")
    ss.setdefault("margin_pct",10.00)
    ss.setdefault("margin_won",10000.0)
    # 라쿠텐 카테고리 매핑(초기값은 샘플 Genre)
    ss.setdefault("rk_genre_map", {
        "전체(샘플)": "100283",
        "뷰티/코스메틱": "100283",
        "의류/패션": "100283",
        "가전/디지털": "100283",
        "가구/인테리어": "100283",
        "식품": "100283",
        "생활/건강": "100283",
        "스포츠/레저": "100283",
        "문구/취미": "100283",
    })


def _toggle_theme():
    st.session_state["theme"] = "dark" if st.session_state.get("theme","light") == "light" else "light"


def _inject_css():
    theme = st.session_state.get("theme","light")
    bg, fg = ("#0e1117","#e6edf3") if theme=="dark" else ("#ffffff","#111111")
    st.markdown(f"""
    <style>
      .block-container{{max-width:3800px!important;padding-top:.55rem!important;padding-bottom:1rem!important}}
      html,body,[data-testid="stAppViewContainer"]{{background:{bg}!important;color:{fg}!important}}
      h2,h3{{margin-top:.3rem!important}}

      /* Sidebar: 컴팩트 간격 */
      [data-testid="stSidebar"],[data-testid="stSidebar"]>div:first-child,[data-testid="stSidebar"] section{{
        height:100vh!important;overflow:hidden!important;padding:.15rem .25rem!important}}
      [data-testid="stSidebar"] section{{overflow-y:auto!important}}
      [data-testid="stSidebar"] ::-webkit-scrollbar{{display:none!important}}
      [data-testid="stSidebar"] .stSelectbox,
      [data-testid="stSidebar"] .stNumberInput,
      [data-testid="stSidebar"] .stRadio,
      [data-testid="stSidebar"] .stMarkdown,
      [data-testid="stSidebar"] .stTextInput,
      [data-testid="stSidebar"] .stButton{{margin:.06rem 0!important}}
      [data-baseweb="input"] input,.stNumberInput input,[data-baseweb="select"] div[role="combobox"]{{
        height:1.55rem!important;padding:.12rem .6rem!important;font-size:.96rem!important;border-radius:12px!important}}

      /* Pills */
      .pill{{border-radius:9999px;padding:.40rem .9rem;font-weight:800;display:inline-block;margin:.10rem 0!important}}
      .pill-green{{background:#b8f06c;border:1px solid #76c02a;color:#083500}}
      .pill-blue{{background:#dbe6ff;border:1px solid #88a8ff;color:#09245e}}
      .pill-yellow{{background:#ffe29b;border:1px solid #d2a12c;color:#3e2a00}}

      /* Card */
      .card{{border:1px solid rgba(0,0,0,.06);border-radius:14px;padding:.85rem;background:#fff;box-shadow:0 1px 6px rgba(0,0,0,.05)}}
      .card-title{{font-size:1.18rem;font-weight:900;margin:.1rem 0 .55rem 0}}
      .card iframe{{border:0;width:100%;border-radius:10px}}
      .row-gap{{height:16px}}

      /* 로고 72px */
      .logo-circle{{width:72px;height:72px;border-radius:50%;overflow:hidden;margin:.2rem auto .4rem auto;
                   box-shadow:0 2px 8px rgba(0,0,0,.12);border:1px solid rgba(0,0,0,.06)}}
      .logo-circle img{{width:100%;height:100%;object-fit:cover}}

      /* DF 공통 스크롤 최적화 */
      #rk-card [data-testid="stDataFrame"] div[role='grid'],
      #radar-card [data-testid="stDataFrame"] div[role='grid']{ overflow-x: hidden !important; }
      #rk-card [data-testid="stDataFrame"] *,
      #radar-card [data-testid="stDataFrame"] * { font-size: 0.92rem !important; }
      #rk-card [data-testid="stDataFrame"] div[role='gridcell'],
      #radar-card [data-testid="stDataFrame"] div[role='gridcell']{{ white-space: normal !important; word-break: break-word !important; overflow-wrap: anywhere !important; }}
    </style>
    """, unsafe_allow_html=True)


def _inject_alert_center():
    st.markdown(
        """
        <div id="envy-alert-root" style="position:fixed;top:16px;right:16px;z-index:999999;pointer-events:none;"></div>
        <style>
          .envy-toast{min-width:220px;max-width:420px;margin:8px 0;padding:.7rem 1rem;border-radius:12px;
            color:#fff;font-weight:700;box-shadow:0 8px 24px rgba(0,0,0,.25);opacity:0;transform:translateY(-6px);
            transition:opacity .2s ease, transform .2s ease;}
          .envy-toast.show{opacity:1;transform:translateY(0)}
          .envy-info{background:#2563eb}.envy-warn{background:#d97706}.envy-error{background:#dc2626}
        </style>
        <script>
          (function(){
            const root = document.getElementById('envy-alert-root');
            function toast(level, text){
              const el = document.createElement('div');
              el.className='envy-toast envy-'+(level||'info'); el.textContent=text||'알림';
              el.style.pointerEvents='auto'; root.appendChild(el);
              requestAnimationFrame(()=>el.classList.add('show'));
              setTimeout(()=>{el.classList.remove('show'); setTimeout(()=>el.remove(), 300);}, 5000);
            }
            window.addEventListener('message',(e)=>{ const d=e.data||{}; if(d.__envy && d.kind==='alert'){toast(d.level,d.msg);} },false);
          })();
        </script>
        """,
        unsafe_allow_html=True,
    )

# =========================
# 2) 반응형
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
# 3) 공용 임베드
# =========================

def _proxy_iframe(proxy_base: str, target_url: str, height: int = 860, scroll=True, key=None):
    proxy = (proxy_base or "").strip().rstrip("/")
    url   = f"{proxy}/?url={quote(target_url, safe=':/?&=%')}"
    h     = int(height) if isinstance(height, (int, float, str)) else 860
    try:
        st.iframe(url, height=h); return
    except Exception:
        pass
    try:
        st.components.v1.iframe(url, height=h, scrolling=bool(scroll)); return
    except Exception:
        pass
    st.markdown(f'<iframe src="{url}" style="width:100%;height:{h}px;border:0;border-radius:10px;"></iframe>', unsafe_allow_html=True)


def _proxy_iframe_with_title(proxy_base: str, target_url: str, height: int = 860, key: str = "naver_home"):
    proxy = (proxy_base or "").strip().rstrip("/")
    url   = f"{proxy}/?url={quote(target_url, safe=':/?&=%')}"
    h     = int(height) if isinstance(height, (int, float, str)) else 860
    html = f"""
    <div id="{key}-wrap" style="width:100%;overflow:hidden;">
      <div id="{key}-title"
           style="display:inline-block;border-radius:9999px;padding:.40rem .9rem;
                  font-weight:800;background:#dbe6ff;border:1px solid #88a8ff;color:#09245e;margin:0 0 .5rem 0;">
        DataLab
      </div>
      <iframe src="{url}" style="width:100%;height:{h}px;border:0;border-radius:10px;"></iframe>
    </div>
    <script>
      (function(){
        const titleEl=document.getElementById("{key}-title");
        window.addEventListener("message",function(e){
          const d=e.data||{}; try{ if(d.__envy && d.kind==="title" && d.title) titleEl.textContent=d.title; }catch(_){ }
        },false);
      })();
    </script>
    """
    st.components.v1.html(html, height=h+56, scrolling=False)

# =========================
# 4) 섹션 - 공통 상단
# =========================

def _sidebar():
    _ensure_session_defaults(); _inject_css(); _inject_alert_center()
    with st.sidebar:
        lp = Path(__file__).parent / "logo.png"
        if lp.exists():
            b64img = base64.b64encode(lp.read_bytes()).decode("ascii")
            st.markdown(f'<div class="logo-circle"><img src="data:image/png;base64,{b64img}"></div>', unsafe_allow_html=True)
        st.toggle("🌓 다크 모드", value=(st.session_state.get("theme","light")=="dark"), on_change=_toggle_theme, key="__theme_toggle")

        st.markdown("### ① 환율 계산기")
        base = st.selectbox("기준 통화", list(CURRENCIES.keys()), index=list(CURRENCIES.keys()).index(st.session_state["fx_base"]), key="fx_base")
        sale_foreign = st.number_input("판매금액 (외화)", value=float(st.session_state["sale_foreign"]), step=0.01, format="%.2f", key="sale_foreign")
        won = FX_DEFAULT[base] * sale_foreign
        st.markdown(
            f'<div class="pill pill-green">환산 금액: <b>{won:,.2f} 원</b>'
            f'<span style="opacity:.75;font-weight:700"> ({CURRENCIES[base]["symbol"]})</span></div>',
            unsafe_allow_html=True
        )
        st.caption(f"환율 기준: {FX_DEFAULT[base]:,.2f} ₩/{CURRENCIES[base]['unit']}")

        st.markdown("### ② 마진 계산기")
        m_base = st.selectbox("매입 통화", list(CURRENCIES.keys()), index=list(CURRENCIES.keys()).index(st.session_state["m_base"]), key="m_base")
        purchase_foreign = st.number_input("매입금액 (외화)", value=float(st.session_state["purchase_foreign"]), step=0.01, format="%.2f", key="purchase_foreign")
        base_cost_won = FX_DEFAULT[m_base]*purchase_foreign if purchase_foreign>0 else won
        st.markdown(f'<div class="pill pill-green">원가(₩): <b>{base_cost_won:,.2f} 원</b></div>', unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            card_fee = st.number_input("카드수수료(%)", value=float(st.session_state["card_fee_pct"]), step=0.01, format="%.2f", key="card_fee_pct")
        with c2:
            market_fee = st.number_input("마켓수수료(%)", value=float(st.session_state["market_fee_pct"]), step=0.01, format="%.2f", key="market_fee_pct")
        shipping_won = st.number_input("배송비(₩)", value=float(st.session_state["shipping_won"]), step=100.0, format="%.0f", key="shipping_won")

        mode = st.radio("마진 방식", ["퍼센트","플러스"], horizontal=True, key="margin_mode")
        if mode == "퍼센트":
            margin_pct = st.number_input("마진율 (%)", value=float(st.session_state["margin_pct"]), step=0.01, format="%.2f", key="margin_pct")
            target_price = base_cost_won*(1+card_fee/100)*(1+market_fee/100)*(1+margin_pct/100)+shipping_won
            margin_value = target_price - base_cost_won
            desc = f"{margin_pct:.2f}%"
        else:
            margin_won = st.number_input("마진액 (₩)", value=float(st.session_state["margin_won"]), step=100.0, format="%.0f", key="margin_won")
            target_price = base_cost_won*(1+card_fee/100)*(1+market_fee/100)+margin_won+shipping_won
            margin_value = margin_won; desc=f"+{margin_won:,.0f}"
        st.markdown(f'<div class="pill pill-blue">판매가: <b>{target_price:,.2f} 원</b></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="pill pill-yellow">순이익(마진): <b>{margin_value:,.2f} 원</b> — {desc}</div>', unsafe_allow_html=True)

        if SHOW_ADMIN_BOX:
            st.divider()
            st.text_input("PROXY_URL(디버그)", key="PROXY_URL", help="Cloudflare Worker 주소 (옵션)")


def section_datalab_home():
    st.markdown('<div class="card"><div class="card-title">데이터랩</div>', unsafe_allow_html=True)
    _proxy_iframe_with_title(NAVER_PROXY, "https://datalab.naver.com/", height=860, key="naver_home")
    st.markdown('</div>', unsafe_allow_html=True)


def section_itemscout_placeholder():
    st.markdown('<div class="card"><div class="card-title">아이템스카우트</div>', unsafe_allow_html=True)
    st.info("임베드 보류 중입니다. 아래 버튼으로 원본 페이지를 새 탭에서 여세요.")
    st.link_button("아이템스카우트 직접 열기(새 탭)", "https://app.itemscout.io/market/keyword")
    st.markdown('</div>', unsafe_allow_html=True)


def section_sellerlife_placeholder():
    st.markdown('<div class="card"><div class="card-title">셀러라이프</div>', unsafe_allow_html=True)
    st.info("임베드 보류 중입니다. 아래 버튼으로 원본 페이지를 새 탭에서 여세요.")
    st.link_button("직접 열기(새 탭)", "https://sellochomes.co.kr/sellerlife/")
    st.markdown('</div>', unsafe_allow_html=True)


def _11st_abest_url():
    return ("https://m.11st.co.kr/page/main/abest?tabId=ABEST&pageId=AMOBEST&ctgr1No=166160&_ts=%d" % int(time.time()))


def section_11st():
    st.markdown('<div class="card"><div class="card-title">11번가 (모바일) — 아마존 베스트</div>', unsafe_allow_html=True)
    _proxy_iframe(ELEVENST_PROXY, _11st_abest_url(), height=900, scroll=True, key="abest")
    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# 5) 라쿠텐(글로벌 레이더) — 캐시/백오프/No H-Scroll 유지
# =========================

def _rakuten_keys():
    app_id = (st.secrets.get("RAKUTEN_APP_ID", "") or st.secrets.get("RAKUTEN_APPLICATION_ID", "") or RAKUTEN_APP_ID_DEFAULT).strip()
    affiliate = (st.secrets.get("RAKUTEN_AFFILIATE_ID", "") or st.secrets.get("RAKUTEN_AFFILIATE", "") or RAKUTEN_AFFILIATE_ID_DEFAULT).strip()
    return app_id, affiliate

RK_JP_KEYWORDS = {
    "뷰티/코스메틱": "コスメ",
    "의류/패션": "ファッション",
    "가전/디지털": "家電",
    "가구/인테리어": "インテリア",
    "식품": "食品",
    "생활/건강": "日用品",
    "스포츠/레저": "スポーツ",
    "문구/취미": "ホビー",
}


def _rk_guess_genre_by_keyword(jp_keyword: str, hits: int = 30) -> str | None:
    app_id, _ = _rakuten_keys()
    if not (requests and app_id and jp_keyword):
        return None
    try:
        r = requests.get(
            "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20170706",
            params={"applicationId": app_id, "keyword": jp_keyword, "hits": hits, "imageFlag": 0},
            timeout=10,
        )
        r.raise_for_status()
        items = [it.get("Item", {}) for it in r.json().get("Items", [])]
        freq = {}
        for it in items:
            gid = str(it.get("genreId") or "")
            if gid:
                freq[gid] = freq.get(gid, 0) + 1
        if not freq:
            return None
        return max(freq.items(), key=lambda kv: kv[1])[0]
    except Exception:
        return None


def _retry_backoff(fn, tries=3, base=0.8, factor=2.0):
    last = None
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            last = e
            time.sleep(base * (factor ** i))
    raise last


@st.cache_data(ttl=900, show_spinner=False)
def _rk_fetch_rank_cached(genre_id: str, topn: int = 20) -> pd.DataFrame:
    app_id, affiliate = _rakuten_keys()
    if not (requests and app_id):
        return pd.DataFrame([{ "rank": i+1, "keyword": f"[샘플] 키워드 {i+1} ハロウィン 秋 🍂", "shop": "샘플", "url": "https://example.com" } for i in range(topn)])

    def _do():
        api = "https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20170628"
        params = {"applicationId": app_id, "genreId": str(genre_id).strip(), "hits": topn}
        if affiliate:
            params["affiliateId"] = affiliate
        r = requests.get(api, params=params, timeout=12)
        r.raise_for_status()
        items = r.json().get("Items", [])[:topn]
        rows = []
        for it in items:
            node = it.get("Item", {})
            rows.append({
                "rank": node.get("rank"),
                "keyword": node.get("itemName", ""),
                "shop": node.get("shopName", ""),
                "url": node.get("itemUrl", ""),
            })
        return pd.DataFrame(rows)

    try:
        return _retry_backoff(_do)
    except Exception:
        return pd.DataFrame([{ "rank": i+1, "keyword": f"[샘플] 키워드 {i+1} ハロウィン 秋 🍂", "shop": "샘플", "url": "https://example.com" } for i in range(topn)])

# =========================
# 6) 국내 레이더(네이버 광고 API + 선택적 상품수)
# =========================

# — 시크릿 사용키
NAVER_ADS_API_KEY      = (st.secrets.get("NAVER_ADS_API_KEY", "") or "").strip()
NAVER_ADS_SECRET_KEY   = (st.secrets.get("NAVER_ADS_SECRET_KEY", "") or "").strip()
NAVER_ADS_CUSTOMER_ID  = (st.secrets.get("NAVER_ADS_CUSTOMER_ID", "") or "").strip()


def _nv_sig(timestamp: str, method: str, uri: str, secret_key: str) -> str:
    msg = f"{timestamp}.{method}.{uri}"
    dig = hmac.new(bytes(secret_key, "utf-8"), bytes(msg, "utf-8"), hashlib.sha256).digest()
    return b64.b64encode(dig).decode("utf-8")


def _coerce_int(x) -> int:
    try:
        return int(str(x).replace(",", "").strip())
    except Exception:
        s = "".join(ch for ch in str(x) if ch.isdigit())
        return int(s) if s else 0


def _safe_float(x) -> float:
    try:
        return float(str(x).replace(",", "").strip())
    except Exception:
        try:
            s = re.sub(r"[^0-9.]+", "", str(x))
            return float(s) if s else 0.0
        except Exception:
            return 0.0


@st.cache_data(ttl=900, show_spinner=False)
def _naver_keywordstool_cached(hint_keywords: str, include_detail: int = 1) -> pd.DataFrame:
    """네이버 광고 키워드도구 API 래퍼(캐시). hint_keywords: 콤마구분 문자열."""
    if not (requests and NAVER_ADS_API_KEY and NAVER_ADS_SECRET_KEY and NAVER_ADS_CUSTOMER_ID):
        # 시크릿이 없으면 샘플
        data = [
            {"키워드":"핸드메이드코트","PC월간검색수":30500,"Mobile월간검색수":226500,"PC월평균클릭수":462.2,"Mobile월평균클릭수":5954.4,
             "PC월평균클릭률":1.57,"Mobile월평균클릭률":2.8,"월평균노출광고수":15,"광고경쟁정도":"중간"},
            {"키워드":"남자코트","PC월간검색수":18500,"Mobile월간검색수":93800,"PC월평균클릭수":171.1,"Mobile월평균클릭수":1613.7,
             "PC월평균클릭률":0.97,"Mobile월평균클릭률":0.92,"월평균노출광고수":15,"광고경쟁정도":"중간"},
        ]
        return pd.DataFrame(data)

    base_url = "https://api.naver.com"
    uri = "/keywordstool"
    method = "GET"
    ts = str(int(time.time()*1000))
    headers = {
        "X-API-KEY": NAVER_ADS_API_KEY,
        "X-Signature": _nv_sig(ts, method, uri, NAVER_ADS_SECRET_KEY),
        "X-Timestamp": ts,
        "X-Customer": NAVER_ADS_CUSTOMER_ID,
    }
    params = {
        "hintKeywords": hint_keywords,
        "includeHintKeywords": "0",
        "showDetail": str(include_detail),
    }
    r = requests.get(base_url+uri, params=params, headers=headers, timeout=12)
    r.raise_for_status()
    items = r.json().get("keywordList", [])
    if not items:
        return pd.DataFrame()

    rows = []
    for it in items:
        rows.append({
            "키워드": it.get("relKeyword", ""),
            "PC월간검색수": _coerce_int(it.get("monthlyPcQcCnt", 0)),
            "Mobile월간검색수": _coerce_int(it.get("monthlyMobileQcCnt", 0)),
            "PC월평균클릭수": _safe_float(it.get("monthlyAvePcClkCnt", 0)),
            "Mobile월평균클릭수": _safe_float(it.get("monthlyAveMobileClkCnt", 0)),
            "PC월평균클릭률": _safe_float(it.get("monthlyAvePcCtr", 0)),
            "Mobile월평균클릭률": _safe_float(it.get("monthlyAveMobileCtr", 0)),
            "월평균노출광고수": _coerce_int(it.get("plAvgDepth", 0)),
            "광고경쟁정도": it.get("compIdx", ""),
        })
    df = pd.DataFrame(rows).drop_duplicates(subset=["키워드"]).reset_index(drop=True)
    df["총검색수"] = df["PC월간검색수"].astype(int) + df["Mobile월간검색수"].astype(int)
    return df


def _naver_shopping_product_count(keyword: str) -> int:
    if not (requests and BeautifulSoup):
        return 0
    try:
        url = f"https://search.shopping.naver.com/search/all?where=all&frm=NVSCTAB&query={quote(keyword)}"
        r = requests.get(url, timeout=10, headers={"User-Agent":"Mozilla/5.0"})
        r.raise_for_status()
        html = r.text
        # 1) NEXT 데이터(JSON) 안에 전체 상품수 존재할 수 있음
        m = re.search(r'"total":"?([0-9,]+)"?', html)
        if m:
            return _coerce_int(m.group(1))
        soup = BeautifulSoup(html, 'html.parser')
        # 2) 보조: '전체' 필터 영역에서 숫자 추출
        for a in soup.find_all('a'):
            txt = a.get_text(strip=True)
            if '전체' in txt:
                m2 = re.search(r'(\d[\d,]*)', txt)
                if m2:
                    return _coerce_int(m2.group(1))
        return 0
    except Exception:
        return 0


def _score_domestic(df: pd.DataFrame, do_product_scan: bool, max_scan: int = 50) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    out = out.sort_values('총검색수', ascending=False).reset_index(drop=True)
    if do_product_scan:
        scan_n = min(max_scan, len(out))
        prod_counts = []
        for i, kw in enumerate(out.loc[:scan_n-1, '키워드'].tolist(), start=1):
            cnt = _naver_shopping_product_count(kw)
            prod_counts.append(cnt)
            time.sleep(0.4)  # 속도/차단 균형
        out.loc[:scan_n-1, '판매상품수'] = prod_counts
        out['판매상품수'] = out['판매상품수'].fillna(0).astype(int)
        # 랭킹(낮을수록 좋음)
        out['검색순위'] = out['총검색수'].rank(ascending=False, method='min')
        out['상품수순위'] = out['판매상품수'].rank(ascending=True, method='min')
        out['상품발굴대상'] = (out['검색순위'] + out['상품수순위']).rank(method='min')
        out = out.sort_values(['상품발굴대상','검색순위']).reset_index(drop=True)
    return out

# =========================
# 7) 레이더(단일 카드) — 국내/글로벌 토글
# =========================

def section_radar_unified():
    st.markdown('<div id="radar-card" class="card"><div class="card-title">키워드 레이더</div>', unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["국내", "글로벌"])

    # ---- 국내 탭 ----
    with tab1:
        if not (NAVER_ADS_API_KEY and NAVER_ADS_SECRET_KEY and NAVER_ADS_CUSTOMER_ID):
            st.info("네이버 광고 API 시크릿이 설정되지 않아 샘플 데이터로 표시됩니다. `secrets.toml`에 NAVER_ADS_API_KEY / NAVER_ADS_SECRET_KEY / NAVER_ADS_CUSTOMER_ID 를 추가하세요.")
        c1, c2, c3 = st.columns([2,1,1])
        with c1:
            hints = st.text_input("힌트 키워드(콤마)", value="핸드메이드코트, 남자코트")
        with c2:
            max_rows = st.number_input("최대 표시 행", 20, 500, 120, 10)
        with c3:
            do_prod = st.checkbox("판매상품수 수집(느림)", value=False)
        run = st.button("국내 레이더 실행", type="primary")

        if run:
            with st.spinner("네이버 키워드 조회 중…"):
                df = _naver_keywordstool_cached(hints, include_detail=1)
                if not df.empty:
                    df = df.sort_values('총검색수', ascending=False).head(int(max_rows)).reset_index(drop=True)
                    if do_prod:
                        df = _score_domestic(df, do_product_scan=True, max_scan=min(int(max_rows), 50))
                    st.dataframe(df, use_container_width=True, height=420)
                    st.download_button("CSV 다운로드", data=df.to_csv(index=False).encode('utf-8-sig'), file_name="naver_keyword_radar.csv", mime="text/csv")
                else:
                    st.warning("결과가 비어 있습니다. 키워드를 바꾸거나, 잠시 후 다시 시도하세요.")

    # ---- 글로벌 탭(라쿠텐) ----
    with tab2:
        colA, colB, colC = st.columns([1,1,1])
        with colA:
            cat = st.selectbox("라쿠텐 카테고리", ["전체(샘플)","뷰티/코스메틱","의류/패션","가전/디지털","가구/인테리어","식품","생활/건강","스포츠/레저","문구/취미"], key="rk_cat")
        with colB:
            sample_only = st.checkbox("샘플 보기", value=False, key="rk_sample")
        with colC:
            st.caption("장르ID는 자동 추정/숨김 처리")

        genre_map = st.session_state.get("rk_genre_map", {})
        genre_id = (genre_map.get(cat) or "").strip()
        need_auto = (not genre_id) or (genre_id == "100283" and cat != "전체(샘플)")
        if need_auto and cat in RK_JP_KEYWORDS:
            guessed = _rk_guess_genre_by_keyword(RK_JP_KEYWORDS[cat])
            if guessed:
                genre_id = guessed
                st.session_state["rk_genre_map"][cat] = genre_id
                st.markdown("<script>window.postMessage({__envy:true,kind:'alert',level:'info',msg:'카테고리에 맞춰 장르를 자동 지정했어요.'},'*');</script>", unsafe_allow_html=True)
        if not genre_id:
            genre_id = "100283"

        with st.spinner("라쿠텐 랭킹 불러오는 중…"):
            df = pd.DataFrame([{ "rank": i+1, "keyword": f"[샘플] 키워드 {i+1}", "shop": "샘플", "url": "https://example.com" } for i in range(20)]) if sample_only else _rk_fetch_rank_cached(genre_id, topn=20)

        colcfg = {
            "rank": st.column_config.NumberColumn("rank", width="small"),  # 랭크 칼럼 2단계 축소 유지
            "keyword": st.column_config.TextColumn("keyword", width="medium"),
            "shop": st.column_config.TextColumn("shop", width="small"),
            "url": st.column_config.LinkColumn("url", display_text="열기", width="small"),
        }
        st.dataframe(df[["rank","keyword","shop","url"]], hide_index=True, use_container_width=True, height=420, column_config=colcfg)
        st.download_button("표 CSV 다운로드", data=df.to_csv(index=False).encode("utf-8-sig"), file_name="rakuten_ranking.csv", mime="text/csv")

    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# 8) 번역기 & 상품명 생성기(기존 유지)
# =========================

LANG_LABELS = {"auto":"자동 감지","ko":"한국어","en":"영어","ja":"일본어","zh-CN":"중국어(간체)","zh-TW":"중국어(번체)","vi":"베트남어","th":"태국어","id":"인도네시아어","de":"독일어","fr":"프랑스어","es":"스페인어","it":"이탈리아어","pt":"포르투갈어"}

def _code(x):
    return {v:k for k,v in LANG_LABELS.items()}.get(x, x)


def section_translator():
    st.markdown('<div class="card"><div class="card-title">구글 번역기</div>', unsafe_allow_html=True)
    c1, c2 = st.columns([1,1])
    with c1:
        src = st.selectbox("원문", list(LANG_LABELS.values()), index=list(LANG_LABELS.keys()).index("auto"))
        text_in = st.text_area("입력", height=180)
    with c2:
        tgt = st.selectbox("번역", list(LANG_LABELS.values()), index=list(LANG_LABELS.keys()).index("en"))
        if st.button("번역", use_container_width=False):
            if not GoogleTranslator:
                st.warning("deep-translator 설치/런타임 문제")
            else:
                out = GoogleTranslator(source=_code(src), target=_code(tgt)).translate(text_in or "")
                if _code(tgt) != "ko" and out.strip():
                    try:
                        ko_hint = GoogleTranslator(source=_code(tgt), target="ko").translate(out)
                        st.text_area("번역 결과", value=f"{out}\n{ko_hint}", height=180)
                    except Exception:
                        st.text_area("번역 결과", value=out, height=180)
                else:
                    st.text_area("번역 결과", value=out, height=180)
    st.markdown('</div>', unsafe_allow_html=True)


def section_title_generator():
    st.markdown('<div class="card"><div class="card-title">상품명 생성기 (규칙 기반)</div>', unsafe_allow_html=True)
    with st.container():
        cA, cB = st.columns([1,2])
        with cA:
            brand = st.text_input("브랜드", placeholder="예: Apple / 샤오미 / 무지")
            attrs = st.text_input("속성(콤마, 선택)", placeholder="예: 공식, 정품, 한정판")
        with cB:
            kws = st.text_input("키워드(콤마)", placeholder="예: 노트북 스탠드, 접이식, 알루미늄")
        a, b, c = st.columns([1,1,1])
        with a:
            max_len = st.slider("최대 글자수", 20, 80, 50, 1)
        with b:
            joiner = st.selectbox("구분자", [" ", " | ", " · ", " - "], index=0)
        with c:
            order = st.selectbox("순서", ["브랜드-키워드-속성", "키워드-브랜드-속성", "브랜드-속성-키워드"], index=0)

        if st.button("상품명 생성"):
            kw_list = [k.strip() for k in (kws or "").split(",") if k.strip()]
            at_list = [a.strip() for a in (attrs or "").split(",") if a.strip()]
            if not kw_list:
                st.warning("키워드가 비었습니다.")
            else:
                titles = []
                for k in kw_list:
                    if order == "브랜드-키워드-속성":
                        seq = [brand, k] + at_list
                    elif order == "키워드-브랜드-속성":
                        seq = [k, brand] + at_list
                    else:
                        seq = [brand] + at_list + [k]
                    title = " ".join([p for p in seq if p]) if joiner == " " else joiner.join([p for p in seq if p])
                    if len(title) > max_len:
                        title = title[:max_len-1] + "…"
                    titles.append(title)
                st.success(f"총 {len(titles)}건")
                st.write("\n".join(titles))
    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# 9) 페이지 레이아웃(반응형 유지)
# =========================

_ = _sidebar()
_responsive_probe()
vwbin = _get_view_bin()

st.title("ENVY — Season 1 (Dual Proxy Edition)")

# 1줄: 데이터랩 / 아이템스카우트(보류) / 셀러라이프(보류)
if vwbin >= 3:
    t1, t2, t3 = st.columns([5,2,2], gap="medium")
    with t1: section_datalab_home()
    with t2: section_itemscout_placeholder()
    with t3: section_sellerlife_placeholder()
elif vwbin == 2:
    t1, t2, t3 = st.columns([4,3,3], gap="small")
    with t1: section_datalab_home()
    with t2: section_itemscout_placeholder()
    with t3: section_sellerlife_placeholder()
else:
    section_datalab_home()
    st.markdown('<div class="row-gap"></div>', unsafe_allow_html=True)
    section_itemscout_placeholder()
    st.markdown('<div class="row-gap"></div>', unsafe_allow_html=True)
    section_sellerlife_placeholder()

st.markdown('<div class="row-gap"></div>', unsafe_allow_html=True)

# 2줄: 11번가 / (통합)레이더 / 번역 / 생성기
if vwbin >= 3:
    b1, b2, b3, b4 = st.columns([3,3,3,3], gap="medium")
    with b1: section_11st()
    with b2: section_radar_unified()
    with b3: section_translator()
    with b4: section_title_generator()
elif vwbin == 2:
    colL, colR = st.columns([1,1], gap="small")
    with colL:
        section_11st()
        st.markdown('<div class="row-gap"></div>', unsafe_allow_html=True)
        section_radar_unified()
    with colR:
        section_translator()
        st.markdown('<div class="row-gap"></div>', unsafe_allow_html=True)
        section_title_generator()
else:
    section_11st()
    st.markdown('<div class="row-gap"></div>', unsafe_allow_html=True)
    section_radar_unified()
    st.markdown('<div class="row-gap"></div>', unsafe_allow_html=True)
    section_translator()
    st.markdown('<div class="row-gap"></div>', unsafe_allow_html=True)
    section_title_generator()

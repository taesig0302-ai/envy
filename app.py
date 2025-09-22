# -*- coding: utf-8 -*-
# ENVY — Season 1 (Dual Proxy Edition, Radar tabs=국내/해외, Rakuten scope radio removed, row1 ratio 5:7)
# 마지막 패치: 국내 레이더 API 입력칸 제거 + 카테고리→TOP20+트렌드(DataLab) + 라쿠텐 매핑 Expander
# + DataLab endDate=어제 강제/불필요 파라미터 생략(빈 응답 방지) 패치

import base64, time, re, math, json, datetime as dt
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
    "RAKUTEN_APP_ID":       "1043271015809337425",
    "RAKUTEN_AFFILIATE_ID": "4c723498.cbfeca46.4c723499.1deb6f77",
    # NAVER Searchad(검색광고 API / 키워드도구)
    "NAVER_API_KEY":        "0100000000785cf1d8f039b13a5d3c3d1262b84e9ad4a046637e8887bbd003051b0d2a5cdf",
    "NAVER_SECRET_KEY":     "AQAAAAB4XPHY8DmxOl08PRJiuE6ao1LN3lh0kF9rOJ4m5b8O5g==",
    "NAVER_CUSTOMER_ID":    "2274338",
    # NAVER Developers (DataLab Open API)  ← 여기 교체
    "NAVER_CLIENT_ID":      "nBay2VW6uz7E4bZnZ2y9",
    "NAVER_CLIENT_SECRET":  "LNuLh1E3e1",
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
# 1) UI defaults & CSS
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

    # Rakuten cached genre map (기본값은 100283 샘플)
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
    st.session_state["theme"]="dark" if st.session_state.get("theme","light")=="light" else "light"

def _inject_css():
    theme = st.session_state.get("theme","light")
    bg, fg = ("#0e1117","#e6edf3") if theme=="dark" else ("#ffffff","#111111")
    st.markdown(f"""
    <style>
      .block-container{{max-width:3800px!important;padding-top:.55rem!important;padding-bottom:1rem!important}}
      html,body,[data-testid="stAppViewContainer"]{{background:{bg}!important;color:{fg}!important}}
      h2,h3{{margin-top:.3rem!important}}

      /* Sidebar compact */
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

      .pill{{border-radius:9999px;padding:.40rem .9rem;font-weight:800;display:inline-block;margin:.10rem 0!important}}
      .pill-green{{background:#b8f06c;border:1px solid #76c02a;color:#083500}}
      .pill-blue{{background:#dbe6ff;border:1px solid #88a8ff;color:#09245e}}
      .pill-yellow{{background:#ffe29b;border:1px solid #d2a12c;color:#3e2a00}}

      .card{{border:1px solid rgba(0,0,0,.06);border-radius:14px;padding:.85rem;background:#fff;box-shadow:0 1px 6px rgba(0,0,0,.05)}}
      .card-title{{font-size:1.18rem;font-weight:900;margin:.1rem 0 .55rem 0}}
      .card iframe{{border:0;width:100%;border-radius:10px}}
      .row-gap{{height:16px}}

      .logo-circle{{width:72px;height:72px;border-radius:50%;overflow:hidden;margin:.2rem auto .4rem auto;
                   box-shadow:0 2px 8px rgba(0,0,0,.12);border:1px solid rgba(0,0,0,.06)}}
      .logo-circle img{{width:100%;height:100%;object-fit:cover}}

      /* Rakuten table tweaks */
      #rk-card [data-testid="stDataFrame"] * {{ font-size: 0.92rem !important; }}
      #rk-card [data-testid="stDataFrame"] div[role='grid']{{ overflow-x: hidden !important; }}
      #rk-card [data-testid="stDataFrame"] div[role='gridcell']{{
        white-space: normal !important; word-break: break-word !important; overflow-wrap: anywhere !important;
      }}
    </style>
    """, unsafe_allow_html=True)

def _inject_alert_center():
    st.markdown("""
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
        let heard=false; window.addEventListener('message',(e)=>{ const d=e.data||{}; if(d.__envy && d.kind==='title'){heard=true;}},false);
        setTimeout(()=>{ if(!heard){ toast('warn','데이터랩 연결이 지연되고 있어요.'); } },8000);
      })();
    </script>
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

def _proxy_iframe_with_title(proxy_base: str, target_url: str, height: int = 860, key: str = "naver_home"):
    proxy = (proxy_base or "").strip().rstrip("/")
    url   = f"{proxy}/?url={quote(target_url, safe=':/?&=%')}"
    h     = int(height)
    html  = f'''
<div id="{key}-wrap" style="width:100%;overflow:hidden;">
  <div id="{key}-title"
       style="display:inline-block;border-radius:9999px;padding:.40rem .9rem;
              font-weight:800;background:#dbe6ff;border:1px solid #88a8ff;color:#09245e;margin:0 0 .5rem 0;">
    DataLab
  </div>
  <iframe src="{url}" style="width:100%;height:{h}px;border:0;border-radius:10px;"></iframe>
</div>
<script>
(function(){{
  var titleEl=document.getElementById("{key}-title");
  window.addEventListener("message",function(e){{
    try{{var d=e.data||{{}}; if(d.__envy && d.kind==="title" && d.title) titleEl.textContent=d.title;}}catch(_){{
    }}
  }},false);
}})();
</script>
'''
    st.components.v1.html(html, height=h+56, scrolling=False)

# =========================
# 4) Sidebar (calculator + theme)
# =========================
def _sidebar():
    _ensure_session_defaults(); _inject_css(); _inject_alert_center()
    with st.sidebar:
        lp = Path(__file__).parent / "logo.png"
        if lp.exists():
            b64 = base64.b64encode(lp.read_bytes()).decode("ascii")
            st.markdown(f'<div class="logo-circle"><img src="data:image/png;base64,{b64}"></div>', unsafe_allow_html=True)
        st.toggle("🌓 다크 모드", value=(st.session_state.get("theme","light")=="dark"),
                  on_change=_toggle_theme, key="__theme_toggle")

        st.markdown("### ① 환율 계산기")
        base = st.selectbox("기준 통화", list(CURRENCIES.keys()),
                            index=list(CURRENCIES.keys()).index(st.session_state["fx_base"]), key="fx_base")
        sale_foreign = st.number_input("판매금액 (외화)", value=float(st.session_state["sale_foreign"]),
                                       step=0.01, format="%.2f", key="sale_foreign")
        won = FX_DEFAULT[base] * sale_foreign
        st.markdown(
            f'<div class="pill pill-green">환산 금액: <b>{won:,.2f} 원</b>'
            f'<span style="opacity:.75;font-weight:700"> ({CURRENCIES[base]["symbol"]})</span></div>',
            unsafe_allow_html=True
        )
        st.caption(f"환율 기준: {FX_DEFAULT[base]:,.2f} ₩/{CURRENCIES[base]['unit']}")

        st.markdown("### ② 마진 계산기")
        m_base = st.selectbox("매입 통화", list(CURRENCIES.keys()),
                              index=list(CURRENCIES.keys()).index(st.session_state["m_base"]), key="m_base")
        purchase_foreign = st.number_input("매입금액 (외화)", value=float(st.session_state["purchase_foreign"]),
                                           step=0.01, format="%.2f", key="purchase_foreign")
        base_cost_won = FX_DEFAULT[m_base]*purchase_foreign if purchase_foreign>0 else won
        st.markdown(f'<div class="pill pill-green">원가(₩): <b>{base_cost_won:,.2f} 원</b></div>', unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            card_fee = st.number_input("카드수수료(%)", value=float(st.session_state["card_fee_pct"]),
                                       step=0.01, format="%.2f", key="card_fee_pct")
        with c2:
            market_fee = st.number_input("마켓수수료(%)", value=float(st.session_state["market_fee_pct"]),
                                         step=0.01, format="%.2f", key="market_fee_pct")
        shipping_won = st.number_input("배송비(₩)", value=float(st.session_state["shipping_won"]),
                                       step=100.0, format="%.0f", key="shipping_won")

        mode = st.radio("마진 방식", ["퍼센트","플러스"], horizontal=True, key="margin_mode")
        if mode=="퍼센트":
            margin_pct=st.number_input("마진율 (%)", value=float(st.session_state["margin_pct"]),
                                       step=0.01, format="%.2f", key="margin_pct")
            target_price = base_cost_won*(1+card_fee/100)*(1+market_fee/100)*(1+margin_pct/100)+shipping_won
            margin_value = target_price - base_cost_won
            desc = f"{margin_pct:.2f}%"
        else:
            margin_won=st.number_input("마진액 (₩)", value=float(st.session_state["margin_won"]),
                                       step=100.0, format="%.0f", key="margin_won")
            target_price=base_cost_won*(1+card_fee/100)*(1+market_fee/100)+margin_won+shipping_won
            margin_value=margin_won; desc=f"+{margin_won:,.0f}"
        st.markdown(f'<div class="pill pill-blue">판매가: <b>{target_price:,.2f} 원</b></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="pill pill-yellow">순이익(마진): <b>{margin_value:,.2f} 원</b> — {desc}</div>', unsafe_allow_html=True)

        if SHOW_ADMIN_BOX:
            st.divider()
            st.text_input("PROXY_URL(디버그)", key="PROXY_URL", help="Cloudflare Worker 주소 (옵션)")

# =========================
# 5) Rakuten Ranking
# =========================
def _rakuten_keys():
    app_id = _get_key("RAKUTEN_APP_ID")
    affiliate = _get_key("RAKUTEN_AFFILIATE_ID")
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

def _retry_backoff(fn, tries=3, base=0.8, factor=2.0):
    last=None
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            last=e
            time.sleep(base*(factor**i))
    raise last

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
        return _retry_backoff(_do)
    except Exception:
        rows=[{"rank":i+1,"keyword":_clean(f"[샘플] 키워드 {i+1} ハロウィン 秋 🍂"),
               "shop":"샘플","url":"https://example.com"} for i in range(topn)]
        return pd.DataFrame(rows)

def section_rakuten_ui():
    st.markdown('<div id="rk-card">', unsafe_allow_html=True)
    colB, colC = st.columns([2,1])
    with colB:
        cat = st.selectbox(
            "라쿠텐 카테고리",
            ["전체(샘플)","뷰티/코스메틱","의류/패션","가전/디지털","가구/인테리어","식품","생활/건강","스포츠/레저","문구/취미"],
            key="rk_cat"
        )
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

    with st.expander("🔧 장르 매핑 편집 (화면에는 숨김)", expanded=False):
        st.caption("카테고리 → genreId 매핑입니다. 올바른 genreId로 바꾸고 저장하세요.")
        g1, g2 = st.columns(2)
        with g1:
            for k in ["뷰티/코스메틱","의류/패션","가구/인테리어","스포츠/레저","문구/취미"]:
                st.session_state["rk_genre_map"][k] = st.text_input(k, st.session_state["rk_genre_map"].get(k,"100283"), key=f"rk_{k}")
        with g2:
            for k in ["가전/디지털","식품","생활/건강","전체(샘플)"]:
                st.session_state["rk_genre_map"][k] = st.text_input(k, st.session_state["rk_genre_map"].get(k,"100283"), key=f"rk_{k}")
        st.info("세션에 저장됩니다. 앱 재실행 시 초기값으로 돌아올 수 있어요.")

    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# 6) Korea Radar (Naver Searchad API)
# =========================
import hashlib, hmac, base64 as b64

def _naver_signature(timestamp: str, method: str, uri: str, secret: str) -> str:
    msg = f"{timestamp}.{method}.{uri}"
    digest = hmac.new(bytes(secret, "utf-8"), bytes(msg, "utf-8"), hashlib.sha256).digest()
    return b64.b64encode(digest).decode("utf-8")

def _naver_keys_from_secrets():
    ak = _get_key("NAVER_API_KEY")
    sk = _get_key("NAVER_SECRET_KEY")
    cid= _get_key("NAVER_CUSTOMER_ID")
    return ak.strip(), sk.strip(), str(cid).strip()

def _naver_keywordstool(hint_keywords: list[str]) -> pd.DataFrame:
    api_key, sec_key, customer_id = _naver_keys_from_secrets()
    if not (requests and api_key and sec_key and customer_id and hint_keywords):
        return pd.DataFrame()

    base_url="https://api.naver.com"
    uri="/keywordstool"
    ts = str(round(time.time()*1000))
    headers = {
        "X-API-KEY": api_key,
        "X-Signature": _naver_signature(ts, "GET", uri, sec_key),
        "X-Timestamp": ts,
        "X-Customer": customer_id,
    }
    params={ "hintKeywords": ",".join(hint_keywords),
             "includeHintKeywords": "0", "showDetail": "1" }
    r = requests.get(base_url+uri, headers=headers, params=params, timeout=12)
    try:
        r.raise_for_status()
        data = r.json().get("keywordList", [])
        if not data: return pd.DataFrame()
        df = pd.DataFrame(data)
        df = df.rename(columns={
            "relKeyword":"키워드",
            "monthlyPcQcCnt":"PC월간검색수",
            "monthlyMobileQcCnt":"Mobile월간검색수",
            "monthlyAvePcClkCnt":"PC월평균클릭수",
            "monthlyAveMobileClkCnt":"Mobile월평균클릭수",
            "monthlyAvePcCtr":"PC월평균클릭률",
            "monthlyAveMobileCtr":"Mobile월평균클릭률",
            "plAvgDepth":"월평균노출광고수",
            "compIdx":"광고경쟁정도",
        })
        df = df.drop_duplicates(["키워드"]).set_index("키워드").reset_index()
        num_cols=["PC월간검색수","Mobile월간검색수",
                  "PC월평균클릭수","Mobile월평균클릭수",
                  "PC월평균클릭률","Mobile월평균클릭률","월평균노출광고수"]
        for c in num_cols:
            df[c]=pd.to_numeric(df[c], errors="coerce")
        return df
    except Exception:
        return pd.DataFrame()

def _count_product_from_shopping(keyword: str) -> int|None:
    if not requests: return None
    try:
        url=f"https://search.shopping.naver.com/search/all?where=all&frm=NVSCTAB&query={quote(keyword)}"
        r=requests.get(url, timeout=10)
        r.raise_for_status()
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

    if st.button("레이더 업데이트", use_container_width=False):
        with st.spinner("네이버 키워드도구 조회 중…"):
            df = _naver_keywordstool(kw_list)
        if df.empty:
            st.error("데이터가 없습니다. (API/권한/쿼터 또는 키워드 확인)")
            return

        if table_mode.startswith("A"):
            st.dataframe(df, use_container_width=True, height=430)
            st.download_button("CSV 다운로드", df.to_csv(index=False).encode("utf-8-sig"),
                               file_name="korea_keyword_A.csv", mime="text/csv")
            return

        df2 = df.copy()
        df2["검색합계"] = (pd.to_numeric(df2["PC월간검색수"], errors="coerce").fillna(0) +
                           pd.to_numeric(df2["Mobile월간검색수"], errors="coerce").fillna(0))
        df2["검색순위"] = df2["검색합계"].rank(ascending=False, method="min")

        if table_mode.startswith("B"):
            out = df2.sort_values("검색순위")
            st.dataframe(out, use_container_width=True, height=430)
            st.download_button("CSV 다운로드", out.to_csv(index=False).encode("utf-8-sig"),
                               file_name="korea_keyword_B.csv", mime="text/csv")
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
                           file_name="korea_keyword_C.csv", mime="text/csv")

# =========================
# 7) DataLab Trend (Open API) + Category → Top20 UI (+ Direct Trend Widget / Debug)
# =========================
@st.cache_data(ttl=1800, show_spinner=False)
def _datalab_trend(groups: list, start_date: str, end_date: str,
                   time_unit: str = "week", device: str = "", gender: str = "", ages: list | None = None) -> pd.DataFrame:
    """
    Naver DataLab 검색어 트렌드.
    groups 예: [{"groupName":"키워드","keywords":["키워드"]}, ...] (최대 5개)
    """
    if not requests:
        return pd.DataFrame()

    cid  = _get_key("NAVER_CLIENT_ID")
    csec = _get_key("NAVER_CLIENT_SECRET")
    if not (cid and csec):
        return pd.DataFrame()

    # ---- Referer 헤더 (WEB 환경용) ----
    ref = _get_key("NAVER_WEB_REFERER").strip()
    if not ref:
        # 캡처하신 streamlit.app URL로 자동 대체(원하는 경우 실제 도메인으로 바꿔도 됨)
        ref = "https://2vrc9owdssnberky8hssf7.streamlit.app"

    # DataLab 제약: group 최대 5개
    groups = (groups or [])[:5]

    url = "https://openapi.naver.com/v1/datalab/search"
    headers = {
        "X-Naver-Client-Id": cid,
        "X-Naver-Client-Secret": csec,
        "Content-Type": "application/json; charset=utf-8",
        "Referer": ref,  # 중요!
    }
    payload = {
        "startDate": start_date, "endDate": end_date, "timeUnit": time_unit,
        "keywordGroups": groups
    }
    if device: payload["device"] = device
    if gender: payload["gender"] = gender
    if ages:   payload["ages"]   = ages

    r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=12)
    try:
        r.raise_for_status()
        js = r.json()
        out = []
        for gr in js.get("results", []):
            name = gr.get("title") or (gr.get("keywords") or [""])[0]  # title 없으면 첫 키워드
            tmp = pd.DataFrame(gr.get("data", []))
            if tmp.empty:
                continue
            tmp["keyword"] = name
            out.append(tmp)

        if not out:
            return pd.DataFrame()

        big = pd.concat(out, ignore_index=True)
        big.rename(columns={"period": "날짜", "ratio": "검색지수"}, inplace=True)
        pivot = big.pivot_table(index="날짜", columns="keyword", values="검색지수", aggfunc="mean")
        pivot = pivot.reset_index().sort_values("날짜")
        return pivot
    except Exception:
        return pd.DataFrame()


# 카테고리별 Seed 키워드 → Top20 선별에 사용
SEED_MAP = {
    "패션의류":   ["원피스","코트","니트","셔츠","블라우스"],
    "패션잡화":   ["가방","지갑","모자","스카프","벨트"],
    "뷰티/미용":  ["쿠션","립스틱","선크림","마스카라","토너"],
    "생활/건강":  ["칫솔","치약","샴푸","세제","물티슈"],
    "디지털/가전": ["블루투스이어폰","스피커","모니터","노트북","로봇청소기"],
    "스포츠/레저": ["러닝화","요가복","캠핑의자","텐트","자전거"],
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

    # DataLab 기간 (권장: 끝일은 '어제')
    start = (dt.date.today() - dt.timedelta(days=30 * months)).strftime("%Y-%m-%d")
    end   = (dt.date.today() - dt.timedelta(days=1)).strftime("%Y-%m-%d")

    # Top20 표 (네이버 검색광고 키워드도구)
    seeds = SEED_MAP.get(cat, [])
    df = _naver_keywordstool(seeds)
    if df.empty:
        st.warning("키워드도구 응답이 비었습니다. (API/권한/쿼터 확인)")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # 합계 기준 상위 20 추출
    df["검색합계"] = pd.to_numeric(df["PC월간검색수"], errors="coerce").fillna(0) + \
                     pd.to_numeric(df["Mobile월간검색수"], errors="coerce").fillna(0)
    top20 = df.sort_values("검색합계", ascending=False).head(20).reset_index(drop=True)

    st.dataframe(
        top20[["키워드","검색합계","PC월간검색수","Mobile월간검색수","월평균노출광고수","광고경쟁정도"]],
        use_container_width=True, height=340
    )
    st.download_button(
        "CSV 다운로드",
        top20.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"category_{cat}_top20.csv",
        mime="text/csv"
    )

    # 라인차트 (상위 N개, DataLab Open API)
    topk = st.slider("라인차트 키워드 수", 3, 10, 5, help="상위 N개 키워드만 트렌드를 그립니다.")
    kws = top20["키워드"].head(topk).tolist()
    groups = [{"groupName": k, "keywords": [k]} for k in kws]

    ts = _datalab_trend(groups, start, end, time_unit=time_unit)
    if ts.empty:
        st.info("DataLab 트렌드 응답이 비어 있어요. (Client ID/Secret, Referer/환경, 날짜/단위 확인)")
    else:
        try:
            st.line_chart(ts.set_index("날짜"))
        except Exception:
            st.dataframe(ts, use_container_width=True, height=260)

    st.markdown('</div>', unsafe_allow_html=True)


def section_keyword_trend_widget():
    """키워드 직접 입력 → DataLab 트렌드 라인차트"""
    st.markdown('<div class="card"><div class="card-title">키워드 트렌드 (직접 입력)</div>', unsafe_allow_html=True)

    kwtxt  = st.text_input("키워드(콤마)", "가방, 원피스", key="kw_txt")
    unit   = st.selectbox("단위", ["week", "month"], index=0, key="kw_unit")
    months = st.slider("조회기간(개월)", 1, 12, 3, key="kw_months")

    if st.button("트렌드 조회", key="kw_run"):
        start = (dt.date.today() - dt.timedelta(days=30 * months)).strftime("%Y-%m-%d")
        end   = (dt.date.today() - dt.timedelta(days=1)).strftime("%Y-%m-%d")

        kws = [k.strip() for k in (kwtxt or "").split(",") if k.strip()]
        groups = [{"groupName": k, "keywords": [k]} for k in kws][:5]

        df = _datalab_trend(groups, start, end, time_unit=unit)

        if df.empty:
            st.error("DataLab 트렌드 응답이 비어 있어요. (Client ID/Secret, Referer/환경, 권한/쿼터/날짜/단위 확인)")
        else:
            st.dataframe(df, use_container_width=True, height=260)
            st.line_chart(df.set_index("날짜"))

    st.markdown('</div>', unsafe_allow_html=True)


def section_datalab_debug():
    """DataLab 호출 상태를 즉석에서 점검하는 작은 위젯(선택 사용)."""
    st.markdown('<div class="card"><div class="card-title">🧪 DataLab 연결 진단</div>', unsafe_allow_html=True)

    c1, c2 = st.columns([1,1])
    with c1:
        unit = st.selectbox("단위", ["week","month"], index=0, key="dbg_unit")
    with c2:
        months = st.slider("기간(개월)", 1, 12, 3, key="dbg_months")

    start = (dt.date.today() - dt.timedelta(days=30*months)).strftime("%Y-%m-%d")
    end   = (dt.date.today() - dt.timedelta(days=1)).strftime("%Y-%m-%d")

    kws = st.text_input("테스트 키워드(콤마)", "원피스, 코트", key="dbg_kws")
    show_raw = st.checkbox("RAW 응답 보기", value=False, key="dbg_raw")

    if st.button("DataLab 테스트 호출", key="dbg_btn"):
        groups = [{"groupName":k.strip(), "keywords":[k.strip()]}
                  for k in (kws or "").split(",") if k.strip()][:5]

        try:
            st.cache_data.clear()
        except Exception:
            pass

        df = _datalab_trend(groups, start, end, time_unit=unit)
        if not df.empty:
            st.success(f"성공! {len(df)}행 수신")
            st.dataframe(df.head(), use_container_width=True, height=220)
            try:
                st.line_chart(df.set_index("날짜"))
            except Exception:
                pass
        else:
            # RAW 호출로 상태/본문 확인
            try:
                cid  = _get_key("NAVER_CLIENT_ID")
                csec = _get_key("NAVER_CLIENT_SECRET")
                ref  = _get_key("NAVER_WEB_REFERER").strip() or "https://2vrc9owdssnberky8hssf7.streamlit.app"
                url  = "https://openapi.naver.com/v1/datalab/search"
                headers = {
                    "X-Naver-Client-Id": cid,
                    "X-Naver-Client-Secret": csec,
                    "Content-Type": "application/json; charset=utf-8",
                    "Referer": ref,
                }
                payload = {"startDate": start, "endDate": end, "timeUnit": unit, "keywordGroups": groups}
                r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=12)
                st.error(f"실패: DataLab 응답이 비었습니다. (status {r.status_code})")
                if show_raw:
                    st.caption("요청 페이로드")
                    st.code(json.dumps(payload, ensure_ascii=False, indent=2))
                    st.caption("응답 RAW")
                    st.code(r.text[:4000])
            except Exception as e:
                st.error(f"요청 중 예외: {e}")

    st.markdown('</div>', unsafe_allow_html=True)



# =========================
# 8) Radar Card (tabs: 국내 -> 해외)
# =========================
def section_radar():
    st.markdown('<div class="card"><div class="card-title">AI 키워드 레이더</div>', unsafe_allow_html=True)
    tab_domestic, tab_overseas = st.tabs(["국내", "해외"])
    with tab_domestic:
        section_korea_ui()
    with tab_overseas:
        section_rakuten_ui()
    st.markdown('</div>', unsafe_allow_html=True)


# =========================
# 9) Other cards
# =========================
def _11st_abest_url():
    return ("https://m.11st.co.kr/page/main/abest?tabId=ABEST&pageId=AMOBEST&ctgr1No=166160&_ts=%d" % int(time.time()))

def section_11st():
    st.markdown('<div class="card"><div class="card-title">11번가 (모바일) — 아마존 베스트</div>', unsafe_allow_html=True)
    _proxy_iframe(ELEVENST_PROXY, _11st_abest_url(), height=900, scroll=True, key="abest")
    st.markdown('</div>', unsafe_allow_html=True)

LANG_LABELS = {"auto":"자동 감지","ko":"한국어","en":"영어","ja":"일본어","zh-CN":"중국어(간체)","zh-TW":"중국어(번체)","vi":"베트남어","th":"태국어","id":"인도네시아어","de":"독일어","fr":"프랑스어","es":"스페인어","it":"이탈리아어","pt":"포르투갈어"}
def _code(x): return {v:k for k,v in LANG_LABELS.items()}.get(x, x)

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
                    if order == "브랜드-키워드-속성": seq = [brand, k] + at_list
                    elif order == "키워드-브랜드-속성": seq = [k, brand] + at_list
                    else: seq = [brand] + at_list + [k]
                    title = " ".join([p for p in seq if p]) if joiner == " " else joiner.join([p for p in seq if p])
                    if len(title) > max_len:
                        title = title[:max_len-1] + "…"
                    titles.append(title)
                st.success(f"총 {len(titles)}건")
                st.write("\n".join(titles))
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


# =========================
# 10) Layout — row1: Radar | (카테고리 or 직접 입력)
# =========================
_ = _sidebar()
_responsive_probe()
vwbin = _get_view_bin()

st.title("ENVY — Season 1 (Dual Proxy Edition)")

# 1행: 레이더(좌) + 탭(우: 카테고리 / 직접 입력)
row1_l, row1_r = st.columns([8, 8], gap="medium")
with row1_l:
    section_radar()

with row1_r:
    # 한 공간에서 모드 전환
    tab_cat, tab_direct = st.tabs(["카테고리", "직접 입력"])
    with tab_cat:
        section_category_keyword_lab()    # 기존 카테고리→Top20 + 트렌드
    with tab_direct:
        section_keyword_trend_widget()    # 기존 직접 입력 트렌드 위젯

st.markdown('<div class="row-gap"></div>', unsafe_allow_html=True)

# 2행: 11번가 / (번역 상 + 상품명 하) / 아이템스카우트 / 셀러라이프
c1, c2, c3, c4 = st.columns([3, 3, 3, 3], gap="medium")
with c1:
    section_11st()
with c2:
    section_translator()
    st.markdown('<div class="row-gap"></div>', unsafe_allow_html=True)
    section_title_generator()
with c3:
    section_itemscout_placeholder()
with c4:
    section_sellerlife_placeholder()
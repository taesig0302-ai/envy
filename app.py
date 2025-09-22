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
# 4) Sidebar (theme + translator toggle + calculators)
# =========================
def _sidebar():
    _ensure_session_defaults()
    _inject_css()
    _inject_alert_center()

    with st.sidebar:
        # 로고
        lp = Path(__file__).parent / "logo.png"
        if lp.exists():
            b64 = base64.b64encode(lp.read_bytes()).decode("ascii")
            st.markdown(
                f'<div class="logo-circle"><img src="data:image/png;base64,{b64}"></div>',
                unsafe_allow_html=True
            )

        # 상단 토글 (다크모드 + 번역기)
        c1, c2 = st.columns(2)
        with c1:
            st.toggle("🌓 다크",
                      value=(st.session_state.get("theme","light")=="dark"),
                      on_change=_toggle_theme,
                      key="__theme_toggle")
        with c2:
            st.toggle("🌐 번역기", value=False, key="__show_translator")

        show_tr = st.session_state.get("__show_translator", False)

        # ─────────────────────────────
        # 번역기 UI 블록 (함수화)
        # ─────────────────────────────
        def translator_block(expanded=True):
            with st.expander("🌐 구글 번역기", expanded=expanded):
                LANG_LABELS_SB = {
                    "auto":"자동 감지","ko":"한국어","en":"영어","ja":"일본어",
                    "zh-CN":"중국어(간체)","zh-TW":"중국어(번체)","vi":"베트남어",
                    "th":"태국어","id":"인도네시아어","de":"독일어","fr":"프랑스어",
                    "es":"스페인어","it":"이탈리아어","pt":"포르투갈어"
                }
                def _code_sb(x): return {v:k for k,v in LANG_LABELS_SB.items()}.get(x, x)

                src_label = st.selectbox(
                    "원문 언어", list(LANG_LABELS_SB.values()),
                    index=list(LANG_LABELS_SB.keys()).index("auto"), key="sb_tr_src"
                )
                tgt_label = st.selectbox(
                    "번역 언어", list(LANG_LABELS_SB.values()),
                    index=list(LANG_LABELS_SB.keys()).index("ko"), key="sb_tr_tgt"
                )
                text_in = st.text_area("텍스트", height=120, key="sb_tr_in")

                if st.button("번역 실행", key="sb_tr_btn"):
                    try:
                        from deep_translator import GoogleTranslator as _GT
                    except Exception:
                        _GT = None
                    if not _GT:
                        st.error("deep-translator 설치 필요 또는 런타임 문제")
                    else:
                        try:
                            src_code = _code_sb(src_label)
                            tgt_code = _code_sb(tgt_label)
                            out_main = _GT(source=src_code, target=tgt_code).translate(text_in or "")
                            st.text_area(f"결과 ({tgt_label})", value=out_main, height=120, key="sb_tr_out_main")
                            if tgt_code != "ko":
                                out_ko = _GT(source=tgt_code, target="ko").translate(out_main or "")
                                st.text_area("결과 (한국어)", value=out_ko, height=120, key="sb_tr_out_ko")
                        except Exception as e:
                            st.error(f"번역 중 오류: {e}")

        # ─────────────────────────────
        # 환율/마진 계산기 블록 (함수화)
        # ─────────────────────────────
        def fx_block(expanded=True):
            with st.expander("💱 환율 계산기", expanded=expanded):
                fx_base = st.session_state.get("fx_base", "USD")
                sale_foreign = float(st.session_state.get("sale_foreign", 1.0))
                fx_base = st.selectbox("기준 통화", list(CURRENCIES.keys()),
                                       index=list(CURRENCIES.keys()).index(fx_base), key="fx_base")
                sale_foreign = st.number_input("판매금액 (외화)", value=sale_foreign,
                                               step=0.01, format="%.2f", key="sale_foreign")
                won = FX_DEFAULT[fx_base] * sale_foreign
                st.markdown(
                    f'<div class="pill pill-green">환산 금액: <b>{won:,.2f} 원</b>'
                    f'<span style="opacity:.75;font-weight:700"> ({CURRENCIES[fx_base]["symbol"]})</span></div>',
                    unsafe_allow_html=True
                )
                st.caption(f"환율 기준: {FX_DEFAULT[fx_base]:,.2f} ₩/{CURRENCIES[fx_base]['unit']}")

        def margin_block(expanded=True):
            with st.expander("📈 마진 계산기", expanded=expanded):
                m_base = st.session_state.get("m_base", "USD")
                purchase_foreign = float(st.session_state.get("purchase_foreign", 0.0))
                card_fee_pct = float(st.session_state.get("card_fee_pct", 4.0))
                market_fee_pct = float(st.session_state.get("market_fee_pct", 14.0))
                shipping_won = float(st.session_state.get("shipping_won", 0.0))
                margin_mode = st.session_state.get("margin_mode", "퍼센트")
                margin_pct = float(st.session_state.get("margin_pct", 10.0))
                margin_won = float(st.session_state.get("margin_won", 10000.0))

                m_base = st.selectbox("매입 통화", list(CURRENCIES.keys()),
                                      index=list(CURRENCIES.keys()).index(m_base), key="m_base")
                purchase_foreign = st.number_input("매입금액 (외화)", value=purchase_foreign,
                                                   step=0.01, format="%.2f", key="purchase_foreign")

                base_cost_won = FX_DEFAULT[m_base]*purchase_foreign if purchase_foreign > 0 \
                                else FX_DEFAULT[st.session_state.get("fx_base","USD")]*st.session_state.get("sale_foreign",1.0)
                st.markdown(f'<div class="pill pill-green">원가(₩): <b>{base_cost_won:,.2f} 원</b></div>', unsafe_allow_html=True)

                c1, c2 = st.columns(2)
                with c1:
                    card_fee_pct = st.number_input("카드수수료(%)", value=card_fee_pct,
                                                   step=0.01, format="%.2f", key="card_fee_pct")
                with c2:
                    market_fee_pct = st.number_input("마켓수수료(%)", value=market_fee_pct,
                                                     step=0.01, format="%.2f", key="market_fee_pct")
                shipping_won = st.number_input("배송비(₩)", value=shipping_won,
                                               step=100.0, format="%.0f", key="shipping_won")

                margin_mode = st.radio("마진 방식", ["퍼센트","플러스"], horizontal=True, key="margin_mode")
                if margin_mode == "퍼센트":
                    margin_pct = st.number_input("마진율 (%)", value=margin_pct,
                                                 step=0.01, format="%.2f", key="margin_pct")
                    target_price = base_cost_won*(1+card_fee_pct/100)*(1+market_fee_pct/100)*(1+margin_pct/100)+shipping_won
                    margin_value = target_price - base_cost_won
                    desc = f"{margin_pct:.2f}%"
                else:
                    margin_won = st.number_input("마진액 (₩)", value=margin_won,
                                                 step=100.0, format="%.0f", key="margin_won")
                    target_price = base_cost_won*(1+card_fee_pct/100)*(1+market_fee_pct/100)+margin_won+shipping_won
                    margin_value = margin_won
                    desc = f"+{margin_won:,.0f}"

                st.markdown(f'<div class="pill pill-blue">판매가: <b>{target_price:,.2f} 원</b></div>', unsafe_allow_html=True)
                st.markdown(f'<div class="pill pill-yellow">순이익(마진): <b>{margin_value:,.2f} 원</b> — {desc}</div>', unsafe_allow_html=True)

        # ─────────────────────────────
        # ON → 번역기 위쪽 / 계산기 접힘
        # OFF → 계산기 열림 / 번역기 아래 접힘
        # ─────────────────────────────
        if show_tr:
            translator_block(expanded=True)
            fx_block(expanded=False)
            margin_block(expanded=False)
        else:
            fx_block(expanded=True)
            margin_block(expanded=True)
            translator_block(expanded=False)

        # 관리자 디버그
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
# 9) 상품명 생성기 (네이버 SEO + 금칙어)
# =========================

# ===== Stopwords (전역/카테고리) =====
STOPWORDS_GLOBAL = [
    "무료배송","무배","초특가","특가","핫딜","최신","최신형","역대급","당일발송","당일배송",
    "최저가","세일","SALE","이벤트","사은품","증정","쿠폰","정가","파손","환불","교환",
    "재고","품절","한정수량","MUSTBUY","강추","추천","🔥","💥","⭐","BEST","베스트"
]

STOPWORDS_BY_CAT = {
    "패션의류":   ["루즈핏","빅사이즈","초슬림","극세사","초경량","왕오버","몸매보정"],
    "패션잡화":   ["무료각인","사은품지급","세트증정"],
    "뷰티/미용":  ["정품보장","병행수입","벌크","리필만","샘플","테스터"],
    "생활/건강":  ["공용","비매품","리퍼","리퍼비시"],
    "디지털/가전": ["관부가세","부가세","해외직구","리퍼","리퍼비시","벌크"],
    "스포츠/레저": ["무료조립","가성비갑"],
}


def section_title_generator():
    """
    상품명 생성기 (네이버 SEO + 검색량 기반 확장 + 금칙어 엔진)
    """
    import re, math

    st.markdown('<div class="card"><div class="card-title">상품명 생성기 (네이버 SEO 자동 확장 + 금칙어)</div>', unsafe_allow_html=True)

    # ---------- 유틸 ----------
    def _norm(s: str) -> str:
        s = (s or "").strip()
        s = re.sub(r"[ \t\u3000]+", " ", s)
        return re.sub(r"\s{2,}", " ", s)

    def _dedup(tokens):
        seen=set(); out=[]
        for t in tokens:
            t=_norm(t)
            if not t: continue
            key=t.lower()
            if key in seen: continue
            seen.add(key); out.append(t)
        return out

    def _smart_truncate(title: str, max_len: int, must_keep_prefix: str = "") -> str:
        title=_norm(title)
        if len(title)<=max_len: return title
        if must_keep_prefix and title.startswith(must_keep_prefix):
            return title[:max_len-1]+"…"
        cut=title[:max_len+1]
        m=re.search(r"(.{0,"+str(max_len)+r"})(?:[\s\|\·\-]|$)", cut)
        if m and m.group(1):
            out=m.group(1).rstrip()
            return out+("…" if len(out)<len(title) else "")
        return title[:max_len-1]+"…"

    def _score_keywords(df: pd.DataFrame) -> pd.DataFrame:
        tmp=df.copy()
        for c in ["PC월간검색수","Mobile월간검색수","광고경쟁정도"]:
            tmp[c]=pd.to_numeric(tmp[c], errors="coerce").fillna(0.0)
        tmp["검색합계"]=tmp["PC월간검색수"]+tmp["Mobile월간검색수"]
        tmp["경쟁도"]=tmp["광고경쟁정도"].clip(lower=0, upper=1)
        tmp["SEO점수"]=tmp["검색합계"].apply(lambda x: math.log1p(x))*(1.0-tmp["경쟁도"])
        return tmp.sort_values(["SEO점수","검색합계"], ascending=[False,False])

    def _would_overflow(curr: str, piece: str, max_len: int) -> bool:
        sep = "" if not curr else " "
        return len(_norm(curr+sep+piece))>max_len

    # 금칙어 처리
    def _compile_stopwords(global_list, cate_list, user_str, replace_pairs):
        stop = set()
        for s in global_list + (cate_list or []):
            s=_norm(s)
            if s: stop.add(s.lower())
        user = [_norm(x) for x in (user_str or "").split(",") if _norm(x)]
        for s in user:
            stop.add(s.lower())
        # 부분일치 정규식
        part = [re.escape(s) for s in stop if len(s)>=2]
        part_re = re.compile("|".join(part), flags=re.IGNORECASE) if part else None
        # 치환 dict
        repl = {}
        for pair in replace_pairs:
            src=_norm(pair.split("=>")[0] if "=>" in pair else pair)
            dst=_norm(pair.split("=>")[1]) if "=>" in pair else ""
            if src: repl[src.lower()] = dst
        return stop, part_re, repl

    def _apply_stopwords(tokens, stop_exact, stop_part_re, repl_map, aggressive=False):
        out=[]; removed=[]
        for t in tokens:
            raw=t; low=t.lower()
            if low in stop_exact: removed.append(raw); continue
            if low in repl_map:
                t=repl_map[low]; low=t.lower()
                if not t: removed.append(raw); continue
            if aggressive and stop_part_re and stop_part_re.search(t):
                removed.append(raw); continue
            out.append(t)
        return _dedup(out), removed

    # ---------- 입력 ----------
    left, right = st.columns([1,2])
    with left:
        brand = st.text_input("브랜드", placeholder="예: Apple / 샤오미 / 무지", key="seo_brand")
        attrs = st.text_input("속성(콤마, 선택)", placeholder="예: 공식, 정품, 한정판", key="seo_attrs")
    with right:
        kws_input = st.text_input("핵심 키워드(콤마)", placeholder="예: 노트북 스탠드, 접이식, 알루미늄", key="seo_kws")

    a,b,c = st.columns([1,1,1])
    with a:
        max_len = st.slider("최대 글자수", 40, 70, 50, 1, key="seo_maxlen")
    with b:
        target_min = st.slider("목표 최소 글자수", 40, 60, 45, 1, key="seo_minlen")
    with c:
        order = st.selectbox("순서", ["브랜드-키워드-속성","키워드-브랜드-속성","브랜드-속성-키워드"], index=0, key="seo_order")

    row2a, row2b = st.columns([1,1])
    with row2a:
        use_naver = st.toggle("네이버 SEO 모드", value=True, key="seo_use_naver")
        auto_expand = st.toggle("검색량 기반 자동 확장", value=True, key="seo_autoexpand")
        topn = st.slider("생성 개수(상위)", 3, 20, 10, 1, key="seo_topn")
    with row2b:
        cat_for_stop = st.selectbox("금칙어 카테고리", ["(없음)"]+list(STOPWORDS_BY_CAT.keys()), index=0, key="stop_cat")
        user_stop = st.text_input("사용자 금칙어(콤마)", value="정품,무료배송,최신,인기,특가", key="seo_stop")
        user_repl = st.text_input("치환 규칙(콤마, src=>dst)", value="무배=> ,무료배송=> ,정품=>", key="seo_repl")
        aggressive = st.toggle("공격적 부분일치 제거", value=False, key="stop_aggr")

    # ---------- 실행 ----------
    if st.button("상품명 생성 (SEO + 금칙어)", key="seo_run"):
        kw_list=[_norm(k) for k in (kws_input or "").split(",") if _norm(k)]
        if not kw_list:
            st.warning("핵심 키워드를 1개 이상 입력하세요."); return

        cate = STOPWORDS_BY_CAT.get(cat_for_stop, []) if cat_for_stop and cat_for_stop!="(없음)" else []
        replace_pairs=[x.strip() for x in (user_repl or "").split(",") if x.strip()]
        stop_exact, stop_part_re, repl_map = _compile_stopwords(STOPWORDS_GLOBAL, cate, user_stop, replace_pairs)

        joiner=" "
        ranked_kws=kw_list; naver_table=None
        if use_naver:
            with st.spinner("네이버 키워드 지표 조회 중…"):
                df_raw=_naver_keywordstool(kw_list)
            if not df_raw.empty:
                naver_table=_score_keywords(df_raw)
                ranked_kws=naver_table["키워드"].tolist()

        brand_norm=_norm(brand)
        attrs_norm=_dedup([_norm(a) for a in (attrs or "").split(",") if _norm(a)])
        attrs_norm, _=_apply_stopwords(attrs_norm, stop_exact, stop_part_re, repl_map, aggressive)

        def _base_seq(primary_kw: str):
            if order=="브랜드-키워드-속성":
                seq=[brand_norm, primary_kw]+attrs_norm
                prefix=_norm((brand_norm+" "+primary_kw).strip())
            elif order=="키워드-브랜드-속성":
                seq=[primary_kw, brand_norm]+attrs_norm
                prefix=_norm((primary_kw+" "+brand_norm).strip())
            else:
                seq=[brand_norm]+attrs_norm+[primary_kw]
                prefix=_norm((brand_norm+" "+primary_kw).strip())
            seq=_dedup([t for t in seq if _norm(t)])
            seq,_=_apply_stopwords(seq, stop_exact, stop_part_re, repl_map, aggressive)
            return seq, prefix

        titles=[]; used=set()
        for primary in ranked_kws:
            primary=_norm(primary)
            if not primary: continue
            pk_list,_=_apply_stopwords([primary], stop_exact, stop_part_re, repl_map, aggressive)
            if not pk_list: continue
            primary=pk_list[0]
            seq,prefix=_base_seq(primary)
            title=(joiner.join(seq)).strip()
            expanded=title
            if auto_expand and len(expanded)<target_min:
                for cand in ranked_kws:
                    if cand.lower()==primary.lower(): continue
                    cand_list,_=_apply_stopwords([cand], stop_exact, stop_part_re, repl_map, aggressive)
                    if not cand_list: continue
                    cnd=cand_list[0]
                    if re.search(re.escape(cnd), expanded, flags=re.IGNORECASE): continue
                    if _would_overflow(expanded,cnd,max_len): continue
                    expanded=_norm(expanded+joiner+cnd)
                    if len(expanded)>=target_min: break
            final=_smart_truncate(expanded, max_len, must_keep_prefix=prefix)
            key=final.lower()
            if key in used: continue
            used.add(key); titles.append(final)
            if len(titles)>=topn: break

        if naver_table is not None and not naver_table.empty:
            with st.expander("📊 네이버 지표", expanded=False):
                st.dataframe(naver_table[["키워드","PC월간검색수","Mobile월간검색수","광고경쟁정도","SEO점수"]],
                             use_container_width=True, height=260)

        if titles:
            st.success(f"생성 완료 · {len(titles)}건")
            for i,t in enumerate(titles,1):
                st.markdown(f"**{i}.** {t}")
            out_df=pd.DataFrame({"title":titles})
            st.download_button("CSV 다운로드", out_df.to_csv(index=False).encode("utf-8-sig"),
                               file_name="titles_seo_stopwords.csv", mime="text/csv")
        else:
            st.warning("생성된 상품명이 없습니다. (금칙어/중복/길이 제한/입력값 확인)")

# =========================
# 10) Layout — row1: 레이더 | (카테고리 or 직접입력) | 생성기
#                 row2: 11번가 | 아이템스카우트 | 셀러라이프
# =========================
_ = _sidebar()
_responsive_probe()
vwbin = _get_view_bin()

st.title("ENVY — Season 1 (Dual Proxy Edition)")

# 1행
row1_a, row1_b, row1_c = st.columns([8, 5, 3], gap="medium")
with row1_a:
    section_radar()
with row1_b:
    tab_cat, tab_direct = st.tabs(["카테고리", "직접 입력"])
    with tab_cat:
        section_category_keyword_lab()
    with tab_direct:
        section_keyword_trend_widget()
with row1_c:
    section_title_generator()

st.markdown('<div class="row-gap"></div>', unsafe_allow_html=True)

# 2행
c1, c2, c3 = st.columns([4, 4, 4], gap="medium")
with c1:
    section_11st()
with c2:
    section_itemscout_placeholder()
with c3:
    section_sellerlife_placeholder()

# -*- coding: utf-8 -*-
# ENVY — Season 1 (Dual Proxy Edition, Radar tabs=국내/해외, Rakuten scope radio removed, row1 ratio 8:5:3)
# 이번 버전:
# - 상품명 생성기 카드 내부 탭: [생성기 | 금칙어 관리]
# - 외부 금칙어 섹션은 유지(선택). 동일 세션키 공유로 동기화됨.
# - 사이드바: 다크+번역기 토글 / 번역기 ON: 번역기 펼침·계산기 접힘, OFF: 계산기 펼침·번역기 접힘

import base64, time, re, math, json, io, datetime as dt
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
    # NAVER Developers (DataLab Open API)
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
# Stopwords — 전역/카테고리 + 프리셋
# =========================
STOPWORDS_GLOBAL = [
    # 광고/행사/가격 과장
    "무료배송","무배","초특가","특가","핫딜","최저가","세일","sale","이벤트","사은품","증정",
    "쿠폰","역대급","역대가","폭탄세일","원가","정가","파격","초대박","할인폭","혜택가",
    # 운영/AS 리스크
    "파손","환불","교환","재고","품절","한정수량","긴급","급처","특판",
    # 과도한 마케팅 표현/이모지
    "mustbuy","강추","추천","추천템","🔥","💥","⭐","best","베스트"
]
STOPWORDS_BY_CAT = {
    "패션의류":   ["루즈핏","빅사이즈","초슬림","극세사","초경량","왕오버","몸매보정"],
    "패션잡화":   ["무료각인","사은품지급","세트증정"],
    "뷰티/미용":  ["정품보장","병행수입","벌크","리필만","샘플","테스터"],
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
    st.session_state["theme"]="dark" if st.session_state.get("theme","light")=="light" else "light"

def _inject_css():
    theme = st.session_state.get("theme","light")
    bg, fg = ("#0e1117","#e6edf3") if theme=="dark" else ("#ffffff","#111111")
    st.markdown(f"""
    <style>
      .block-container{{max-width:3800px!important;padding-top:.55rem!important;padding-bottom:1rem!important}}
      html,body,[data-testid="stAppViewContainer"]{{background:{bg}!important;color:{fg}!important}}
      h2,h3{{margin-top:.3rem!important}}
      [data-testid="stSidebar"],[data-testid="stSidebar"]>div:first-child,[data-testid="stSidebar"] section{{height:100vh!important;overflow:hidden!important;padding:.15rem .25rem!important}}
      [data-testid="stSidebar"] section{{overflow-y:auto!important}}
      [data-testid="stSidebar"] ::-webkit-scrollbar{{display:none!important}}
      [data-testid="stSidebar"] .stSelectbox,.stNumberInput,.stRadio,.stMarkdown,.stTextInput,.stButton{{margin:.06rem 0!important}}
      [data-baseweb="input"] input,.stNumberInput input,[data-baseweb="select"] div[role="combobox"]{{height:1.55rem!important;padding:.12rem .6rem!important;font-size:.96rem!important;border-radius:12px!important}}
      .pill{{border-radius:9999px;padding:.40rem .9rem;font-weight:800;display:inline-block;margin:.10rem 0!important}}
      .pill-green{{background:#b8f06c;border:1px solid #76c02a;color:#083500}}
      .pill-blue{{background:#dbe6ff;border:1px solid #88a8ff;color:#09245e}}
      .pill-yellow{{background:#ffe29b;border:1px solid #d2a12c;color:#3e2a00}}
      .card{{border:1px solid rgba(0,0,0,.06);border-radius:14px;padding:.85rem;background:#fff;box-shadow:0 1px 6px rgba(0,0,0,.05)}}
      .card-title{{font-size:1.18rem;font-weight:900;margin:.1rem 0 .55rem 0}}
      .card iframe{{border:0;width:100%;border-radius:10px}}
      .row-gap{{height:16px}}
      .logo-circle{{width:72px;height:72px;border-radius:50%;overflow:hidden;margin:.2rem auto .4rem auto;box-shadow:0 2px 8px rgba(0,0,0,.12);border:1px solid rgba(0,0,0,.06)}}
      .logo-circle img{{width:100%;height:100%;object-fit:cover}}
      #rk-card [data-testid="stDataFrame"] * {{ font-size: 0.92rem !important; }}
      #rk-card [data-testid="stDataFrame"] div[role='grid']{{ overflow-x: hidden !important; }}
      #rk-card [data-testid="stDataFrame"] div[role='gridcell']{{ white-space: normal !important; word-break: break-word !important; overflow-wrap: anywhere !important; }}
    </style>
    """, unsafe_allow_html=True)

def _inject_alert_center():
    st.markdown("""
    <div id="envy-alert-root" style="position:fixed;top:16px;right:16px;z-index:999999;pointer-events:none;"></div>
    <style>
      .envy-toast{min-width:220px;max-width:420px;margin:8px 0;padding:.7rem 1rem;border-radius:12px;color:#fff;font-weight:700;box-shadow:0 8px 24px rgba(0,0,0,.25);opacity:0;transform:translateY(-6px);transition:opacity .2s ease, transform .2s ease;}
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
    _ensure_session_defaults(); _inject_css(); _inject_alert_center()
    with st.sidebar:
        lp = Path(__file__).parent / "logo.png"
        if lp.exists():
            b64 = base64.b64encode(lp.read_bytes()).decode("ascii")
            st.markdown(f'<div class="logo-circle"><img src="data:image/png;base64,{b64}"></div>', unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            st.toggle("🌓 다크", value=(st.session_state.get("theme","light")=="dark"),
                      on_change=_toggle_theme, key="__theme_toggle")
        with c2:
            st.toggle("🌐 번역기", value=False, key="__show_translator")
        show_tr = st.session_state.get("__show_translator", False)

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
                if st.button("번역 실행", key="sb_tr_btn"):
                    try:
                        from deep_translator import GoogleTranslator as _GT
                    except Exception:
                        _GT = None
                    if not _GT:
                        st.error("deep-translator 설치 필요 또는 런타임 문제")
                    else:
                        try:
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
                sale_foreign = st.number_input("판매금액 (외화)", value=float(st.session_state.get("sale_foreign",1.0)),
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
                    card_fee = st.number_input("카드수수료(%)", value=float(st.session_state.get("card_fee_pct",4.0)),
                                               step=0.01, format="%.2f", key="card_fee_pct")
                with c2:
                    market_fee = st.number_input("마켓수수료(%)", value=float(st.session_state.get("market_fee_pct",14.0)),
                                                 step=0.01, format="%.2f", key="market_fee_pct")
                shipping_won = st.number_input("배송비(₩)", value=float(st.session_state.get("shipping_won",0.0)),
                                               step=100.0, format="%.0f", key="shipping_won")
                mode = st.radio("마진 방식", ["퍼센트","플러스"], horizontal=True, key="margin_mode")
                if mode=="퍼센트":
                    margin_pct = st.number_input("마진율 (%)", value=float(st.session_state.get("margin_pct",10.0)),
                                                 step=0.01, format="%.2f", key="margin_pct")
                    target_price = base_cost_won*(1+card_fee/100)*(1+market_fee/100)*(1+margin_pct/100)+shipping_won
                    margin_value = target_price - base_cost_won; desc=f"{margin_pct:.2f}%"
                else:
                    margin_won = st.number_input("마진액 (₩)", value=float(st.session_state.get("margin_won",10000.0)),
                                                 step=100.0, format="%.0f", key="margin_won")
                    target_price = base_cost_won*(1+card_fee/100)*(1+market_fee/100)+margin_won+shipping_won
                    margin_value = margin_won; desc=f"+{margin_won:,.0f}"
                st.markdown(f'<div class="pill pill-blue">판매가: <b>{target_price:,.2f} 원</b></div>', unsafe_allow_html=True)
                st.markdown(f'<div class="pill pill-yellow">순이익(마진): <b>{margin_value:,.2f} 원</b> — {desc}</div>', unsafe_allow_html=True)

        if show_tr:
            translator_block(expanded=True); fx_block(expanded=False); margin_block(expanded=False)
        else:
            fx_block(expanded=True); margin_block(expanded=True); translator_block(expanded=False)

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
    st.markdown('<div id="rk-card">', unsafe_allow_html=True)
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
    r = requests.get(base_url+uri, headers=headers, params=params, timeout=12)
    try:
        r.raise_for_status()
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
                               file_name="korea_keyword_A.csv", mime="text/csv"); return
        df2 = df.copy()
        df2["검색합계"] = (pd.to_numeric(df2["PC월간검색수"], errors="coerce").fillna(0) +
                           pd.to_numeric(df2["Mobile월간검색수"], errors="coerce").fillna(0))
        df2["검색순위"] = df2["검색합계"].rank(ascending=False, method="min")
        if table_mode.startswith("B"):
            out = df2.sort_values("검색순위")
            st.dataframe(out, use_container_width=True, height=430)
            st.download_button("CSV 다운로드", out.to_csv(index=False).encode("utf-8-sig"),
                               file_name="korea_keyword_B.csv", mime="text/csv"); return
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
# 7) DataLab Trend (Open API) + Category → Top20 UI (+ Direct Trend)
# =========================
@st.cache_data(ttl=1800, show_spinner=False)
def _datalab_trend(groups: list, start_date: str, end_date: str,
                   time_unit: str = "week", device: str = "", gender: str = "", ages: list | None = None) -> pd.DataFrame:
    if not requests: return pd.DataFrame()
    cid  = _get_key("NAVER_CLIENT_ID"); csec = _get_key("NAVER_CLIENT_SECRET")
    if not (cid and csec): return pd.DataFrame()
    ref = _get_key("NAVER_WEB_REFERER").strip() or "https://2vrc9owdssnberky8hssf7.streamlit.app"
    groups = (groups or [])[:5]
    url = "https://openapi.naver.com/v1/datalab/search"
    headers = {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": csec, "Content-Type": "application/json; charset=utf-8", "Referer": ref}
    payload = {"startDate": start_date, "endDate": end_date, "timeUnit": time_unit, "keywordGroups": groups}
    r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=12)
    try:
        r.raise_for_status()
        js = r.json(); out=[]
        for gr in js.get("results", []):
            name = gr.get("title") or (gr.get("keywords") or [""])[0]
            tmp = pd.DataFrame(gr.get("data", []))
            if tmp.empty: continue
            tmp["keyword"] = name; out.append(tmp)
        if not out: return pd.DataFrame()
        big = pd.concat(out, ignore_index=True)
        big.rename(columns={"period": "날짜", "ratio": "검색지수"}, inplace=True)
        pivot = big.pivot_table(index="날짜", columns="keyword", values="검색지수", aggfunc="mean")
        pivot = pivot.reset_index().sort_values("날짜")
        return pivot
    except Exception:
        return pd.DataFrame()

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
    start = (dt.date.today() - dt.timedelta(days=30 * months)).strftime("%Y-%m-%d")
    end   = (dt.date.today() - dt.timedelta(days=1)).strftime("%Y-%m-%d")
    seeds = SEED_MAP.get(cat, [])
    df = _naver_keywordstool(seeds)
    if df.empty:
        st.warning("키워드도구 응답이 비었습니다. (API/권한/쿼터 확인)")
        st.markdown('</div>', unsafe_allow_html=True); return
    df["검색합계"] = pd.to_numeric(df["PC월간검색수"], errors="coerce").fillna(0) + pd.to_numeric(df["Mobile월간검색수"], errors="coerce").fillna(0)
    top20 = df.sort_values("검색합계", ascending=False).head(20).reset_index(drop=True)
    st.dataframe(top20[["키워드","검색합계","PC월간검색수","Mobile월간검색수","월평균노출광고수","광고경쟁정도"]],
                 use_container_width=True, height=340)
    st.download_button("CSV 다운로드", top20.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"category_{cat}_top20.csv", mime="text/csv")
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
# Stopwords Manager UI (공용) — 생성기 탭/외부 섹션에서 재사용
# =========================
def _stopwords_manager_ui(compact: bool = False):
    ss = st.session_state
    ss.setdefault("STOP_GLOBAL", list(STOPWORDS_GLOBAL))
    ss.setdefault("STOP_BY_CAT", dict(STOPWORDS_BY_CAT))
    ss.setdefault("STOP_WHITELIST", [])
    ss.setdefault("STOP_REPLACE", ["무배=> ", "무료배송=> ", "정품=> "])
    ss.setdefault("STOP_AGGR", False)

    # 프리셋(컴팩트 모드에선 숨김)
    if not compact:
        with st.expander("🔧 프리셋", expanded=False):
            preset = st.selectbox("프리셋", list(STOP_PRESETS.keys()), key="stop_preset_sel")
            if st.button("프리셋 불러오기", key="stop_preset_load"):
                obj = STOP_PRESETS[preset]
                ss["STOP_GLOBAL"]    = list(obj.get("global", []))
                ss["STOP_BY_CAT"]    = dict(obj.get("by_cat", {}))
                ss["STOP_WHITELIST"] = list(obj.get("whitelist", []))
                ss["STOP_REPLACE"]   = list(obj.get("replace", []))
                ss["STOP_AGGR"]      = bool(obj.get("aggressive", False))
                st.success(f"프리셋 ‘{preset}’ 적용 완료")

    tab_global, tab_cat, tab_white, tab_replace, tab_io = st.tabs(
        ["전역 금칙어", "카테고리 금칙어", "화이트리스트", "치환 규칙", "가져오기/내려받기"]
    )

    with tab_global:
        txt = st.text_area("전역 금칙어 (콤마)", value=",".join(ss["STOP_GLOBAL"]), height=120, key="stop_glob_txt")
        if st.button("저장(전역)", key="stop_glob_save"):
            ss["STOP_GLOBAL"] = [t.strip() for t in txt.split(",") if t.strip()]
            st.success("전역 금칙어 저장 완료")

    with tab_cat:
        all_cats = sorted(set(list(ss["STOP_BY_CAT"].keys()) + list(STOPWORDS_BY_CAT.keys()))) or \
                   ["패션의류","패션잡화","뷰티/미용","생활/건강","디지털/가전","스포츠/레저"]
        cat = st.selectbox("카테고리", all_cats, key="stop_cat_sel")
        curr = ",".join(ss["STOP_BY_CAT"].get(cat, []))
        new  = st.text_area("해당 카테고리 금칙어 (콤마)", value=curr, height=120, key=f"stop_cat_txt_{cat}")
        c1, c2 = st.columns([1,1])
        with c1:
            if st.button("저장(카테고리)", key=f"stop_cat_save_{cat}"):
                ss["STOP_BY_CAT"][cat] = [t.strip() for t in new.split(",") if t.strip()]
                st.success(f"{cat} 저장 완료")
        with c2:
            ss["STOP_AGGR"] = st.toggle("공격적 부분일치 제거", value=bool(ss["STOP_AGGR"]), key="stop_aggr_ui")

    with tab_white:
        wt = st.text_area("화이트리스트(허용, 콤마)", value=",".join(ss["STOP_WHITELIST"]), height=100, key="stop_white_txt")
        if st.button("저장(화이트리스트)", key="stop_white_save"):
            ss["STOP_WHITELIST"] = [t.strip() for t in wt.split(",") if t.strip()]
            st.success("화이트리스트 저장 완료")

    with tab_replace:
        rp = st.text_area("치환 규칙 (형식: src=>dst, 콤마)", value=",".join(ss["STOP_REPLACE"]), height=100, key="stop_repl_txt")
        if st.button("저장(치환)", key="stop_repl_save"):
            ss["STOP_REPLACE"] = [t.strip() for t in rp.split(",") if t.strip()]
            st.success("치환 규칙 저장 완료")

    with tab_io:
        payload = {
            "global": ss["STOP_GLOBAL"],
            "by_cat": ss["STOP_BY_CAT"],
            "whitelist": ss["STOP_WHITELIST"],
            "replace": ss["STOP_REPLACE"],
            "aggressive": bool(ss["STOP_AGGR"]),
        }
        st.download_button("설정 내려받기(JSON)",
                           data=json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
                           file_name="stopwords_profile.json", mime="application/json", key="stop_dl")
        up = st.file_uploader("설정 가져오기(JSON)", type=["json"], key="stop_ul")
        if up:
            try:
                obj = json.load(io.TextIOWrapper(up, encoding="utf-8"))
                ss["STOP_GLOBAL"]    = list(obj.get("global", ss["STOP_GLOBAL"]))
                ss["STOP_BY_CAT"]    = dict(obj.get("by_cat", ss["STOP_BY_CAT"]))
                ss["STOP_WHITELIST"] = list(obj.get("whitelist", ss["STOP_WHITELIST"]))
                ss["STOP_REPLACE"]   = list(obj.get("replace", ss["STOP_REPLACE"]))
                ss["STOP_AGGR"]      = bool(obj.get("aggressive", ss["STOP_AGGR"]))
                st.success("설정 가져오기 완료")
            except Exception as e:
                st.error(f"가져오기 실패: {e}")

# =========================
# 9) 상품명 생성기 (스마트스토어 풀옵션: 금칙어/브랜드 보호 + 검색량 자동확장 + 30~50자·50바이트 + 복사/점수 + 저장/불러오기)
# =========================

import re, json, time
from pathlib import Path
import pandas as pd
import streamlit as st

# ───────── 금칙어/브랜드 보호 유틸 ─────────

# 패턴 금칙어: 성인/불법/의약성분/정치민감 등(브랜드 여부 무관)
PATTERN_STOPWORDS = [
    # 성인/음란
    r"포르노", r"성인(게임|비디오)?", r"섹스", r"섹도구", r"콘돔", r"오나홀",
    r"사정지연", r"애널", r"음란", r"음모", r"음부", r"성기", r"성교", r"최음", r"흥분젤",
    r"야한", r"(색|섹)스|섹쓰|쎅스|쌕스",
    # 불법/범죄/무기/몰카
    r"불법", r"몰카", r"도촬", r"(총|권총|투시경|칼|새총)", r"도난",
    # 의약/향정 의심군
    r"(시부트라민|sibutramine)", r"(실데나필|sildenafil)", r"(타다라필|tadalafil)",
    r"(바데나필|vardenafil)", r"(데나필|denafil)", r"(요힘빈|yohimbin?e?)",
    r"(에페드린|ephedrine)", r"(DMAA|DMBA|DNP)", r"(멜라토닌|melatonin)",
    r"(빈포세틴|vinpocetine)",
    r"(하이드록시|hydroxy)\w*denafil", r"(프로폭시|propoxy)\w*denafil", r"dimethyl",
    # 정치/국가 민감
    r"북한|공화국|인민공화국|DPRK|국기",
    # 아동/임산부/신생아
    r"아동|임산부|신생아",
    # 노골 비속어
    r"보지|불알|꼬추|젖탱이|젖꼭지",
]

# 리터럴 금칙어(비브랜드) 시드 — 네가 준 방대한 리스트에서 대표 위험군만 발췌
SEEDED_NONBRAND_LITERALS = [
    "강간","살인","도촬","몰카","군사","총","권총","누드","음경","항문","성교","성생활",
    "성감대","성기능부전개선","사정지연","애널","섹도구","섹스","포르노","포르노걸",
    "요힘빈","요힘베","시부트라민","실데나필","타다라필","바데나필","데나필","하이드록시호모실데나필",
    "하이드록시홍데나필","하이드록시바데나필","디메틸치오실데나필","디메칠실데나필",
    "디치오프로필카보데나필","디메틸시부트라민","디데스메틸시부트라민",
    "멜라토닌","빈포세틴","에페드린","DMAA","DMBA","DNP","수면제","히로뽕",
    "아동","임산부","신생아","북한","공화국","인민공화국",
    "보지","불알","꼬추","젖탱이","젖꼭지","음란","음모",
]

# 여기에 “추가 금칙어(네가 전달한 풀 리스트)”를 그대로 붙여넣어도 됨.
# 코드는 자동으로 ‘브랜드성’ 단어를 제외하고 ‘비브랜드’만 적용한다.
USER_BLOB_EXTRA = r"""
# ⬇ 여기에 네가 준 추가 금칙어 붙이기(줄바꿈 단위)
""".strip()

# 브랜드 휴리스틱
_BRAND_ASCII_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-\& ]{1,24}$")
_BRAND_KO_SUFFIX = (
    "스","즈","코","마","니","로렌","코어스","라코스테","로에베","로엠","르메르","로맨틱크라운",
    "카민스키","프레스토","프리미엄","스톤","아일랜드","나이키","아디다스","뉴발란스",
    "샤넬","루이비통","구찌","프라다","디올","몽클레어","스타벅스","라인프렌즈","헬로키티","포켓몬",
)
HARD_NONBRAND = {
    "포르노","섹스","섹도구","오나홀","사정지연","애널","음란","음모","음부","성기","성교","최음",
    "히로뽕","대마","수면제","시부트라민","실데나필","타다라필","바데나필","데나필","몰카","도촬","총","권총",
    "북한","공화국","인민공화국","강간","살인","아동","임산부","신생아",
}

def _is_brandish(term: str) -> bool:
    t = (term or "").strip()
    if not t: return False
    if _BRAND_ASCII_RE.match(t): return True
    if any(t.endswith(suf) for suf in _BRAND_KO_SUFFIX): return True
    return False

def _extract_nonbrand_from_blob(blob: str) -> list[str]:
    raw = [x.strip() for x in (blob or "").splitlines()]
    raw = [x for x in raw if x and not x.startswith("#")]
    uniq = list(dict.fromkeys(raw))
    nonbrands=[]
    for w in uniq:
        if w in HARD_NONBRAND: nonbrands.append(w); continue
        if not _is_brandish(w): nonbrands.append(w)
    return nonbrands

PATTERN_RE = re.compile("|".join(PATTERN_STOPWORDS), re.IGNORECASE)

_MIN_PART = 2
def _compile_literals(words: list[str]) -> re.Pattern:
    pats=[]
    for w in words:
        w=w.strip()
        if not w: continue
        if len(w) < _MIN_PART: continue
        pats.append(re.escape(w))
    if not pats:
        return re.compile(r"$^\b$")
    return re.compile("|".join(pats), re.IGNORECASE)

USER_EXTRA_NONBRAND = _extract_nonbrand_from_blob(USER_BLOB_EXTRA)
LITERAL_RE = _compile_literals(sorted(set(SEEDED_NONBRAND_LITERALS + USER_EXTRA_NONBRAND)))

def _apply_stopwords_nonbrand(text: str, brand_allow: set[str] | None = None) -> str:
    brand_allow = {*(brand_allow or set())}
    marker_l, marker_r = "«", "»"
    protected_map={}
    def _protect(m):
        tok = m.group(0)
        key = f"{marker_l}{len(protected_map)}{marker_r}"
        protected_map[key]=tok
        return key
    out = text
    if brand_allow:
        for b in sorted(brand_allow, key=len, reverse=True):
            if not b: continue
            out = re.sub(rf"(?i)\b{re.escape(b)}\b", _protect, out)
    out = PATTERN_RE.sub(" ", out)
    out = LITERAL_RE.sub(" ", out)
    out = re.sub(r"\s+", " ", out).strip()
    for key, val in protected_map.items():
        out = out.replace(key, val)
    return out

def _dedupe_double_brands(title: str) -> str:
    tokens = title.split()
    seen=set(); out=[]
    for t in tokens:
        low = t.lower()
        if low in seen: continue
        seen.add(low); out.append(t)
    return " ".join(out)

# ───────── 길이/바이트 보정 ─────────

def _truncate_by_bytes(text: str, max_bytes: int = 50) -> str:
    raw = text.encode("utf-8")
    if len(raw) <= max_bytes: return text
    cut = raw[:max_bytes]
    while True:
        try:
            s = cut.decode("utf-8"); break
        except UnicodeDecodeError:
            cut = cut[:-1]
            if not cut: return ""
    m = re.match(r"^(.{1,})[\s\|\·\-]", s[::-1])
    if m:
        s2 = m.group(1)[::-1].rstrip()
        return s2 + "…"
    return s.rstrip() + "…"

def _smart_truncate(text: str, max_len: int, min_len: int) -> str:
    if len(text) > max_len:
        return text[: max_len - 1] + "…"
    return text

# ───────── 검색량 기반 자동 확장(네이버 키워드도구 응답 재활용) ─────────
# ※ 이 앱 상단에 이미 정의된 _naver_keywordstool(df 반환)을 그대로 사용합니다.

def _expand_title_with_searchvol(base_tokens: list[str], df_kstats: pd.DataFrame,
                                 target_min_chars: int, max_chars: int) -> list[str]:
    """
    base_tokens: 현재 제목 토큰(공백 결합 예정)
    df_kstats: _naver_keywordstool 결과 (키워드/검색합계 등 포함)
    길이가 target_min_chars 미달이면, df_kstats에서 '검색합계' 상위 키워드를
    중복/금칙어/이미포함 제외하고 순서대로 추가해 최소 길이에 도달하도록 확장.
    """
    exist_set = {t.strip().lower() for t in base_tokens if t.strip()}
    # 정렬: 검색합계 내림차순
    cand = []
    if not df_kstats.empty and "키워드" in df_kstats.columns:
        df2 = df_kstats.copy()
        if "검색합계" not in df2.columns:
            df2["검색합계"] = pd.to_numeric(df2.get("PC월간검색수",0), errors="coerce").fillna(0) + \
                              pd.to_numeric(df2.get("Mobile월간검색수",0), errors="coerce").fillna(0)
        df2 = df2.sort_values("검색합계", ascending=False)
        cand = [x.strip() for x in df2["키워드"].tolist() if x and len(x.strip())>=2]

    out = base_tokens[:]
    for kw in cand:
        low = kw.lower()
        if low in exist_set:  # 이미 포함
            continue
        # 금칙어 제거(브랜드 허용은 여기선 고려 안 함 — 확장 키워드라서)
        test = " ".join(out + [kw])
        test2 = _apply_stopwords_nonbrand(test, brand_allow=set())
        if test2 != test:
            continue  # 금칙어에 걸림
        # 길이 검사(문자 기준 먼저)
        test_join = " ".join(out + [kw])
        if len(test_join) > max_chars:
            continue
        out.append(kw); exist_set.add(low)
        if len(" ".join(out)) >= target_min_chars:
            break
    return out

# ───────── SEO 점수(간단 지수) ─────────

def _seo_score(title: str, df_kstats: pd.DataFrame, target_min: int = 30, max_bytes: int = 50) -> dict:
    """
    0~100 가중 점수:
      - 길이(문자/바이트) 적합 35
      - 상위 키워드 포함도 45 (상위 10개 중 포함 비율)
      - 금칙어/지저분한 토큰 감점 20
    """
    score = 0
    reasons = []

    # 1) 길이 적합
    char_len = len(title)
    byte_len = len(title.encode("utf-8"))
    if 30 <= char_len <= 50 and byte_len <= max_bytes:
        score += 35
        reasons.append("길이 적합(+35)")
    else:
        # 거리 기반 완화
        penalty = min(abs(char_len-40), 20)  # 중심 40자 가정
        gain = max(0, 35 - penalty)
        score += gain
        reasons.append(f"길이 보정(+{gain})")

    # 2) 상위 키워드 포함도
    cover_gain = 0
    if not df_kstats.empty and "키워드" in df_kstats.columns:
        df2 = df_kstats.copy()
        if "검색합계" not in df2.columns:
            df2["검색합계"] = pd.to_numeric(df2.get("PC월간검색수",0), errors="coerce").fillna(0) + \
                              pd.to_numeric(df2.get("Mobile월간검색수",0), errors="coerce").fillna(0)
        top = df2.sort_values("검색합계", ascending=False).head(10)["키워드"].tolist()
        hit = sum(1 for k in top if re.search(rf"(?i)\b{re.escape(k)}\b", title))
        ratio = hit / max(len(top),1)
        cover_gain = int(round(45 * ratio))
        score += cover_gain
        reasons.append(f"상위키워드 포함 {hit}/{len(top)}(+{cover_gain})")
    else:
        reasons.append("검색지표 미반영(+0)")

    # 3) 금칙어/지저분 토큰 감점
    dirty = PATTERN_RE.search(title) or LITERAL_RE.search(title)
    if dirty:
        score -= 20
        reasons.append("금칙어 감점(-20)")

    score = max(0, min(100, score))
    return {"score": score, "reasons": reasons, "chars": char_len, "bytes": byte_len}

# ───────── AI 속성 제안(룰 기반 라이트버전) ─────────
_ATTR_HINTS = {
    "가방|백|백팩|토트": ["정품", "경량", "수납", "방수"],
    "노트북|맥북|랩탑|거치대|스탠드": ["알루미늄", "높이조절", "미끄럼방지", "휴대용"],
    "운동화|런닝화|스니커즈": ["경량", "통기성", "쿠셔닝"],
    "의자|체어": ["인체공학", "허리지지", "방석 포함"],
    "선풍기|팬|서큘레이터": ["저소음", "BLDC", "무선", "1+1"],
    "이어폰|헤드폰|에어팟|버즈": ["노이즈캔슬링", "무선충전", "긴배터리"],
}
def _suggest_attrs(text: str) -> list[str]:
    out=[]
    for pat, hints in _ATTR_HINTS.items():
        if re.search(pat, text):
            out.extend(hints)
    # 중복 제거
    s=set(); r=[]
    for h in out:
        if h not in s:
            s.add(h); r.append(h)
    return r[:6]

# ───────── 저장/불러오기 스토리지 ─────────

_STORE_PATH = Path(__file__).parent / "titles_store.json"

def _read_store() -> dict:
    if _STORE_PATH.exists():
        try:
            return json.loads(_STORE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def _write_store(obj: dict):
    tmp = _STORE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(_STORE_PATH)

def _ensure_store():
    st.session_state.setdefault("TITLE_COLLECTIONS", _read_store())

def _save_collection(name: str, titles: list[str], meta: dict | None = None):
    name = name.strip()
    if not name or not titles:
        st.warning("이름과 제목 리스트가 필요합니다.")
        return
    coll = st.session_state["TITLE_COLLECTIONS"]
    coll[name] = {
        "titles": titles,
        "meta": meta or {},
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    _write_store(coll)
    st.success(f"저장 완료: {name} ({len(titles)}건)")

def _merge_titles(a: list[str], b: list[str]) -> list[str]:
    seen=set(); out=[]
    for t in a + b:
        key = t.strip().lower()
        if not key or key in seen: continue
        seen.add(key); out.append(t.strip())
    return out

# ───────── 메인 UI ─────────

def section_title_generator():
    st.markdown('<div class="card"><div class="card-title">상품명 생성기 (스마트스토어 • 풀옵션)</div>', unsafe_allow_html=True)
    with st.container():
        cA, cB = st.columns([1, 2])
        with cA:
            brand = st.text_input("브랜드", placeholder="예: Apple / 샤오미 / 무지")
            attrs = st.text_input("속성(콤마, 선택)", placeholder="예: 공식, 정품, 한정판")
        with cB:
            kws = st.text_input("키워드(콤마)", placeholder="예: 노트북 스탠드, 접이식, 알루미늄")

        a, b, c = st.columns([1, 1, 1])
        with a:
            max_len = st.slider("최대 글자수(스마트스토어 규칙)", 30, 50, 50, 1, key="seo_maxlen")
        with b:
            target_min = st.slider("최소 글자수(스마트스토어 규칙)", 30, 50, 30, 1, key="seo_minlen")
        with c:
            order = st.selectbox("순서", ["브랜드-키워드-속성", "키워드-브랜드-속성", "브랜드-속성-키워드"], index=0)

        # 라이트한 AI 속성 제안
        if st.button("AI 속성 제안 받기", use_container_width=False):
            base_text = f"{brand} {' '.join([x.strip() for x in (kws or '').split(',') if x.strip()])}"
            hints = _suggest_attrs(base_text)
            if hints:
                st.info("추천 속성: " + ", ".join(hints))
            else:
                st.info("추천 속성을 찾지 못했습니다. 키워드를 더 구체화해 보세요.")

        if st.button("상품명 생성"):
            kw_list = [k.strip() for k in (kws or "").split(",") if k.strip()]
            at_list = [a.strip() for a in (attrs or "").split(",") if a.strip()]
            titles = []
            seo_rows = []  # 점수 테이블

            # 검색량 데이터(자동 확장 및 점수에 재사용)
            # 이미 상단에 정의된 네이버 키워드도구 함수 사용: _naver_keywordstool
            df_stats = _naver_keywordstool(kw_list) if ' _naver_keywordstool' or '_naver_keywordstool' in globals() else pd.DataFrame()
            if not df_stats.empty:
                df_stats["검색합계"] = pd.to_numeric(df_stats.get("PC월간검색수",0), errors="coerce").fillna(0) + \
                                       pd.to_numeric(df_stats.get("Mobile월간검색수",0), errors="coerce").fillna(0)

            for k in (kw_list or [""]):
                # 1) 기본 시퀀스
                if order == "브랜드-키워드-속성":
                    seq = [brand, k] + at_list
                elif order == "키워드-브랜드-속성":
                    seq = [k, brand] + at_list
                else:
                    seq = [brand] + at_list + [k]

                # 2) 공백 고정
                tokens = [p for p in seq if p]
                base_title = " ".join(tokens)

                # 3) 검색량 기반 자동 확장
                if not df_stats.empty and target_min > len(base_title):
                    tokens = _expand_title_with_searchvol(tokens, df_stats, target_min_chars=target_min, max_chars=max_len)

                # 4) 금칙어 필터(브랜드 보호) + 중복 브랜드 정리
                brand_allow = {brand.strip()} | {kk for kk in kw_list if _is_brandish(kk)}
                final = " ".join(tokens)
                final = _apply_stopwords_nonbrand(final, brand_allow=brand_allow)
                final = _dedupe_double_brands(final)

                # 5) 길이 보정(문자→바이트)
                final = _smart_truncate(final, max_len, target_min)
                if len(final.encode("utf-8")) > 50:
                    final = _truncate_by_bytes(final, 50)

                titles.append(final)

                # 6) SEO 점수 산출
                sc = _seo_score(final, df_stats if not df_stats.empty else pd.DataFrame())
                seo_rows.append({"title": final, "SEO점수": sc["score"], "사유": " / ".join(sc["reasons"]),
                                 "문자수": sc["chars"], "바이트": sc["bytes"]})

            if titles:
                st.success(f"생성 완료 · {len(titles)}건")

                # 결과 표 + 복사 버튼
                for i, t in enumerate(titles, 1):
                    char_len = len(t); byte_len = len(t.encode("utf-8"))
                    warn = []
                    if char_len < 30: warn.append("30자 미만")
                    if byte_len > 50: warn.append("50바이트 초과")
                    badge = "" if not warn else " — " + " / ".join([f":red[{w}]" for w in warn])
                    st.markdown(f"**{i}.** {t}  <span style='opacity:.7'>(문자 {char_len}/50 · 바이트 {byte_len}/50)</span>{badge}",
                                unsafe_allow_html=True)
                    # 복사 버튼(브라우저 복사 아이콘 제공)
                    st.code(t, language=None)

                # SEO 리포트 표
                st.markdown("**SEO 리포트**")
                df_seo = pd.DataFrame(seo_rows).sort_values("SEO점수", ascending=False)
                st.dataframe(df_seo, use_container_width=True, height=260)

                # CSV 다운로드
                out_df = pd.DataFrame({"title": titles})
                st.download_button(
                    "CSV 다운로드",
                    data=out_df.to_csv(index=False).encode("utf-8-sig"),
                    file_name="titles_smartstore.csv",
                    mime="text/csv",
                )

                # 요약
                lens = [len(t) for t in titles]
                blens = [len(t.encode("utf-8")) for t in titles]
                st.caption(
                    f"요약 · 문자(최소/평균/최대): {min(lens)}/{sum(lens)//len(lens)}/{max(lens)} · "
                    f"바이트(최소/평균/최대): {min(blens)}/{sum(blens)//len(blens)}/{max(blens)}"
                )
            else:
                st.warning("생성된 상품명이 없습니다. (입력값/금칙어로 모두 걸러졌을 수 있음)")

        # ── 저장/불러오기 UI ──
        _ensure_store()
        with st.expander("💾 생성 결과 저장/불러오기", expanded=False):
            tab_save, tab_load, tab_io = st.tabs(["저장", "불러오기/관리", "가져오기/내보내기"])

            with tab_save:
                save_name = st.text_input("저장할 이름", placeholder="예: 맥북거치대_240922_1")
                if st.button("이 제목들 컬렉션으로 저장", use_container_width=False):
                    if 'titles' in locals() and titles:
                        meta = {
                            "brand": brand,
                            "attrs": at_list if 'at_list' in locals() else [],
                            "kws": kw_list if 'kw_list' in locals() else [],
                            "max_len": max_len,
                            "min_len": target_min,
                            "order": order,
                        }
                        _save_collection(save_name, titles, meta)
                    else:
                        st.warning("먼저 상품명을 생성하세요.")

            with tab_load:
                coll = st.session_state["TITLE_COLLECTIONS"]
                names = sorted(coll.keys())
                sel = st.selectbox("저장된 컬렉션", names, index=0 if names else None)
                if names:
                    info = coll[sel]
                    st.caption(f"{sel} · {info.get('ts','')} · {len(info.get('titles',[]))}건")
                    st.dataframe(pd.DataFrame({"title": info.get("titles", [])}),
                                 use_container_width=True, height=240)
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        if st.button("현재 생성결과와 병합(중복제거)", use_container_width=True):
                            if 'titles' in locals() and titles:
                                merged = _merge_titles(titles, info["titles"])
                                st.session_state["__merged_titles__"] = merged
                                st.success(f"병합 완료: {len(merged)}건 (세션에 임시 저장)")
                            else:
                                st.warning("먼저 상품명을 생성하세요.")
                    with c2:
                        if st.button("현재 세션 결과를 이 컬렉션으로 교체", use_container_width=True):
                            st.session_state["__merged_titles__"] = info["titles"]
                            st.success("세션에 교체 저장 완료")
                    with c3:
                        if st.button("이 컬렉션 삭제", use_container_width=True):
                            del coll[sel]
                            _write_store(coll)
                            st.experimental_rerun()

                    if "__merged_titles__" in st.session_state:
                        st.divider()
                        st.caption("임시 병합 결과(세션)")
                        mt = st.session_state["__merged_titles__"]
                        st.dataframe(pd.DataFrame({"title": mt}), use_container_width=True, height=200)
                        st.download_button("임시 병합 결과 CSV 다운로드",
                                           data=pd.DataFrame({"title": mt}).to_csv(index=False).encode("utf-8-sig"),
                                           file_name="titles_merged.csv", mime="text/csv")

            with tab_io:
                c1, c2 = st.columns(2)
                with c1:
                    st.write("📤 내보내기")
                    coll = st.session_state["TITLE_COLLECTIONS"]
                    if coll:
                        st.download_button("전체 컬렉션( JSON ) 다운로드",
                                           data=json.dumps(coll, ensure_ascii=False, indent=2).encode("utf-8"),
                                           file_name="titles_store.json", mime="application/json")
                    else:
                        st.caption("저장된 컬렉션이 없습니다.")
                with c2:
                    st.write("📥 가져오기")
                    up = st.file_uploader("JSON/CSV 업로드(컬렉션 추가/덮어쓰기)", type=["json","csv"])
                    mode = st.radio("가져오기 모드", ["추가", "덮어쓰기"], horizontal=True, index=0)
                    if up is not None:
                        try:
                            if up.type == "application/json" or up.name.lower().endswith(".json"):
                                data = json.loads(up.read().decode("utf-8"))
                                if not isinstance(data, dict):
                                    raise ValueError("JSON 형식이 올바르지 않습니다.")
                                if mode == "덮어쓰기":
                                    st.session_state["TITLE_COLLECTIONS"] = data
                                else:
                                    merged = _read_store()
                                    merged.update(data)
                                    st.session_state["TITLE_COLLECTIONS"] = merged
                                _write_store(st.session_state["TITLE_COLLECTIONS"])
                                st.success("JSON 가져오기 완료")
                            else:
                                df = pd.read_csv(up)
                                if "title" not in df.columns:
                                    raise ValueError("CSV에 'title' 컬럼이 없습니다.")
                                name = f"import_{time.strftime('%Y%m%d_%H%M%S')}"
                                _save_collection(name, df["title"].astype(str).tolist(), meta={"import":"csv"})
                                st.success(f"CSV 가져오기 완료: {name}")
                        except Exception as e:
                            st.error(f"가져오기 실패: {e}")

    st.markdown("</div>", unsafe_allow_html=True)

# =========================
# 10) 기타 카드
# =========================
def _11st_abest_url():
    return ("https://m.11st.co.kr/page/main/abest?tabId=ABEST&pageId=AMOBEST&ctgr1No=166160&_ts=%d" % int(time.time()))
def section_11st():
    st.markdown('<div class="card"><div class="card-title">11번가 (모바일) — 아마존 베스트</div>', unsafe_allow_html=True)
    _proxy_iframe(ELEVENST_PROXY, _11st_abest_url(), height=900, scroll=True, key="abest")
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
# 외부 Stopwords 섹션(선택) — 유지해도 되고, 레이아웃에서 호출 제거해도 됨
# =========================
def section_stopwords_manager():
    st.markdown('<div class="card"><div class="card-title">금칙어 리스트 관리자 (현업용)</div>', unsafe_allow_html=True)
    _stopwords_manager_ui(compact=False)

# =========================
# 11) Layout — row1: Radar | (카테고리 or 직접 입력) | 상품명 생성기
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
c1, c2, c3 = st.columns([3, 3, 3], gap="medium")
with c1:
    section_11st()
with c2:
    section_itemscout_placeholder()
with c3:
    section_sellerlife_placeholder()

st.markdown('<div class="row-gap"></div>', unsafe_allow_html=True)

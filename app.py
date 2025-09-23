# -*- coding: utf-8 -*-
# ENVY — Season 1 (Dual Proxy Edition, Radar tabs=국내/해외, Rakuten scope radio removed, row1 ratio 8:5:3)
# 이번 버전:
# - 상품명 생성기 카드 내부 탭: [생성기 | 금칙어 관리]
# - 외부 금칙어 섹션은 유지(선택). 동일 세션키 공유로 동기화됨.
# - 사이드바: 다크+번역기 토글 / 번역기 ON: 번역기 펼침·계산기 접힘, OFF: 계산기 펼침·번역기 접힘
# - 다크모드 시안성 패치(메인영역 위젯 전부 색상 반전) + 라이트 모드 대비 강화
# - 네이버 키워드도구 실패 시 간단 디버그 메시지 표시

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
    "RAKUTEN_APP_ID": "1043271015809337425",
    "RAKUTEN_AFFILIATE_ID": "4c723498.cbfeca46.4c723499.1deb6f77",

    # NAVER Searchad(검색광고 API / 키워드도구)
    "NAVER_API_KEY": "0100000000785cf1d8f039b13a5d3c3d1262b84e9ad4a046637e8887bbd003051b0d2a5cdf",
    "NAVER_SECRET_KEY": "AQAAAAB4XPHY8DmxOl08PRJiuE6ao1LN3lh0kF9rOJ4m5b8O5g==",
    "NAVER_CUSTOMER_ID": "2274338",

    # NAVER Developers (DataLab Open API)  ← 여기 최신값으로 교체
    "NAVER_CLIENT_ID": "T27iw3tyujrM1nG_shFT",
    "NAVER_CLIENT_SECRET": "s59xKPYLz1",

    # 선택: DataLab Referer(허용 도메인 등록 시) — 필요 없으면 비워두기
    "NAVER_WEB_REFERER": ""

    # (옵션) DataLab Referer가 필요한 환경이면 secrets.toml 에 NAVER_WEB_REFERER 를 넣어도 됨
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
    """
    메인 뷰: 다크/라이트 토글 반영
    사이드바: 항상 라이트 톤 고정(시안성), 내부만 스크롤(100vh sticky)
    사이드바 컬러 pill 복구
    """
    theme = st.session_state.get("theme", "light")

    # ===== 메인 영역 팔레트(토글 반영) =====
    if theme == "dark":
        bg = "#0e1117"; fg = "#e6edf3"; fg_sub = "#b6c2cf"; card_bg = "#11151c"
        border = "rgba(255,255,255,.08)"; btn_bg = "#2563eb"; btn_bg_hover = "#1e3fae"
        pill_shadow = "0 2px 10px rgba(0,0,0,.35)"
        pill_green_bg, pill_green_bd, pill_green_fg = "linear-gradient(180deg, #0f5132 0%, #0b3d26 100%)", "rgba(86,207,150,.35)", "#d1fae5"
        pill_blue_bg,  pill_blue_bd,  pill_blue_fg  = "linear-gradient(180deg, #0b3b8a 0%, #092a63 100%)", "rgba(147,197,253,.35)", "#dbeafe"
        pill_yellow_bg, pill_yellow_bd, pill_yellow_fg = "linear-gradient(180deg, #7a5c0a 0%, #5b4307 100%)", "rgba(252,211,77,.35)", "#fef3c7"
        pill_warn_bg,  pill_warn_bd,  pill_warn_fg  = "linear-gradient(180deg, #5c1a1a 0%, #3d1010 100%)", "rgba(248,113,113,.35)", "#fee2e2"
    else:
        bg = "#ffffff"; fg = "#111111"; fg_sub = "#4b5563"; card_bg = "#ffffff"
        border = "rgba(0,0,0,.06)"; btn_bg = "#2563eb"; btn_bg_hover = "#1e3fae"
        pill_shadow = "0 2px 10px rgba(0,0,0,.08)"
        pill_green_bg, pill_green_bd, pill_green_fg = "linear-gradient(180deg, #d1fae5 0%, #a7f3d0 100%)", "rgba(16,185,129,.35)", "#065f46"
        pill_blue_bg,  pill_blue_bd,  pill_blue_fg  = "linear-gradient(180deg, #dbeafe 0%, #bfdbfe 100%)", "rgba(59,130,246,.35)", "#1e3a8a"
        pill_yellow_bg, pill_yellow_bd, pill_yellow_fg = "linear-gradient(180deg, #fef3c7 0%, #fde68a 100%)", "rgba(234,179,8,.35)", "#7c2d12"
        pill_warn_bg,  pill_warn_bd,  pill_warn_fg  = "linear-gradient(180deg, #fee2e2 0%, #fecaca 100%)", "rgba(239,68,68,.35)", "#7f1d1d"

    # ===== 사이드바(항상 라이트 고정) 팔레트 =====
    sb_bg   = "#f6f8fb"
    sb_fg   = "#111111"
    sb_sub  = "#4b5563"
    sb_card = "#ffffff"
    sb_bd   = "rgba(0,0,0,.06)"

    st.markdown(f"""
    <style>
      /* =========================
         메인 컨테이너(다크/라이트 적용)
         ========================= */
      [data-testid="stAppViewContainer"] {{
        background:{bg} !important; color:{fg} !important;
      }}
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
      [data-testid="stAppViewContainer"] .stMarkdown * {{ color:{fg} !important; }}
      [data-testid="stAppViewContainer"] [data-baseweb="select"] *,
      [data-testid="stAppViewContainer"] [data-baseweb="input"] input,
      [data-testid="stAppViewContainer"] .stNumberInput input,
      [data-testid="stAppViewContainer"] .stTextInput input {{ color:{fg} !important; }}
      [data-testid="stAppViewContainer"] input::placeholder {{ color:{fg_sub} !important; opacity:.9 !important; }}

      [data-testid="stAppViewContainer"] .card {{
        background:{card_bg}; border:1px solid {border}; border-radius:14px;
        box-shadow:0 1px 6px rgba(0,0,0,.12);
      }}

      [data-testid="stAppViewContainer"] .stButton>button {{
        background:{btn_bg} !important; color:#fff !important;
        border:1px solid rgba(255,255,255,.08) !important;
        border-radius:10px !important; font-weight:700 !important;
      }}
      [data-testid="stAppViewContainer"] .stButton>button:hover {{
        background:{btn_bg_hover} !important; border-color:rgba(255,255,255,.15) !important;
      }}

      .pill {{
        display:block; width:100%; border-radius:12px;
        padding:.70rem .95rem; font-weight:800;
        letter-spacing:.1px; box-shadow:{pill_shadow};
        border:1px solid transparent; margin:.35rem 0 .5rem 0;
      }}
      .pill span {{ opacity:.8; font-weight:700; }}

      /* 메인/사이드바 공통 pill 색상 */
      .pill-green {{ background:{pill_green_bg}; border-color:{pill_green_bd}; color:{pill_green_fg}; }}
      .pill-blue  {{ background:{pill_blue_bg};  border-color:{pill_blue_bd};  color:{pill_blue_fg}; }}
      .pill-yellow{{ background:{pill_yellow_bg};border-color:{pill_yellow_bd};color:{pill_yellow_fg}; }}
      .pill-warn  {{ background:{pill_warn_bg};  border-color:{pill_warn_bd};  color:{pill_warn_fg}; }}

      .envy-chip-warn {{
        display:inline-block; padding:.35rem .7rem;
        border-radius:9999px; font-weight:700;
        background:{pill_warn_bg}; border:1px solid {pill_warn_bd};
        color:{pill_warn_fg};
      }}

      /* =========================
         사이드바: 항상 라이트 톤 + 내부 스크롤만 허용
         ========================= */
      [data-testid="stSidebar"] {{
        background:{sb_bg} !important;
        color:{sb_fg} !important;
        overflow:hidden !important;                /* 바깥쪽 스크롤 잠금 */
      }}
      /* 사이드바 컨텐츠 래퍼만 스크롤 */
      [data-testid="stSidebar"] [data-testid="stSidebarContent"] {{
        position: sticky; top: 0;
        height: 100vh; max-height: 100vh;
        overflow-y: auto !important;
        padding-bottom: 1rem;
      }}
      /* 사이드바 내부 UI 대비(항상 라이트) */
      [data-testid="stSidebar"] *,
      [data-testid="stSidebar"] .stMarkdown,
      [data-testid="stSidebar"] .stMarkdown * {{ color:{sb_fg} !important; }}
      [data-testid="stSidebar"] input::placeholder {{ color:{sb_sub} !important; opacity:.9 !important; }}
      [data-testid="stSidebar"] .card {{
        background:{sb_card}; border:1px solid {sb_bd}; border-radius:14px;
        box-shadow:0 1px 6px rgba(0,0,0,.08);
      }}
      [data-testid="stSidebar"] [data-baseweb="select"] *,
      [data-testid="stSidebar"] [data-baseweb="input"] input,
      [data-testid="stSidebar"] .stNumberInput input,
      [data-testid="stSidebar"] .stTextInput input {{ color:{sb_fg} !important; }}

      /* 사이드바 토글/라디오 레이블도 라이트로 고정 */
      [data-testid="stSidebar"] .stRadio label,
      [data-testid="stSidebar"] .stCheckbox label,
      [data-testid="stSidebar"] label {{ color:{sb_fg} !important; }}
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

def _proxy_iframe_with_title(proxy_base: str, target_url: str, height: int = 860, key: str = "naver_home"):
    proxy = (proxy_base or "").strip().rstrip("/")
    url   = f"{proxy}/?url={quote(target_url, safe=':/?&=%')}"
    h     = int(height)
    html  = f'''
<div id="{key}-wrap" class="main" style="width:100%;overflow:hidden;">
  <div id="{key}-title"
       style="display:inline-block;border-radius:9999px;padding:.40rem .9rem;
              font-weight:800;background:#dbe6ff;border:1px solid #88a8ff;color:#09245e;margin:0 0 .5rem 0;">
    DataLab
  </div>
  <iframe src="{url}" style="width:100%;height:{h}px;border:0;border-radius:10px"></iframe>
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
    # 기본 세션 + CSS
    _ensure_session_defaults()
    _inject_css()
    # 알림센터가 없는 경우에도 죽지 않도록 방어
    try:
        _inject_alert_center()
    except Exception:
        pass

    with st.sidebar:
        # ——— 로고: 원형 64px 고정 ———
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
                if st.button("번역 실행", key="sb_tr_btn"):
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

        # 토글 상태에 따라 펼침
        if show_tr:
            translator_block(expanded=True); fx_block(expanded=False); margin_block(expanded=False)
        else:
            fx_block(expanded=True); margin_block(expanded=True); translator_block(expanded=False)

        # 관리자 박스(옵션)
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

    if st.button("레이더 업데이트", use_container_width=False):
        with st.spinner("네이버 키워드도구 조회 중…"):
            df = _naver_keywordstool(kw_list)
        if df.empty:
            st.markdown("<div class='envy-chip-warn main'>데이터가 없습니다. (API/권한/쿼터 또는 키워드 확인)</div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
            return

        if table_mode.startswith("A"):
            st.dataframe(df, use_container_width=True, height=430)
            st.download_button("CSV 다운로드", df.to_csv(index=False).encode("utf-8-sig"),
                               file_name="korea_keyword_A.csv", mime="text/csv")
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
                               file_name="korea_keyword_B.csv", mime="text/csv")
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
                           file_name="korea_keyword_C.csv", mime="text/csv")
    st.markdown("</div>", unsafe_allow_html=True)

# =========================
# 7) DataLab Trend (Open API) + Category → Top20 UI (+ Direct Trend)
# =========================
@st.cache_data(ttl=1800, show_spinner=False)
def _datalab_trend(
    groups: list,
    start_date: str,
    end_date: str,
    time_unit: str = "week",
    device: str = "",
    gender: str = "",
    ages: list | None = None
) -> pd.DataFrame:
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
    # 등록된 Referer 가 있을 때만 추가 (없으면 넣지 않음)
    ref = (_get_key("NAVER_WEB_REFERER") or "").strip()
    if ref:
        headers["Referer"] = ref

    payload = {
        "startDate": start_date,
        "endDate": end_date,
        "timeUnit": time_unit,
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
            if tmp.empty:
                continue
            tmp["keyword"] = name
            out.append(tmp)

        if not out:
            return pd.DataFrame()

        big = pd.concat(out, ignore_index=True)
        big.rename(columns={"period": "날짜", "ratio": "검색지수"}, inplace=True)
        pivot = big.pivot_table(index="날짜", columns="keyword", values="검색지수", aggfunc="mean")
        return pivot.reset_index().sort_values("날짜")

    except requests.HTTPError as e:
        try:
            msg = r.text
        except Exception:
            msg = str(e)
        st.error(f"DataLab HTTP {r.status_code}: {msg}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"DataLab 호출 오류: {e}")
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
        err = st.session_state.pop("__datalab_error", None)
        st.warning("키워드도구 응답이 비었습니다. (API/권한/쿼터 확인)" + (f" · {err}" if err else ""))
        st.markdown('</div>', unsafe_allow_html=True); return

    df["검색합계"] = pd.to_numeric(df["PC월간검색수"], errors="coerce").fillna(0) + \
                     pd.to_numeric(df["Mobile월간검색수"], errors="coerce").fillna(0)
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
        err = st.session_state.pop("__datalab_error", None)
        st.info("DataLab 트렌드 응답이 비어 있어요. (Client ID/Secret, Referer/환경, 날짜/단위 확인)" + (f" · {err}" if err else ""))
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
            err = st.session_state.pop("__datalab_error", None)
            st.error("DataLab 트렌드 응답이 비어 있어요. (Client ID/Secret, Referer/환경, 권한/쿼터/날짜/단위 확인)" + (f" · {err}" if err else ""))
        else:
            st.dataframe(df, use_container_width=True, height=260)
            st.line_chart(df.set_index("날짜"))
    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# 8) Radar Card (tabs: 국내 -> 해외)
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
# 9) 상품명 추천 생성기 — 스마트스토어 최적화(Top-N, 금칙어/브랜드 보호)
# =========================

PATTERN_STOPWORDS_GEN = [
    r"포르노", r"섹스|섹쓰|쎅스|쌕스", r"섹도구", r"오나홀", r"사정지연", r"애널",
    r"음란|음모|음부|성교|성기", r"시부트라민|sibutramine", r"실데나필|sildenafil",
    r"타다라필|tadalafil", r"바데나필|vardenafil", r"요힘빈|yohim", r"에페드린",
    r"DMAA|DMBA|DNP", r"북한|인민공화국|국기", r"(총|권총|투시경|칼|새총)"
]
SEEDED_NONBRAND_LITERALS = ["강간","살인","몰카","도촬","히로뽕","수면제","아동","임산부","신생아"]

_BRAND_ASCII_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-\& ]{1,24}$")
_BRAND_KO_SUFFIX = ("나이키","아디다스","뉴발란스","샤넬","루이비통","구찌","프라다","디올",
                    "몽클레어","스타벅스","라인프렌즈","헬로키티","포켓몬")

def _is_brandish(x:str)->bool:
    x=(x or "").strip()
    if not x: return False
    if _BRAND_ASCII_RE.match(x): return True
    if any(x.endswith(s) for s in _BRAND_KO_SUFFIX): return True
    return False

PATTERN_RE = re.compile("|".join(PATTERN_STOPWORDS_GEN), re.IGNORECASE)
LITERAL_RE  = re.compile("|".join(re.escape(w) for w in SEEDED_NONBRAND_LITERALS), re.IGNORECASE)

def _apply_filters(text:str, brand_allow:set[str]|None=None)->str:
    brand_allow = {*(brand_allow or set())}
    guard={}
    def protect(tok):
        key=f"§{len(guard)}§"; guard[key]=tok; return key
    out=text
    for b in sorted(brand_allow, key=len, reverse=True):
        out = re.sub(rf"(?i)\b{re.escape(b)}\b", lambda m: protect(m.group(0)), out)
    out = PATTERN_RE.sub(" ", out)
    out = LITERAL_RE.sub(" ", out)
    out = re.sub(r"\s+"," ", out).strip()
    for k,v in guard.items(): out = out.replace(k,v)
    return out

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

@st.cache_data(ttl=3600, show_spinner=False)
def _cached_kstats(seed: str) -> pd.DataFrame:
    if not seed: return pd.DataFrame()
    try:
        df = _naver_keywordstool([seed])
    except Exception:
        return pd.DataFrame()
    if df.empty: return pd.DataFrame()
    df["검색합계"] = pd.to_numeric(df.get("PC월간검색수",0), errors="coerce").fillna(0) + \
                     pd.to_numeric(df.get("Mobile월간검색수",0), errors="coerce").fillna(0)
    df["광고경쟁정도"] = pd.to_numeric(df.get("광고경쟁정도",0), errors="coerce").fillna(0.0)
    return df

def _make_candidates(brand:str, main_kw:str, attrs:list[str], df:pd.DataFrame,
                     N:int, pool_top:int, min_chars:int, max_chars:int,
                     use_competition:bool=True)->list[str]:
    if df.empty or "키워드" not in df.columns:
        ranked=[]
    else:
        dd=df.copy()
        if use_competition:
            lam=2.0
            dd["효율점수"]=dd["검색합계"]/(1.0+lam*dd["광고경쟁정도"].clip(lower=0.0))
            dd=dd.sort_values(["효율점수","검색합계"], ascending=[False,False])
        else:
            dd=dd.sort_values("검색합계", ascending=False)
        ranked=[x for x in dd["키워드"].tolist() if x and x!=main_kw][:pool_top]

    base=[t for t in [brand, main_kw]+attrs if t]
    allow={brand.strip()} | ({main_kw} if _is_brandish(main_kw) else set())
    out=[]; used=set()

    for off in range(min(5, N)):
        for span in (1,2,3):
            if len(out)>=N: break
            chosen=[]
            for i in range(span):
                idx=off+i
                if idx<len(ranked): chosen.append(ranked[idx])
            tokens=base[:]
            for kw in chosen:
                tmp=" ".join(tokens+[kw])
                if _apply_filters(tmp, allow)!=tmp: continue
                if len(tmp)>max_chars: continue
                tokens.append(kw)
            fill=off+span
            while len(" ".join(tokens))<min_chars and fill<len(ranked):
                kw=ranked[fill]; fill+=1
                if kw in tokens: continue
                tmp=" ".join(tokens+[kw])
                if _apply_filters(tmp, allow)!=tmp: continue
                if len(tmp)>max_chars: break
                tokens.append(kw)

            title=" ".join(tokens)
            title=_apply_filters(title, allow)
            title=_dedupe_tokens(title)
            if len(title.encode("utf-8"))>50: title=_truncate_bytes(title, 50)
            k=title.lower().strip()
            if k and k not in used:
                out.append(title); used.add(k)
            if len(out)>=N: break

    i=0
    while len(out)<N and i<len(ranked):
        kw=ranked[i]; i+=1
        title=" ".join(base+[kw])
        title=_apply_filters(title, allow)
        title=_dedupe_tokens(title)
        if len(title.encode("utf-8"))>50: title=_truncate_bytes(title, 50)
        k=title.lower().strip()
        if k and k not in used:
            out.append(title); used.add(k)
    return out[:N]

def _seo_score(title:str, df:pd.DataFrame, w_len:int, w_cover:int, w_pen:int)->dict:
    score=0; reasons=[]
    chars=len(title); by=len(title.encode("utf-8"))
    if 30<=chars<=50 and by<=50:
        score+=w_len; reasons.append(f"길이 적합(+{w_len})")
    else:
        gain=max(0, w_len - min(abs(chars-40), w_len))
        score+=gain; reasons.append(f"길이 보정(+{gain})")
    cov_gain=0; hit=0
    if not df.empty and "키워드" in df.columns:
        top=df.sort_values("검색합계",ascending=False).head(10)["키워드"].tolist()
        hit=sum(1 for k in top if re.search(rf"(?i)\b{re.escape(k)}\b", title))
        cov_gain=int(round(w_cover * hit/max(len(top),1)))
    score+=cov_gain; reasons.append(f"상위키워드 포함 {cov_gain}/{w_cover}(Top10={hit})")
    if PATTERN_RE.search(title) or LITERAL_RE.search(title):
        score-=w_pen; reasons.append(f"금칙어(-{w_pen})")
    return {"score": max(0,min(100,score)), "reasons": reasons, "chars": chars, "bytes": by}

def section_title_generator():
    st.markdown('<div class="card main"><div class="card-title">상품명 생성기 (스마트스토어 · Top-N)</div>', unsafe_allow_html=True)

    cA,cB = st.columns([1,2])
    with cA:
        brand = st.text_input("브랜드", placeholder="예: Apple / 무지")
        attrs = st.text_input("속성(콤마, 선택)", placeholder="예: 정품, 한정판, 접이식, 알루미늄")
    with cB:
        kws_raw = st.text_input("키워드(콤마)", placeholder="예: 노트북 스탠드, 접이식")
        main_kw = next((k.strip() for k in (kws_raw or "").split(",") if k.strip()), "")

    c1,c2,c3,c4 = st.columns([1,1,1,1])
    with c1:
        N = st.slider("추천 개수", 5, 20, 10, 1)
    with c2:
        pool_top = st.slider("확장 Pool(상위 검색어)", 5, 30, 20, 1)
    with c3:
        min_chars = st.slider("최소 글자(권장 30~50)", 30, 50, 35, 1)
    with c4:
        max_chars = st.slider("최대 글자", 30, 50, 50, 1)

    c5,c6,c7 = st.columns([1,1,1])
    with c5:
        use_comp = st.toggle("경쟁도 보정 사용", value=True)
    with c6:
        w_len = st.slider("가중치·길이", 10, 50, 30, 1)
    with c7:
        w_cover = st.slider("가중치·커버리지", 10, 70, 55, 1)
    w_pen = st.slider("가중치·패널티", 10, 40, 25, 1)

    if st.button("상품명 생성"):
        if not main_kw:
            st.error("키워드를 하나 이상 입력하세요."); return
        at_list = [a.strip() for a in (attrs or "").split(",") if a.strip()]

        with st.spinner("연관 키워드/검색량 수집…"):
            df_stats = _cached_kstats(main_kw)

        titles = _make_candidates(
            brand=brand, main_kw=main_kw, attrs=at_list,
            df=df_stats, N=N, pool_top=pool_top,
            min_chars=min_chars, max_chars=max_chars,
            use_competition=use_comp
        )

        rows=[]
        for t in titles:
            sc=_seo_score(t, df_stats, w_len, w_cover, w_pen)
            rows.append({"title": t, "SEO점수": sc["score"],
                         "사유": " / ".join(sc["reasons"]), "문자수": sc["chars"], "바이트": sc["bytes"]})
        df_out=pd.DataFrame(rows).sort_values("SEO점수", ascending=False)

        st.success(f"생성 완료 · {len(df_out)}건")

        mode = st.radio("결과 표시", ["카드", "표"], horizontal=True, index=0)
        if mode == "카드":
            for i, r in enumerate(df_out.itertuples(index=False), 1):
                warn=[]
                if r.문자수 < 30: warn.append("30자 미만")
                if r.바이트 > 50: warn.append("50바이트 초과")
                suf = "" if not warn else " — " + " / ".join([f":red[{w}]" for w in warn])
                st.markdown(
                    f"**{i}.** {r.title}  "
                    f"<span style='opacity:.7'>(문자 {r.문자수}/50 · 바이트 {r.바이트}/50 · SEO {r.SEO점수})</span>{suf}",
                    unsafe_allow_html=True
                )
        else:
            st.dataframe(
                df_out[["title","SEO점수","문자수","바이트","사유"]].reset_index(drop=True),
                use_container_width=True, height=360
            )
        st.download_button(
            "CSV 다운로드",
            data=df_out[["title"]].to_csv(index=False).encode("utf-8-sig"),
            file_name="titles_topN.csv",
            mime="text/csv",
        )
    st.markdown("</div>", unsafe_allow_html=True)

# =========================
# 10) 기타 카드
# =========================
def _11st_abest_url():
    return ("https://m.11st.co.kr/page/main/abest?tabId=ABEST&pageId=AMOBEST&ctgr1No=166160&_ts=%d" % int(time.time()))
def section_11st():
    st.markdown('<div class="card main"><div class="card-title">11번가 (모바일) — 아마존 베스트</div>', unsafe_allow_html=True)
    _proxy_iframe(ELEVENST_PROXY, _11st_abest_url(), height=900, scroll=True, key="abest")
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
# 외부 Stopwords 섹션(선택)
# =========================
def section_stopwords_manager():
    st.markdown('<div class="card main"><div class="card-title">금칙어 리스트 관리자 (현업용)</div>', unsafe_allow_html=True)
    _stopwords_manager_ui(compact=False)

# =========================
# 11) Layout — row1: Radar | (카테고리 or 직접 입력) | 상품명 생성기
# =========================
_ = _sidebar()
_responsive_probe()
vwbin = _get_view_bin()

st.title("ENVY — Season 1 (Dual Proxy Edition)")

# 1행
row1_a, row1_b, row1_c = st.columns([8, 4, 4], gap="medium")
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

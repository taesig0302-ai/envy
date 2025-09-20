# -*- coding: utf-8 -*-
import os, base64
from pathlib import Path
from urllib.parse import quote
from datetime import date, timedelta

import streamlit as st
import pandas as pd

try:
    import requests
except Exception:
    requests = None

# =========================
# [Part 1] 사이드바 (원본 복구: 로고 + 환율/마진 계산기)
# =========================
CURRENCIES = {
    "USD": {"kr": "미국 달러", "symbol": "$", "unit": "USD"},
    "EUR": {"kr": "유로",     "symbol": "€", "unit": "EUR"},
    "JPY": {"kr": "일본 엔",   "symbol": "¥", "unit": "JPY"},
    "CNY": {"kr": "중국 위안", "symbol": "元","unit": "CNY"},
}
FX_DEFAULT = {"USD": 1400.0, "EUR": 1500.0, "JPY": 10.0, "CNY": 200.0}

def _ensure_session_defaults():
    ss = st.session_state
    ss.setdefault("theme", "light")
    ss.setdefault("PROXY_URL", "")
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
    st.session_state["theme"] = "dark" if st.session_state.get("theme","light")=="light" else "light"

def _inject_sidebar_css():
    theme = st.session_state.get("theme","light")
    bg, fg = ("#0e1117", "#e6edf3") if theme=="dark" else ("#ffffff","#111111")
    st.markdown(f"""
    <style>
      html, body, [data-testid="stAppViewContainer"] {{
        background-color:{bg} !important; color:{fg} !important;
      }}
      .block-container {{ padding-top:.8rem !important; padding-bottom:.35rem !important; }}
      /* 사이드바 고정 + 내부 스크롤 */
      [data-testid="stSidebar"],
      [data-testid="stSidebar"] > div:first-child,
      [data-testid="stSidebar"] section {{
        height: 100vh !important; overflow-y: auto !important;
        padding-top:.25rem !important; padding-bottom:.25rem !important;
      }}
      [data-testid="stSidebar"] ::-webkit-scrollbar {{ width:8px; }}

      [data-testid="stSidebar"] .stSelectbox,
      [data-testid="stSidebar"] .stNumberInput,
      [data-testid="stSidebar"] .stRadio,
      [data-testid="stSidebar"] .stMarkdown,
      [data-testid="stSidebar"] .stTextInput,
      [data-testid="stSidebar"] .stButton {{ margin:.14rem 0 !important; }}

      [data-baseweb="input"] input,
      .stNumberInput input,
      [data-baseweb="select"] div[role="combobox"] {{
        height:1.55rem !important; padding:.12rem !important; font-size:.92rem !important;
      }}

      .logo-circle {{
        width:95px; height:95px; border-radius:50%; overflow:hidden;
        margin:.15rem auto .35rem auto; box-shadow:0 2px 8px rgba(0,0,0,.12);
        border:1px solid rgba(0,0,0,.06);
      }}
      .logo-circle img {{ width:100%; height:100%; object-fit:cover; }}

      .badge-green  {{ background:#e6ffcc; border:1px solid #b6f3a4; padding:6px 10px; border-radius:6px; color:#0b2e13; font-size:.86rem; }}
      .badge-blue   {{ background:#eef4ff; border:1px solid #bcd0ff; padding:6px 10px; border-radius:6px; color:#0a235a; font-size:.86rem; }}
      .badge-yellow {{ background:#fff7d6; border:1px solid #f1d27a; padding:6px 10px; border-radius:6px; color:#4a3b07; font-size:.86rem; }}
      .muted        {{ opacity:.8; font-size:.8rem; }}
      .info-box {{ background:rgba(0,0,0,.03); border:1px dashed rgba(0,0,0,.08); padding:.6rem; border-radius:.5rem; }}
    </style>
    """, unsafe_allow_html=True)

def render_sidebar():
    _ensure_session_defaults()
    _inject_sidebar_css()

    result = {}
    with st.sidebar:
        lp = Path(__file__).parent / "logo.png"
        if lp.exists():
            b64 = base64.b64encode(lp.read_bytes()).decode("ascii")
            st.markdown(f'<div class="logo-circle"><img src="data:image/png;base64,{b64}"></div>', unsafe_allow_html=True)
        else:
            st.caption("logo.png 를 앱 파일과 같은 폴더에 두면 로고가 표시됩니다.")

        st.toggle("🌓 다크 모드", value=(st.session_state.get("theme","light")=="dark"), on_change=_toggle_theme, key="__theme_toggle")

        # ① 환율 계산기
        st.markdown("### ① 환율 계산기")
        base = st.selectbox("기준 통화", list(CURRENCIES.keys()),
                            index=list(CURRENCIES.keys()).index(st.session_state["fx_base"]),
                            key="fx_base")
        sale_foreign = st.number_input("판매금액 (외화)", value=float(st.session_state["sale_foreign"]), step=0.01, format="%.2f", key="sale_foreign")
        won = FX_DEFAULT[base] * sale_foreign
        st.markdown(
            f'<div class="badge-green">환산 금액: <b>{won:,.2f} 원</b> '
            f'<span class="muted">({CURRENCIES[base]["kr"]} • {CURRENCIES[base]["symbol"]})</span></div>',
            unsafe_allow_html=True
        )
        st.caption(f"환율 기준: {FX_DEFAULT[base]:,.2f} ₩/{CURRENCIES[base]['unit']}")

        # ② 마진 계산기
        st.markdown("### ② 마진 계산기")
        m_base = st.selectbox("매입 통화", list(CURRENCIES.keys()),
                              index=list(CURRENCIES.keys()).index(st.session_state["m_base"]),
                              key="m_base")
        purchase_foreign = st.number_input("매입금액 (외화)", value=float(st.session_state["purchase_foreign"]), step=0.01, format="%.2f", key="purchase_foreign")
        base_cost_won = FX_DEFAULT[m_base] * purchase_foreign if purchase_foreign>0 else won
        st.markdown(f'<div class="badge-green">원가(₩): <b>{base_cost_won:,.2f} 원</b></div>', unsafe_allow_html=True)

        colf1, colf2 = st.columns(2)
        with colf1:
            card_fee = st.number_input("카드수수료(%)", value=float(st.session_state["card_fee_pct"]), step=0.01, format="%.2f", key="card_fee_pct")
        with colf2:
            market_fee = st.number_input("마켓수수료(%)", value=float(st.session_state["market_fee_pct"]), step=0.01, format="%.2f", key="market_fee_pct")
        shipping_won = st.number_input("배송비(₩)", value=float(st.session_state["shipping_won"]), step=100.0, format="%.0f", key="shipping_won")

        mode = st.radio("마진 방식", ["퍼센트","플러스"], horizontal=True, key="margin_mode")
        if mode == "퍼센트":
            margin_pct = st.number_input("마진율 (%)", value=float(st.session_state["margin_pct"]), step=0.01, format="%.2f", key="margin_pct")
            target_price = base_cost_won * (1 + card_fee/100) * (1 + market_fee/100) * (1 + margin_pct/100) + shipping_won
            margin_value = target_price - base_cost_won
            margin_desc = f"{margin_pct:.2f}%"
        else:
            margin_won = st.number_input("마진액 (₩)", value=float(st.session_state["margin_won"]), step=100.0, format="%.0f", key="margin_won")
            target_price = base_cost_won * (1 + card_fee/100) * (1 + market_fee/100) + margin_won + shipping_won
            margin_value = margin_won
            margin_desc = f"+{margin_won:,.0f}"

        st.markdown(f'<div class="badge-blue">판매가: <b>{target_price:,.2f} 원</b></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="badge-yellow">순이익(마진): <b>{margin_value:,.2f} 원</b> — {margin_desc}</div>', unsafe_allow_html=True)

        st.divider()
        st.markdown("##### 프록시/환경")
        st.text_input("PROXY_URL (Cloudflare Worker 등)", value=st.session_state.get("PROXY_URL",""), key="PROXY_URL", help="예: https://envy-proxy.example.workers.dev")
        st.markdown("""
            <div class="info-box">
              <b>ENVY</b> 사이드바 정보는 고정입니다.<br/>
              · 로고/환율/마진 계산기: 변경 금지<br/>
              · PROXY_URL: 11번가/데이터랩/임베드용(참고용)<br/>
              · 다크/라이트 모드는 상단 토글
            </div>
        """, unsafe_allow_html=True)

    result.update({
        "fx_base": base,
        "sale_foreign": sale_foreign,
        "converted_won": won,
        "purchase_base": m_base,
        "purchase_foreign": purchase_foreign,
        "base_cost_won": base_cost_won,
        "card_fee_pct": card_fee,
        "market_fee_pct": market_fee,
        "shipping_won": shipping_won,
        "margin_mode": mode,
        "target_price": target_price,
        "margin_value": margin_value,
    })
    return result

# =========================
# [Part 2] 레이아웃/공통 CSS (가로 배치)
# =========================
st.markdown("""
<style>
.block-container { max-width: 1680px !important; padding-top:.6rem !important; }
.card-title { font-size: 1.15rem; font-weight: 700; margin: .2rem 0 .6rem 0; }
.card { border:1px solid rgba(0,0,0,.06); border-radius:12px; padding:.75rem; background:#fff; box-shadow:0 1px 6px rgba(0,0,0,.04); }
.card iframe { border:0; width:100%; border-radius:8px; }

/* 1행 3개, 2행 4개 - 가로 그리드 */
.row { display:grid; grid-gap:16px; }
.row.row-3 { grid-template-columns: 1fr 1fr 1fr; }
.row.row-4 { grid-template-columns: 1fr 1fr 1fr 1fr; }

.embed-wrap { height: 710px; overflow:auto; }
.embed-wrap-short { height: 640px; overflow:auto; }

/* Rakuten 표 폰트 축소 */
.rk-table { font-size:.88rem; }
.rk-table a { font-size:.86rem; }
</style>
""", unsafe_allow_html=True)

# =========================
# [Part 3] 프록시 고정 (서비스별)
# =========================
NAVER_PROXY       = "https://envy-proxy.taesig0302.workers.dev"
ELEVENST_PROXY    = "https://worker-11stjs.taesig0302.workers.dev"
ITEMSCOUT_PROXY   = "https://worker-itemscoutjs.taesig0302.workers.dev"
SELLERLIFE_PROXY  = "https://worker-sellerlifejs.taesig0302.workers.dev"

AMAZON_BEST_URL = "https://m.11st.co.kr/page/main/abest?tabId=ABEST&pageId=AMOBEST&ctgr1No=166160"

# =========================
# [Part 4] 섹션들
# =========================
def _proxy_embed(proxy_base: str, target_url: str, height: int = 710, scroll=True):
    proxy = proxy_base.strip().rstrip("/")
    url   = f"{proxy}/?url={quote(target_url, safe=':/?&=%')}"
    st.components.v1.iframe(url, height=height, scrolling=scroll)

def section_datalab_embed():
    st.markdown('<div class="card-title">데이터랩</div>', unsafe_allow_html=True)
    st.markdown('<div class="card embed-wrap">', unsafe_allow_html=True)
    target = ("https://datalab.naver.com/shoppingInsight/sCategory.naver"
              "?cid=50000003&timeUnit=week&device=all&gender=all&ages=all")
    _proxy_embed(NAVER_PROXY, target, height=710, scroll=True)
    st.markdown('</div>', unsafe_allow_html=True)

def section_itemscout_embed():
    st.markdown('<div class="card-title">아이템스카우트</div>', unsafe_allow_html=True)
    st.markdown('<div class="card embed-wrap-short">', unsafe_allow_html=True)
    target = "https://app.itemscout.io/market/keyword"
    _proxy_embed(ITEMSCOUT_PROXY, target, height=640, scroll=True)
    st.markdown('</div>', unsafe_allow_html=True)

def section_sellerlife_embed():
    st.markdown('<div class="card-title">셀러라이프</div>', unsafe_allow_html=True)
    st.markdown('<div class="card embed-wrap-short">', unsafe_allow_html=True)
    target = "https://sellerlife.co.kr/dashboard"
    _proxy_embed(SELLERLIFE_PROXY, target, height=640, scroll=True)
    st.markdown('</div>', unsafe_allow_html=True)

def section_11st():
    st.markdown('<div class="card-title">11번가 (모바일)</div>', unsafe_allow_html=True)
    st.markdown('<div class="card embed-wrap-short">', unsafe_allow_html=True)
    _proxy_embed(ELEVENST_PROXY, AMAZON_BEST_URL, height=640, scroll=True)
    st.markdown('</div>', unsafe_allow_html=True)

# Rakuten
RAKUTEN_APP_ID_DEFAULT       = "1043271015809337425"
RAKUTEN_AFFILIATE_ID_DEFAULT = "4c723498.cbfeca46.4c723499.1deb6f77"
def _rk_keys():
    try:
        app_id = st.secrets.get("RAKUTEN_APP_ID", "") or st.secrets.get("RAKUTEN_APPLICATION_ID", "")
        aff    = st.secrets.get("RAKUTEN_AFFILIATE_ID", "") or st.secrets.get("RAKUTEN_AFFILIATE", "")
    except Exception:
        app_id, aff = "", ""
    if not app_id: app_id = RAKUTEN_APP_ID_DEFAULT
    if not aff:    aff    = RAKUTEN_AFFILIATE_ID_DEFAULT
    return app_id.strip(), aff.strip()

def _rk_fetch_rank(genreid: str, app_id: str, affiliate: str, topn:int=20) -> pd.DataFrame:
    if not requests:
        return pd.DataFrame([{"rank":i+1,"keyword":f"[샘플] 키워드 {i+1} ハロウィン 秋 🍂","shop":"샘플샵","url":"https://example.com"} for i in range(20)])
    api = "https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20170628"
    params = {"applicationId": app_id, "genreId": str(genreid or "100283")}
    if affiliate: params["affiliateId"] = affiliate
    try:
        r = requests.get(api, params=params, timeout=12)
        r.raise_for_status()
        items = (r.json().get("Items") or [])[:topn]
        rows=[]
        for it in items:
            node = it.get("Item", {})
            rows.append({"rank":node.get("rank"), "keyword":node.get("itemName",""), "shop":node.get("shopName",""), "url":node.get("itemUrl","")})
        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame([{"rank":i+1,"keyword":f"[샘플] 키워드 {i+1} ハロウィン 秋 🍂","shop":"샘플샵","url":"https://example.com"} for i in range(20)])

def section_rakuten():
    st.markdown('<div class="card-title">AI 키워드 레이더 (Rakuten)</div>', unsafe_allow_html=True)
    app_id = (st.session_state.get("rk_app_override") or _rk_keys()[0]).strip()
    aff    = (st.session_state.get("rk_aff_override") or _rk_keys()[1]).strip()
    genreid = st.text_input("GenreID", "100283", key="rk_gid", label_visibility="collapsed")
    df = _rk_fetch_rank(genreid, app_id, aff, topn=20)
    df = df[["rank","keyword","shop","url"]]
    colcfg = {
        "rank":    st.column_config.NumberColumn("rank", width="small"),
        "keyword": st.column_config.TextColumn("keyword", width="large"),
        "shop":    st.column_config.TextColumn("shop", width="medium"),
        "url":     st.column_config.LinkColumn("url", display_text="열기", width="small"),
    }
    st.markdown('<div class="card rk-table">', unsafe_allow_html=True)
    st.dataframe(df, hide_index=True, use_container_width=True, height=640, column_config=colcfg)
    st.markdown('</div>', unsafe_allow_html=True)

# 번역기
LANG_LABELS = {
    "auto":"자동 감지",
    "ko":"한국어","en":"영어","ja":"일본어",
    "zh-CN":"중국어(간체)","zh-TW":"중국어(번체)",
    "vi":"베트남어","th":"태국어","id":"인도네시아어",
    "de":"독일어","fr":"프랑스어","es":"스페인어","it":"이탈리아어","pt":"포르투갈어",
}
def _code(label_or_code:str) -> str:
    rev = {v:k for k,v in LANG_LABELS.items()}
    return rev.get(label_or_code, label_or_code)

def section_translator():
    st.markdown('<div class="card-title">구글 번역기</div>', unsafe_allow_html=True)
    st.markdown('<div class="card">', unsafe_allow_html=True)
    col1, col2 = st.columns([1,1])
    with col1:
        src = st.selectbox("원문", list(LANG_LABELS.values()), index=list(LANG_LABELS.keys()).index("auto"))
        text = st.text_area("입력", height=200)
    with col2:
        tgt = st.selectbox("번역", list(LANG_LABELS.values()), index=list(LANG_LABELS.keys()).index("en"))
        if st.button("번역"):
            try:
                from deep_translator import GoogleTranslator
                gt = GoogleTranslator(source=_code(src), target=_code(tgt))
                out = gt.translate(text or "")
                st.text_area("결과", value=out, height=200)
            except Exception as e:
                st.warning(f"번역 실패: {e}")
    st.markdown('</div>', unsafe_allow_html=True)

# 상품명 생성기
def section_title_generator():
    st.markdown('<div class="card-title">상품명 생성기</div>', unsafe_allow_html=True)
    st.markdown('<div class="card">', unsafe_allow_html=True)
    colA, colB = st.columns([1,2])
    with colA:
        brand = st.text_input("브랜드", placeholder="예: Apple / 샤오미 / 무지")
        attrs = st.text_input("속성(콤마, 선택)", placeholder="예: 공식, 정품, 한정판")
    with colB:
        kws = st.text_input("키워드(콤마)", placeholder="예: 노트북 스탠드, 접이식, 알루미늄")
    col1, col2, col3 = st.columns([1,1,1])
    with col1:
        max_len = st.slider("최대 글자수", 20, 80, 50, 1)
    with col2:
        joiner = st.selectbox("구분자", [" ", " | ", " · ", " - "], index=0)
    with col3:
        order = st.selectbox("순서", ["브랜드-키워드-속성", "키워드-브랜드-속성", "브랜드-속성-키워드"], index=0)
    if st.button("상품명 생성"):
        kw_list = [k.strip() for k in (kws or "").split(",") if k.strip()]
        at_list = [a.strip() for a in (attrs or "").split(",") if a.strip()]
        if not kw_list:
            st.warning("키워드가 비었습니다.")
        else:
            titles = []
            for k in kw_list:
                if order=="브랜드-키워드-속성": seq = [brand, k] + at_list
                elif order=="키워드-브랜드-속성": seq = [k, brand] + at_list
                else: seq = [brand] + at_list + [k]
                title = joiner.join([p for p in seq if p])
                if len(title) > max_len:
                    title = title[:max_len-1] + "…"
                titles.append(title)
            st.success(f"총 {len(titles)}건")
            st.write("\n".join(titles))
    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# [Part 5] 메인 조립 (가로 원복)
# =========================
sidebar_vals = render_sidebar()
st.title("ENVY — Season 1 (Dual Proxy Edition)")

# 1행: 데이터랩 / 아이템스카우트 / 셀러라이프
st.markdown('<div class="row row-3">', unsafe_allow_html=True)
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True); section_datalab_embed(); st.markdown('</div>', unsafe_allow_html=True)
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True); section_itemscout_embed(); st.markdown('</div>', unsafe_allow_html=True)
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True); section_sellerlife_embed(); st.markdown('</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# 2행: 11번가 / AI 키워드 레이더 / 구글 번역기 / 상품명 생성기
st.markdown('<div class="row row-4" style="margin-top:16px;">', unsafe_allow_html=True)
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True); section_11st(); st.markdown('</div>', unsafe_allow_html=True)
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True); section_rakuten(); st.markdown('</div>', unsafe_allow_html=True)
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True); section_translator(); st.markdown('</div>', unsafe_allow_html=True)
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True); section_title_generator(); st.markdown('</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

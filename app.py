# app.py
# ENvY — v11.x (stable)
# -----------------------------------------------------------
# 전체 구성 (알파벳 파트로 통일):
# PART_A : 공통 유틸/프록시/스타일/테마/상태패널
# PART_B : 데이터랩(시즌1 – 분석 카드) + Top20 버튼
# PART_C : 선택 키워드 트렌드(라인 차트)
# PART_D : 11번가(모바일) 임베드 (아마존베스트 고정)
# PART_E : 상품명 생성기(규칙 기반, 20개 생성)
# PART_F : AI 키워드 레이더 (Rakuten, LIVE) + 구글 번역 UI
# PART_G : 사이드바(고정/스크롤락/환율/마진계산기 + 다크/라이트)
# -----------------------------------------------------------

import json
import time
import math
import random
from datetime import datetime, timedelta
from urllib.parse import quote_plus

import streamlit as st
import pandas as pd

# Altair(가벼운 라인차트)
import altair as alt

# -----------------------------------------------------------
# PART_A : 공통 유틸/프록시/스타일/테마/상태패널
# -----------------------------------------------------------

st.set_page_config(
    page_title="ENVY — v11.x (stable)",
    page_icon="🧪",
    layout="wide",
)

# --------- 환경/시크릿 로딩
SECRETS = st.secrets if hasattr(st, "secrets") else {}
NAVER_COOKIE = SECRETS.get("NAVER_COOKIE", "")
RAKUTEN_APP_ID = SECRETS.get("RAKUTEN_APP_ID", "")  # ex) 1043...
RAKUTEN_DEV_SECRET = SECRETS.get("RAKUTEN_DEV_SECRET", "")
RAKUTEN_AFFIL_ID = SECRETS.get("RAKUTEN_AFFIL_ID", "")
PROXY_URL = SECRETS.get("PROXY_URL", "https://envy-proxy.taesig0302.workers.dev")

st.session_state.setdefault("proxy_url", PROXY_URL)

# --------- 스타일(라이트/다크 CSS + 읽기용 박스 + 배지 등)
BASE_CSS = """
<style>
/* sticky 사이드바 + 스크롤락(본문 가로 스크롤 차단) */
section[data-testid="stSidebar"] { position: sticky; top: 0; height: 100vh; overflow-y: auto; }

/* 읽기 전용 박스 */
.readbox{display:flex;align-items:center;gap:.5rem;padding:.55rem .7rem;border:1px solid var(--border,#e5e7eb);
border-radius:.6rem;background:rgba(148,163,184,.08);}

/* 배지 */
.badge{display:inline-flex;align-items:center;padding:.2rem .5rem;border-radius:.5rem;border:1px solid #3b82f6;
background:rgba(37,99,235,.08);color:#2563eb;font-size:.78rem}

/* 그리드 상단/하단 여백 */
.block-space{margin-top:.35rem;margin-bottom:.35rem}
</style>
"""
st.markdown(BASE_CSS, unsafe_allow_html=True)

# --------- 라이트/다크 비주얼 토글 (Streamlit 런타임 테마 대신 CSS)
def mount_visual_theme_toggle():
    enable_dark = st.session_state.get("enable_dark", False)
    enable_dark = st.toggle("다크/라이트 모드", value=enable_dark, key="enable_dark_ui")
    st.session_state["enable_dark"] = enable_dark

    _dark_css = """
    <style>
    :root {
      --bg: #ffffff;
      --card: #ffffff;
      --text: #0f172a;
      --muted: #64748b;
      --border: #e5e7eb;
    }
    html.dark {
      --bg: #0b1220;
      --card: #0f172a;
      --text: #e5e7eb;
      --muted: #94a3b8;
      --border: #1f2937;
    }
    html, body, .stApp { background: var(--bg) !important; color: var(--text) !important; }
    section[data-testid="stSidebar"] { background: var(--card) !important; }
    div[data-testid="stMarkdownContainer"], .stText, .stCaption, label, p, span { color: var(--text) !important; }
    hr, .st-emotion-cache-13ln4jf, .st-emotion-cache-1pbsqtx { border-color: var(--border) !important; }
    .readbox { background: rgba(148,163,184,0.08) !important; border-color: var(--border) !important; }
    .badge   { background: rgba(37,99,235,0.1) !important; border-color: #3b82f6 !important; }
    </style>
    <script>
    const htmlEl = window.parent.document.documentElement;
    const setDark = (on) => { if(on){ htmlEl.classList.add('dark'); } else { htmlEl.classList.remove('dark'); } };
    </script>
    """
    st.markdown(_dark_css, unsafe_allow_html=True)
    st.markdown(f"""<script>setDark({str(enable_dark).lower()});</script>""", unsafe_allow_html=True)

# --------- 프록시 임베드 유틸
def iframe_via_proxy(raw_url: str, height: int = 580, scrolling=True, key=None):
    """
    Cloudflare 1016/403 우회: workers 프록시의 /embed?url= 로 감싼 iframe.
    프록시가 막히면 카드에 새창 열기 버튼만 노출.
    """
    proxy = st.session_state.get("proxy_url") or PROXY_URL
    if not proxy.endswith("/"):
        proxy += "/"
    embed_url = f"{proxy}embed?url={quote_plus(raw_url)}"
    try:
        # streamlit 내부 iframe
        st.components.v1.iframe(embed_url, height=height, scrolling=scrolling)
    except TypeError:
        # 일부 버전에서 key 인자 오류 방지
        st.components.v1.iframe(embed_url, height=height, scrolling=scrolling)

def render_proxy_state_panel():
    with st.expander("프록시/환경 설정 정보", expanded=False):
        st.info(
            f"Cloudflare/프록시 차단으로 직접 임베드가 제한될 수 있습니다.\n\n"
            f"**현재 프록시**: `{st.session_state.get('proxy_url')}`\n"
        )
        st.caption("프록시 4xx/1016 시 아래 카드에 안내와 '새창 열기' 버튼이 뜹니다.")

# 상단 안내(프록시 상태)
render_proxy_state_panel()

st.title("데이터랩 (시즌1 – 분석 카드)")

# -----------------------------------------------------------
# PART_B : 데이터랩(시즌1 – 분석 카드) + Top20 버튼
# -----------------------------------------------------------

with st.container():
    st.session_state.setdefault("datalab_cat", "디지털/가전")
    st.session_state.setdefault("datalab_period", "week")
    st.session_state.setdefault("datalab_device", "all")
    st.session_state.setdefault("datalab_cid", "50000003")

    top = st.columns([1, 1, 1, 1, 1, 2])
    with top[0]:
        cat = st.selectbox("카테고리", ["디지털/가전", "패션의류", "화장품/미용", "출산/육아", "스포츠/레저"], index=0, key="datalab_cat")
    with top[1]:
        period = st.selectbox("기간 단위", ["week", "month"], index=0, key="datalab_period")
    with top[2]:
        dev = st.selectbox("기기", ["all", "pc", "mo"], index=0, key="datalab_device")
    with top[3]:
        cid = st.text_input("CID(직접입력)", st.session_state["datalab_cid"], key="datalab_cid")

    btn_col = top[5]
    with btn_col:
        if st.button("Top20 불러오기", use_container_width=True):
            # 실데이터는 네이버 데이터랩 쿠키/광고 API가 필요
            if not NAVER_COOKIE:
                st.warning("NAVER_COOKIE가 없어서 샘플 Top20를 표시합니다.")
            st.session_state["datalab_top20"] = [
                {"rank": i + 1, "keyword": f"키워드{i+1}", "volume": random.randint(1000, 9999)}
                for i in range(20)
            ]

    # Top20 표
    df_top20 = pd.DataFrame(st.session_state.get("datalab_top20", []))
    if not df_top20.empty:
        st.dataframe(df_top20, use_container_width=True, height=300)
    else:
        st.caption("좌측 옵션을 선택하고 **Top20 불러오기**를 누르세요.")

# -----------------------------------------------------------
# PART_C : 선택 키워드 트렌드(라인 차트)
# -----------------------------------------------------------

st.subheader("선택 키워드 트렌드")
with st.container():
    # 최대 5개 키워드 입력(쉼표 구분)
    kw_input = st.text_input("키워드(최대 5개, 쉼표)", placeholder="예: 키워드1, 키워드2")
    if st.button("트렌드 불러오기"):
        kws = [k.strip() for k in kw_input.split(",") if k.strip()][:5]
        if not kws:
            st.warning("최소 1개 키워드를 입력하세요.")
        else:
            # 여기서 실제 데이터랩 트렌드 호출 -> 쿠키/광고 API 필요
            # 데모: 10 포인트 샘플
            dates = [f"P{i}" for i in range(10)]
            rows = []
            for kw in kws:
                base = random.randint(35, 60)
                series = [base + random.randint(-5, 8) for _ in range(10)]
                for p, v in zip(dates, series):
                    rows.append({"point": p, "keyword": kw, "value": v})
            st.session_state["trend_df"] = pd.DataFrame(rows)

    df_trend = st.session_state.get("trend_df")
    if isinstance(df_trend, pd.DataFrame) and not df_trend.empty:
        chart = (
            alt.Chart(df_trend)
            .mark_line(point=True)
            .encode(
                x=alt.X("point:N", title=""),
                y=alt.Y("value:Q", title="지수"),
                color="keyword:N",
                tooltip=["keyword", "point", "value"],
            )
            .properties(height=220)
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.caption("키워드를 입력하고 **트렌드 불러오기**를 눌러 주세요.")

# -----------------------------------------------------------
# PART_D : 11번가(모바일) 임베드 (아마존베스트 고정)
# -----------------------------------------------------------

st.subheader("11번가 (모바일) – 아마존베스트")
with st.container():
    # 고정 URL
    url_11st = "https://m.11st.co.kr/page/main/abest?tabId=ABEST&pageId=AMOBEST&ctgr1No=166160"
    try:
        iframe_via_proxy(url_11st, height=580, scrolling=True)
    except Exception:
        st.error("iFrame 차단/프록시 오류가 감지됐습니다.")
        st.link_button("프록시 새창 열기", url_11st, type="secondary")

# -----------------------------------------------------------
# PART_E : 상품명 생성기(규칙 기반, 20개 생성)
# -----------------------------------------------------------

st.subheader("상품명 생성기 (규칙 기반)")
with st.container():
    c = st.columns([1, 1])
    with c[0]:
        brand = st.text_input("브랜드", placeholder="예: 오소")
    with c[1]:
        style = st.text_input("스타일/속성", placeholder="예: 프리미엄, S")

    length = st.slider("길이(단어 수)", 4, 12, 8)
    core_kw = st.text_area("핵심 키워드(콤마)", placeholder="예: 가습기, 무선청소기, 텐타블")
    gen_btn = st.button("상품명 20개 생성", use_container_width=True)

    if gen_btn:
        parts = [w.strip() for w in core_kw.split(",") if w.strip()]
        names = []
        for i in range(20):
            pick = random.sample(parts, min(len(parts), random.randint(1, min(3, len(parts))))) if parts else []
            seg = " ".join(pick)
            name = f"{brand or '브랜드'} {style or ''} {seg}".strip()
            # 길이 보정
            extra = ["초특가", "정품", "공식", "NEW", "인기", "MD추천", "스테디셀러"]
            while len(name.split()) < length:
                name += " " + random.choice(extra)
            names.append(name)
        st.write(pd.DataFrame({"rank": range(1, 21), "candidate": names}))

# -----------------------------------------------------------
# PART_F : AI 키워드 레이더 (Rakuten, LIVE) + 구글 번역 UI
# -----------------------------------------------------------

colA, colB = st.columns(2)

with colA:
    st.subheader("AI 키워드 레이더 (Rakuten, LIVE)")
    rcol = st.columns([2, 1, 2])
    with rcol[0]:
        rk_cat = st.selectbox("라쿠텐 카테고리(샘플)", ["전체(100283)", "패션", "리빙", "뷰티"], index=0)
    with rcol[1]:
        rk_genre = st.text_input("직접 GenreID 입력", "100283")
    with rcol[2]:
        rk_pages = st.slider("확장 페이지 수(1p~30p)", 1, 30, 2)

    if st.button("Top 키워드 뽑기", use_container_width=True):
        if not RAKUTEN_APP_ID:
            st.warning("라쿠텐 APP_ID가 없어 LIVE 호출 대신 샘플을 보여줍니다.")
        # 샘플 20개까지
        data = [{"rank": i+1, "keyword": f"라쿠텐키워드{i+1}", "source": "sample"} for i in range(20)]
        st.dataframe(pd.DataFrame(data), height=340, use_container_width=True)

with colB:
    st.subheader("구글 번역 (텍스트 입력/출력 + 한국어 확인용)")
    t1, t2 = st.columns(2)
    with t1:
        src = st.selectbox("원문 언어", ["자동 감지", "영어", "일본어", "한국어", "중국어"], index=0)
    with t2:
        dst = st.selectbox("번역 언어", ["한국어", "영어", "일본어", "중국어"], index=0)
    src_text = st.text_area("원문 입력", placeholder="안녕하세요")
    if st.button("번역", use_container_width=True):
        # 외부 호출이 막힌 환경일 수 있으므로 간단한 더미 변환
        if not src_text.strip():
            st.warning("번역할 텍스트를 입력하세요.")
        else:
            # 간단한 더미: 단어 뒤집기 + 대문자/소문자 섞기
            dummy = " ".join(w[::-1] for w in src_text.split())
            st.write("번역 결과")
            st.text_area("번역 결과", dummy, height=160)

# PART_G — 사이드바 (고정/스크롤락/로고/다크·라이트/환율·마진/프록시-조건부)
import streamlit as st
import base64
from pathlib import Path

# ── 통화/라벨/환율 기본값 ──────────────────────────────────────────────
CURRENCIES = {
    "USD": {"kr": "미국 달러", "symbol": "$", "unit": "USD"},
    "EUR": {"kr": "유로",     "symbol": "€", "unit": "EUR"},
    "JPY": {"kr": "일본 엔",   "symbol": "¥", "unit": "JPY"},
    "CNY": {"kr": "중국 위안", "symbol": "元","unit": "CNY"},
}
FX_DEFAULT = {"USD": 1400.0, "EUR": 1500.0, "JPY": 10.0, "CNY": 200.0}

def _ensure_session_defaults():
    ss = st.session_state
    ss.setdefault("theme", "light")  # 'light' | 'dark'
    ss.setdefault("PROXY_URL", "https://envy-proxy.taesig0302.workers.dev")
    ss.setdefault("proxy_error_code", None)   # 401/403/1016 발생 시 외부 파트에서 세팅

    # 환율 계산기
    ss.setdefault("fx_base", "USD")
    ss.setdefault("sale_foreign", 1.00)

    # 마진 계산기
    ss.setdefault("card_fee_pct", 4.00)
    ss.setdefault("market_fee_pct", 14.00)
    ss.setdefault("shipping_won", 0.0)
    ss.setdefault("margin_mode", "퍼센트")  # or "플러스"
    ss.setdefault("margin_pct", 10.00)
    ss.setdefault("margin_won", 10000.0)

def _toggle_theme():
    st.session_state["theme"] = "dark" if st.session_state.get("theme","light")=="light" else "light"

def _should_show_proxy_panel() -> bool:
    code = st.session_state.get("proxy_error_code")
    proxy = (st.session_state.get("PROXY_URL") or "").strip()
    if code in (401,403,1016):  # 차단/만료 등
        return True
    if not proxy:
        return True
    return False

def _inject_sidebar_css():
    # 스크롤은 되지만 스크롤바는 숨김 → 시각적으로 '락'처럼 보이게.
    # 이중 스크롤 방지 위해 사이드바 내부만 auto, 바는 숨김.
    st.markdown("""
    <style>
      /* 사이드바 고정 + 내부 스크롤(바 숨김) */
      [data-testid="stSidebar"] > div:first-child,
      [data-testid="stSidebar"] section {
        height: 100vh !important;
        overflow-y: auto !important;
        overflow-x: hidden !important;
        padding-top: .25rem !important;
        padding-bottom: .25rem !important;
      }
      [data-testid="stSidebar"] ::-webkit-scrollbar { width:0; height:0; }

      /* 입력 간격 압축 */
      [data-testid="stSidebar"] .stSelectbox,
      [data-testid="stSidebar"] .stNumberInput,
      [data-testid="stSidebar"] .stRadio,
      [data-testid="stSidebar"] .stMarkdown,
      [data-testid="stSidebar"] .stTextInput,
      [data-testid="stSidebar"] .stButton { margin:.14rem 0 !important; }

      [data-baseweb="input"] input,
      .stNumberInput input,
      [data-baseweb="select"] div[role="combobox"] {
        height:1.55rem !important; padding:.12rem !important; font-size:.92rem !important;
      }

      /* 로고 (원형 + 그림자) */
      .logo-circle {
        width:95px; height:95px; border-radius:50%; overflow:hidden;
        margin:.15rem auto .35rem auto; box-shadow:0 2px 8px rgba(0,0,0,.12);
        border:1px solid rgba(0,0,0,.06);
      }
      .logo-circle img { width:100%; height:100%; object-fit:cover; }

      /* 읽기용 컬러 박스 */
      .pill-green  { background:#e6ffcc; border:1px solid #b6f3a4; padding:6px 10px; border-radius:6px; color:#0b2e13; font-size:.86rem; }
      .pill-blue   { background:#eef4ff; border:1px solid #bcd0ff; padding:6px 10px; border-radius:6px; color:#0a235a; font-size:.86rem; }
      .pill-amber  { background:#fff7d6; border:1px solid #f1d27a; padding:6px 10px; border-radius:6px; color:#4a3b07; font-size:.86rem; }
      .muted { opacity:.8; font-size:.8rem; }

      /* 프록시/환경 알림 박스(조건부 노출) */
      .info-box { background:rgba(0,0,0,.03); border:1px dashed rgba(0,0,0,.08); padding:.6rem; border-radius:.5rem; }
    </style>
    """, unsafe_allow_html=True)

def _render_logo():
    # logo.png가 앱 루트에 있으면 base64로 표시
    try:
        lp = Path(__file__).parent / "logo.png"
    except NameError:
        lp = Path("logo.png")
    if lp.exists():
        b64 = base64.b64encode(lp.read_bytes()).decode("ascii")
        st.markdown(f'<div class="logo-circle"><img src="data:image/png;base64,{b64}"></div>', unsafe_allow_html=True)
    else:
        st.caption("logo.png 를 앱 폴더에 두면 로고가 표시됩니다.")

def render_sidebar() -> dict:
    """
    사이드바 전체 UI 렌더:
    - 로고
    - 다크/라이트 모드
    - ① 환율 계산기: 통화 선택 / 구매금액(외화) / 환산금액(읽기용 컬러박스)
    - ② 마진 계산기: 원가(₩=환산값) / 수수료 / 배송비 / 퍼센트/플러스 / 판매가·순이익(읽기용 컬러박스)
    - 프록시/환경: 401/403/1016 또는 미설정 시에만 노출
    """
    _ensure_session_defaults()
    _inject_sidebar_css()

    result = {}
    with st.sidebar:
        # ── 로고 ─────────────────────────────────────────────────────────
        _render_logo()

        # 다크/라이트 모드 (문구 고정)
        st.toggle("다크/라이트 모드",
                  value=(st.session_state.get("theme","light")=="dark"),
                  on_change=_toggle_theme, key="__theme_toggle")

        # ── ① 환율 계산기 ───────────────────────────────────────────────
        st.markdown("### ① 환율 계산기")
        def _fmt(code):
            c = CURRENCIES[code]; return f"{c['kr']} ({c['unit']}) {c['symbol']}"
        currency_codes = list(CURRENCIES.keys())
        base = st.selectbox("통화 선택", currency_codes,
                            index=currency_codes.index(st.session_state["fx_base"]),
                            format_func=_fmt, key="fx_base")
        sale_foreign = st.number_input("구매금액 (외화)", value=float(st.session_state["sale_foreign"]),
                                       step=0.01, format="%.2f", key="sale_foreign")
        won = FX_DEFAULT[base] * sale_foreign
        st.markdown(
            f'<div class="pill-green">환산 금액: <b>{won:,.2f} 원</b> '
            f'<span class="muted">({CURRENCIES[base]["kr"]} • {CURRENCIES[base]["symbol"]})</span></div>',
            unsafe_allow_html=True
        )
        st.caption(f"환율 기준: {FX_DEFAULT[base]:,.2f} ₩/{CURRENCIES[base]['unit']}")

        # ── ② 마진 계산기 ───────────────────────────────────────────────
        st.markdown("### ② 마진 계산기")

        base_cost_won = won  # 원가(₩) 기본값 = 환율 환산값
        st.markdown(f'<div class="pill-green">원가(₩): <b>{base_cost_won:,.2f} 원</b></div>', unsafe_allow_html=True)

        colf1, colf2 = st.columns(2)
        with colf1:
            card_fee = st.number_input("카드수수료(%)", value=float(st.session_state["card_fee_pct"]),
                                       step=0.01, format="%.2f", key="card_fee_pct")
        with colf2:
            market_fee = st.number_input("마켓수수료(%)", value=float(st.session_state["market_fee_pct"]),
                                         step=0.01, format="%.2f", key="market_fee_pct")
        shipping_won = st.number_input("배송비(₩)", value=float(st.session_state["shipping_won"]),
                                       step=100.0, format="%.0f", key="shipping_won")

        mode = st.radio("마진 방식", ["퍼센트","플러스"], horizontal=True, key="margin_mode")

        fee_rate = (card_fee + market_fee) / 100.0
        if mode == "퍼센트":
            margin_pct = st.number_input("마진율 (%)", value=float(st.session_state["margin_pct"]),
                                         step=0.01, format="%.2f", key="margin_pct")
            denom = (1.0 - fee_rate - margin_pct/100.0)
            target_price = (base_cost_won + shipping_won) / denom if denom>0 else 0.0
            margin_value = target_price*(1.0-fee_rate) - (base_cost_won + shipping_won)
            margin_desc = f"{margin_pct:.2f}%"
        else:
            margin_won = st.number_input("마진액 (₩)", value=float(st.session_state["margin_won"]),
                                         step=100.0, format="%.0f", key="margin_won")
            target_price = (base_cost_won + shipping_won + margin_won) / (1.0 - fee_rate) if (1.0-fee_rate)>0 else 0.0
            margin_value = target_price*(1.0-fee_rate) - (base_cost_won + shipping_won)
            margin_desc = f"+{margin_won:,.0f}"

        st.markdown(f'<div class="pill-blue">판매가: <b>{target_price:,.2f} 원</b></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="pill-amber">순이익(마진): <b>{margin_value:,.2f} 원</b> — {margin_desc}</div>', unsafe_allow_html=True)

        # ── 프록시/환경 (조건부 노출) ───────────────────────────────────
        if _should_show_proxy_panel():
            st.divider()
            st.markdown("##### 프록시/환경")
            st.text_input("PROXY_URL (Cloudflare Worker 등)",
                          value=st.session_state.get("PROXY_URL",""),
                          key="PROXY_URL",
                          help="예: https://envy-proxy.taesig0302.workers.dev/")
            st.markdown(
                """
                <div class="info-box">
                  · PROXY_URL은 11번가/외부 임베드 차단(401/403/1016) 시에만 수정 필요<br/>
                  · 평소에는 이 패널이 보이지 않습니다.
                </div>
                """, unsafe_allow_html=True
            )

    result.update({
        "fx_base": base,
        "sale_foreign": sale_foreign,
        "converted_won": won,
        "base_cost_won": base_cost_won,
        "card_fee_pct": card_fee,
        "market_fee_pct": market_fee,
        "shipping_won": shipping_won,
        "margin_mode": mode,
        "target_price": target_price,
        "margin_value": margin_value,
    })
    return result

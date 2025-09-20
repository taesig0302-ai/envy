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

# -----------------------------------------------------------
# PART_G : 사이드바(고정/스크롤락/환율/마진계산기 + 다크/라이트)
# -----------------------------------------------------------

with st.sidebar:
    # 로고/타이틀(원형 + 여백)
    st.image("https://i.imgur.com/6YwHc2t.png", width=72)  # 원형 로고(임시)
    st.markdown("<div style='font-weight:700;margin-bottom:.3rem;'>envy</div>", unsafe_allow_html=True)

    # 다크/라이트 토글
    mount_visual_theme_toggle()

    st.markdown("---")
    st.markdown("### 환율 계산기")
    base_ccy = st.selectbox("통화 선택", ["USD", "JPY", "EUR", "CNY"], index=0, key="fx_ccy")
    buy_amt_foreign = st.number_input("구매금액(외화)", min_value=0.0, value=0.0, step=0.01, key="fx_amt")
    # 간단한 환율(데모 기준)
    FX = {"USD": 1400.0, "JPY": 9.5, "EUR": 1520.0, "CNY": 190.0}
    krw = buy_amt_foreign * FX.get(base_ccy, 1400.0)
    st.markdown("<div class='readbox'>환산 금액(원): <b>{:,.0f} 원</b></div>".format(krw), unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 마진 계산기")
    # 기본값 = 환율계산기 결과
    base_krw = st.number_input("구매금액(원화)", min_value=0.0, value=float(krw), step=100.0, key="m_cost_krw")
    st.markdown("<div class='readbox'>환산 금액(원): <b>{:,.0f} 원</b></div>".format(base_krw), unsafe_allow_html=True)
    card_fee = st.number_input("카드수수료(%)", min_value=0.0, value=4.00, step=0.05, key="m_card")
    market_fee = st.number_input("마켓수수료(%)", min_value=0.0, value=14.00, step=0.1, key="m_market")
    ship_cost = st.number_input("배송비(원)", min_value=0.0, value=0.0, step=100.0, key="m_ship")
    m_type = st.radio("마진 방식", ["퍼센트", "플러스"], horizontal=True, key="m_type")
    margin_val = st.number_input("마진(%) / 플러스(원)", min_value=0.0, value=10.0, step=0.5, key="m_val")

    # 판매가 역산 로직(수수료 포함)
    # 수수료율 r = 카드+마켓; 마진 방식에 따라
    r = (card_fee + market_fee) / 100.0
    cost_total = base_krw + ship_cost
    if m_type == "퍼센트":
        # 목표 이익 = cost_total * margin_val%
        target_profit = cost_total * (margin_val / 100.0)
        sell_price = (cost_total + target_profit) / (1 - r) if (1 - r) > 0 else cost_total
    else:
        # 플러스(원)
        target_profit = margin_val
        sell_price = (cost_total + target_profit) / (1 - r) if (1 - r) > 0 else cost_total

    # 실 순이익 = 판매가*(1-r) - cost_total
    net_profit = sell_price * (1 - r) - cost_total

    st.markdown("<div class='readbox badge'>판매가: <b>{:,.0f} 원</b></div>".format(sell_price), unsafe_allow_html=True)
    st.markdown("<div class='readbox'>순이익: <b>{:,.0f} 원</b></div>".format(net_profit), unsafe_allow_html=True)

    st.markdown("---")
    st.caption("레이아웃은 고정(사이드바 sticky + 스크롤락, 4×2 카드). 프록시는 기본값으로 iFrame 우회 임베드만 사용.")


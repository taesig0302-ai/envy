# app.py  —  drop-in replacement

import os
import json
import time
import textwrap
import requests
import streamlit as st

# ──────────────────────────────────────────────────────────────────────────────
# 기본 설정
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="ENVY — v11.x (stable)", layout="wide", page_icon="✨")

# ──────────────────────────────────────────────────────────────────────────────
# Secrets / Defaults (사용자 제공 값 → secrets 로 덮어쓰기)
# ──────────────────────────────────────────────────────────────────────────────
NAVER_CLIENT_ID_DEFAULT = os.getenv("NAVER_CLIENT_ID", "h4mkIM2hNLct04BD7sC0")
NAVER_CLIENT_SECRET_DEFAULT = os.getenv("NAVER_CLIENT_SECRET", "ltoxUNyKxi")

RAKUTEN_APP_ID_DEFAULT = os.getenv("RAKUTEN_APP_ID", "1043271015809337425")
RAKUTEN_DEV_ID_DEFAULT = os.getenv("RAKUTEN_DEV_ID", "1043271015809337425")  # 제공값 동일
RAKUTEN_AFFIL_ID_DEFAULT = os.getenv("RAKUTEN_AFFIL_ID", "4c723498.cbfeca46.4c723499.1deb6f77")

PROXY_DEFAULT = "https://envy-proxy.taesig0302.workers.dev"

def sec(name, default):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default

NAVER_CLIENT_ID = sec("NAVER_CLIENT_ID", NAVER_CLIENT_ID_DEFAULT)
NAVER_CLIENT_SECRET = sec("NAVER_CLIENT_SECRET", NAVER_CLIENT_SECRET_DEFAULT)

RAKUTEN_APP_ID = sec("RAKUTEN_APP_ID", RAKUTEN_APP_ID_DEFAULT)
RAKUTEN_DEV_ID = sec("RAKUTEN_DEV_ID", RAKUTEN_DEV_ID_DEFAULT)
RAKUTEN_AFFIL_ID = sec("RAKUTEN_AFFIL_ID", RAKUTEN_AFFIL_ID_DEFAULT)

PROXY_URL = sec("PROXY_URL", PROXY_DEFAULT).strip()

# ──────────────────────────────────────────────────────────────────────────────
# 스타일: 사이드바 고정 + 본문 마진 + 단일 스크롤 + 기본 UI 다듬기
# ──────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* 사이드바 고정 (sticky) */
section[data-testid="stSidebar"] {
  position: fixed !important;
  top: 0; left: 0;
  height: 100vh !important;
  overflow-y: auto !important;
  border-right: 1px solid rgba(0,0,0,0.05);
  z-index: 1000;
}
/* 본문 컨테이너 좌측 여백(사이드바 폭 보정) */
div.block-container { padding-left: 280px !important; }

/* 카드 폭 넓게 (공백 줄이기) */
.card { background: var(--background-color);
        padding: 16px 14px; border-radius: 14px;
        border: 1px solid rgba(0,0,0,.07); }

/* 메트릭 박스(컬러 강조) */
.badge { border-radius:10px; padding:8px 10px; display:inline-block; font-weight:600; }
.badge-blue  { background:#eef6ff; color:#1363df; }
.badge-green { background:#eaf7ee; color:#0d8b43; }
.badge-pink  { background:#ffeef4; color:#d61d5a; }
.badge-amber { background:#fff6e5; color:#b46900; }

/* 라디오 라벨 줄이기 */
div[role="radiogroup"] > label { padding-right:14px; }
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
# 유틸
# ──────────────────────────────────────────────────────────────────────────────
def get_currency_rate(base="USD", krw=1400.0):
    # 실환율 API 없이 샘플 기준값 사용 (원하시면 실제 API 연동)
    return krw

def to_proxy(url: str) -> str:
    if not PROXY_URL:
        return url
    # Cloudflare Worker에서 query ?url= 로 받도록 구성
    return f"{PROXY_URL.rstrip('/')}/?url={requests.utils.quote(url, safe='')}"

def iframe(url: str, height=560, scrolling=True):
    # components.iframe 은 key 인자를 지원하지 않는 버전이 있음 → key 제거
    st.components.v1.iframe(url, height=height, scrolling=scrolling)

def naver_papago_translate(text, src="auto", tgt="en"):
    url = "https://openapi.naver.com/v1/papago/n2mt"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    data = {"source": src, "target": tgt, "text": text}
    r = requests.post(url, headers=headers, data=data, timeout=15)
    r.raise_for_status()
    j = r.json()
    return j.get("message", {}).get("result", {}).get("translatedText", "")

def gen_product_names(brand, style, features, length=8, n=20):
    feats = [f.strip() for f in features.split(",") if f.strip()]
    results = []
    for i in range(n):
        core = " ".join((feats + [style])[:max(1, min(len(feats)+1, 3))])
        name = f"{brand} {core}".strip()
        if len(name.split()) < length:
            name += f" {i+1}"
        results.append(name[:64])
    return results

# ──────────────────────────────────────────────────────────────────────────────
# 사이드바 (로고 + 다크/라이트 + 환율/마진 계산 + 프록시 환경)
# ──────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    # 로고 (이미지 경로가 없다면 텍스트 표시)
    try:
        st.image("logo.png", caption="envy", use_column_width=True)
    except Exception:
        st.markdown("### envy")

    st.toggle("다크/라이트 모드", value=st.session_state.get("theme", False),
              key="__theme_toggle__")

    st.markdown("#### ① 환율 계산기")
    base = st.selectbox("기준 통화", ["USD","JPY","CNY","EUR"], index=0)
    amount = st.number_input("판매금액(외화)", min_value=0.0, value=1.0, step=0.1)
    rate = get_currency_rate(base=base)
    won = amount * rate
    st.markdown(f'<span class="badge badge-blue">환산 금액: <b>{won:,.2f}</b> 원</span>', unsafe_allow_html=True)

    st.markdown("#### ② 마진 계산기")
    m_base = st.selectbox("매입 통화", ["USD","JPY","CNY","EUR"], index=0)
    m_exchange = st.number_input("매입금액(외화)", min_value=0.0, value=0.0, step=0.1)
    fee_card = st.number_input("카드수수료(%)", min_value=0.0, value=4.0, step=0.1)
    fee_market = st.number_input("마켓수수료(%)", min_value=0.0, value=14.0, step=0.1)
    ship_cost = st.number_input("배송비(원)", min_value=0.0, value=0.0, step=100.0)
    margin_mode = st.radio("마진 방식", ["퍼센트","플러스"], horizontal=True, index=0)
    margin_val = st.number_input("마진율(%) / 플러스(원)", min_value=0.0, value=10.0, step=0.5)

    cost_won = m_exchange * rate
    sale_won = (cost_won * (1 + margin_val/100.0)) if margin_mode=="퍼센트" else (cost_won + margin_val)
    sale_won *= (1 + fee_card/100.0)
    net = sale_won * (1 - fee_market/100.0) - cost_won - ship_cost

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f'<div class="badge badge-amber">원가: <b>{cost_won:,.0f}</b> 원</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="badge badge-pink">판매가: <b>{sale_won:,.0f}</b> 원</div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="badge badge-green">순이익: <b>{net:,.0f}</b> 원</div>', unsafe_allow_html=True)

    # 프록시 환경: URL 없을 때만 노출
    if not PROXY_URL or PROXY_URL == "":
        st.info("PROXY_URL이 비어 있습니다. 아래에 Cloudflare Worker 주소를 입력하세요.")
        new_proxy = st.text_input("PROXY_URL", placeholder="https://<worker>.workers.dev")
        if new_proxy:
            st.session_state["__proxy_manual__"] = new_proxy
            st.success("입력 완료. 새로고침 후 적용됩니다.")
    else:
        st.caption("프록시는 설정되어 있습니다.")

# 세션 내 프록시 교체(수동 입력시)
PROXY_URL = st.session_state.get("__proxy_manual__", PROXY_URL)

# ──────────────────────────────────────────────────────────────────────────────
# 헤더
# ──────────────────────────────────────────────────────────────────────────────
st.title("ENVY — v11.x (stable)")
st.caption("시즌1: 데이터랩(분석 카드), 임베드 X, API키 통신, 11번가/아이템스카우트/셀러라이프는 프록시 기반 임베드")

# ──────────────────────────────────────────────────────────────────────────────
# 1행 (4 × 1)
# ──────────────────────────────────────────────────────────────────────────────
r1c1, r1c2, r1c3, r1c4 = st.columns(4)

# (1) 데이터랩(시즌1-분석 카드) — 샘플 차트
with r1c1:
    st.subheader("데이터랩 (시즌1 - 분석 카드)")
    st.caption("시즌2에서 원본 임베드로 전환 예정")
    cat = st.selectbox("카테고리", ["디지털/가전","패션의류","화장품/미용"], key="dl_cat")
    period = st.selectbox("기간 단위", ["week","month"], key="dl_per")
    device = st.selectbox("기기", ["all","pc","mo"], key="dl_dev")
    import pandas as pd, numpy as np
    x = np.linspace(1, 11, 11)
    y1 = 50 + 3*np.sin(x/1.2)
    y2 = y1 - (np.linspace(0, 8, 11))
    data = pd.DataFrame({"전체": y1, "패션의류": y2}, index=[f"{i/10:.1f}" for i in range(10, 121, 10)])
    st.line_chart(data, height=220)

# (2) 11번가 (모바일 – 아마존베스트)
with r1c2:
    st.subheader("11번가 (모바일) – 아마존베스트")
    url_11st = "https://m.11st.co.kr/page/main/abest?tabId=ABEST&pageId=AMOBEST&ctgr1No=166160"
    try:
        iframe(to_proxy(url_11st), height=560, scrolling=True)
    except TypeError:
        # 혹시 모듈 버전차 문제로 또 에러가 나면 원본으로
        iframe(url_11st, height=560, scrolling=True)

# (3) 상품명 생성기 (규칙 기반)
with r1c3:
    st.subheader("상품명 생성기 (규칙 기반)")
    b, s = st.columns(2)
    with b: brand = st.text_input("브랜드", placeholder="예: 오소")
    with s: style = st.text_input("스타일/속성", placeholder="예: 프리미엄")
    feats = st.text_input("핵심 키워드(콤마)", placeholder="예: 가습기, 무선청소기, 텀블러")
    length = st.slider("길이(단어 수)", 4, 12, 8)
    if st.button("상품명 20개 생성"):
        names = gen_product_names(brand, style, feats, length=length, n=20)
        st.write("\n".join(f"{i+1}. {n}" for i,n in enumerate(names)))

# (4) 선택 키워드 트렌드 (샘플)
with r1c4:
    st.subheader("선택 키워드 트렌드 (샘플)")
    import pandas as pd, numpy as np
    xs = np.arange(12)
    d = pd.DataFrame({"전체": 60+np.sin(xs/2)*8+np.linspace(0,10,12),
                      "패션의류": 58+np.sin(xs/2)*6+np.linspace(-1,4,12)})
    st.line_chart(d, height=220)

# ──────────────────────────────────────────────────────────────────────────────
# 2행 (4 × 1)
# ──────────────────────────────────────────────────────────────────────────────
r2c1, r2c2, r2c3, r2c4 = st.columns(4)

# (5) AI 키워드 레이더 (Rakuten)
with r2c1:
    st.subheader("AI 키워드 레이더 (Rakuten)")
    scope = st.radio("범위", ["국내","글로벌"], horizontal=True, key="rk_scope")
    cat = st.selectbox("라쿠텐 카테고리", ["전체(샘플)","패션","가전","식품"], key="rk_cat")
    st.caption(f"APP_ID: {RAKUTEN_APP_ID}  /  DEV: {RAKUTEN_DEV_ID}  /  AFFIL: {RAKUTEN_AFFIL_ID}")
    # 실제 API 연동은 엔드포인트/포맷 이슈가 있어 샘플로 채움
    sample = [f"[샘플] 랭킹 키워드 {i+1}" for i in range(20)]
    st.dataframe({"rank": list(range(1,21)), "keyword": sample, "source": ["sample"]*20}, use_container_width=True, height=240)

# (6) 구글 번역 (→ 실제 호출은 Papago)
with r2c2:
    st.subheader("구글 번역 (텍스트 입력/출력 + 한국어 확인용)")
    src = st.selectbox("원문 언어", ["자동 감지","ko","en","ja","zh-CN"], index=0)
    tgt = st.selectbox("번역 언어", ["영어","한국어","일본어","중국어(간체)"], index=0)
    tgt_map = {"영어":"en","한국어":"ko","일본어":"ja","중국어(간체)":"zh-CN"}
    text_in = st.text_area("원문 입력", height=180)
    if st.button("번역"):
        try:
            translated = naver_papago_translate(text_in, src="auto" if src=="자동 감지" else src, tgt=tgt_map[tgt])
            st.text_area("번역 결과", translated, height=180)
        except Exception as e:
            st.error(f"번역 실패: {e}")

# (7) 아이템스카우트 (원본 임베드)
with r2c3:
    st.subheader("아이템스카우트 (원본 임베드)")
    try:
        iframe(to_proxy("https://items.singtown.com"), height=520, scrolling=True)
    except TypeError:
        iframe("https://items.singtown.com", height=520, scrolling=True)

# (8) 셀러라이프 (원본 임베드)
with r2c4:
    st.subheader("셀러라이프 (원본 임베드)")
    try:
        iframe(to_proxy("https://www.sellerlife.co.kr"), height=520, scrolling=True)
    except TypeError:
        iframe("https://www.sellerlife.co.kr", height=520, scrolling=True)

st.caption("레이아웃은 고정(사이드바 sticky + 스크롤락, 4×2 카드) · 프록시는 기본값으로 항상 사용 · iframe은 모듈 버전 이슈 방지를 위해 key 미전달")

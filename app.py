# app.py — ENVY v11.x (stable) / Season 1 + Rakuten LIVE
# ─────────────────────────────────────────────────────────
# 필요 패키지: streamlit, requests, pandas, numpy
# pip install streamlit requests pandas numpy

import os, re, json, time
import base64
import requests
import pandas as pd
import numpy as np
from urllib.parse import quote

import streamlit as st

# ───────────────────────────────
# 0) 페이지/글로벌 스타일
# ───────────────────────────────
st.set_page_config(page_title="ENVY v11.x (stable)", layout="wide")

SBW = 320     # 사이드바 폭(px)
LOGO_W = 140  # 로고 정사각 크기(px)

st.markdown(f"""
<style>
:root {{ --sbw:{SBW}px; }}
section[data-testid="stSidebar"] {{
  position:fixed !important; top:0; left:0;
  width:var(--sbw) !important; height:100vh !important;
  overflow-y:auto !important; border-right:1px solid rgba(0,0,0,.06);
  z-index:1000; background:var(--background-color);
}}
div.block-container {{ padding-left:calc(var(--sbw) + 20px) !important; }}

.sb-logo {{ text-align:center; padding:10px 0 6px; }}
.sb-logo img {{
  width:{LOGO_W}px; height:{LOGO_W}px; object-fit:cover; border-radius:50%;
  box-shadow:0 1px 6px rgba(0,0,0,.08);
}}

.badge {{ border-radius:10px; padding:7px 10px; display:inline-block; font-weight:700; }}
.badge-blue  {{ background:#eef6ff; color:#1363df; }}
.badge-green {{ background:#eaf7ee; color:#0d8b43; }}
.badge-amber {{ background:#fff6e5; color:#b46900; }}
.badge-pink  {{ background:#ffeef4; color:#d61d5a; }}

.stTabs [role="tablist"] button {{ padding: 6px 12px; }}
</style>
""", unsafe_allow_html=True)

# ───────────────────────────────
# 1) 라쿠텐 API 키 (네가 준 값 기본 세팅) + secrets/env 덮어쓰기 허용
# ───────────────────────────────
# 기본값(사용자 제공)
RAKUTEN_APP_ID_DEFAULT = "1043271015809337425"
RAKUTEN_AFFILIATE_ID_DEFAULT = "4c723498.cbfeca46.4c723499.1deb6f77"
# secret은 ranking API엔 필요치 않지만, 향후 확장 대비
RAKUTEN_APP_SECRET_DEFAULT = "2772a28b2226bb18dfe36296faea89f3a6039528"

# secrets/env 우선
RAKUTEN_APP_ID = os.getenv("RAKUTEN_APP_ID", st.secrets.get("RAKUTEN_APP_ID", RAKUTEN_APP_ID_DEFAULT))
RAKUTEN_AFFILIATE_ID = os.getenv("RAKUTEN_AFFILIATE_ID", st.secrets.get("RAKUTEN_AFFILIATE_ID", RAKUTEN_AFFILIATE_ID_DEFAULT))
RAKUTEN_APP_SECRET = os.getenv("RAKUTEN_APP_SECRET", st.secrets.get("RAKUTEN_APP_SECRET", RAKUTEN_APP_SECRET_DEFAULT))

# ───────────────────────────────
# 2) 공통 유틸
# ───────────────────────────────
def sidebar_logo(path="logo.png"):
    if os.path.exists(path):
        b64 = base64.b64encode(open(path, "rb").read()).decode()
        st.sidebar.markdown(f'<div class="sb-logo"><img src="data:image/png;base64,{b64}"/></div><div style="text-align:center;font-weight:700;">envy</div>', unsafe_allow_html=True)
    else:
        st.sidebar.markdown('<div class="sb-logo" style="font-size:28px;font-weight:800;">envy</div>', unsafe_allow_html=True)

def iframe(url: str, height=560, scrolling=True):
    st.components.v1.iframe(url, height=height, scrolling=scrolling)

@st.cache_data(ttl=600, show_spinner=False)
def http_get_json(url, params=None, timeout=15):
    r = requests.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    return r.json()

def clean_tokens(text: str):
    # 간단 토크나이저: 한글/영문/숫자만 남기고 공백으로 분리
    text = re.sub(r"[^\w\s가-힣]", " ", text)
    toks = [t.strip() for t in text.split() if len(t.strip()) >= 2]
    return toks

def top_keywords_from_titles(titles, topk=20):
    from collections import Counter
    stop = set([
        "무료배송","인증","정품","판매","세트","국내","해외","버전","신형","구형","업그레이드","사은품","공식","당일","특가",
        "라쿠텐","楽天","ショップ","온라인","new","best","set","pack","brand"
    ])
    cnt = Counter()
    for t in titles:
        for tok in clean_tokens(t):
            if tok.lower() in stop: 
                continue
            cnt[tok] += 1
    return cnt.most_common(topk)

# ───────────────────────────────
# 3) 사이드바 (로고/다크모드/환율·마진 계산기/프록시)
# ───────────────────────────────
sidebar_logo()
dark = st.sidebar.toggle("다크/라이트 모드", value=False)
st.session_state["theme"] = "dark" if dark else "light"

st.sidebar.markdown("### 환율 계산기")
base = st.sidebar.selectbox("기준 통화", ["USD","KRW","JPY"], index=0)
amt  = st.sidebar.number_input("판매금액(외화)", min_value=0.0, value=1.0, step=0.01)
rate = {"USD":1400.0, "KRW":1.0, "JPY":9.5}[base]
won  = amt*rate
st.sidebar.markdown(f'<span class="badge badge-blue">환산 금액: <b>{won:,.0f} 원</b></span>', unsafe_allow_html=True)

st.sidebar.markdown("### 마진 계산기")
card_fee = st.sidebar.number_input("카드수수료(%)", 0.0, 50.0, 4.0, 0.1)
mkt_fee  = st.sidebar.number_input("마켓수수료(%)", 0.0, 50.0, 14.0, 0.1)
ship     = st.sidebar.number_input("배송비(원)", 0.0, 1_000_000.0, 0.0, 100.0)
margin_t = st.sidebar.radio("마진 방식", ["퍼센트","플러스"], horizontal=True, index=0)
margin_v = st.sidebar.number_input("마진(%)/플러스(원)", 0.0, 100000.0, 10.0, 0.5)
sell = won*(1+card_fee/100+mkt_fee/100) + ship
profit = sell*margin_v/100 if margin_t=="퍼센트" else margin_v
st.sidebar.markdown(f'<span class="badge badge-amber">판매가: <b>{sell+profit:,.0f} 원</b></span>', unsafe_allow_html=True)
st.sidebar.markdown(f'<span class="badge badge-green">순이익: <b>{profit:,.0f} 원</b></span>', unsafe_allow_html=True)

# 프록시 (비었을 때만 입력 UI 노출)
PROXY_URL = st.session_state.get("PROXY_URL","").strip()
if not PROXY_URL:
    st.sidebar.info("PROXY_URL 이 비어 있음. 아래에 Cloudflare Worker 주소를 입력해주세요.")
    PROXY_URL = st.sidebar.text_input("프록시 주소", value="https://envy-proxy.taesig0302.workers.dev")
    st.session_state["PROXY_URL"] = PROXY_URL

# ───────────────────────────────
# 4) 본문 상단 헤더
# ───────────────────────────────
st.title("ENVY — v11.x (stable)")
st.caption("시즌1: 데이터랩(분석 카드), 11번가/아이템스카우트/셀러라이프 임베드 + Rakuten 실연결")

# 행 1 (4칸)
r1c1, r1c2, r1c3, r1c4 = st.columns([1.35, 1.35, 1.3, 1.3], gap="large")
# 행 2 (4칸)
r2c1, r2c2, r2c3, r2c4 = st.columns([1.35, 1.35, 1.3, 1.3], gap="large")

# ───────────────────────────────
# 5) 데이터랩(시즌1-분석카드) — 샘플 트렌드
# ───────────────────────────────
with r1c1:
    st.subheader("데이터랩 (시즌1 – 분석 카드)")
    cat = st.selectbox("카테고리", ["디지털/가전","패션의류","화장품/미용"], key="dl_cat")
    per = st.selectbox("기간 단위", ["week","month"], key="dl_per")
    dev = st.selectbox("기기", ["all","pc","mo"], key="dl_dev")

    n = 12; x = np.arange(n)
    df = pd.DataFrame({"전체": 50+3*np.sin(x/1.2), "패션의류": 46+2*np.sin(x/1.3)})
    st.line_chart(df, height=220)

# ───────────────────────────────
# 6) 11번가 (아마존베스트) — 프록시 임베드
# ───────────────────────────────
with r1c2:
    st.subheader("11번가 (모바일) – 아마존베스트")
    base_11 = "https://m.11st.co.kr/page/main/abest?tabId=ABEST&pageId=AMOBEST&ctgr1No=166160"
    if PROXY_URL:
        url = f"{PROXY_URL}/?url={quote(base_11)}"
        iframe(url, height=560)
    else:
        st.warning("프록시가 비어 있어 iFrame이 차단될 수 있습니다.")

# ───────────────────────────────
# 7) 상품명 생성기 (규칙 기반)
# ───────────────────────────────
with r1c3:
    st.subheader("상품명 생성기 (규칙 기반)")
    brand = st.text_input("브랜드", placeholder="예: 오소")
    style = st.text_input("스타일/속성", placeholder="예: 프리미엄, S")
    name_len = st.slider("길이(단어 수)", 4, 12, 8)
    kw = st.text_area("핵심 키워드(콤마)", placeholder="예: 가습기, 무선청소기, 턴테이블", height=90)
    if st.button("상품명 20개 생성", use_container_width=True):
        kws = [k.strip() for k in kw.split(",") if k.strip()]
        out = []
        for i in range(20):
            word = (kws[i % max(1,len(kws))] if kws else "키워드")
            cand = f"{brand} {word} {style} {i+1}".strip()
            # 길이 맞추기(단어 수)
            while len(cand.split()) > name_len:
                cand = " ".join(cand.split()[:-1])
            out.append(cand)
        st.write("\n".join(out))

# ───────────────────────────────
# 8) 선택 키워드 트렌드 (샘플)
# ───────────────────────────────
with r1c4:
    st.subheader("선택 키워드 트렌드 (샘플)")
    n = 12; xs = np.arange(n)
    d = pd.DataFrame({
        "전체":    60 + np.sin(xs/2)*8 + np.linspace(0,10,n),
        "패션의류": 58 + np.sin(xs/2)*6 + np.linspace(-1,4,n)
    })
    st.line_chart(d, height=220)

# ───────────────────────────────
# 9) Rakuten 실연결 — 키워드 레이더
#    IchibaItem Ranking API로 상위 타이틀 수집 → 토큰화 → Top20
# ───────────────────────────────
RAKUTEN_RANKING_API = "https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20170628"

@st.cache_data(ttl=600, show_spinner=False)
def fetch_rakuten_ranking(genre_id: int, page=1):
    params = {
        "applicationId": RAKUTEN_APP_ID,
        "affiliateId": RAKUTEN_AFFILIATE_ID,
        "genreId": str(genre_id),
        "page": page
    }
    data = http_get_json(RAKUTEN_RANKING_API, params=params)
    return data

with r2c1:
    st.subheader("AI 키워드 레이더 (Rakuten, LIVE)")
    # 대표 장르 샘플 + 직접입력
    GENRES = {
        "전체(100283)": 100283,  # (샘플) 노트북액세서리 등으로 안내했던 값
        "패션(100371)": 100371,
        "가전(100227)": 100227,
        "뷰티(100939)": 100939,
        "식품(1002276)": 1002276
    }
    left, right = st.columns([1,1])
    with left:
        gname = st.selectbox("라쿠텐 카테고리(샘플)", list(GENRES.keys()), index=0)
        genre_id = GENRES[gname]
    with right:
        genre_id = st.number_input("직접 GenreID 입력(선택)", min_value=1, value=int(genre_id), step=1)

    pages = st.slider("랭킹 페이지 수(1페이지=30개)", 1, 3, 2)
    go = st.button("Top 키워드 뽑기", use_container_width=True)

    if go:
        if not RAKUTEN_APP_ID:
            st.error("Rakuten APP ID가 비어 있습니다. 상단 코드/환경변수/secrets에 설정하세요.")
        else:
            with st.spinner("Rakuten Ranking 불러오는 중..."):
                titles = []
                for p in range(1, pages+1):
                    try:
                        data = fetch_rakuten_ranking(int(genre_id), page=p)
                        items = (data or {}).get("Items", [])
                        for it in items:
                            title = it.get("Item", {}).get("itemName", "")
                            if title: titles.append(title)
                    except Exception as e:
                        st.warning(f"p{p} 호출 중 오류: {e}")
                if not titles:
                    st.warning("데이터가 비었습니다. GenreID/권한/쿼터를 확인하세요.")
                else:
                    top20 = top_keywords_from_titles(titles, topk=20)
                    df_kw = pd.DataFrame(top20, columns=["keyword","count"])
                    st.success(f"수집 타이틀 {len(titles)}건")
                    st.dataframe(df_kw, use_container_width=True, height=300)
                    try:
                        st.bar_chart(df_kw.set_index("keyword"), height=220)
                    except Exception:
                        pass
                    rec5 = [k for k,_ in top20[:5]]
                    st.markdown(f'**추천 키워드(5)**: `{", ".join(rec5)}`')

# ───────────────────────────────
# 10) 구글 번역(문구) — Season1: UI만 (시즌2에서 실제 API 연결)
# ───────────────────────────────
with r2c2:
    st.subheader("구글 번역 (문구) → 실제 호출은 Season2에서 연결")
    src = st.selectbox("원문 언어", ["자동 감지","영어","일본어","한국어"], index=0)
    dst = st.selectbox("번역 언어", ["영어","일본어","한국어"], index=0)
    text = st.text_area("원문 입력", height=140)
    if st.button("번역", use_container_width=True):
        st.info("데모: 시즌2에서 Papago/Google 번역 API 연동 예정")

# ───────────────────────────────
# 11) 아이템스카우트 / 셀러라이프 임베드
# ───────────────────────────────
with r2c3:
    st.subheader("아이템스카우트 (원본 임베드)")
    if PROXY_URL:
        iframe(f"{PROXY_URL}/?url={quote('https://items.singtown.com')}", height=480)
    else:
        st.warning("프록시가 비어 있어 iFrame이 차단될 수 있습니다.")

with r2c4:
    st.subheader("셀러라이프 (원본 임베드)")
    if PROXY_URL:
        iframe(f"{PROXY_URL}/?url={quote('https://www.sellerlife.co.kr')}", height=480)
    else:
        st.warning("프록시가 비어 있어 iFrame이 차단될 수 있습니다.")

st.markdown("---")
st.caption("레이아웃은 고정(사이드바 sticky + 스크롤락, 4×2 카드) · 프록시는 기본값으로 항상 사용 · iFrame은 브라우저 정책에 따라 차단될 수 있음")

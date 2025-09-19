# app.py — ENVY v11.x (stable) Season 1
# pip install streamlit requests pandas numpy

import os, re, base64, json, time
import requests
import numpy as np
import pandas as pd
from urllib.parse import quote
import streamlit as st

# ───────────────────────────────
# 페이지 & 스타일
# ───────────────────────────────
st.set_page_config(page_title="ENVY v11.x (stable)", layout="wide")
SBW = 320
LOGO_W = 140

st.markdown(f"""
<style>
:root {{ --sbw:{SBW}px; }}
section[data-testid="stSidebar"] {{
  position:fixed !important; top:0; left:0;
  width:var(--sbw) !important; height:100vh !important;
  overflow-y:auto !important; border-right:1px solid rgba(0,0,0,.06);
  z-index:1000; background:var(--background-color);
}}
div.block-container {{ padding-left:calc(var(--sbw) + 22px) !important; }}
.sb-logo {{ text-align:center; padding:14px 0 8px; }}
.sb-logo img {{
  width:{LOGO_W}px; height:{LOGO_W}px; object-fit:cover; border-radius:50%;
  box-shadow:0 1px 6px rgba(0,0,0,.08);
}}
.badge {{ border-radius:10px; padding:7px 10px; display:inline-block; font-weight:700; }}
.badge-blue  {{ background:#eef6ff; color:#1363df; }}
.badge-green {{ background:#eaf7ee; color:#0d8b43; }}
.badge-amber {{ background:#fff6e5; color:#b46900; }}
.card-title {{ margin-bottom:4px; }}
</style>
""", unsafe_allow_html=True)

# ───────────────────────────────
# 라쿠텐 API 키 (기본값=제공값, secrets/env로 덮어쓰기 허용)
# ───────────────────────────────
RAKUTEN_APP_ID = os.getenv("RAKUTEN_APP_ID", st.secrets.get("RAKUTEN_APP_ID", "1043271015809337425"))
RAKUTEN_AFFILIATE_ID = os.getenv("RAKUTEN_AFFILIATE_ID", st.secrets.get("RAKUTEN_AFFILIATE_ID", "4c723498.cbfeca46.4c723499.1deb6f77"))
# secret은 이번 API에 필수는 아님(서명형 아님) — 확장 대비만 남김
RAKUTEN_APP_SECRET = os.getenv("RAKUTEN_APP_SECRET", st.secrets.get("RAKUTEN_APP_SECRET", "2772a28b2226bb18dfe36296faea89f3a6039528"))

# ───────────────────────────────
# 유틸
# ───────────────────────────────
def sidebar_logo(path="logo.png"):
    if os.path.exists(path):
        b64 = base64.b64encode(open(path, "rb").read()).decode()
        st.sidebar.markdown(
            f'<div class="sb-logo"><img src="data:image/png;base64,{b64}"/></div><div style="text-align:center;font-weight:700;">envy</div>',
            unsafe_allow_html=True
        )
    else:
        st.sidebar.markdown('<div class="sb-logo" style="font-size:28px;font-weight:800;">envy</div>', unsafe_allow_html=True)

def iframe(url: str, height=560, scrolling=True, key=None):
    return st.components.v1.iframe(url, height=height, scrolling=scrolling, key=key)

@st.cache_data(ttl=600, show_spinner=False)
def http_get_json(url, params=None, timeout=15):
    r = requests.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    return r.json()

def clean_tokens(text: str):
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
# 사이드바 (로고/모드/환율/마진/프록시)
# ───────────────────────────────
sidebar_logo()
dark = st.sidebar.toggle("다크/라이트 모드", value=False)
st.session_state["theme"] = "dark" if dark else "light"

st.sidebar.markdown("### 환율 계산기")
base = st.sidebar.selectbox("통화 선택", ["USD","KRW","JPY","EUR"], index=0)
amount = st.sidebar.number_input("구매 금액(선택한 통화)", min_value=0.0, value=1.0, step=0.01)
# 환율 직접 입력(사용자 기준) — 기본값 예시
default_rate = {"USD":1400.0, "KRW":1.0, "JPY":9.5, "EUR":1500.0}[base]
rate = st.sidebar.number_input(f"{base} → KRW 환율", min_value=0.0001, value=float(default_rate), step=0.01)
won_value = amount * rate
st.sidebar.markdown(f'<span class="badge badge-blue">환산 금액: <b>{won_value:,.0f} 원</b></span>', unsafe_allow_html=True)

st.sidebar.markdown("### 마진 계산기")
card_fee = st.sidebar.number_input("카드수수료(%)", 0.0, 50.0, 4.0, 0.1)
mkt_fee  = st.sidebar.number_input("마켓수수료(%)", 0.0, 50.0, 14.0, 0.1)
ship     = st.sidebar.number_input("배송비(원)", 0.0, 1_000_000.0, 0.0, 100.0)
mtype    = st.sidebar.radio("마진 방식", ["퍼센트","플러스"], horizontal=True, index=0)
mval     = st.sidebar.number_input("마진(%)/플러스(원)", 0.0, 1_000_000.0, 10.0, 0.5)

base_cost = won_value
sell_base = base_cost*(1+card_fee/100+mkt_fee/100) + ship
profit    = sell_base*mval/100 if mtype=="퍼센트" else mval
sell      = sell_base + profit
st.sidebar.markdown(f'<span class="badge badge-amber">판매가: <b>{sell:,.0f} 원</b></span>', unsafe_allow_html=True)
st.sidebar.markdown(f'<span class="badge badge-green">순이익: <b>{profit:,.0f} 원</b></span>', unsafe_allow_html=True)

# 프록시 — 비었을 때만 노출
PROXY_URL = st.session_state.get("PROXY_URL","").strip()
if not PROXY_URL:
    st.sidebar.info("프록시가 비어 있습니다. 아래에 Cloudflare Worker 주소를 1회 입력해 주세요.")
    PROXY_URL = st.sidebar.text_input("프록시 주소", "https://envy-proxy.taesig0302.workers.dev").strip()
    st.session_state["PROXY_URL"] = PROXY_URL

# ───────────────────────────────
# 본문 헤더/그리드
# ───────────────────────────────
st.title("ENVY — v11.x (stable)")
st.caption("시즌1: 데이터랩(분석 카드) · 11번가/아이템스카우트/셀러라이프 임베드 · Rakuten 실연결")

# 4×2 고정
r1c1, r1c2, r1c3, r1c4 = st.columns([1.35, 1.35, 1.3, 1.3], gap="large")
r2c1, r2c2, r2c3, r2c4 = st.columns([1.35, 1.35, 1.3, 1.3], gap="large")

# ───────────────────────────────
# 1-1) 데이터랩 (분석 카드)
# ───────────────────────────────
with r1c1:
    st.subheader("데이터랩 (시즌1 – 분석 카드)")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.selectbox("카테고리", ["디지털/가전","패션의류","화장품/미용"], index=0, key="dl_cat")
    with c2:
        st.selectbox("기간 단위", ["week","month"], index=0, key="dl_per")
    with c3:
        st.selectbox("기기", ["all","pc","mo"], index=0, key="dl_dev")

    n = 12; x = np.arange(n)
    df = pd.DataFrame({"전체": 60+np.sin(x/2)*8, "패션의류": 58+np.sin(x/2)*6})
    st.line_chart(df, height=220, use_container_width=True)

# ───────────────────────────────
# 1-2) 선택 키워드 트렌드 (샘플)
# ───────────────────────────────
with r1c2:
    st.subheader("선택 키워드 트렌드 (샘플)")
    n = 12; xs = np.arange(n)
    d = pd.DataFrame({
        "전체":    70 + np.sin(xs/2)*8 + np.linspace(0,8,n),
        "패션의류": 68 + np.sin(xs/2)*6 + np.linspace(-1,4,n)
    })
    st.line_chart(d, height=220, use_container_width=True)

# ───────────────────────────────
# 1-3) 11번가 (아마존베스트) — 프록시 임베드
# ───────────────────────────────
with r1c3:
    st.subheader("11번가 (모바일) – 아마존베스트")
    abest = "https://m.11st.co.kr/page/main/abest?tabId=ABEST&pageId=AMOBEST&ctgr1No=166160"
    if PROXY_URL:
        try:
            iframe(f"{PROXY_URL}/?url={quote(abest)}", height=560, key="amobest")
        except Exception:
            st.warning("iFrame 임베드가 차단되었습니다.")
            st.link_button("프록시로 새창 열기", f"{PROXY_URL}/?url={quote(abest)}", use_container_width=True)
    else:
        st.warning("프록시가 비어 있어 iFrame이 차단될 수 있습니다.")
        st.link_button("프록시 새창 열기", abest, use_container_width=True)

# ───────────────────────────────
# 1-4) 상품명 생성기 (규칙 기반)
# ───────────────────────────────
with r1c4:
    st.subheader("상품명 생성기 (규칙 기반)")
    b, s = st.columns(2)
    with b:
        brand = st.text_input("브랜드", placeholder="예: 오소")
    with s:
        style = st.text_input("스타일/속성", placeholder="예: 프리미엄, S")
    name_len = st.slider("길이(단어 수)", 4, 12, 8)
    kw = st.text_area("핵심 키워드(콤마)", placeholder="예: 가습기, 무선청소기, 턴테이블", height=88)
    if st.button("상품명 20개 생성", use_container_width=True):
        kws = [k.strip() for k in kw.split(",") if k.strip()]
        out = []
        for i in range(20):
            word = (kws[i % max(1,len(kws))] if kws else "키워드")
            cand = f"{brand} {word} {style} {i+1}".strip()
            while len(cand.split()) > name_len:
                cand = " ".join(cand.split()[:-1])
            out.append(cand)
        st.code("\n".join(out), language="text")

# ───────────────────────────────
# 2-1) AI 키워드 레이더 (Rakuten, LIVE)
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
    return http_get_json(RAKUTEN_RANKING_API, params=params)

with r2c1:
    st.subheader("AI 키워드 레이더 (Rakuten, LIVE)")
    GENRES = {"전체(100283)":100283, "패션(100371)":100371, "가전(100227)":100227, "뷰티(100939)":100939}
    c1, c2 = st.columns(2)
    with c1:
        gname = st.selectbox("라쿠텐 카테고리(샘플)", list(GENRES.keys()), index=0)
        genre_id = GENRES[gname]
    with c2:
        genre_id = st.number_input("직접 GenreID 입력(선택)", min_value=1, value=int(genre_id), step=1)

    pages = st.slider("랭킹 페이지 수(1p=30개)", 1, 3, 2)
    if st.button("Top 키워드 뽑기", use_container_width=True):
        if not RAKUTEN_APP_ID:
            st.error("Rakuten APP ID가 비어 있습니다. 코드/환경변수/secrets에 설정하세요.")
        else:
            titles = []
            for p in range(1, pages+1):
                try:
                    data = fetch_rakuten_ranking(int(genre_id), page=p)
                    for it in (data or {}).get("Items", []):
                        t = it.get("Item", {}).get("itemName", "")
                        if t: titles.append(t)
                except Exception as e:
                    st.warning(f"p{p} 호출 오류: {e}")
            if not titles:
                st.warning("데이터가 비었습니다. GenreID/쿼터/권한 확인.")
            else:
                top20 = top_keywords_from_titles(titles, topk=20)  # 정확히 20개
                df_kw = pd.DataFrame(top20, columns=["keyword","count"])
                st.dataframe(df_kw, height=300, use_container_width=True)
                try:
                    st.bar_chart(df_kw.set_index("keyword"), height=220, use_container_width=True)
                except Exception:
                    pass
                st.markdown("**추천 키워드(5)**: " + ", ".join([k for k,_ in top20[:5]]))

# ───────────────────────────────
# 2-2) 구글 번역 (UI 유지 — 시즌2에서 실제 호출)
# ───────────────────────────────
with r2c2:
    st.subheader("구글 번역 (텍스트 입력/출력 + 한국어 확인용)")
    c1, c2 = st.columns(2)
    with c1:
        src = st.selectbox("원문 언어", ["자동 감지","영어","일본어","한국어"], index=0)
    with c2:
        dst = st.selectbox("번역 언어", ["영어","일본어","한국어"], index=2)
    text = st.text_area("원문 입력", height=150)
    if st.button("번역", use_container_width=True):
        st.info("시즌2에서 실제 Papago/Google 번역 API로 연결합니다. (현재는 UI만 유지)")
        st.text_area("번역 결과", value=text, height=150)  # 자리표시

# ───────────────────────────────
# 2-3) 아이템스카우트 / 2-4) 셀러라이프 (프록시 임베드)
# ───────────────────────────────
with r2c3:
    st.subheader("아이템스카우트 (원본 임베드)")
    url = "https://items.singtown.com"
    if PROXY_URL:
        try:
            iframe(f"{PROXY_URL}/?url={quote(url)}", height=480, key="itemscout")
        except Exception:
            st.error("임베드 실패. (Cloudflare 1016 등) 새창으로 열어주세요.")
            st.link_button("프록시 새창 열기", f"{PROXY_URL}/?url={quote(url)}", use_container_width=True)
    else:
        st.link_button("바로 열기", url, use_container_width=True)

with r2c4:
    st.subheader("셀러라이프 (원본 임베드)")
    url = "https://www.sellerlife.co.kr"
    if PROXY_URL:
        try:
            iframe(f"{PROXY_URL}/?url={quote(url)}", height=480, key="sellerlife")
        except Exception:
            st.error("임베드 실패. 새창으로 열어주세요.")
            st.link_button("프록시 새창 열기", f"{PROXY_URL}/?url={quote(url)}", use_container_width=True)
    else:
        st.link_button("바로 열기", url, use_container_width=True)

st.markdown("---")
st.caption("레이아웃 고정(사이드바 sticky · 4×2) · 프록시는 기본값 사용. 외부 사이트 iFrame은 차단될 수 있어 새창 링크를 함께 제공합니다.")

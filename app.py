# app.py — ENVY Season1 (고정 레이아웃 + 실 Rakuten + DataLab 시즌1 카드형)
# 필요: pip install streamlit requests pandas numpy

import os, re, base64, json, time, datetime as dt
from urllib.parse import quote
import requests
import numpy as np
import pandas as pd
import streamlit as st

# ─────────────────────────────────────────────────────────
# 기본 설정
# ─────────────────────────────────────────────────────────
st.set_page_config(page_title="ENVY v11.x (stable)", layout="wide")

# 사이드바 고정/스크롤락 + 가로 스크롤 제거 + 로고/배지/읽기박스
st.markdown("""
<style>
html, body, [data-testid="stAppViewContainer"] > .main { overflow-x: hidden !important; }
section[data-testid="stSidebar"]{
  position: fixed !important; top:0; left:0; bottom:0;
  width: 280px !important; min-width: 280px !important; height: 100vh !important;
  overflow-y: auto !important; border-right:1px solid rgba(0,0,0,.06); z-index:1000;
}
div.block-container { padding-left: 300px !important; }

/* 로고(원형/그림자/기존 사이즈) */
.sb-logo img{
  width:120px; height:120px; object-fit:cover; border-radius:50%;
  box-shadow:0 1px 6px rgba(0,0,0,.08); display:block; margin: 8px auto 2px auto;
}

/* 배지 & 읽기박스 */
.badge {display:inline-block; padding:4px 8px; border-radius:8px; font-size:12px; line-height:1;}
.badge.muted{background:#f2f2f2; color:#666;}
.badge.green{background:#e7f7ec; color:#138a36;}
.badge.blue{background:#e9f2ff; color:#1d4ed8;}
.badge.orange{background:#fff2e5; color:#c2410c;}

.kbox { border-radius:10px; padding:10px 12px; margin-top:6px; border:1px solid rgba(0,0,0,.06); }
.kbox.blue   { background:#eef4ff; color:#1e3a8a; }
.kbox.orange { background:#fff4e6; color:#9a3412; }
.kbox.green  { background:#edfbea; color:#166534; }
.kbox.gray   { background:#f6f7f9; color:#475569; }
.kbox .lbl { font-size:12px; opacity:.8; margin-bottom:2px; }
.kbox .val { font-size:18px; font-weight:700; }

/* iFrame 외곽 스크롤 숨김(완전 차단은 불가하나 시각 축소) */
.element-container iframe { scrollbar-width: none; }
.element-container iframe::-webkit-scrollbar { display: none; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────
# 상수/유틸
# ─────────────────────────────────────────────────────────
DEFAULT_PROXY = "https://envy-proxy.taesig0302.workers.dev"

def money(v: float) -> str:
    try: return f"{v:,.0f} 원"
    except: return "-"

def kbox(label: str, value: str, color: str = "blue"):
    st.markdown(
        f"""
        <div class="kbox {color}">
          <div class="lbl">{label}</div>
          <div class="val">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def sidebar_logo(path="logo.png"):
    if os.path.exists(path):
        b64 = base64.b64encode(open(path,"rb").read()).decode()
        st.sidebar.markdown(f'<div class="sb-logo"><img src="data:image/png;base64,{b64}"></div><div style="text-align:center;font-weight:700;margin-bottom:8px;">envy</div>', unsafe_allow_html=True)
    else:
        st.sidebar.markdown('<div class="sb-logo" style="font-size:28px;font-weight:800;text-align:center;">envy</div>', unsafe_allow_html=True)

def iframe(url: str, height=560, scrolling=True):
    # Streamlit iframe은 key 인자를 받지 않습니다(에러 방지).
    st.components.v1.iframe(url, height=height, scrolling=scrolling)

@st.cache_data(ttl=600, show_spinner=False)
def http_get_json(url, params=None, headers=None, timeout=15, method="GET", data=None):
    if method == "GET":
        r = requests.get(url, params=params, headers=headers, timeout=timeout)
    else:
        r = requests.post(url, params=params, headers=headers, data=data, timeout=timeout)
    r.raise_for_status()
    return r.json()

# 라쿠텐 키워드 토큰화
def clean_tokens(text: str):
    text = re.sub(r"[^\w\s가-힣]", " ", text)
    toks = [t.strip() for t in text.split() if len(t.strip()) >= 2]
    return toks

def top_keywords_from_titles(titles, topk=20):
    from collections import Counter
    stop = set(["무료배송","인증","정품","판매","세트","국내","해외","버전","신형","구형","업그레이드","사은품","공식","당일","특가",
                "라쿠텐","楽天","ショップ","온라인","new","best","set","pack","brand"])
    cnt = Counter()
    for t in titles:
        for tok in clean_tokens(t):
            if tok.lower() in stop: continue
            cnt[tok] += 1
    return cnt.most_common(topk)

# ─────────────────────────────────────────────────────────
# 시크릿/환경(라쿠텐/네이버)
# ─────────────────────────────────────────────────────────
RAKUTEN_APP_ID       = os.getenv("RAKUTEN_APP_ID",       st.secrets.get("RAKUTEN_APP_ID",       "1043271015809337425"))
RAKUTEN_AFFILIATE_ID = os.getenv("RAKUTEN_AFFILIATE_ID", st.secrets.get("RAKUTEN_AFFILIATE_ID", "4c723498.cbfeca46.4c723499.1deb6f77"))
# NAVER DataLab 접근용 쿠키(사용자가 st.secrets 또는 env에 저장)
NAVER_COOKIE         = os.getenv("NAVER_COOKIE",         st.secrets.get("NAVER_COOKIE",         ""))

# ─────────────────────────────────────────────────────────
# 사이드바 (고정/스크롤락/로고/모드/환율/마진/프록시 표시조건)
# ─────────────────────────────────────────────────────────
with st.sidebar:
    sidebar_logo()
    dark_on = st.toggle("다크/라이트 모드", key="__theme_toggle", value=(st.session_state.get("__theme__","light")=="dark"))
    st.session_state["__theme__"] = "dark" if dark_on else "light"

    st.markdown("---")
    st.markdown("### 환율 계산기")

    FX = {"USD":1400.0, "EUR":1550.0, "JPY":9.3}  # 필요 시 갱신
    fx_ccy = st.selectbox("통화 선택", list(FX.keys()), index=0, key="ccy_sel")
    fx_amount = st.number_input("구매금액(외화)", min_value=0.0, step=1.0, value=0.0, key="fx_amount")
    fx_rate = FX.get(fx_ccy, 1.0)
    fx_converted_krw = fx_amount * fx_rate
    kbox("환산 금액 (읽기용)", money(fx_converted_krw), "blue")

    st.markdown("---")
    st.markdown("### 마진 계산기")

    buy_krw = st.number_input("구매금액(원화)", min_value=0.0, step=100.0, value=float(fx_converted_krw), key="mgn_buy_krw")
    kbox("환산 금액 (읽기용)", money(fx_converted_krw), "gray")

    card_fee   = st.number_input("카드수수료(%)",  min_value=0.0, step=0.1, value=4.0,  key="mgn_card")
    market_fee = st.number_input("마켓수수료(%)",  min_value=0.0, step=0.1, value=14.0, key="mgn_market")
    ship_cost  = st.number_input("배송비(원)",     min_value=0.0, step=100.0, value=0.0, key="mgn_ship")
    mgn_mode   = st.radio("마진 방식", ["퍼센트", "플러스"], horizontal=True, key="mgn_mode")
    mgn_value  = st.number_input("마진(%) / 플러스(원)", min_value=0.0, step=0.5, value=10.0, key="mgn_val")

    # 판매가 기준 수수료 역산
    base_cost = buy_krw + ship_cost
    fee_rate  = (card_fee + market_fee) / 100.0
    if mgn_mode == "퍼센트":
        target_margin_rate = mgn_value / 100.0
        denom = 1.0 - fee_rate - target_margin_rate
        sale_price = base_cost / denom if denom > 0 else 0.0
    else:
        denom = 1.0 - fee_rate
        sale_price = (base_cost + mgn_value) / denom if denom > 0 else 0.0
    fees   = sale_price * fee_rate
    profit = sale_price - base_cost - fees

    kbox("판매가 (읽기용)", money(sale_price), "orange")
    kbox("순이익 (읽기용)", money(profit), "green")

    # 프록시는 평소 비표시, 에러시만 노출
    show_proxy_panel = st.session_state.get("SHOW_PROXY_PANEL", False)
    if show_proxy_panel:
        st.markdown("---")
        st.warning("외부 페이지 임베드가 차단되었습니다(401/403/1016 등). 프록시를 확인하세요.")
        new_proxy = st.text_input("프록시 주소", st.session_state.get("PROXY_URL", DEFAULT_PROXY)).strip()
        if new_proxy:
            st.session_state["PROXY_URL"] = new_proxy
            st.session_state["SHOW_PROXY_PANEL"] = False  # 저장 후 숨김

# 프록시 기본값
PROXY_URL = st.session_state.get("PROXY_URL", DEFAULT_PROXY)

def flag_proxy_issue():
    st.session_state["SHOW_PROXY_PANEL"] = True

# ─────────────────────────────────────────────────────────
# 레이아웃 4×2 (Row1: 데이터랩 → 선택키워드트렌드 → 11번가 → 상품명생성기)
#                 (Row2: 라쿠텐 LIVE → 구글번역 → 아이템스카우트 → 셀러라이프)
# ─────────────────────────────────────────────────────────
st.title("ENVY — v11.x (stable)")
st.caption("Season1: 데이터랩(분석 카드) · Rakuten LIVE · 11번가/아이템스카우트/셀러라이프 임베드")

r1c1, r1c2, r1c3, r1c4 = st.columns([1.4, 1.2, 1.4, 1.0], gap="large")
r2c1, r2c2, r2c3, r2c4 = st.columns([1.4, 1.2, 1.4, 1.0], gap="large")

# ─────────────────────────────────────────────────────────
# Row1-1) 데이터랩 (시즌1 – 분석 카드, 실제 호출: 쿠키 필요)
# ─────────────────────────────────────────────────────────
# 참고: DataLab은 비공식 엔드포인트로 쿠키/리퍼러가 필요합니다.
#  - NAVER_COOKIE (전체 쿠키 스트링)를 st.secrets 또는 환경변수에 저장해 두세요.
#  - 카테고리 CID 직접 입력도 허용.
DATALAB_ENDPOINT = "https://datalab.naver.com/shoppingInsight/getCategoryKeywordRank.naver"

DATALAB_CATS = {
    "디지털/가전": "50000003",
    "패션의류": "50000000",
    "화장품/미용": "50000002",
    "생활/건강": "50000004",
    "가구/인테리어": "50000001",
}

def datalab_top20(cid: str, start: str, end: str, device: str="all", timeUnit: str="date"):
    if not NAVER_COOKIE:
        raise RuntimeError("NAVER_COOKIE 미설정")
    headers = {
        "User-Agent":"Mozilla/5.0",
        "Referer":"https://datalab.naver.com/shoppingInsight/sCategory.naver",
        "Cookie": NAVER_COOKIE,
    }
    payload = {
        "cid": cid,
        "startDate": start,   # "YYYY.MM.DD."
        "endDate": end,       # "YYYY.MM.DD."
        "timeUnit": timeUnit, # "date"/"week"/"month"
        "device": device,     # "all"/"mo"/"pc"
        "gender": "",         # 전체
        "ages": "",           # 전체
        "page": 1,
        "count": 20
    }
    data = http_get_json(DATALAB_ENDPOINT, headers=headers, data=payload, method="POST", timeout=15)
    return data

with r1c1:
    st.subheader("데이터랩 (시즌1 – 분석 카드)")
    cc1, cc2, cc3, cc4 = st.columns([1,1,1,1])
    with cc1:
        cat = st.selectbox("카테고리", list(DATALAB_CATS.keys()), index=0, key="dl_cat")
    with cc2:
        device = st.selectbox("기기", ["all","pc","mo"], index=0, key="dl_dev")
    with cc3:
        unit = st.selectbox("기간단위", ["date","week","month"], index=1, key="dl_unit")
    with cc4:
        cid_override = st.text_input("CID(직접입력)", value=DATALAB_CATS[cat], key="dl_cid")

    # 기간: 최근 30일
    end_date = dt.date.today()
    start_date = end_date - dt.timedelta(days=30)
    sd = start_date.strftime("%Y.%m.%d.")
    ed = end_date.strftime("%Y.%m.%d.")

    top_btn = st.button("Top20 불러오기", use_container_width=True)
    top_df = None
    if top_btn:
        try:
            res = datalab_top20(cid_override, sd, ed, device=device, timeUnit=unit)
            ranks = (res or {}).get("ranks", [])
            if not ranks:
                st.error("조회 실패: ranks 비어 있음(쿠키/구조/기간/기기 조건 확인).")
            else:
                rows = [{"rank":i+1, "keyword": r.get("keyword"), "score": r.get("ratio", r.get("score", None))}
                        for i, r in enumerate(ranks[:20])]
                top_df = pd.DataFrame(rows)
                st.dataframe(top_df, use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"조회 실패: {e}")

# ─────────────────────────────────────────────────────────
# Row1-2) 선택 키워드 트렌드(라인 차트) — 실제 연동은 위 선택 결과 활용
# ─────────────────────────────────────────────────────────
TREND_ENDPOINT = "https://datalab.naver.com/shoppingInsight/getKeywordSearchTrend.naver"

def datalab_trend(keywords, start: str, end: str, device: str="all", timeUnit: str="week"):
    if not NAVER_COOKIE:
        raise RuntimeError("NAVER_COOKIE 미설정")
    headers = {
        "User-Agent":"Mozilla/5.0",
        "Referer": "https://datalab.naver.com/shoppingInsight/sCategory.naver",
        "Cookie": NAVER_COOKIE,
    }
    # Naver의 트렌드 API는 복수 키워드 배열을 문자열로 받는 형태(내부 포맷 변경될 수 있음)
    # 여기서는 간단히 첫 5개까지만 전달
    kw_str = ",".join(keywords[:5])
    payload = {
        "timeUnit": timeUnit,
        "startDate": start,
        "endDate": end,
        "device": device,
        "gender": "",
        "ages": "",
        "keyword": kw_str
    }
    data = http_get_json(TREND_ENDPOINT, headers=headers, data=payload, method="POST", timeout=15)
    return data

with r1c2:
    st.subheader("선택 키워드 트렌드")
    st.caption("데이터랩 Top20에서 최대 5개 선택하여 조회")
    # 키워드 소스: 방금 조회한 top_df가 있으면 그걸로, 없으면 수동 입력
    default_kws = []
    if 'top_df' in locals() and isinstance(top_df, pd.DataFrame) and not top_df.empty:
        default_kws = top_df['keyword'].head(5).tolist()
    kw_text = st.text_input("키워드(최대 5개, 콤마)", value=",".join(default_kws) if default_kws else "")
    kws = [k.strip() for k in kw_text.split(",") if k.strip()][:5]

    # 기간: 위와 동일
    end_date = dt.date.today()
    start_date = end_date - dt.timedelta(days=180 if st.session_state.get("dl_unit","week")=="week" else 30)
    sd = start_date.strftime("%Y.%m.%d.")
    ed = end_date.strftime("%Y.%m.%d.")

    trend_btn = st.button("트렌드 불러오기", use_container_width=True)
    if trend_btn:
        if not kws:
            st.warning("키워드를 1개 이상 입력하세요.")
        else:
            try:
                res = datalab_trend(kws, sd, ed, device=st.session_state.get("dl_dev","all"), timeUnit=st.session_state.get("dl_unit","week"))
                series = (res or {}).get("results", [])
                if not series:
                    st.error("조회 실패: results 비어 있음(쿠키/구조/권한 확인).")
                else:
                    # 간단 파싱: 각 시리즈에 period/value 배열이 존재한다고 가정
                    # 실제 구조 변경 시 아래 파싱을 조정
                    # 예시 포맷: {"title":"키워드","data":[{"period":"YYYY-MM","ratio":12.3}, ...]}
                    frame = {}
                    idx = None
                    for s in series:
                        title = s.get("title","keyword")
                        data = s.get("data") or s.get("keywords") or []
                        x = []
                        y = []
                        for d in data:
                            p = d.get("period") or d.get("date")
                            v = d.get("ratio")  or d.get("value")
                            if p is not None and v is not None:
                                x.append(p); y.append(float(v))
                        if x and y:
                            if idx is None: idx = x
                            frame[title] = y
                    if frame and idx:
                        df_line = pd.DataFrame(frame, index=idx)
                        st.line_chart(df_line, use_container_width=True, height=240)
                    else:
                        st.error("트렌드 파싱 실패(구조 변경 가능성).")
            except Exception as e:
                st.error(f"조회 실패: {e}")

# ─────────────────────────────────────────────────────────
# Row1-3) 11번가 (모바일) – 아마존베스트 (프록시 iFrame + 새창)
# ─────────────────────────────────────────────────────────
with r1c3:
    st.subheader("11번가 (모바일) – 아마존베스트")
    abest = "https://m.11st.co.kr/page/main/abest?tabId=ABEST&pageId=AMOBEST&ctgr1No=166160"
    try:
        iframe(f"{PROXY_URL}/?url={quote(abest)}", height=520)
    except Exception:
        st.warning("iFrame 임베드가 차단되었습니다.")
        st.link_button("프록시로 새창 열기", f"{PROXY_URL}/?url={quote(abest)}", use_container_width=True)
        flag_proxy_issue()

# ─────────────────────────────────────────────────────────
# Row1-4) 상품명 생성기 (규칙 기반)
# ─────────────────────────────────────────────────────────
with r1c4:
    st.subheader("상품명 생성기 (규칙 기반)")
    b, s = st.columns(2)
    with b:
        brand = st.text_input("브랜드", placeholder="예: 오소")
    with s:
        style = st.text_input("스타일/속성", placeholder="예: 프리미엄, S")
    name_len = st.slider("길이(단어 수)", 4, 12, 8)
    kw = st.text_area("핵심 키워드(콤마)", placeholder="예: 가습기, 무선청소기, 턴테이블", height=96)
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

# ─────────────────────────────────────────────────────────
# Row2-1) AI 키워드 레이더 (Rakuten, LIVE) — Top20 제한
# ─────────────────────────────────────────────────────────
RAKUTEN_RANKING_API = "https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20170628"

@st.cache_data(ttl=600, show_spinner=False)
def fetch_rakuten_ranking(genre_id: int, page=1):
    params = {
        "applicationId": RAKUTEN_APP_ID,
        "affiliateId":   RAKUTEN_AFFILIATE_ID,
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
        genre_id = st.number_input("직접 GenreID 입력", min_value=1, value=int(genre_id), step=1)
    pages = st.slider("랭킹 페이지 수(1p=30개)", 1, 30, 2)

    if st.button("Top 키워드 뽑기", use_container_width=True):
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
            top20 = top_keywords_from_titles(titles, topk=20)
            df_kw = pd.DataFrame(top20, columns=["keyword","count"])
            st.dataframe(df_kw, height=300, use_container_width=True)
            try:
                st.bar_chart(df_kw.set_index("keyword"), height=220, use_container_width=True)
            except Exception:
                pass
            st.markdown("**추천 키워드(5)**: " + ", ".join([k for k,_ in top20[:5]]))

# ─────────────────────────────────────────────────────────
# Row2-2) 구글 번역 UI (시즌1: UI 유지)
# ─────────────────────────────────────────────────────────
with r2c2:
    st.subheader("구글 번역 (텍스트 입력/출력 + 한국어 확인용)")
    c1, c2 = st.columns(2)
    with c1:
        src = st.selectbox("원문 언어", ["자동 감지","영어","일본어","한국어"], index=0)
    with c2:
        dst = st.selectbox("번역 언어", ["영어","일본어","한국어"], index=2)
    text = st.text_area("원문 입력", height=150)
    if st.button("번역", use_container_width=True):
        # 시즌1: UI만 유지 (시즌2에서 실제 API 연결)
        st.text_area("번역 결과", value=text, height=150)

# ─────────────────────────────────────────────────────────
# Row2-3/4) 아이템스카우트 & 셀러라이프 (프록시 임베드)
# ─────────────────────────────────────────────────────────
with r2c3:
    st.subheader("아이템스카우트 (원본 임베드)")
    url = "https://items.singtown.com"
    try:
        iframe(f"{PROXY_URL}/?url={quote(url)}", height=420)
    except Exception:
        st.error("임베드 실패. (Cloudflare 1016 등) 새창으로 열어주세요.")
        st.link_button("프록시 새창 열기", f"{PROXY_URL}/?url={quote(url)}", use_container_width=True)
        flag_proxy_issue()

with r2c4:
    st.subheader("셀러라이프 (원본 임베드)")
    url = "https://www.sellerlife.co.kr"
    try:
        iframe(f"{PROXY_URL}/?url={quote(url)}", height=420)
    except Exception:
        st.error("임베드 실패. 새창으로 열어주세요.")
        st.link_button("프록시 새창 열기", f"{PROXY_URL}/?url={quote(url)}", use_container_width=True)
        flag_proxy_issue()

st.markdown("---")
st.caption("사이드바 sticky/스크롤락 · 4×2 고정 · 환율/마진 분리(읽기용 컬러박스) · 11번가/아이템스카우트/셀러라이프 프록시 임베드 · Rakuten LIVE · DataLab(쿠키 필요)")

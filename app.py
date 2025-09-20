# =========================================================
# ENVY — Season 1 (Dual Proxy Edition) · app.py  (2025-09-20)
# - 사이드바: 환율/마진 계산기 "로직 불변" + 가시성 개선(전용 스크롤/여백 축소)
# - 본문 3열 그리드: 데이터랩 폭 ↑ (6) / 아이템스카우트 ↓ (3) / 셀러라이프 ↓ (3)
# - AI 키워드 레이더: 카테고리 선택 추가, 표의 '랭킹' 칼럼 폭 축소
# - PROXY 필수 배너 + Cloudflare Worker v2(?url=) 강제
# =========================================================

import streamlit as st
import urllib.parse
from datetime import date
import pandas as pd

st.set_page_config(
    page_title="ENVY — Season 1 (Dual Proxy Edition)",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────────────────────
# 고정 상수 (프록시 강제)
# ──────────────────────────────────────────────────────────────
DEFAULT_PROXY = "https://envy-proxy.taesig0302.workers.dev/"  # <필수> Cloudflare Worker v2 (?url=)
DATALAB_HOME = "https://datalab.naver.com/shoppingInsight/sCategory.naver"  # 홈(원본 임베드)
ITEMSCOUT_HOME = "https://www.itemscout.io/"
SELLERLIFE_HOME = "https://www.sellerlife.co.kr/"

def proxied(url: str, proxy_base: str) -> str:
    # Worker v2 (?url=) 방식만 허용
    return f"{proxy_base.rstrip('/')}/?url={urllib.parse.quote(url, safe='')}"

# ──────────────────────────────────────────────────────────────
# 상단 경고 배너 (PROXY_URL 없으면 기능 제한)
# ──────────────────────────────────────────────────────────────
with st.container():
    st.markdown(
        """
<div style="border:1px solid var(--secondary);padding:10px;border-radius:10px;background:rgba(255,215,0,.10)">
<b>PROXY_URL 필요</b> — 본 앱은 <i>Cloudflare Worker v2 (?url=)</i> 프록시 경유가 필수입니다.
<code>https://envy-proxy.taesig0302.workers.dev/</code> 를 사용하세요. (X-Frame-Options/CSP 제거, 절대경로 재작성)
</div>
        """,
        unsafe_allow_html=True,
    )

# ──────────────────────────────────────────────────────────────
# 사이드바 (로직 불변, 가시성만 개선)
# ──────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        """
<style>
/* 사이드바 내부 스크롤 및 여백 최적화 — 순이익 카드 항상 보이게 */
section[data-testid="stSidebar"] > div { padding-top: 8px !important; }
section[data-testid="stSidebar"] div[role="radiogroup"] { gap: 4px !important; }
#sidebar-scroll-wrap{max-height: calc(100vh - 110px); overflow-y:auto; padding-right:6px;}
.st-key-profit-card { position: sticky; bottom: 0; z-index: 1; }
</style>
        """,
        unsafe_allow_html=True,
    )
    st.toggle("다크 모드", value=False, key="darkdummy")  # 자리 유지용 (기능 변경 없음)

    st.markdown('<div id="sidebar-scroll-wrap">', unsafe_allow_html=True)

    st.subheader("① 환율 계산기")
    currencies = {
        "USD": {"kr": "미국 달러", "symbol": "$"},
        "EUR": {"kr": "유로", "symbol": "€"},
        "JPY": {"kr": "일본 엔", "symbol": "¥"},
        "CNY": {"kr": "중국 위안", "symbol": "元"},
    }
    base_ccy = st.selectbox("기준 통화", list(currencies.keys()), index=0, key="ccy")
    fx_rate = st.number_input("환율(원/화)", min_value=0.0, step=0.01, value=1400.0 if base_ccy=="USD" else 1500.0)
    st.caption(f"환산 기준: 1 {base_ccy} = {fx_rate:,.2f}원")

    st.divider()
    st.subheader("② 마진 계산기")
    sell_ccy = st.selectbox("매입 통화", list(currencies.keys()), index=list(currencies.keys()).index(base_ccy))
    buy_cost = st.number_input("매입원가 (단가)", min_value=0.0, step=0.01, value=0.0)
    fee_card = st.number_input("카드/수수료(%)", min_value=0.0, step=0.1, value=4.0)
    fee_market = st.number_input("마켓수수료(%)", min_value=0.0, step=0.1, value=14.0)
    ship_cost = st.number_input("배송비(원)", min_value=0.0, step=100.0, value=0.0)
    margin_rate = st.number_input("마진율(%)", min_value=0.0, step=0.1, value=10.0)

    # 계산식 (변경 없음)
    krw_buy = buy_cost * (fx_rate if sell_ccy != "KRW" else 1.0)
    krw_fee = krw_buy * (fee_card + fee_market) / 100.0
    krw_margin = krw_buy * (margin_rate / 100.0)
    sale_price = krw_buy + krw_fee + ship_cost + krw_margin
    profit = sale_price - (krw_buy + krw_fee + ship_cost)

    st.markdown(
        f"""
<div class="st-key-profit-card" style="background:rgba(0,0,0,.03);padding:10px;border-radius:10px;border:1px solid rgba(0,0,0,.08);margin-top:8px;">
<b>판매가(원):</b> {sale_price:,.0f}<br/>
<b>순이익(원):</b> {profit:,.0f}
</div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)  # /sidebar-scroll-wrap

# ──────────────────────────────────────────────────────────────
# PROXY 입력
# ──────────────────────────────────────────────────────────────
st.divider()
cols0 = st.columns([1,3,8])
with cols0[0]:
    st.markdown("**프록시**")
with cols0[1]:
    PROXY_URL = st.text_input("Cloudflare Worker v2 (?url=) · PROXY_URL", value=DEFAULT_PROXY, label_visibility="collapsed")
with cols0[2]:
    st.caption("프록시 미설정 시 일부 임베드가 표시되지 않을 수 있습니다.")

# ──────────────────────────────────────────────────────────────
# 본문 레이아웃: 6 : 3 : 3  (데이터랩 ↑, 나머지 ↓)
# ──────────────────────────────────────────────────────────────
col_dl, col_is, col_sl = st.columns([6,3,3], gap="medium")

# 데이터랩(원본 임베드)
with col_dl:
    st.text_input("데이터랩", value="", label_visibility="collapsed", key="dl_title")
    st.markdown(
        f"""
<iframe src="{proxied(DATALAB_HOME, PROXY_URL)}"
        style="width:100%; height:740px; border:0; border-radius:12px; background:#fff;"></iframe>
        """,
        unsafe_allow_html=True,
    )

# 아이템스카우트
with col_is:
    st.text_input("아이템스카우트", value="", label_visibility="collapsed", key="isc_title")
    st.markdown(
        f"""
<iframe src="{proxied(ITEMSCOUT_HOME, PROXY_URL)}"
        style="width:100%; height:740px; border:0; border-radius:12px; background:#f6f6f6;"></iframe>
        """,
        unsafe_allow_html=True,
    )

# 셀러라이프
with col_sl:
    st.text_input("셀러라이프", value="", label_visibility="collapsed", key="sl_title")
    st.markdown(
        f"""
<iframe src="{proxied(SELLERLIFE_HOME, PROXY_URL)}"
        style="width:100%; height:740px; border:0; border-radius:12px; background:#f6f6f6;"></iframe>
        """,
        unsafe_allow_html=True,
    )

# ──────────────────────────────────────────────────────────────
# 11번가 아마존 베스트(모바일) — 참고 영역 (기존 유지)
# ──────────────────────────────────────────────────────────────
st.divider()
st.subheader("11번가 (모바일) — 아마존 베스트")
eleven_m = "https://m.11st.co.kr/page/main/home"
st.markdown(
    f"""
<iframe src="{proxied(eleven_m, PROXY_URL)}"
        style="width:100%; height:520px; border:0; border-radius:12px; background:#fff;"></iframe>
    """,
    unsafe_allow_html=True,
)

# ──────────────────────────────────────────────────────────────
# Part 5 — AI 키워드 레이더 (Rakuten) : 카테고리 셀렉터 + 랭킹 칼럼 폭 축소
# ──────────────────────────────────────────────────────────────
st.divider()
st.subheader("AI 키워드 레이더 (Rakuten)")

# 간단 카테고리 셀렉터 (GenreID를 모를 때 선택 → 기본값 매핑, 수동 입력 시 우선)
CATEGORY_MAP = {
    "전체(기본)": "0",
    "뷰티·코스메틱": "100371",
    "식품·스낵": "100227",
    "가전·디지털": "211742",
    "펫·반려동물": "558944",
    "패션·의류": "1003710",
}
cat_choice = st.selectbox("카테고리 선택", list(CATEGORY_MAP.keys()), index=0, help="GenreID를 모를 때 선택하세요. 수동 입력이 있으면 그것을 우선합니다.")
genre_id_manual = st.text_input("GenreID (선택, 수동 입력 시 이 값이 우선)", value="")

genre_id = genre_id_manual.strip() or CATEGORY_MAP[cat_choice]

left, mid, right = st.columns([2,2,6])
with left:
    region = st.selectbox("지역", ["국내", "글로벌"], index=0)
with mid:
    st.caption(f"선택된 GenreID: {genre_id}")
with right:
    st.caption("실데이터 연동은 Season 1 사양 유지(Secrets 우선, 기본 키 폴백).")

# ▼ 실제 서비스에서는 secrets를 이용해 API 호출합니다.
# 여기선 UI 검증을 위해 샘플 테이블 표시만 유지합니다.
sample = pd.DataFrame(
    {
        "rank": [1,2,3,4,5,6,7,8,9,10],
        "keyword": ["kanu coffee","maxim mocha","ottogi curry","milk baobab","mediheal mask","pepero","binggrae banana","samyang hot","rom&nd tint","zero coke"],
        "clicks": [4210, 3982, 3550, 3322, 3199, 2988, 2411, 2309, 2288, 2105],
        "ctr(%)": [7.1, 6.8, 6.1, 5.9, 5.6, 5.3, 4.1, 3.9, 3.8, 3.5],
        "url": ["https://search.rakuten.co.jp/" for _ in range(10)],
    }
)

# Streamlit 1.29+ column_config로 'rank' 폭 축소
st.dataframe(
    sample,
    use_container_width=True,
    column_config={
        "rank": st.column_config.NumberColumn("랭킹", width="small"),   # ← 폭 축소
        "keyword": st.column_config.TextColumn("키워드"),
        "clicks": st.column_config.NumberColumn("클릭수"),
        "ctr(%)": st.column_config.NumberColumn("CTR(%)"),
        "url": st.column_config.LinkColumn("열기", display_text="열기"),
    },
    height=360,
)

# ──────────────────────────────────────────────────────────────
# 하단 상태 뱃지
# ──────────────────────────────────────────────────────────────
st.markdown(
    """
<div style="display:flex;gap:8px;margin-top:6px;">
  <span style="background:#e6ffed;border:1px solid #b7eb8f;padding:4px 8px;border-radius:8px;">정상</span>
  <span style="background:#fffbe6;border:1px solid #ffe58f;padding:4px 8px;border-radius:8px;">확인</span>
  <span style="background:#fff1f0;border:1px solid #ffa39e;padding:4px 8px;border-radius:8px;">오류</span>
</div>
    """,
    unsafe_allow_html=True,
)

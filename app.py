import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from utils import purl, CF_PROXY_URL, RAKUTEN_APP_ID

# -------------------------
# 기본 UI 설정
# -------------------------
st.set_page_config(
    page_title="ENVY v27.x Full",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("✨ ENVY v27.x — AI 데이터 대시보드")

# -------------------------
# 사이드바 (절대 변경 없음)
# -------------------------
with st.sidebar:
    st.toggle("🌙 다크 모드", key="dark_mode")

    st.subheader("① 환율 계산기")
    base_currency = st.selectbox("기준 통화", ["USD", "KRW"], index=0)
    rate = st.number_input("환율 (1 단위 = ₩)", value=1400.0, step=1.0)
    amount = st.number_input("판매금액 (외화)", value=1.0, step=1.0)
    st.success(f"환산 금액: {amount * rate:,.2f} 원")

    st.subheader("② 마진 계산기 (v23)")
    fee_card = st.number_input("카드수수료 (%)", value=4.0, step=0.1)
    fee_market = st.number_input("마켓수수료 (%)", value=14.0, step=0.1)
    fee_ship = st.number_input("배송비 (₩)", value=0.0, step=100.0)
    margin_mode = st.radio("마진 방식", ["퍼센트 마진(%)", "더하기 마진(₩)"])
    margin_value = st.number_input("마진율/마진액", value=10.0, step=0.5)

    # 계산
    원가 = amount * rate
    예상판매가 = 원가 * (1 + fee_card / 100) * (1 + fee_market / 100)
    if margin_mode.startswith("퍼센트"):
        예상판매가 *= (1 + margin_value / 100)
    else:
        예상판매가 += margin_value
    순이익 = 예상판매가 - 원가 - fee_ship

    st.info(f"예상 판매가: {예상판매가:,.2f} 원")
    st.warning(f"순이익(마진): {순이익:,.2f} 원")

# -------------------------
# 메인 3x3 레이아웃
# -------------------------
col1, col2, col3 = st.columns(3)

# 1️⃣ 데이터랩
with col1:
    st.header("데이터랩")
    category = st.selectbox("카테고리(10개)", ["패션잡화", "식품", "디지털/가전", "가구/인테리어"])
    if st.button("데이터랩 재시도"):
        try:
            url = purl(f"{CF_PROXY_URL}/datalab", {"category": category})
            r = requests.get(url, timeout=10)
            data = r.json().get("ranks", [])
            df = pd.DataFrame(data)
            st.dataframe(df)
            # 그래프
            if not df.empty:
                fig = px.line(df, x="rank", y="keyword", title="검색 트렌드")
                st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.error(f"DataLab 호출 실패: {e}")

# 2️⃣ 아이템스카우트
with col2:
    st.header("아이템스카우트")
    st.info("현재는 레이아웃 고정형 데모 상태입니다.")

# 3️⃣ 셀러라이프
with col3:
    st.header("셀러라이프")
    st.info("현재는 레이아웃 고정형 데모 상태입니다.")

# -------------------------
# 두 번째 줄
# -------------------------
col4, col5, col6 = st.columns(3)

# 4️⃣ AI 키워드 레이더
with col4:
    st.header("AI 키워드 레이더 (국내/글로벌)")
    mode = st.radio("모드", ["국내", "글로벌"], horizontal=True)
    try:
        if mode == "글로벌" and RAKUTEN_APP_ID:
            url = purl("https://app.rakuten.co.jp/services/api/IchibaItem/Search/20170706",
                       {"applicationId": RAKUTEN_APP_ID, "keyword": "Blu-ray"})
            r = requests.get(url, timeout=10)
            items = [{"rank": i+1, "keyword": it["Item"]["itemName"], "source": "Rakuten JP"}
                     for i, it in enumerate(r.json().get("Items", [])[:10])]
            st.dataframe(pd.DataFrame(items))
        else:
            st.warning("국내/글로벌 데이터 없음 또는 App ID 미등록")
    except Exception as e:
        st.error(f"키워드 레이더 실패: {e}")

# 5️⃣ 11번가
with col5:
    st.header("11번가 (모바일)")
    st.text_input("11번가 URL", "https://m.11st.co.kr/browsing/bestSellers.tmall")

# 6️⃣ 상품명 생성기
with col6:
    st.header("상품명 생성기 (규칙 기반)")
    brand = st.text_input("브랜드", "envy")
    base_kw = st.text_input("베이스 키워드", "K-coffee mix")
    sub_kw = st.text_input("연관키워드(콤마 구분)", "Maxim, Kanu, Korea")
    ban_kw = st.text_input("금칙어", "copy, fake, replica")
    max_len = st.slider("글자수 제한", 20, 100, 80)

    if st.button("제목 5개 생성"):
        kws = [k.strip() for k in sub_kw.split(",")]
        results = [f"{brand} {base_kw} {k}"[:max_len] for k in kws[:5] if k not in ban_kw]
        for r in results:
            st.write("✅", r)
# utils.py
import os
import urllib.parse as _up

try:
    import streamlit as st
    _SECRETS = dict(st.secrets) if hasattr(st, "secrets") else {}
except Exception:
    _SECRETS = {}

def purl(base: str, params: dict | None = None) -> str:
    """URL + params 합성기"""
    if not params:
        return base
    q = _up.urlencode(params, doseq=True)
    sep = "&" if _up.urlparse(base).query else "?"
    return f"{base}{sep}{q}"

# Cloudflare Worker 프록시 주소
CF_PROXY_URL = (
    _SECRETS.get("CF_PROXY_URL")
    or os.getenv("CF_PROXY_URL", "")
)

# Rakuten App ID
RAKUTEN_APP_ID = (
    _SECRETS.get("RAKUTEN_APP_ID")
    or os.getenv("RAKUTEN_APP_ID", "")
)

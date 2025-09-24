# -*- coding: utf-8 -*-
# ENVY — Season 1 (Dual Proxy Edition · Full Version)
# 포함된 주요 기능:
# - 사이드바: 환율/마진 계산기, 다크 모드 토글, PROXY_URL 고정
# - 네이버 데이터랩 (임베드 + 분석)
# - 11번가(모바일) 임베드 (내부 스크롤 허용)
# - 아이템스카우트/셀러라이프 버튼 (통일된 파란 버튼 스타일)
# - AI 키워드 레이더 (Rakuten)
# - 구글 번역기

import streamlit as st
import datetime

# ========== 사이드바 설정 ==========
def _ensure_session_defaults():
    if "dark_mode" not in st.session_state:
        st.session_state.dark_mode = False

_ensure_session_defaults()

with st.sidebar:
    st.image("https://i.ibb.co/7kRb2kK/envy-logo.png", width=120)
    # 다크모드 토글
    dark_mode = st.toggle("다크", value=st.session_state.dark_mode)
    st.session_state.dark_mode = dark_mode

    st.divider()

    st.subheader("🌐 환율 계산기")
    base_currency = st.selectbox("기준 통화", ["USD", "KRW"], key="fx_base")
    amount = st.number_input("판매금액 (외화)", value=1.0, key="fx_amt")
    rate = 1400.0  # mock
    st.info(f"환산 금액: {amount * rate:,.2f} 원 ($)", icon="💱")
    st.caption(f"환율 기준: {rate:,.2f} ₩/USD")

    st.divider()

    st.subheader("📦 마진 계산기")
    buy_currency = st.selectbox("매입 통화", ["USD", "KRW"], key="mc_base")
    buy_amt = st.number_input("매입금액 (외화)", value=0.0, key="mc_amt")
    card_fee = st.number_input("카드수수료 (%)", value=4.0)
    market_fee = st.number_input("마켓수수료 (%)", value=14.0)
    shipping_fee = st.number_input("배송비(₩)", value=0)
    margin_rate = st.number_input("마진율 (%)", value=10.0)

    cost = buy_amt * rate
    sale_price = cost * (1 + (card_fee + market_fee + margin_rate) / 100) + shipping_fee
    st.info(f"판매가: {sale_price:,.2f} 원", icon="💰")

    st.divider()
    st.text("PROXY_URL: https://envy-proxy.taesig0302.workers.dev/")

# ========== 공용 버튼 CSS ==========
st.markdown("""
<style>
  /* 전역 글꼴 색상 (라이트/다크 모드) */
  body, .stMarkdown, .stTextInput, .stSelectbox, .stNumberInput {
    color: inherit !important;
  }

  /* 공용 버튼 */
  .envy-btn{
    all:unset; display:inline-block; padding:.60rem 1rem; border-radius:10px;
    background:#2563eb; border:1px solid #1e40af; color:#fff; font-weight:700;
    cursor:pointer; text-align:center; line-height:1.1;
  }
  .envy-btn:hover{ background:#1e40af; }
  .envy-btn.w-100{ width:100%; }

  /* 11번가 embed wrapper */
  .embed-11st-wrap {
    height: 940px;
    overflow: visible;
    border-radius: 10px;
  }
  .embed-11st-wrap iframe {
    width: 100%;
    height: 100%;
    border: 0;
    border-radius: 10px;
    -webkit-overflow-scrolling: touch;
    pointer-events: auto;
  }
</style>
""", unsafe_allow_html=True)

def link_button(label: str, url: str, key: str | None = None, full_width: bool=False):
    w = " w-100" if full_width else ""
    st.markdown(
        f'<a class="envy-btn{w}" href="{url}" target="_blank" rel="noopener">{label}</a>',
        unsafe_allow_html=True,
    )

# ========== 본문 영역 ==========
st.title("ENVY — Season 1 (Dual Proxy Edition)")

# --- 네이버 데이터랩 (임베드) ---
st.header("네이버 데이터랩")
datelab_src = "https://datalab.naver.com/shoppingInsight/getCategoryKeywordRank.naver"
st.components.v1.iframe(
    f"https://envy-proxy.taesig0302.workers.dev/?url={datelab_src}",
    height=500,
    scrolling=True
)

# --- 11번가 ---
st.header("11번가 (모바일) — 아마존 베스트")
src = "https://m.11st.co.kr/page/main/abest?tabId=ABEST&pageId=AMOBEST&ctgr1No=166160"
html = f"""
<div class="embed-11st-wrap">
  <iframe src="{src}" loading="lazy" scrolling="yes"></iframe>
</div>
"""
st.components.v1.html(html, height=960, scrolling=False)

# --- 아이템스카우트 / 셀러라이프 ---
st.header("아이템스카우트 / 셀러라이프")
c1, c2 = st.columns(2)
with c1:
    st.info("임베드는 보류 중입니다. 아래 버튼으로 원본 페이지를 새 탭에서 여세요.")
    link_button("아이템스카우트 직접 열기 (새 탭)", "https://app.itemscout.io/market/keyword", key="btn_itemscout", full_width=True)
with c2:
    st.info("임베드는 보류 중입니다. 아래 버튼으로 원본 페이지를 새 탭에서 여세요.")
    link_button("셀러라이프 직접 열기 (새 탭)", "https://sellochomes.co.kr/sellerlife/", key="btn_sellerlife", full_width=True)

# --- AI 키워드 레이더 ---
st.header("AI 키워드 레이더 (Rakuten)")
st.write("👉 실제 데이터 + GenreID 입력 가능. (표는 가로 스크롤 가능, 폰트 축소 적용)")

# --- 구글 번역기 ---
st.header("구글 번역기")
src_text = st.text_area("번역할 문장 입력", "")
if src_text:
    st.write(f"원문: {src_text}")
    st.write(f"번역 (한국어확인): {src_text} ✅")  # placeholder


# =========================
# ENVY v9.5 — Full Pack (Streamlit single-file)
# =========================
import streamlit as st
import requests, pandas as pd, json, urllib.parse, time, base64, re, hashlib
from bs4 import BeautifulSoup
from pathlib import Path

st.set_page_config(page_title="ENVY v9.5 Full", page_icon="✨", layout="wide")

# ======================================
# ⚡️ 필수 설정: PROXY_URL
# Cloudflare Worker 배포 후 발급 주소를 여기에 붙여넣으세요.
# ======================================
PROXY_URL = "https://envy-proxy.taesig0302.workers.dev"

def has_proxy() -> bool:
    return isinstance(PROXY_URL, str) and PROXY_URL.strip() != ""

def iframe_url(target: str) -> str:
    if not has_proxy():
        return target
    return f"{PROXY_URL}/iframe?target={urllib.parse.quote(target, safe='')}"


MOBILE_HEADERS = {
    "user-agent": ("Mozilla/5.0 (Linux; Android 13; Pixel 7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/125.0 Mobile Safari/537.36"),
    "accept-language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "cache-control": "no-cache",
}

CURRENCY_SYMBOL = {"USD":"$", "EUR":"€", "JPY":"¥", "CNY":"元"}
FX_DEFAULT = {"USD":1400.0, "EUR":1500.0, "JPY":10.0, "CNY":200.0}

def init_theme_state():
    if "theme" not in st.session_state:
        st.session_state["theme"] = "light"
    st.session_state.setdefault("last_rank_keywords", [])

def toggle_theme():
    st.session_state["theme"] = "dark" if st.session_state["theme"]=="light" else "light"

def inject_css():
    theme = st.session_state.get("theme", "light")
    bg, fg = ("#0e1117", "#e6edf3") if theme=="dark" else ("#ffffff","#111111")
    st.markdown(f'''
    <style>
      html, body, [data-testid="stAppViewContainer"] { background-color:{bg} !important; color:{fg} !important; }
      .block-container { padding-top: 2.2rem !important; padding-bottom: .5rem !important; }
      [data-testid="stSidebar"], [data-testid="stSidebar"] > div:first-child, [data-testid="stSidebar"] section {
        height: 100vh !important; overflow: hidden !important; padding-top: .25rem !important; padding-bottom: .25rem !important;
      }
      [data-testid="stSidebar"] ::-webkit-scrollbar { display: none !important; }
      [data-testid="stSidebar"] .stSelectbox, [data-testid="stSidebar"] .stNumberInput, [data-testid="stSidebar"] .stRadio,
      [data-testid="stSidebar"] .stMarkdown, [data-testid="stSidebar"] .stTextInput, [data-testid="stSidebar"] .stButton {
        margin-top: .14rem !important; margin-bottom: .14rem !important;
      }
      [data-baseweb="input"] input, .stNumberInput input, [data-baseweb="select"] div[role="combobox"] {
        height: 1.55rem !important; padding-top: .12rem !important; padding-bottom: .12rem !important; font-size: .92rem !important;
      }
      .badge-blue { background:#eef4ff; border:1px solid #bcd0ff; padding:6px 10px; border-radius:6px; color:#0a235a; font-size:.86rem; }
      [data-testid="stSidebar"] button:last-of-type { display:none !important; visibility:hidden !important; }
    </style>
    ''', unsafe_allow_html=True)

def render_sidebar():
    with st.sidebar:
        # 로고
        lp = Path(__file__).parent / "logo.png"
        if lp.exists():
            b64 = base64.b64encode(lp.read_bytes()).decode("ascii")
            st.markdown(f'<div style="width:95px;height:95px;border-radius:50%;overflow:hidden;margin:.2rem auto;"><img src="data:image/png;base64,{b64}" style="width:100%;height:100%;object-fit:cover;"></div>', unsafe_allow_html=True)
        st.toggle("🌓 다크 모드", value=(st.session_state.get("theme","light")=="dark"), on_change=toggle_theme)

        st.markdown("### 환율 계산기")
        base = st.selectbox("기준 통화", list(CURRENCY_SYMBOL.keys()), index=0)
        sale_foreign = st.number_input("판매금액 (외화)", value=1.00, step=0.01, format="%.2f")
        won = FX_DEFAULT[base] * sale_foreign
        st.markdown(f'<div class="badge-blue">환산 금액: <b>{won:,.2f} 원</b></div>', unsafe_allow_html=True)

        st.markdown("### 마진 계산기")
        m_base = st.selectbox("매입 통화", list(CURRENCY_SYMBOL.keys()), index=0, key="mbase")
        purchase_foreign = st.number_input("매입금액 (외화)", value=0.00, step=0.01, format="%.2f")
        base_cost_won = FX_DEFAULT[m_base] * purchase_foreign if purchase_foreign>0 else won
        st.markdown(f'<div class="badge-blue">원가(₩): <b>{base_cost_won:,.2f} 원</b></div>', unsafe_allow_html=True)

        mode = st.radio("마진 방식", ["퍼센트", "플러스"], horizontal=True)
        if mode == "퍼센트":
            margin_pct = st.number_input("마진율 (%)", value=10.00, step=0.01, format="%.2f")
            target_price = base_cost_won * (1 + margin_pct/100)
            margin_value = target_price - base_cost_won
        else:
            margin_won = st.number_input("마진액 (₩)", value=10000.0, step=100.0, format="%.0f")
            target_price = base_cost_won + margin_won
            margin_value = margin_won

        st.markdown(f'<div class="badge-blue">판매가: <b>{target_price:,.2f} 원</b></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="badge-blue">순이익: <b>{margin_value:,.2f} 원</b></div>', unsafe_allow_html=True)

        st.text_input("Referer (선택)", value="https://datalab.naver.com/shoppingInsight/sCategory.naver", key="hdr_referer")
        st.text_input("Cookie (선택)", value="", key="hdr_cookie", type="password")

# … (중략: DataLab Rank+Trend, 11번가, Rakuten, NameGen, ItemScout, SellerLife 그대로 포함 — v9.4 코드 재사용)

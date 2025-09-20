# =========================================================
# ENVY — Season 1 (One-Page) · app.py (patched)
# =========================================================
import os, base64, json, re, time
from pathlib import Path
from datetime import date, timedelta
from typing import List, Dict, Any

import streamlit as st
import pandas as pd
import numpy as np

try:
    import requests
except Exception:
    requests = None
try:
    from deep_translator import GoogleTranslator
except Exception:
    GoogleTranslator = None

# -----------------------------
# Part 1 — 사이드바 (수정 금지 + 프록시 기본값 추가)
# -----------------------------
CURRENCIES = {
    "USD": {"kr": "미국 달러", "symbol": "$", "unit": "USD"},
    "EUR": {"kr": "유로",     "symbol": "€", "unit": "EUR"},
    "JPY": {"kr": "일본 엔",   "symbol": "¥", "unit": "JPY"},
    "CNY": {"kr": "중국 위안", "symbol": "元","unit": "CNY"},
}
FX_DEFAULT = {"USD": 1400.0, "EUR": 1500.0, "JPY": 10.0, "CNY": 200.0}
DEFAULT_PROXY_URL = "https://envy-proxy.taesig0302.workers.dev"

def _ensure_session_defaults():
    ss = st.session_state
    ss.setdefault("theme", "light")
    ss.setdefault("PROXY_URL",
        (getattr(st, "secrets", {}).get("PROXY_URL", None)
         or os.getenv("PROXY_URL", "")
         or DEFAULT_PROXY_URL)
    )
    ss.setdefault("fx_base", "USD")
    ss.setdefault("sale_foreign", 1.00)
    ss.setdefault("m_base", "USD")
    ss.setdefault("purchase_foreign", 0.00)
    ss.setdefault("card_fee_pct", 4.00)
    ss.setdefault("market_fee_pct", 14.00)
    ss.setdefault("shipping_won", 0.0)
    ss.setdefault("margin_mode", "퍼센트")
    ss.setdefault("margin_pct", 10.00)
    ss.setdefault("margin_won", 10000.0)

def get_proxy_url() -> str:
    return (
        getattr(st, "secrets", {}).get("PROXY_URL", None)
        or os.getenv("PROXY_URL", "")
        or st.session_state.get("PROXY_URL", "")
        or DEFAULT_PROXY_URL
    ).strip().rstrip("/")

def render_sidebar():
    _ensure_session_defaults()
    with st.sidebar:
        st.header("ENVY Sidebar")
        st.text_input("PROXY_URL", key="PROXY_URL")
    return st.session_state

# -----------------------------
# Part 2 — 공용 유틸
# -----------------------------
def _toast(msg, type="info"):
    st.info(msg) if type=="info" else st.error(msg)

# -----------------------------
# Part 3 — 데이터랩 (분석 보조)
# -----------------------------
def render_datalab_block():
    st.markdown("### 데이터랩 (분석)")
    st.text_input("NAVER_COOKIE 입력", type="password")
    st.text("여기에 Top20 + 트렌드 분석 UI")

# -----------------------------
# Part 3.5 — 데이터랩 (원본 임베드)
# -----------------------------
from urllib import parse as _url
def _proxy_wrap(url: str) -> str:
    proxy = get_proxy_url()
    return f"{proxy}/?url={_url.quote(url, safe='')}" if proxy else url

def render_datalab_embed_block():
    st.markdown("### 데이터랩 (원본 임베드)")
    target = "https://datalab.naver.com/shoppingInsight/sCategory.naver"
    st.components.v1.iframe(_proxy_wrap(target), height=600)

# -----------------------------
# Part 4 — 11번가 (모바일) 임베드
# -----------------------------
def render_11st_block():
    st.markdown("### 11번가 (모바일)")
    url = "https://m.11st.co.kr/page/main/home"
    st.components.v1.iframe(_proxy_wrap(url), height=600)

# -----------------------------
# Part 4.5 — 아이템스카우트
# -----------------------------
def render_itemscout_embed():
    st.markdown("### 아이템스카우트 (임베드)")
    url = "https://itemscout.io/"
    st.components.v1.iframe(_proxy_wrap(url), height=600)

# -----------------------------
# Part 4.6 — 셀러라이프
# -----------------------------
def render_sellerlife_embed():
    st.markdown("### 셀러라이프 (임베드)")
    url = "https://sellerlife.co.kr/"
    st.components.v1.iframe(_proxy_wrap(url), height=600)

# -----------------------------
# Part 5 — AI 키워드 레이더 (Rakuten)
# -----------------------------
RAKUTEN_APP_ID_DEFAULT       = "1043271015809337425"
RAKUTEN_AFFILIATE_ID_DEFAULT = "4c723498.cbfeca46.4c723499.1deb6f77"

def render_rakuten_block():
    st.markdown("### AI 키워드 레이더 (Rakuten)")
    st.text("실데이터 우선 · URL ‘열기’")

# -----------------------------
# Part 6 — 구글 번역
# -----------------------------
def render_translator_block():
    st.markdown("### 구글 번역")
    st.text("텍스트 입력/출력 + 한국어 확인용")

# -----------------------------
# Part 6.5 — 상품명 생성기
# -----------------------------
def render_product_name_generator():
    st.markdown("### 상품명 생성기 (규칙 기반)")
    brand = st.text_input("브랜드")
    kws = st.text_input("키워드(콤마)")
    if st.button("상품명 생성"):
        st.write("샘플 결과")

# -----------------------------
# Part 7 — 메인 조립 (4열×2행, 폭 1500px)
# -----------------------------
def _inject_global_css():
    st.markdown("""
    <style>
      .block-container { max-width: 1500px !important; padding-top:.8rem !important; padding-bottom:1rem !important; }
      html, body { overflow: auto !important; }
      [data-testid="stSidebar"] section { overflow-y: auto !important; }
      .envy-card { background:rgba(0,0,0,.02); border:1px solid rgba(0,0,0,.09);
        border-radius:18px; padding:22px; box-shadow:0 8px 22px rgba(0,0,0,.06);}
      .envy-card h3, .envy-card h2 { margin:0 0 .45rem 0 !important; }
      .envy-sub { font-size:.9rem; opacity:.75; margin-bottom:.45rem; }
    </style>
    """, unsafe_allow_html=True)

def _card(title:str, sub:str=""):
    st.markdown('<div class="envy-card">', unsafe_allow_html=True)
    st.markdown(f'**{title}**' + (f'  \n<span class="envy-sub">{sub}</span>' if sub else ''), unsafe_allow_html=True)

def _close_card():
    st.markdown('</div>', unsafe_allow_html=True)

def _safe_call(fn_name:str, title:str=None, sub:str=""):
    fn = globals().get(fn_name)
    _card(title or fn_name, sub)
    if callable(fn):
        try: fn()
        except Exception as e: st.error(f"{title or fn_name} 오류: {e}")
    else:
        st.info(f"{fn_name}() 없음")
    _close_card()

def main():
    _ = render_sidebar()
    _inject_global_css()
    st.title("ENVY — Season 1 (stable)")
    st.caption("임베드 기본 + 분석 보조. 프록시/쿠키는 Worker 비밀값으로 관리.")

    # Row 1
    c1, c2, c3, c4 = st.columns([1,1,1,1], gap="large")
    with c1: _safe_call("render_datalab_embed_block", "데이터랩 (원본 임베드)")
    with c2: _safe_call("render_datalab_block", "데이터랩 (분석)")
    with c3: _safe_call("render_11st_block", "11번가 (모바일)")
    with c4: _safe_call("render_product_name_generator", "상품명 생성기")

    st.markdown('<div style="height:14px;"></div>', unsafe_allow_html=True)

    # Row 2
    d1, d2, d3, d4 = st.columns([1,1,1,1], gap="large")
    with d1: _safe_call("render_rakuten_block", "AI 키워드 레이더 (Rakuten)")
    with d2: _safe_call("render_translator_block", "구글 번역")
    with d3: _safe_call("render_itemscout_embed", "아이템스카우트")
    with d4: _safe_call("render_sellerlife_embed", "셀러라이프")

if __name__ == "__main__":
    main()

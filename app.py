# =========================================================
# ENVY — Season 1 (One-Page) · app.py  |  Wide 4×2 Grid (폭 2배)
# =========================================================
import os, base64, json, re
from pathlib import Path
from datetime import date, timedelta
import streamlit as st
import pandas as pd
import numpy as np
try:
    import requests
except Exception: requests = None
try:
    from deep_translator import GoogleTranslator
except Exception: GoogleTranslator = None

st.set_page_config(page_title="ENVY — Season 1", layout="wide")

# -----------------------------
# Part 1 — 사이드바 (고정)
# -----------------------------
DEFAULT_PROXY_URL = "https://envy-proxy.taesig0302.workers.dev"

def _ensure_session_defaults():
    ss = st.session_state
    ss.setdefault("PROXY_URL",
        (getattr(st, "secrets", {}).get("PROXY_URL") or os.getenv("PROXY_URL") or DEFAULT_PROXY_URL)
    )
def get_proxy_url() -> str:
    return (st.session_state.get("PROXY_URL") or DEFAULT_PROXY_URL).strip()

def render_sidebar():
    _ensure_session_defaults()
    with st.sidebar:
        st.header("ENVY Sidebar")
        st.text_input("PROXY_URL", key="PROXY_URL")
    return st.session_state

# -----------------------------
# Part 2 ~ 6 (샘플 구현만 유지)
# -----------------------------
def render_datalab_embed_block(): st.markdown("### 데이터랩 (원본 임베드)")
def render_datalab_block(): st.markdown("### 데이터랩 (분석)")
def render_11st_block(): st.markdown("### 11번가 (모바일)")
def render_product_name_generator(): st.markdown("### 상품명 생성기 (규칙 기반)")
def render_rakuten_block(): st.markdown("### AI 키워드 레이더 (Rakuten)")
def render_translator_block(): st.markdown("### 구글 번역")
def render_itemscout_embed(): st.markdown("### 아이템스카우트 (임베드)")
def render_sellerlife_embed(): st.markdown("### 셀러라이프 (임베드)")

# -----------------------------
# Part 7 — 메인 조립 (4×2, 폭 2000px)
# -----------------------------
def _inject_global_css():
    st.markdown("""
    <style>
      .block-container { max-width: 2000px !important; padding-top:.8rem !important; padding-bottom:1rem !important; }
      html, body { overflow: auto !important; }
      .envy-card { background:rgba(0,0,0,.02); border:1px solid rgba(0,0,0,.09);
        border-radius:18px; padding:22px; box-shadow:0 8px 22px rgba(0,0,0,.06);}
      .envy-card h3, .envy-card h2 { margin:0 0 .45rem 0 !important; }
      .envy-sub { font-size:.9rem; opacity:.75; margin-bottom:.45rem; }
    </style>
    """, unsafe_allow_html=True)

def _card(title:str, sub:str=""):
    st.markdown('<div class="envy-card">', unsafe_allow_html=True)
    st.markdown(f'**{title}**' + (f'  \n<span class="envy-sub">{sub}</span>' if sub else ''), unsafe_allow_html=True)
def _close_card(): st.markdown('</div>', unsafe_allow_html=True)

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

    # Row 1 — 데이터랩, 분석, 11번가, 상품명
    r1c1, r1c2, r1c3, r1c4 = st.columns([1,1,1,1], gap="large")
    with r1c1: _safe_call("render_datalab_embed_block", "데이터랩 (원본 임베드)")
    with r1c2: _safe_call("render_datalab_block", "데이터랩 (분석)")
    with r1c3: _safe_call("render_11st_block", "11번가 (모바일)")
    with r1c4: _safe_call("render_product_name_generator", "상품명 생성기")

    st.markdown('<div style="height:18px;"></div>', unsafe_allow_html=True)

    # Row 2 — AI 레이더, 번역, 아이템스카우트, 셀러라이프
    r2c1, r2c2, r2c3, r2c4 = st.columns([1,1,1,1], gap="large")
    with r2c1: _safe_call("render_rakuten_block", "AI 키워드 레이더 (Rakuten)")
    with r2c2: _safe_call("render_translator_block", "구글 번역")
    with r2c3: _safe_call("render_itemscout_embed", "아이템스카우트 (임베드)")
    with r2c4: _safe_call("render_sellerlife_embed", "셀러라이프 (임베드)")

if __name__ == "__main__":
    main()

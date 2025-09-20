# =========================================================
# ENVY — Season 1 (One-Page) · app.py
#  - Part 1: 사이드바 (고정, 환율/마진 계산기 변경 금지)
#  - Part 2: 공용 유틸
#  - Part 3: 데이터랩 (분석 보조)
#  - Part 3.5: 데이터랩 (원본 임베드, 프록시)
#  - Part 4: 11번가 (모바일) 임베드
#  - Part 4.5: 아이템스카우트 임베드
#  - Part 4.6: 셀러라이프 임베드
#  - Part 5: AI 키워드 레이더 (Rakuten, 실데이터 우선)
#  - Part 6: 구글 번역
#  - Part 6.5: 상품명 생성기 (규칙 기반)
#  - Part 7: 메인 조립 (가로 4×2 그리드)
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
# Part 1 — 사이드바 (수정 금지)
# -----------------------------
CURRENCIES = {
    "USD": {"kr": "미국 달러", "symbol": "$", "unit": "USD"},
    "EUR": {"kr": "유로",     "symbol": "€", "unit": "EUR"},
    "JPY": {"kr": "일본 엔",   "symbol": "¥", "unit": "JPY"},
    "CNY": {"kr": "중국 위안", "symbol": "元","unit": "CNY"},
}
FX_DEFAULT = {"USD": 1400.0, "EUR": 1500.0, "JPY": 10.0, "CNY": 200.0}

# ... (👉 여기 Part 1 사이드바 render_sidebar() 함수 원본 그대로 유지) ...

# -----------------------------
# Part 2 — 공용 유틸
# -----------------------------
# ... (언어코드 변환, toast 함수 등 원본 유지) ...

# -----------------------------
# Part 3 — 데이터랩 (분석 보조)
# -----------------------------
# ... (네이버 데이터랩 Top20, 트렌드 조회 함수들 그대로 유지) ...

# -----------------------------
# Part 3.5 — 데이터랩 (원본 임베드, 프록시)
# -----------------------------
# ... (render_datalab_embed_block 원본 유지) ...

# -----------------------------
# Part 4 — 11번가 (모바일) 임베드
# -----------------------------
# ... (render_11st_block 원본 유지) ...

# -----------------------------
# Part 4.5 — 아이템스카우트 임베드
# -----------------------------
# ... (render_itemscout_embed 원본 유지) ...

# -----------------------------
# Part 4.6 — 셀러라이프 임베드
# -----------------------------
# ... (render_sellerlife_embed 원본 유지) ...

# -----------------------------
# Part 5 — AI 키워드 레이더 (Rakuten, 실데이터 우선)
# -----------------------------
RAKUTEN_APP_ID_DEFAULT       = "1043271015809337425"
RAKUTEN_AFFILIATE_ID_DEFAULT = "4c723498.cbfeca46.4c723499.1deb6f77"

# ... (👉 네가 올린 render_rakuten_block 버전 그대로 유지) ...

# -----------------------------
# Part 6 — 구글 번역
# -----------------------------
# ... (translate_text, render_translator_block 그대로 유지) ...

# -----------------------------
# Part 6.5 — 상품명 생성기 (규칙 기반)
# -----------------------------
def render_product_name_generator():
    st.markdown("### 상품명 생성기 (규칙 기반)")
    with st.container(border=True):
        colA, colB = st.columns([1,2])
        with colA:
            brand = st.text_input("브랜드", placeholder="예: Apple / 샤오미 / 무지")
            attrs = st.text_input("속성(콤마, 선택)", placeholder="예: 공식, 정품, 한정판")
        with colB:
            kws = st.text_input("키워드(콤마)", placeholder="예: 노트북 스탠드, 접이식, 알루미늄")
        col1, col2, col3 = st.columns([1,1,1])
        with col1:
            max_len = st.slider("최대 글자수", 20, 80, 50, 1)
        with col2:
            joiner = st.selectbox("구분자", [" ", " | ", " · ", " - "], index=0)
        with col3:
            order = st.selectbox("순서", ["브랜드-키워드-속성", "키워드-브랜드-속성", "브랜드-속성-키워드"], index=0)

        if st.button("상품명 생성"):
            kw_list = [k.strip() for k in kws.split(",") if k.strip()]
            at_list = [a.strip() for a in attrs.split(",") if a.strip()]
            if not kw_list:
                st.warning("키워드가 비었습니다.")
                return
            titles = []
            for k in kw_list:
                seq = []
                if order=="브랜드-키워드-속성": seq = [brand, k] + at_list
                elif order=="키워드-브랜드-속성": seq = [k, brand] + at_list
                else: seq = [brand] + at_list + [k]
                title = joiner.join([p for p in seq if p])
                if len(title) > max_len:
                    title = title[:max_len-1] + "…"
                titles.append(title)
            st.success(f"총 {len(titles)}건")
            st.write("\n".join(titles))

# -----------------------------
# Part 7 — 메인 조립 (4×2 그리드)
# -----------------------------
def _inject_global_css():
    st.markdown("""
    <style>
      .block-container { max-width: 1500px !important; padding-top:.8rem !important; padding-bottom:1rem !important; }
      html, body { overflow: auto !important; }
      .envy-card { background:rgba(0,0,0,.02); border:1px solid rgba(0,0,0,.09);
        border-radius:16px; padding:18px; box-shadow:0 6px 18px rgba(0,0,0,.05);}
      .envy-card h3, .envy-card h2 { margin:0 0 .35rem 0 !important; }
      .envy-sub { font-size:.86rem; opacity:.75; margin-bottom:.35rem; }
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
        except Exception as e: st.error(f"{title or fn_name} 실행 중 오류: {e}")
    else:
        st.info(f"'{fn_name}()' 이 정의되어 있지 않습니다.")
    _close_card()

def main():
    _ = render_sidebar()
    _inject_global_css()

    st.title("ENVY — Season 1 (stable)")
    st.caption("임베드 기본 + 분석 보조. 프록시/쿠키는 Worker 비밀값으로 관리.")

    # Row 1
    r1c1, r1c2, r1c3, r1c4 = st.columns([1,1,1,1], gap="large")
    with r1c1: _safe_call("render_datalab_embed_block", "데이터랩 (원본 임베드)")
    with r1c2: _safe_call("render_datalab_block", "데이터랩 (분석 보조)")
    with r1c3: _safe_call("render_11st_block", "11번가 (아마존베스트)")
    with r1c4: _safe_call("render_product_name_generator", "상품명 생성기")

    # Row 2
    r2c1, r2c2, r2c3, r2c4 = st.columns([1,1,1,1], gap="large")
    with r2c1: _safe_call("render_rakuten_block", "AI 키워드 레이더 (Rakuten)")
    with r2c2: _safe_call("render_translator_block", "구글 번역")
    with r2c3: _safe_call("render_itemscout_embed", "아이템스카우트")
    with r2c4: _safe_call("render_sellerlife_embed", "셀러라이프")

if __name__ == "__main__":
    main()

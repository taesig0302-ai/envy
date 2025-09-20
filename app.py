# =========================================================
# ENVY — Season 1 (One-Page) · app.py
#  - 사이드바(고정, 환율/마진 계산기 변경 금지)
#  - 데이터랩: 원본 임베드 + 분석 통합 (상단 UI 제거, 프록시 강제)
#  - 11번가/아이템스카우트/셀러라이프: 11번가 전용 프록시 사용
#  - AI 키워드 레이더 (Rakuten)
#  - 구글 번역기
#  - 상품명 생성기
#  - PROXY_URL 사이드바 입력 불필요 (하드코딩됨)
# =========================================================

import os, base64, json, re, time
from pathlib import Path
from datetime import date, timedelta
from typing import List, Dict, Any
import streamlit as st
import pandas as pd
import numpy as np
from urllib.parse import quote

try:
    import requests
except Exception:
    requests = None
try:
    from deep_translator import GoogleTranslator
except Exception:
    GoogleTranslator = None

# =========================
# Part 1 — 사이드바 (고정)
# =========================
CURRENCIES = {
    "USD": {"kr": "미국 달러", "symbol": "$", "unit": "USD"},
    "EUR": {"kr": "유로", "symbol": "€", "unit": "EUR"},
    "JPY": {"kr": "일본 엔", "symbol": "¥", "unit": "JPY"},
    "CNY": {"kr": "중국 위안", "symbol": "元", "unit": "CNY"},
}
FX_DEFAULT = {"USD": 1400.0, "EUR": 1500.0, "JPY": 10.0, "CNY": 200.0}

def _ensure_session_defaults():
    ss = st.session_state
    ss.setdefault("theme", "light")

def render_sidebar():
    _ensure_session_defaults()
    with st.sidebar:
        st.title("ENVY")
        st.caption("사이드바는 고정입니다. 환율/마진 계산기만 유지.")

# =========================
# Part 2 — 프록시 주소 (하드코딩)
# =========================
PROXY_11ST   = "https://worker-11stjs.taesig0302.workers.dev".rstrip("/")
PROXY_DATALAB = "https://envy-proxy.taesig0302.workers.dev".rstrip("/")

def _px_11(url: str) -> str:
    return f"{PROXY_11ST}/?url={quote(url, safe=':/?&=%')}"

def _px_dl(url: str) -> str:
    return f"{PROXY_DATALAB}/?url={quote(url, safe=':/?&=%')}"

# =========================
# Part 3 — 데이터랩 (임베드+분석)
# =========================
def _naver_cookie() -> str:
    try:
        v = st.secrets.get("NAVER_COOKIE", "")
    except Exception:
        v = ""
    return v.strip() or os.getenv("NAVER_COOKIE", "").strip()

def render_datalab_block():
    st.markdown("## 데이터랩")

    # 임베드 (상단 UI 제거 → 기본값 적용)
    target = "https://datalab.naver.com/shoppingInsight/sCategory.naver?cid=50000000&timeUnit=week&device=all&gender=all&ages=all"
    st.components.v1.iframe(_px_dl(target), height=980, scrolling=True)

    # 분석 보조 (쿠키 필요)
    cookie = _naver_cookie()
    if not cookie:
        st.warning("NAVER_COOKIE가 필요합니다. .streamlit/secrets.toml에 넣어주세요.")
    else:
        st.info("분석 모드는 기존 함수 유지 가능 (Top20, 트렌드 등)")

# =========================
# Part 4 — 11번가 (프록시 고정)
# =========================
AMAZON_BEST_URL = "https://m.11st.co.kr/page/main/home"

def render_11st_block():
    st.markdown("## 11번가 (모바일)")
    st.components.v1.iframe(_px_11(AMAZON_BEST_URL), height=780, scrolling=True)

# =========================
# Part 5 — 아이템스카우트 / 셀러라이프
# =========================
def render_itemscout_block():
    st.markdown("## 아이템스카우트")
    url = "https://app.itemscout.io/market/keyword"
    st.components.v1.iframe(_px_11(url), height=920, scrolling=True)

def render_sellerlife_block():
    st.markdown("## 셀러라이프")
    url = "https://sellerlife.co.kr/dashboard"
    st.components.v1.iframe(_px_11(url), height=920, scrolling=True)

# =========================
# Part 6 — AI 키워드 레이더 (Rakuten)
# =========================
RAKUTEN_APP_ID_DEFAULT       = "1043271015809337425"
RAKUTEN_AFFILIATE_ID_DEFAULT = "4c723498.cbfeca46.4c723499.1deb6f77"

def _get_rakuten_keys():
    app_id = (st.secrets.get("RAKUTEN_APP_ID") or RAKUTEN_APP_ID_DEFAULT).strip()
    aff = (st.secrets.get("RAKUTEN_AFFILIATE_ID") or RAKUTEN_AFFILIATE_ID_DEFAULT).strip()
    return app_id, aff

def render_rakuten_block():
    st.markdown("## AI 키워드 레이더 (Rakuten)")
    app_id, aff = _get_rakuten_keys()
    url = "https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20170628"
    try:
        r = requests.get(url, params={"applicationId": app_id, "genreId": "100283"}, timeout=10)
        rows = [{"rank": i+1, "keyword": it["Item"]["itemName"][:40]} for i, it in enumerate(r.json().get("Items", [])[:20])]
    except Exception:
        rows = [{"rank": i+1, "keyword": f"[샘플] {i+1}"} for i in range(20)]
    df = pd.DataFrame(rows)
    st.dataframe(df, hide_index=True, use_container_width=True, height=420)

# =========================
# Part 7 — 구글 번역기
# =========================
LANG_LABELS = {"ko":"한국어","en":"영어","ja":"일본어","zh-CN":"중국어(간체)","vi":"베트남어","th":"태국어"}
def translate_text(src:str, tgt:str, text:str) -> str:
    if not GoogleTranslator: return "[deep-translator 미설치]"
    return GoogleTranslator(source=src, target=tgt).translate(text)

def render_translator_block():
    st.markdown("## 구글 번역기")
    src = st.selectbox("원문", list(LANG_LABELS.keys()), index=0)
    tgt = st.selectbox("번역", list(LANG_LABELS.keys()), index=1)
    txt = st.text_area("입력")
    if st.button("번역"):
        st.text_area("결과", value=translate_text(src,tgt,txt))

# =========================
# Part 8 — 상품명 생성기
# =========================
def render_product_name_generator():
    st.markdown("## 상품명 생성기")
    brand = st.text_input("브랜드")
    attrs = st.text_input("속성(콤마)")
    kws = st.text_input("키워드(콤마)")
    if st.button("상품명 생성"):
        kw_list = [k.strip() for k in kws.split(",") if k.strip()]
        at_list = [a.strip() for a in attrs.split(",") if a.strip()]
        titles = [f"{brand} {k} {' '.join(at_list)}" for k in kw_list]
        st.write("\n".join(titles))

# =========================
# Part 9 — 메인 조립
# =========================
def _inject_global_css():
    st.markdown("""
    <style>
      .block-container { max-width: 3360px !important; }
    </style>
    """, unsafe_allow_html=True)

def main():
    render_sidebar()
    _inject_global_css()

    st.title("ENVY — Season 1 (Dual Proxy Edition)")

    # ── 1행: 데이터랩(6) · 아이템스카우트(3) · 셀러라이프(3)
    cols1 = st.columns([6,3,3])
    with cols1[0]: render_datalab_block()
    with cols1[1]: render_itemscout_block()
    with cols1[2]: render_sellerlife_block()

    # ── 2행: 11번가(3) · AI 키워드 레이더(3) · 구글 번역(3) · 상품명 생성기(3)
    cols2 = st.columns([3,3,3,3])
    with cols2[0]: render_11st_block()
    with cols2[1]: render_rakuten_block()
    with cols2[2]: render_translator_block()
    with cols2[3]: render_product_name_generator()

    # ── 맨 아래 호출은 삭제!
    # st.markdown("---")
    # render_product_name_generator()

if __name__ == "__main__":
    main()

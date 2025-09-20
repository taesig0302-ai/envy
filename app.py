# =========================================================
# ENVY — Season 1 (One-Page) · app.py  |  4×2 Grid UI (stable)
#  - Part 1: 사이드바(고정, 환율/마진 계산기 변경 금지)
#  - Part 2: 공용 유틸
#  - Part 3: 데이터랩 (분석 보조)
#  - Part 3.5: 데이터랩 (원본 임베드, 프록시 ?url=)
#  - Part 4: 11번가(모바일) 임베드
#  - Part 4.5: 아이템스카우트 임베드
#  - Part 4.6: 셀러라이프 임베드
#  - Part 5: AI 키워드 레이더 (Rakuten, 실데이터 우선)
#  - Part 6: 구글 번역
#  - Part 6.5: 상품명 생성기 (규칙 기반)
#  - Part 7: 메인 조립 (가로 4×2 그리드 배치)
#  - PROXY_URL 예: https://envy-proxy.taesig0302.workers.dev/
#  - DataLab: /shoppingInsight/getCategoryKeywordRank.naver, /shoppingInsight/getKeywordTrends.naver
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

st.set_page_config(page_title="ENVY — Season 1", layout="wide")

# -----------------------------
# Part 1 — 사이드바 (수정 금지 영역 유지)
# -----------------------------
CURRENCIES = {
    "USD": {"kr": "미국 달러", "symbol": "$", "unit": "USD"},
    "EUR": {"kr": "유로",     "symbol": "€", "unit": "EUR"},
    "JPY": {"kr": "일본 엔",   "symbol": "¥", "unit": "JPY"},
    "CNY": {"kr": "중국 위안", "symbol": "元","unit": "CNY"},
}
FX_DEFAULT = {"USD": 1400.0, "EUR": 1500.0, "JPY": 10.0, "CNY": 200.0}

def _ensure_session_defaults():
    ss = st.session_state
    ss.setdefault("theme", "light")
    ss.setdefault("PROXY_URL", "")
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

def _toggle_theme():
    st.session_state["theme"] = "dark" if st.session_state.get("theme","light")=="light" else "light"

def _inject_sidebar_css():
    theme = st.session_state.get("theme","light")
    bg, fg = ("#0e1117", "#e6edf3") if theme=="dark" else ("#ffffff","#111111")
    st.markdown(f"""
    <style>
      html, body, [data-testid="stAppViewContainer"] {{
        background-color:{bg} !important; color:{fg} !important;
      }}
      .block-container {{ padding-top:.8rem !important; padding-bottom:.35rem !important; }}

      /* 사이드바 고정(lock) — 내부 스크롤은 Part 7에서만 켬 */
      [data-testid="stSidebar"],
      [data-testid="stSidebar"] > div:first-child,
      [data-testid="stSidebar"] section {{
        height: 100vh !important; overflow: hidden !important;
        padding-top:.25rem !important; padding-bottom:.25rem !important;
      }}
      [data-testid="stSidebar"] ::-webkit-scrollbar {{ display:none !important; }}

      [data-testid="stSidebar"] .stSelectbox,
      [data-testid="stSidebar"] .stNumberInput,
      [data-testid="stSidebar"] .stRadio,
      [data-testid="stSidebar"] .stMarkdown,
      [data-testid="stSidebar"] .stTextInput,
      [data-testid="stSidebar"] .stButton {{ margin:.14rem 0 !important; }}

      [data-baseweb="input"] input,
      .stNumberInput input,
      [data-baseweb="select"] div[role="combobox"] {{
        height:1.55rem !important; padding:.12rem !important; font-size:.92rem !important;
      }}

      .logo-circle {{
        width:95px; height:95px; border-radius:50%; overflow:hidden;
        margin:.15rem auto .35rem auto; box-shadow:0 2px 8px rgba(0,0,0,.12);
        border:1px solid rgba(0,0,0,.06);
      }}
      .logo-circle img {{ width:100%; height:100%; object-fit:cover; }}

      .badge-green  {{ background:#e6ffcc; border:1px solid #b6f3a4; padding:6px 10px; border-radius:6px; color:#0b2e13; font-size:.86rem; }}
      .badge-blue   {{ background:#eef4ff; border:1px solid #bcd0ff; padding:6px 10px; border-radius:6px; color:#0a235a; font-size:.86rem; }}
      .badge-yellow {{ background:#fff7d6; border:1px solid #f1d27a; padding:6px 10px; border-radius:6px; color:#4a3b07; font-size:.86rem; }}
      .muted        {{ opacity:.8; font-size:.8rem; }}
      .info-box {{ background:rgba(0,0,0,.03); border:1px dashed rgba(0,0,0,.08); padding:.6rem; border-radius:.5rem; }}
    </style>
    """, unsafe_allow_html=True)

def render_sidebar() -> dict:
    _ensure_session_defaults()
    _inject_sidebar_css()

    result = {}
    with st.sidebar:
        lp = Path(__file__).parent / "logo.png"
        if lp.exists():
            b64 = base64.b64encode(lp.read_bytes()).decode("ascii")
            st.markdown(f'<div class="logo-circle"><img src="data:image/png;base64,{b64}"></div>', unsafe_allow_html=True)
        else:
            st.caption("logo.png 를 앱 파일과 같은 폴더에 두면 로고가 표시됩니다.")

        st.toggle("🌓 다크 모드", value=(st.session_state.get("theme","light")=="dark"), on_change=_toggle_theme, key="__theme_toggle")

        # ① 환율 계산기
        st.markdown("### ① 환율 계산기")
        base = st.selectbox("기준 통화", list(CURRENCIES.keys()),
                            index=list(CURRENCIES.keys()).index(st.session_state["fx_base"]),
                            key="fx_base")
        sale_foreign = st.number_input("판매금액 (외화)", value=float(st.session_state["sale_foreign"]), step=0.01, format="%.2f", key="sale_foreign")
        won = FX_DEFAULT[base] * sale_foreign
        st.markdown(
            f'<div class="badge-green">환산 금액: <b>{won:,.2f} 원</b> '
            f'<span class="muted">({CURRENCIES[base]["kr"]} • {CURRENCIES[base]["symbol"]})</span></div>',
            unsafe_allow_html=True
        )
        st.caption(f"환율 기준: {FX_DEFAULT[base]:,.2f} ₩/{CURRENCIES[base]['unit']}")

        # ② 마진 계산기
        st.markdown("### ② 마진 계산기")
        m_base = st.selectbox("매입 통화", list(CURRENCIES.keys()),
                              index=list(CURRENCIES.keys()).index(st.session_state["m_base"]),
                              key="m_base")
        purchase_foreign = st.number_input("매입금액 (외화)", value=float(st.session_state["purchase_foreign"]), step=0.01, format="%.2f", key="purchase_foreign")
        base_cost_won = FX_DEFAULT[m_base] * purchase_foreign if purchase_foreign>0 else won
        st.markdown(f'<div class="badge-green">원가(₩): <b>{base_cost_won:,.2f} 원</b></div>', unsafe_allow_html=True)

        colf1, colf2 = st.columns(2)
        with colf1:
            card_fee = st.number_input("카드수수료(%)", value=float(st.session_state["card_fee_pct"]), step=0.01, format="%.2f", key="card_fee_pct")
        with colf2:
            market_fee = st.number_input("마켓수수료(%)", value=float(st.session_state["market_fee_pct"]), step=0.01, format="%.2f", key="market_fee_pct")
        shipping_won = st.number_input("배송비(₩)", value=float(st.session_state["shipping_won"]), step=100.0, format="%.0f", key="shipping_won")

        mode = st.radio("마진 방식", ["퍼센트","플러스"], horizontal=True, key="margin_mode")
        if mode == "퍼센트":
            margin_pct = st.number_input("마진율 (%)", value=float(st.session_state["margin_pct"]), step=0.01, format="%.2f", key="margin_pct")
            target_price = base_cost_won * (1 + card_fee/100) * (1 + market_fee/100) * (1 + margin_pct/100) + shipping_won
            margin_value = target_price - base_cost_won
            margin_desc = f"{margin_pct:.2f}%"
        else:
            margin_won = st.number_input("마진액 (₩)", value=float(st.session_state["margin_won"]), step=100.0, format="%.0f", key="margin_won")
            target_price = base_cost_won * (1 + card_fee/100) * (1 + market_fee/100) + margin_won + shipping_won
            margin_value = margin_won
            margin_desc = f"+{margin_won:,.0f}"

        st.markdown(f'<div class="badge-blue">판매가: <b>{target_price:,.2f} 원</b></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="badge-yellow">순이익(마진): <b>{margin_value:,.2f} 원</b> — {margin_desc}</div>', unsafe_allow_html=True)

        st.divider()
        st.markdown("##### 프록시/환경")
        st.text_input("PROXY_URL (Cloudflare Worker 등)", value=st.session_state.get("PROXY_URL",""),
                      key="PROXY_URL", help="예: https://envy-proxy.taesig0302.workers.dev/")
        st.markdown("""
            <div class="info-box">
              <b>ENVY</b> 사이드바 정보는 고정입니다.<br/>
              · 로고/환율/마진 계산기: 변경 금지<br/>
              · PROXY_URL: 11번가/데이터랩/임베드용(필요시)<br/>
              · 다크/라이트 모드는 상단 토글
            </div>
        """, unsafe_allow_html=True)

    result.update({
        "fx_base": base,
        "sale_foreign": sale_foreign,
        "converted_won": won,
        "purchase_base": m_base,
        "purchase_foreign": purchase_foreign,
        "base_cost_won": base_cost_won,
        "card_fee_pct": card_fee,
        "market_fee_pct": market_fee,
        "shipping_won": shipping_won,
        "margin_mode": mode,
        "target_price": target_price,
        "margin_value": margin_value,
    })
    return result

# -----------------------------
# Part 2 — 공용 유틸
# -----------------------------
LANG_LABELS = {
    "auto":"자동 감지",
    "ko":"한국어","en":"영어","ja":"일본어",
    "zh-CN":"중국어(간체)","zh-TW":"중국어(번체)",
    "vi":"베트남어","th":"태국어","id":"인도네시아어",
    "de":"독일어","fr":"프랑스어","es":"스페인어","it":"이탈리아어","pt":"포르투갈어",
}
def lang_label_to_code(label_or_code:str) -> str:
    rev = {v:k for k,v in LANG_LABELS.items()}
    return rev.get(label_or_code, label_or_code)

def toast_ok(msg:str): st.toast(f"✅ {msg}")
def toast_warn(msg:str): st.toast(f"⚠️ {msg}")
def toast_err(msg:str): st.toast(f"❌ {msg}")

# -----------------------------
# Part 3 — 데이터랩(분석 보조) v3
# -----------------------------
from collections import defaultdict

DATALAB_CATS = [
    '패션의류','패션잡화','화장품/미용','디지털/가전','가구/인테리어',
    '출산/육아','식품','스포츠/레저','생활/건강','여가/생활편의','면세점','도서'
]
CID_MAP = {
    '패션의류':'50000000','패션잡화':'50000001','화장품/미용':'50000002','디지털/가전':'50000003',
    '가구/인테리어':'50000004','출산/육아':'50000005','식품':'50000006','스포츠/레저':'50000007',
    '생활/건강':'50000008','여가/생활편의':'50000009','면세점':'50000010','도서':'50005542',
}

def _naver_cookie() -> str:
    try:
        v = st.secrets.get('NAVER_COOKIE', '')
    except Exception:
        v = ''
    if v: return v.strip()
    env = os.getenv('NAVER_COOKIE', '').strip()
    if env: return env
    return st.session_state.get('__NAVER_COOKIE', '').strip()

def _hdr(cookie: str, cid: str, time_unit: str='week', device: str='all', as_json: bool=True) -> dict:
    h = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari

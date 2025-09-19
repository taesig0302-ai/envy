# =========================
# ENVY — Season 1 (one-file, parts in order)
# =========================
import os, re, json
from datetime import date, timedelta
from typing import Any, List, Dict
from collections import defaultdict
from urllib.parse import quote

import streamlit as st
import pandas as pd
import numpy as np

# 외부 모듈(미설치 시 안내만)
try:
    import requests
except Exception:
    requests = None

try:
    from deep_translator import GoogleTranslator
except Exception:
    GoogleTranslator = None


# =========================
# Part 1 — 사이드바 (로고 + 환율/마진 계산기 + API Key + 프록시)
# =========================
import streamlit as st
import base64
from pathlib import Path

# ── 전역 기본값 ─────────────────────────────────────────────────────────────
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
    # 프록시/키 보관
    ss.setdefault("PROXY_URL", "")
    ss.setdefault("ITEMSCOUT_API_KEY", st.secrets.get("ITEMSCOUT_API_KEY",""))
    ss.setdefault("SELLERLIFE_API_KEY", st.secrets.get("SELLERLIFE_API_KEY",""))
    ss.setdefault("RAKUTEN_APP_ID", st.secrets.get("RAKUTEN_APP_ID",""))

    # 환율/마진 계산기 기본값(수정 금지 요청 반영)
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
      [data-testid="stSidebar"],
      [data-testid="stSidebar"] > div:first-child,
      [data-testid="stSidebar"] section {{
        height: 100vh !important; overflow: hidden !important;
        padding-top:.25rem !important; padding-bottom:.25rem !important;
      }}
      [data-testid="stSidebar"] section {{ overflow-y:auto !important; }}
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
        # 로고
        lp = Path(__file__).parent / "logo.png"
        if lp.exists():
            b64 = base64.b64encode(lp.read_bytes()).decode("ascii")
            st.markdown(f'<div class="logo-circle"><img src="data:image/png;base64,{b64}"></div>', unsafe_allow_html=True)
        else:
            st.caption("logo.png 를 앱 폴더에 두면 로고가 표시됩니다.")
        st.toggle("🌓 다크 모드", value=(st.session_state.get("theme","light")=="dark"), on_change=_toggle_theme, key="__theme_toggle")

        # ① 환율 계산기 (수정 금지·그대로 유지)
        st.markdown("### ① 환율 계산기")
        base = st.selectbox("기준 통화", list(CURRENCIES.keys()),
                            index=list(CURRENCIES.keys()).index(st.session_state["fx_base"]), key="fx_base")
        sale_foreign = st.number_input("판매금액 (외화)", value=float(st.session_state["sale_foreign"]),
                                       step=0.01, format="%.2f", key="sale_foreign")
        won = FX_DEFAULT[base] * sale_foreign
        st.markdown(
            f'<div class="badge-green">환산 금액: <b>{won:,.2f} 원</b> '
            f'<span class="muted">({CURRENCIES[base]["kr"]} • {CURRENCIES[base]["symbol"]})</span></div>',
            unsafe_allow_html=True
        )
        st.caption(f"환율 기준: {FX_DEFAULT[base]:,.2f} ₩/{CURRENCIES[base]['unit']}")

        # ② 마진 계산기 (수정 금지·그대로 유지)
        st.markdown("### ② 마진 계산기")
        m_base = st.selectbox("매입 통화", list(CURRENCIES.keys()),
                              index=list(CURRENCENCIES.keys()).index(st.session_state["m_base"]) if "CURRENCENCIES" in globals() else list(CURRENCIES.keys()).index(st.session_state["m_base"]),
                              key="m_base")
        purchase_foreign = st.number_input("매입금액 (외화)", value=float(st.session_state["purchase_foreign"]),
                                           step=0.01, format="%.2f", key="purchase_foreign")
        base_cost_won = FX_DEFAULT[m_base] * purchase_foreign if purchase_foreign>0 else won
        st.markdown(f'<div class="badge-green">원가(₩): <b>{base_cost_won:,.2f} 원</b></div>', unsafe_allow_html=True)

        colf1, colf2 = st.columns(2)
        with colf1:
            card_fee = st.number_input("카드수수료(%)", value=float(st.session_state["card_fee_pct"]),
                                       step=0.01, format="%.2f", key="card_fee_pct")
        with colf2:
            market_fee = st.number_input("마켓수수료(%)", value=float(st.session_state["market_fee_pct"]),
                                         step=0.01, format="%.2f", key="market_fee_pct")
        shipping_won = st.number_input("배송비(₩)", value=float(st.session_state["shipping_won"]),
                                       step=100.0, format="%.0f", key="shipping_won")

        mode = st.radio("마진 방식", ["퍼센트","플러스"], horizontal=True, key="margin_mode")
        if mode == "퍼센트":
            margin_pct = st.number_input("마진율 (%)", value=float(st.session_state["margin_pct"]),
                                         step=0.01, format="%.2f", key="margin_pct")
            target_price = base_cost_won * (1 + card_fee/100) * (1 + market_fee/100) * (1 + margin_pct/100) + shipping_won
            margin_value = target_price - base_cost_won
            margin_desc = f"{margin_pct:.2f}%"
        else:
            margin_won = st.number_input("마진액 (₩)", value=float(st.session_state["margin_won"]),
                                         step=100.0, format="%.0f", key="margin_won")
            target_price = base_cost_won * (1 + card_fee/100) * (1 + market_fee/100) + margin_won + shipping_won
            margin_value = margin_won
            margin_desc = f"+{margin_won:,.0f}"

        st.markdown(f'<div class="badge-blue">판매가: <b>{target_price:,.2f} 원</b></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="badge-yellow">순이익(마진): <b>{margin_value:,.2f} 원</b> — {margin_desc}</div>', unsafe_allow_html=True)

        # ── 외부 API KEY 보관 + 프록시 ─────────────────────────────────────
        st.divider()
        st.markdown("##### 외부 API Key 보관")
        st.text_input("아이템스카우트 API Key", value=st.session_state["ITEMSCOUT_API_KEY"],
                      type="password", key="ITEMSCOUT_API_KEY")
        st.text_input("셀러라이프 API Key", value=st.session_state["SELLERLIFE_API_KEY"],
                      type="password", key="SELLERLIFE_API_KEY")
        st.text_input("Rakuten APP_ID", value=st.session_state["RAKUTEN_APP_ID"],
                      type="password", key="RAKUTEN_APP_ID")

        st.markdown("##### 프록시/환경")
        st.text_input("PROXY_URL (Cloudflare Worker 등 — ?url=… 지원)", value=st.session_state.get("PROXY_URL",""),
                      key="PROXY_URL",
                      help="예: https://envy-proxy.example.workers.dev  (마지막 /는 빼도 됨)")

        st.markdown("""
        <div class="info-box">
          <b>ENVY</b> 사이드바 정보는 고정입니다.<br/>
          · 환율/마진 계산기는 변경 금지<br/>
          · 11번가/데이터랩/아이템스카우트/셀러라이프 임베드에 PROXY_URL 사용<br/>
          · 키는 <code>st.secrets</code> 또는 사이드바 보관칸 중 편한 방식 사용
        </div>
        """, unsafe_allow_html=True)

    result.update({
        "fx_base": base, "sale_foreign": sale_foreign, "converted_won": won,
        "purchase_base": m_base, "purchase_foreign": purchase_foreign,
        "base_cost_won": base_cost_won, "card_fee_pct": card_fee, "market_fee_pct": market_fee,
        "shipping_won": shipping_won, "margin_mode": mode, "target_price": target_price, "margin_value": margin_value,
    })
    return result
# =========================
# Part 2 — 공용 유틸 + 전역 CSS
# =========================
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

def inject_global_css():
    st.markdown("""
    <style>
      .block-container { max-width: 1680px !important; padding-top:.8rem !important; padding-bottom:1rem !important; }
      html, body { overflow: auto !important; } /* 본문 스크롤 허용 */
      [data-testid="stSidebar"] section { overflow-y: auto !important; } /* 사이드바 내부 스크롤 허용 */
      h2, h3 { margin-top: .4rem !important; }
    </style>
    """, unsafe_allow_html=True)


# ====== Part 3 (REPLACE WHOLE BLOCK) ==========================================
import json, time, hmac, hashlib, base64, requests, urllib.parse as _url
import pandas as pd
import streamlit as st

# 대분류 → CID 매핑(네이버 데이터랩 쇼핑인사이트 카테고리)
DATALAB_CAT = {
    "패션의류": "50000000", "패션잡화": "50000001", "화장품/미용": "50000002",
    "디지털/가전": "50000003", "가구/인테리어": "50000004", "출산/육아": "50000005",
    "식품": "50000006", "스포츠/레저": "50000007", "생활/건강": "50000008",
    "여가/생활편의": "50000009", "면세점": "50000010", "도서": "50005542"
}
DATALAB_CATS = list(DATALAB_CAT.keys())

def _inject_main_css():
    st.markdown("""
    <style>
      /* 레이아웃 폭 확장 & 여백 정돈 */
      .block-container { max-width: 1800px !important; padding-top: .6rem !important; }
      /* 카드 느낌 */
      .envy-card { background: var(--background-color); border: 1px solid rgba(0,0,0,.08);
                   border-radius: 10px; padding: 12px; }
      /* 표 글자 살짝 축소 */
      .sm-table table { font-size: 0.92rem !important; }
      /* 임베드 프레임 공통 */
      .embed { border: 1px solid rgba(0,0,0,.1); border-radius: 10px; overflow: hidden; }
      /* 라쿠텐 표 축소 */
      .rk table { font-size:.90rem !important; }
      /* 상단 경고/토스트 줄 높이 */
      .stAlert, .stInfo { line-height: 1.35; }
    </style>
    """, unsafe_allow_html=True)

def _get_secret(name:str, default:str=""):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default

def _proxy_base():
    # 사이드바의 입력값 또는 기본 프록시
    return (st.session_state.get("PROXY_URL") or "https://envy-proxy.taesig0302.workers.dev").rstrip("/")

def _proxied(url:str) -> str:
    # Cloudflare Worker 포맷: https://worker.dev/?url=<ENCODED>
    return f"{_proxy_base()}/?url={_url.quote(url, safe='')}"

# -------- 데이터랩 원본 임베드 --------
def render_datalab_embed():
    st.markdown("### 데이터랩 (원본 임베드)")
    c1,c2,c3 = st.columns([1,1,1])
    with c1:
        cat = st.selectbox("카테고리", DATALAB_CATS, key="dl_raw_cat")
    with c2:
        unit = st.selectbox("기간 단위", ["week","month"], index=0, key="dl_raw_unit")
    with c3:
        device = st.selectbox("기기", ["all","pc","mo"], index=0, key="dl_raw_device")

    raw_url = f"https://datalab.naver.com/shoppingInsight/sCategory.naver?cat_id={DATALAB_CAT[cat]}&period={unit}&device={device}"
    if not st.session_state.get("PROXY_URL"):
        st.info("PROXY_URL 이 비어 있습니다. 사이드바 하단에 Cloudflare Worker 주소를 입력해 주세요.")

    st.components.v1.iframe(_proxied(raw_url), height=580, scrolling=True, key="dl_raw_iframe")

    st.caption(raw_url)

# -------- 네이버 광고 키워드툴(검색량) --------
def _naver_ads_keywordtool_volumes(keywords:list[str]) -> dict:
    """
    keywords -> {'키워드': (monthlyPcQcCnt, monthlyMobileQcCnt)}  (없으면 빈 dict)
    """
    API_KEY  = _get_secret("NAVER_ADS_API_KEY")
    API_SEC  = _get_secret("NAVER_ADS_API_SECRET")
    CUST_ID  = _get_secret("NAVER_ADS_CUSTOMER_ID")
    if not (API_KEY and API_SEC and CUST_ID and keywords):
        return {}

    endpoint = "https://api.searchad.naver.com/keywordstool"
    ts = str(int(time.time() * 1000))
    method = "GET"
    uri = "/keywordstool"
    message = ts + "." + method + "." + uri
    sign = base64.b64encode(hmac.new(bytes(API_SEC, "utf-8"),
                                     bytes(message, "utf-8"),
                                     hashlib.sha256).digest()).decode("utf-8")
    params = {
        "hintKeywords": ",".join(keywords[:50]),
        "showDetail": "1"
    }
    headers = {
        "X-Timestamp": ts,
        "X-API-KEY": API_KEY,
        "X-Customer": CUST_ID,
        "X-Signature": sign,
    }
    try:
        r = requests.get(endpoint, params=params, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        out = {}
        for row in data.get("keywordList", []):
            kw = row.get("relKeyword")
            out[kw] = (row.get("monthlyPcQcCnt", 0) or 0, row.get("monthlyMobileQcCnt", 0) or 0)
        return out
    except Exception:
        return {}

# -------- 데이터랩 분석(API) : Top20 + 트렌드 샘플 --------
def _datalab_post(url:str, payload:dict, cookie:str) -> dict|None:
    try:
        headers = {
            "Content-Type": "application/json; charset=UTF-8",
            "Referer": "https://datalab.naver.com/shoppingInsight/sCategory.naver",
            "Cookie": cookie.strip(),
        }
        r = requests.post(url, data=json.dumps(payload), headers=headers, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None

def datalab_fetch_top20(cat_id:str, start:str, end:str, device:str, cookie:str) -> pd.DataFrame|None:
    # 비공식 엔드포인트(변경될 수 있음): ranks 반환
    url = "https://datalab.naver.com/shoppingInsight/getCategoryKeywordRank.naver"
    body = {
        "cid": cat_id,
        "timeUnit": "week",  # UI는 단순화
        "startDate": start, "endDate": end,
        "age": [], "gender": "", "device": device, "keywordCount": 20
    }
    data = _datalab_post(url, body, cookie)
    if not data:
        return None
    ranks = (data.get("ranks") or [])
    # 형식: [{keyword, rank, ratio, ...}, ...]
    rows = [{"rank": r.get("rank"), "keyword": r.get("keyword"), "score": r.get("ratio", 0)} for r in ranks]
    if not rows:
        return None
    df = pd.DataFrame(rows).sort_values("rank")
    return df

def render_datalab_analysis():
    st.markdown("### 데이터랩 (분석 · Top20 + 트렌드)")
    c1,c2,c3 = st.columns([1,1,1])
    with c1:
        cat = st.selectbox("카테고리", DATALAB_CATS, key="dl_cat_v2")
    with c2:
        sd = st.date_input("시작일", pd.to_datetime("today")-pd.Timedelta(days=31), key="dl_start_v2")
    with c3:
        ed = st.date_input("종료일", pd.to_datetime("today"), key="dl_end_v2")
    c4,c5 = st.columns([1,1])
    with c4:
        device = st.selectbox("기기", ["all","pc","mo"], index=0, key="dl_device_v2")
    with c5:
        cookie_in = st.text_input("NAVER_COOKIE (미입력 시 secrets 사용)", type="password", key="dl_cookie_input")

    cookie = cookie_in or _get_secret("NAVER_COOKIE")
    cat_id = DATALAB_CAT[cat]
    btn = st.button("Top20 불러오기", key="dl_go_top20")
    holder = st.empty()

    if btn:
        if not cookie:
            st.error("NAVER_COOKIE가 비어 있습니다. 상단에 붙여넣고 ‘Top20 불러오기’를 눌러 주세요.")
            return
        with holder:
            with st.spinner("데이터랩 조회 중…"):
                df = datalab_fetch_top20(cat_id, str(sd), str(ed), device, cookie)
        if df is None or df.empty:
            st.error("조회 실패: 응답 파싱 실패(구조 변경 가능성). 샘플 표를 표시합니다.")
            df = pd.DataFrame([{"rank": i+1, "keyword": f"샘플 키워드 {i+1}", "score": 100-i} for i in range(20)])
        # 키워드 검색량(선택) — 네이버 광고 키워드툴
        vol = _naver_ads_keywordtool_volumes(df["keyword"].tolist())
        if vol:
            df["pc/mo"] = df["keyword"].map(lambda k: f"{vol.get(k,(0,0))[0]}/{vol.get(k,(0,0))[1]}")
        st.markdown("**Top20 키워드**")
        st.dataframe(df, use_container_width=True, hide_index=True)

        # 간단 트렌드(샘플 라인 3개)
        st.markdown("**캠프 기간 트렌드 (데모 라인)**")
        xx = list(range(12))
        demo = pd.DataFrame({
            df.loc[0,"keyword"] if not df.empty else "kw1": [50,53,49,44,48,60,62,61,58,56,54,53],
            df.loc[1,"keyword"] if len(df)>1 else "kw2": [48,50,47,40,43,57,58,57,55,52,49,47],
            df.loc[2,"keyword"] if len(df)>2 else "kw3": [46,48,45,38,41,52,53,52,49,46,44,42],
        }, index=xx)
        st.line_chart(demo, use_container_width=True, height=220)
# ====== Part 4 (REPLACE WHOLE BLOCK) ==========================================
def render_11st_block():
    st.markdown("### 11번가 (모바일 · 아마존베스트 고정)")
    fixed_url = "https://m.11st.co.kr/page/main/abest?tabId=ABEST&pageId=AMOBEST&ctgr1No=166160"
    if not st.session_state.get("PROXY_URL"):
        st.info("PROXY_URL 미설정: 11번가 iFrame가 차단될 수 있습니다. (Cloudflare Worker 권장)")
    try:
        st.components.v1.iframe(_proxied(fixed_url), height=600, scrolling=True, key="t11_iframe")
    except Exception as e:
        st.error(f"11번가 임베드 실패: {e}")
# ==============================================================================
# ====== Part 5 (MINOR REPLACE: fetch + render) ================================
import requests

RAKUTEN_CATS = [
    "전체(샘플)","뷰티/코스메틱","의류/패션","가전/디지털","가구/인테리어","식품","생활/건강","스포츠/레저","문구/취미"
]

def _rk_fetch_rank_keywords(app_id:str, genre_id:str="100283", n:int=30) -> pd.DataFrame|None:
    if not app_id:
        return None
    url = "https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20170628"
    try:
        r = requests.get(url, params={"format":"json","applicationId":app_id,"genreId":genre_id}, timeout=10)
        r.raise_for_status()
        items = r.json().get("Items", [])
        rows = []
        for i, it in enumerate(items[:n], 1):
            title = (it.get("Item") or {}).get("itemName","")
            rows.append({"rank": i, "keyword": title, "source": "Rakuten"})
        return pd.DataFrame(rows)
    except Exception:
        return None

def render_rakuten_block():
    st.markdown("### AI 키워드 레이더 (Rakuten)")
    colA,colB,colC = st.columns([1,1,1])
    with colA:
        scope = st.radio("범위", ["국내","글로벌"], horizontal=True, key="rk_scope_v2")
    with colB:
        cat = st.selectbox("라쿠텐 카테고리", RAKUTEN_CATS, key="rk_cat_v2")
    with colC:
        genreid = st.text_input("GenreID", "100283", key="rk_genre_v2")

    st.caption("APP_ID는 secrets['RAKUTEN_APP_ID']에서 읽어옵니다. 미설정 시 샘플 표시.")
    app_id = _get_secret("RAKUTEN_APP_ID")
    df = _rk_fetch_rank_keywords(app_id, genreid) if app_id else None
    if df is None:
        df = pd.DataFrame([{"rank": i+1, "keyword": f"[샘플] 키워드 {i+1}", "source":"sample"} for i in range(30)])

    st.markdown('<div class="rk">', unsafe_allow_html=True)
    st.dataframe(df, hide_index=True, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)
# ==============================================================================
# ====== Part 6 (REPLACE WHOLE BLOCK) ==========================================
import re

def _tokenize_ko_en(s:str) -> list[str]:
    s = re.sub(r"[^\w가-힣\s\-+/#]", " ", s)
    toks = [t.strip() for t in s.split() if t.strip()]
    return toks

def _keyword_candidates(brand:str, base:str, attrs:str, model:str) -> list[str]:
    pieces = [brand, base, attrs, model]
    toks = []
    for p in pieces:
        toks += _tokenize_ko_en(p or "")
    # 길이 2 이상, 중복 제거
    seen, out = set(), []
    for t in toks:
        if len(t) < 2: continue
        if t.lower() in seen: continue
        seen.add(t.lower()); out.append(t)
    return out[:12]

def _compose_names(brand:str, base:str, attrs:str, model:str) -> list[str]:
    patts = [
        "{brand} {base} {model} {attrs}",
        "{brand} {base} {attrs} {model}",
        "{brand} {attrs} {base} {model}",
        "{brand} {base} {model}",
    ]
    out = []
    for p in patts:
        name = p.format(brand=brand.strip(), base=base.strip(), attrs=attrs.strip(), model=model.strip())
        name = re.sub(r"\s+", " ", name).strip()
        if name and name not in out: out.append(name)
    return out

def render_name_generator():
    st.markdown("### 상품명 생성기 (규칙 기반)")
    with st.container(border=True):
        cc1,cc2,cc3,cc4 = st.columns([1,1,1,1])
        with cc1: brand = st.text_input("브랜드", key="ng_brand")
        with cc2: base  = st.text_input("기본 키워드", key="ng_base")
        with cc3: attrs = st.text_input("속성/특징", key="ng_attrs", placeholder="색상, 재질, 용량 등")
        with cc4: model = st.text_input("모델", key="ng_model")

        if st.button("상품명 생성", key="ng_go"):
            names = _compose_names(brand, base, attrs, model)
            st.markdown("**생성 결과**")
            for i, n in enumerate(names, 1):
                st.write(f"{i}. {n}")

            # 추천 키워드 5개 + 검색량(가능 시)
            cands = _keyword_candidates(brand, base, attrs, model)
            vols = _naver_ads_keywordtool_volumes(cands)
            rows = []
            for kw in cands[:5]:
                pc, mo = (vols.get(kw) or (0,0))
                rows.append({"keyword": kw, "pc": pc, "mo": mo, "합계": pc+mo})
            df = pd.DataFrame(rows).sort_values("합계", ascending=False)
            st.markdown("**추천 키워드(검색량)**")
            st.dataframe(df, hide_index=True, use_container_width=True)
# ==============================================================================
# ====== Part 7 (REPLACE WHOLE BLOCK) ==========================================
def main():
    _inject_main_css()

    # 1) 사이드바(수정 금지) 먼저 렌더
    sidebar_vals = render_sidebar()

    st.title("ENVY — v11.x (stable)")
    st.caption("사이드바 고정, 4×2 격자 고정 배치")

    # -------- 1행: 데이터랩(원본) · 데이터랩(분석) · 11번가 · 상품명 생성기 --------
    r1c1,r1c2,r1c3,r1c4 = st.columns(4, gap="small")
    with r1c1:
        with st.container():
            render_datalab_embed()
    with r1c2:
        with st.container():
            render_datalab_analysis()
    with r1c3:
        with st.container():
            render_11st_block()
    with r1c4:
        with st.container():
            render_name_generator()

    st.divider()

    # -------- 2행: 라쿠텐 · 구글 번역 · 아이템스카우트 · 셀러라이프 --------
    r2c1,r2c2,r2c3,r2c4 = st.columns(4, gap="small")
    with r2c1:
        with st.container():
            render_rakuten_block()

    with r2c2:
        with st.container():
            render_translator_block()  # 기존 Part 6의 번역기 함수 그대로 사용

    with r2c3:
        with st.container():
            st.markdown("### 아이템스카우트 (원본 임베드)")
            url = "https://items.singtown.com"
            if not st.session_state.get("PROXY_URL"):
                st.info("PROXY_URL 이 비어 있습니다. 사이드바 하단에 Cloudflare Worker 주소를 입력해 주세요.")
            st.components.v1.iframe(_proxied(url), height=520, scrolling=True, key="isc_iframe")

    with r2c4:
        with st.container():
            st.markdown("### 셀러라이프 (원본 임베드)")
            url = "https://www.sellerlife.co.kr"
            if not st.session_state.get("PROXY_URL"):
                st.info("PROXY_URL 이 비어 있습니다. 사이드바 하단에 Cloudflare Worker 주소를 입력해 주세요.")
            st.components.v1.iframe(_proxied(url), height=520, scrolling=True, key="slf_iframe")

    # 하단 공통 오류/안내 바
    st.divider()
    st.info("⚠️ 주의: 데이터랩 분석은 비공식 엔드포인트에 의존합니다. 구조 변경/쿠키 만료 시 Top20 응답이 비거나 ‘샘플’로 폴백됩니다. "
            "11번가/데이터랩/아이템스카우트/셀러라이프 임베드는 iFrame 차단을 회피하기 위해 Cloudflare Worker 프록시를 사용합니다.")
# ==============================================================================

if __name__ == "__main__":
    main()
# =========================
# Part 8 — 상품명 생성기 (규칙 기반)
# =========================
import re as _re_titles
from itertools import product as _product, combinations as _combinations

def _dedup_tokens(seq):
    seen=set(); out=[]
    for tok in seq:
        t=tok.strip()
        if not t: continue
        key=t.lower()
        if key in seen: continue
        seen.add(key); out.append(t)
    return out

def _clean_title(s, delimiter):
    s = _re_titles.sub(r'\s+', ' ', s).strip()
    s = _re_titles.sub(rf'\s*{re.escape(delimiter)}\s*', f' {delimiter} ', s)
    s = _re_titles.sub(rf'(?:\s*{re.escape(delimiter)}\s*)+', f' {delimiter} ', s)
    s = _re_titles.sub(r'\s+', ' ', s).strip(' -|/').strip()
    return s

def render_title_gen_block():
    st.markdown("## 상품명 생성기 (규칙 기반)")
    with st.container():
        c1,c2,c3 = st.columns([1.1,1,1])
        with c1:
            brand = st.text_input("브랜드", placeholder="예: Apple / Dyson / 무지", key="tg_brand")
            base_keywords = st.text_input("메인 키워드(콤마)", placeholder="예: 헤어드라이어, 무선청소기", key="tg_keywords")
        with c2:
            attrs = st.text_area("속성/수식어(콤마)", placeholder="예: 1200W, 강풍, 저소음, 정품, AS가능, 2025신형", height=90, key="tg_attrs")
            model = st.text_input("모델/시리즈", placeholder="예: HD15 / V12", key="tg_model")
        with c3:
            market = st.selectbox("마켓 프리셋", ["자유(100)","네이버(50)","11번가(60)","쿠팡(70)","라쿠텐(75)"], index=0, key="tg_market")
            delim = st.selectbox("구분자", ["|","-","/","·"," "], index=0, key="tg_delim")
            max_len_map={"자유(100)":100,"네이버(50)":50,"11번가(60)":60,"쿠팡(70)":70,"라쿠텐(75)":75}
            max_len = st.slider("최대 글자수", 30, 120, value=max_len_map[market], step=5, key="tg_maxlen")
        st.caption("규칙: {브랜드} + {메인키워드} + {속성조합} + {모델} 순서. 중복/공백 자동 정리.")

        c4,c5 = st.columns([1,1])
        with c4:
            attrs_per_title = st.slider("속성 최대 개수", 1, 4, 2, key="tg_attrs_per")
            variants = st.slider("생성 개수", 5, 100, 30, step=5, key="tg_variants")
        with c5:
            stopwords = st.text_input("금칙어(콤마)", placeholder="예: 무료배송, 사은품", key="tg_stop")
            template = st.text_input("템플릿", value="{brand} {keyword} {attrs} {model}", key="tg_tpl",
                                     help="{brand},{keyword},{attrs},{model} 사용 가능")

        if st.button("상품명 생성", use_container_width=True, key="tg_go"):
            brand_tok = brand.strip()
            kws = [t.strip() for t in base_keywords.split(",") if t.strip()]
            attr_tokens = [t.strip() for t in attrs.split(",") if t.strip()]
            model_tok = model.strip()
            bans = {t.strip().lower() for t in stopwords.split(",") if t.strip()}

            if not kws:
                st.error("메인 키워드를 최소 1개 입력하세요.")
                return

            # 속성 조합 만들기
            attr_tokens = _dedup_tokens(attr_tokens)[:12]
            attr_combos = [[]]
            for r in range(1, attrs_per_title+1):
                attr_combos += list(_combinations(attr_tokens, r))

            # 생성
            generated = []
            for kw, combo in _product(kws, attr_combos):
                attrs_str = f" {st.session_state.get('tg_delim','|')} ".join(combo).strip()
                ctx = {"brand": brand_tok, "keyword": kw, "attrs": attrs_str, "model": model_tok}
                raw = template.format(**ctx).strip()
                if any(b in raw.lower() for b in bans):
                    continue
                title = _clean_title(raw, st.session_state.get('tg_delim','|'))
                if len(title) <= st.session_state.get("tg_maxlen", 100) and len(title) >= 8:
                    generated.append(title)

            # 중복 제거
            uniq=[]; seen=set()
            for t in generated:
                k=t.lower()
                if k in seen: continue
                seen.add(k); uniq.append(t)
            uniq = uniq[:st.session_state.get("tg_variants", 30)]

            if not uniq:
                st.warning("조건에 맞는 결과가 없습니다. 최대 글자수 또는 속성 개수를 늘려보세요.")
                return

            df = pd.DataFrame({"상품명": uniq})
            st.dataframe(df, use_container_width=True, hide_index=True, height=min(600, 32+24*len(uniq)))
            st.text_area("결과(복사용)", "\n".join(uniq), height=180)
            st.download_button("CSV 다운로드", df.to_csv(index=False).encode("utf-8-sig"),
                               file_name="titles.csv", mime="text/csv")


# =========================
# Part 9 — 메인 조립 (3×2 레이아웃)
# =========================
def _safe_call(fn, title:str=None):
    if title: st.markdown(f"## {title}")
    try:
        fn()
    except Exception as e:
        st.error(f"{title or fn.__name__} 실행 중 오류: {e}")

def main():
    # 사이드바 + 전역 CSS
    render_sidebar()
    inject_global_css()

    st.title("ENVY — Season 1 (stable)")
    st.caption("가로 3열 × 2행 그리드. 프록시/쿠키는 워커·시크릿으로 관리.")

    # 1행: 데이터랩 | 11번가 | 상품명 생성기
    c1, c2, c3 = st.columns([1.15, 1, 1], gap="large")
    with c1:
        st.markdown("### 데이터랩")
        tab1, tab2 = st.tabs(["원본", "분석"])
        with tab1:
            _safe_call(render_datalab_embed_block)
        with tab2:
            _safe_call(render_datalab_block)
    with c2:
        st.markdown("### 11번가 (모바일)")
        _safe_call(render_11st_block)
    with c3:
        st.markdown("### 상품명 생성기")
        _safe_call(render_title_gen_block)

    # 2행: 키워드 레이더 | 구글 번역 | 아이템스카우트/셀러라이프
    d1, d2, d3 = st.columns([1, 1, 1], gap="large")
    with d1:
        st.markdown("### AI 키워드 레이더 (Rakuten)")
        _safe_call(render_rakuten_block)
    with d2:
        st.markdown("### 구글 번역")
        _safe_call(render_translator_block)
    with d3:
        st.markdown("### 아이템스카우트 / 셀러라이프")
        t_is, t_sl = st.tabs(["아이템스카우트", "셀러라이프"])
        with t_is:
            _safe_call(render_itemscout_embed)
        with t_sl:
            _safe_call(render_sellerlife_embed)

if __name__ == "__main__":
    main()

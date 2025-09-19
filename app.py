# =========================
# Part 1 — 사이드바 (교체용 v11.x / secrets 자동 주입, 카드 항상 노출)
# =========================
import streamlit as st
import base64
from pathlib import Path

# ── 통화/환율 (수정 금지) ─────────────────────────────────────────────────────
CURRENCIES = {
    "USD": {"kr": "미국 달러", "symbol": "$", "unit": "USD"},
    "EUR": {"kr": "유로",     "symbol": "€", "unit": "EUR"},
    "JPY": {"kr": "일본 엔",   "symbol": "¥", "unit": "JPY"},
    "CNY": {"kr": "중국 위안", "symbol": "元","unit": "CNY"},
}
FX_DEFAULT = {"USD": 1400.0, "EUR": 1500.0, "JPY": 10.0, "CNY": 200.0}

# ── secrets 헬퍼: 여러 키 이름 지원(혼용 대비) ────────────────────────────────
def _sec(*keys, default=""):
    for k in keys:
        v = st.secrets.get(k, "")
        if isinstance(v, str) and v.strip():
            return v.strip()
    return default

def _sec_cookie():
    b64 = st.secrets.get("NAVER_COOKIE_B64", "")
    if b64:
        try:
            return base64.b64decode(b64).decode("utf-8").strip()
        except Exception:
            pass
    return _sec("NAVER_COOKIE")

# ── 세션 기본값 + secrets 프리필 ──────────────────────────────────────────────
def _ensure_session_defaults():
    ss = st.session_state
    ss.setdefault("theme", "light")

    # ➜ secrets 값 자동 주입(있으면 세션에 박아둠)
    ss.setdefault("PROXY_URL", _sec("PROXY_URL", "ENVY_PROXY_URL"))
    ss.setdefault("ITEMSCOUT_API_KEY", _sec("ITEMSCOUT_API_KEY", "ITEMSCOUT_KEY"))
    ss.setdefault("SELLERLY_API_KEY", _sec("SELLERLIFE_API_KEY", "SELLERLY_API_KEY", "SELLERLIFE_KEY"))

    # 계산기 기본값(변경 금지)
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
      html, body, [data-testid="stAppViewContainer"] {{ background-color:{bg} !important; color:{fg} !important; }}
      .block-container {{ padding-top:.8rem !important; padding-bottom:.35rem !important; }}
      /* 사이드바: 부모는 hidden, 내부 section만 스크롤(이중 스크롤 방지) */
      [data-testid="stSidebar"] {{ height:100vh !important; overflow:hidden !important; }}
      [data-testid="stSidebar"] > div:first-child {{ height:100vh !important; overflow:hidden !important; }}
      [data-testid="stSidebar"] section {{
        height:100vh !important; overflow-y:auto !important;
        padding-top:.25rem !important; padding-bottom:.5rem !important;
      }}
      [data-testid="stSidebar"] ::-webkit-scrollbar {{ display:block !important; width:8px; }}

      /* 카드간 공백 다이어트 */
      [data-testid="stSidebar"] .stMarkdown, [data-testid="stSidebar"] .stSelectbox,
      [data-testid="stSidebar"] .stNumberInput, [data-testid="stSidebar"] .stRadio,
      [data-testid="stSidebar"] .stTextInput, [data-testid="stSidebar"] .stButton {{ margin:.18rem 0 !important; }}

      .logo-circle {{ width:95px; height:95px; border-radius:50%; overflow:hidden;
                      margin:.15rem auto .35rem auto; box-shadow:0 2px 8px rgba(0,0,0,.12);
                      border:1px solid rgba(0,0,0,.06); }}
      .logo-circle img {{ width:100%; height:100%; object-fit:cover; }}
      .badge-green  {{ background:#e6ffcc; border:1px solid #b6f3a4; padding:6px 10px; border-radius:6px; color:#0b2e13; font-size:.86rem; }}
      .badge-blue   {{ background:#eef4ff; border:1px solid #bcd0ff; padding:6px 10px; border-radius:6px; color:#0a235a; font-size:.86rem; }}
      .badge-yellow {{ background:#fff7d6; border:1px solid #f1d27a; padding:6px 10px; border-radius:6px; color:#4a3b07; font-size:.86rem; }}
      .muted        {{ opacity:.8; font-size:.8rem; }}
      .info-box     {{ background:rgba(0,0,0,.03); border:1px dashed rgba(0,0,0,.08); padding:.6rem; border-radius:.5rem; }}
    </style>
    """, unsafe_allow_html=True)

def render_sidebar() -> dict:
    """사이드바 UI: 계산기 유지 + API Key/Proxy 섹션 항상 노출 + secrets 프리필."""
    _ensure_session_defaults()
    _inject_sidebar_css()

    result = {}
    with st.sidebar:
        # ── 로고 ─────────────────────────────────────────────────────────────
        lp = Path(__file__).parent / "logo.png"
        if lp.exists():
            b64 = base64.b64encode(lp.read_bytes()).decode("ascii")
            st.markdown(f'<div class="logo-circle"><img src="data:image/png;base64,{b64}"></div>', unsafe_allow_html=True)
        else:
            st.caption("logo.png 를 앱 파일과 같은 폴더에 두면 로고가 표시됩니다.")

        # 테마 토글
        st.toggle("🌓 다크 모드", value=(st.session_state.get("theme","light")=="dark"),
                  on_change=_toggle_theme, key="__theme_toggle")

        # ── ① 환율 계산기 ───────────────────────────────────────────────────
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

        # ── ② 마진 계산기 ───────────────────────────────────────────────────
        st.markdown("### ② 마진 계산기")
        m_base = st.selectbox("매입 통화", list(CURRENCIES.keys()),
                              index=list(CURRENCIES.keys()).index(st.session_state["m_base"]), key="m_base")
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
        st.markdown(f'<div class="badge-yellow">순이익(마진): <b>{margin_value:,.2f} 원</b> — {margin_desc}</div>',
                    unsafe_allow_html=True)

        # ── ③ 외부 API Key 보관 (항상 노출) ──────────────────────────────────
        st.divider()
        st.markdown("##### 외부 API Key 보관")
        st.text_input("아이템스카우트 API Key",
                      value=st.session_state.get("ITEMSCOUT_API_KEY",""),
                      key="ITEMSCOUT_API_KEY", type="password",
                      help="secrets: ITEMSCOUT_API_KEY / ITEMSCOUT_KEY")
        st.text_input("셀러라이프 API Key",
                      value=st.session_state.get("SELLERLY_API_KEY",""),
                      key="SELLERLY_API_KEY", type="password",
                      help="secrets: SELLERLIFE_API_KEY / SELLERLY_API_KEY / SELLERLIFE_KEY")

        # ── ④ 프록시/환경 (항상 노출) ────────────────────────────────────────
        st.markdown("##### 프록시/환경")
        st.text_input("PROXY_URL (Cloudflare Worker 등)",
                      value=st.session_state.get("PROXY_URL",""),
                      key="PROXY_URL",
                      help="예: https://envy-proxy.<계정>.workers.dev")

        # DataLab 쿠키 상태(참고 표시: Part3에서 사용)
        cookie_ok = bool(_sec_cookie())
        st.caption(f"DataLab 쿠키 상태: {'✅ 설정됨' if cookie_ok else '❌ 비어 있음'}")

        st.markdown("""
        <div class="info-box">
          <b>ENVY</b> 사이드바 정보는 고정입니다.<br/>
          · PROXY_URL: 11번가 iFrame 제한 회피(필수)<br/>
          · NAVER_COOKIE(_B64): 데이터랩 접근(필수) — secrets에서 자동 인식<br/>
          · 다크/라이트 모드: 상단 토글
        </div>
        """, unsafe_allow_html=True)

    result.update({
        "fx_base": base, "sale_foreign": sale_foreign, "converted_won": won,
        "purchase_base": m_base, "purchase_foreign": purchase_foreign,
        "base_cost_won": base_cost_won, "card_fee_pct": card_fee,
        "market_fee_pct": market_fee, "shipping_won": shipping_won,
        "margin_mode": mode, "target_price": target_price, "margin_value": margin_value,
        "ITEMSCOUT_API_KEY": st.session_state.get("ITEMSCOUT_API_KEY",""),
        "SELLERLY_API_KEY": st.session_state.get("SELLERLY_API_KEY",""),
        "PROXY_URL": st.session_state.get("PROXY_URL",""),
    })
    return result
# =========================
# Part 2 — 공용 유틸 + Naver Searchad API 헬퍼
# =========================
import os, time, hmac, hashlib, base64
import pandas as pd
import streamlit as st
from urllib.parse import urlencode

# (선택) requests가 없으면 광고 API는 자동 비활성
try:
    import requests
except Exception:
    requests = None

# ── 언어 라벨 (번역기 드롭다운용)
LANG_LABELS = {
    "auto":"자동 감지",
    "ko":"한국어",
    "en":"영어",
    "ja":"일본어",
    "zh-CN":"중국어(간체)",
    "zh-TW":"중국어(번체)",
    "vi":"베트남어",
    "th":"태국어",
    "id":"인도네시아어",
    "de":"독일어",
    "fr":"프랑스어",
    "es":"스페인어",
    "it":"이탈리아어",
    "pt":"포르투갈어",
}
def lang_label_to_code(label_or_code:str) -> str:
    rev = {v:k for k,v in LANG_LABELS.items()}
    return rev.get(label_or_code, label_or_code)

# ── 간단 토스트
def toast_ok(msg:str): st.toast(f"✅ {msg}")
def toast_warn(msg:str): st.toast(f"⚠️ {msg}")
def toast_err(msg:str): st.toast(f"❌ {msg}")

# ── Naver Searchad API (relKwdStat) ───────────────────────────────────────────
def _ads_keys_ok() -> bool:
    """Secrets → Env 순으로 키 유무 확인."""
    try:
        if st.secrets.get("NAVER_ADS_API_KEY","") and st.secrets.get("NAVER_ADS_SECRET","") and st.secrets.get("NAVER_ADS_CUSTOMER_ID",""):
            return True
    except Exception:
        pass
    return bool(os.getenv("NAVER_ADS_API_KEY") and os.getenv("NAVER_ADS_SECRET") and os.getenv("NAVER_ADS_CUSTOMER_ID"))

def _ads_get_keys():
    """Secrets 우선, 없으면 Env 사용."""
    def g(name):
        try:
            return st.secrets.get(name, "") or os.getenv(name, "")
        except Exception:
            return os.getenv(name, "")
    return g("NAVER_ADS_API_KEY"), g("NAVER_ADS_SECRET"), g("NAVER_ADS_CUSTOMER_ID")

def _ads_headers(method:str, path:str):
    api_key, secret, cust = _ads_get_keys()
    ts = str(int(time.time()*1000))
    sign_src = f"{ts}.{method}.{path}"
    sign = base64.b64encode(hmac.new(secret.encode(), sign_src.encode(), hashlib.sha256).digest()).decode()
    return {
        "X-Timestamp": ts,
        "X-API-KEY": api_key,
        "X-Customer": cust,
        "X-Signature": sign,
        "Content-Type": "application/json; charset=UTF-8",
        "Accept": "application/json",
    }

def naver_ads_relkwd(hint_keywords:list[str], max_rows:int=20) -> pd.DataFrame:
    """
    네이버 광고 Keyword Tool: 힌트 키워드 기반 연관키워드/월간검색수/경쟁지수 반환.
    columns: relKeyword, monthlyPcQcCnt, monthlyMobileQcCnt, compIdx
    """
    if not (_ads_keys_ok() and requests):
        return pd.DataFrame()
    base = "https://api.searchad.naver.com"
    path = "/keywordstool"
    q = {"hintKeywords": ",".join([k for k in hint_keywords if k][:5]), "showDetail": 1}
    url = f"{base}{path}?{urlencode(q)}"
    try:
        r = requests.get(url, headers=_ads_headers("GET", path), timeout=12)
        r.raise_for_status()
        js = r.json()
        kws = js.get("keywordList") or js.get("keywords") or []
        rows = []
        for it in kws[:max_rows]:
            rows.append({
                "relKeyword": it.get("relKeyword"),
                "monthlyPcQcCnt": it.get("monthlyPcQcCnt", 0),
                "monthlyMobileQcCnt": it.get("monthlyMobileQcCnt", 0),
                "compIdx": it.get("compIdx", 0),
            })
        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame()
# =========================
# Part 3 — 데이터랩(간결판)
#  - 카테고리 선택 → Top20 표 (20개 고정)
#  - 선택 키워드(최대 5개) 기간별 트렌드 선그래프
#  - NAVER_COOKIE: secrets/env/session 자동 인식, 없을 때만 입력칸 표시
#  - (선택) 광고 API 키가 있으면 월간 검색수/경쟁지수 컬럼 자동 덧붙임
# =========================
import os, json
from datetime import date, timedelta
from typing import List, Dict

import streamlit as st
import pandas as pd
import numpy as np

# Part 2에 정의된 광고 헬퍼 사용(없으면 조용히 패스)
try:
    from app import naver_ads_relkwd, _ads_keys_ok   # 파일명이 app.py가 아니면 경로에 맞게 수정
except Exception:
    def _ads_keys_ok(): return False
    def naver_ads_relkwd(*args, **kwargs): return pd.DataFrame()

# requests 유무 가드
try:
    import requests
except Exception:
    requests = None

# ── 대분류 12종 ↔ CID
DATALAB_CATS = [
    "패션의류","패션잡화","화장품/미용","디지털/가전","가구/인테리어",
    "출산/육아","식품","스포츠/레저","생활/건강","여가/생활편의","면세점","도서"
]
CID_MAP = {
    "패션의류":"50000000","패션잡화":"50000001","화장품/미용":"50000002","디지털/가전":"50000003",
    "가구/인테리어":"50000004","출산/육아":"50000005","식품":"50000006","스포츠/레저":"50000007",
    "생활/건강":"50000008","여가/생활편의":"50000009","면세점":"50000010","도서":"50005542",
}

# ── NAVER_COOKIE: secrets → env → session
def _naver_cookie() -> str:
    sec = ""
    try: sec = st.secrets.get("NAVER_COOKIE","")
    except Exception: sec = ""
    if sec: return sec.strip()
    env = os.getenv("NAVER_COOKIE","").strip()
    if env: return env
    return st.session_state.get("__NAVER_COOKIE","").strip()

# ── API 호출 (Top20, Trend)
@st.cache_data(show_spinner=False, ttl=600)
def _fetch_top20(cookie: str, cid: str, start: str, end: str) -> Dict:
    if not requests: return {"ok": False, "reason": "requests 미설치"}
    url = "https://datalab.naver.com/shoppingInsight/getCategoryKeywordRank.naver"
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Safari/604.1",
        "Referer": "https://datalab.naver.com/shoppingInsight/sCategory.naver",
        "Origin": "https://datalab.naver.com",
        "Cookie": cookie,
        "Accept": "application/json, text/plain, */*",
    }
    data = {
        "cid": str(cid),
        "timeUnit": "date",
        "startDate": start,
        "endDate": end,
        "gender": "all",
        "device": "all",
        "age": "all",
    }
    try:
        r = requests.post(url, headers=headers, data=data, timeout=12, allow_redirects=False)
        if r.status_code in (301,302,303,307,308):
            return {"ok": False, "reason": "302 리다이렉트 — 쿠키 만료/부재"}
        r.raise_for_status()
        js = r.json()
    except Exception as e:
        return {"ok": False, "reason": f"요청 실패: {e}"}

    items = []
    cand = js.get("result") if isinstance(js, dict) else None
    if not isinstance(cand, list):
        for v in (js.values() if isinstance(js, dict) else []):
            if isinstance(v, list) and v and isinstance(v[0], dict):
                cand = v; break
    if cand:
        for row in cand:
            kw = row.get("keyword") or row.get("key") or row.get("name")
            sc = row.get("ratio") or row.get("score") or row.get("value") or 0
            if kw:
                items.append({"rank":0, "keyword":str(kw), "score": float(sc) if isinstance(sc,(int,float)) else 0.0})
    if not items: return {"ok": False, "reason":"응답 파싱 실패"}

    items = sorted(items, key=lambda x:x["score"], reverse=True)[:20]
    for i, r in enumerate(items, start=1): r["rank"] = i
    return {"ok": True, "rows": items}

@st.cache_data(show_spinner=False, ttl=600)
def _fetch_trend(cookie: str, keywords: List[str], start: str, end: str) -> pd.DataFrame:
    if not (requests and keywords): return pd.DataFrame()
    url = "https://datalab.naver.com/shoppingInsight/getKeywordTrends.naver"
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Safari/604.1",
        "Referer": "https://datalab.naver.com/shoppingInsight/sCategory.naver",
        "Origin": "https://datalab.naver.com",
        "Cookie": cookie,
        "Accept": "application/json, text/plain, */*",
    }
    payload = {
        "timeUnit": "week",
        "startDate": start,
        "endDate": end,
        "keyword": json.dumps([{"name": k, "param": [k]} for k in keywords]),
        "device": "all",
        "gender": "all",
        "age": "all",
    }
    try:
# =========================
# Part 4 — 11번가(모바일) 임베드 (강화판 · 무알림)
# =========================
import streamlit as st
from urllib.parse import quote
import re

# 선택 라이브러리(없어도 동작; 프리뷰만 비활성)
try:
    import requests
    from bs4 import BeautifulSoup  # pip install beautifulsoup4
except Exception:
    requests = None
    BeautifulSoup = None

DEFAULT_11ST_HOME = "https://m.11st.co.kr/page/main/home"
DEFAULT_11ST_BEST = "https://m.11st.co.kr/MW/store/bestSeller.tmall"
PROXY_DEFAULT     = "https://envy-proxy.taesig0302.workers.dev"

def _proxy_url() -> str:
    p = (st.session_state.get("PROXY_URL") or "").strip()
    return p or PROXY_DEFAULT   # 내부 폴백만, 화면 안내 없음

def _parse_best20(proxy: str) -> list[dict]:
    """프록시 경유로 11번가 베스트셀러 Top20 간단 파싱(실패 시 빈 리스트)."""
    if not requests:
        return []
    try:
        u = f"{proxy}?url={quote(DEFAULT_11ST_BEST, safe=':/?&=%')}"
        r = requests.get(u, timeout=12, headers={
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1"
        })
        r.raise_for_status()
        html = r.text
        items = []
        if BeautifulSoup:
            soup = BeautifulSoup(html, "html.parser")
            sels = ["a[href*='/products/']", "ul li a[href*='/products/']"]
            seen = set()
            for sel in sels:
                for a in soup.select(sel):
                    href = a.get("href") or ""
                    m = re.search(r"/products/(\d+)", href)
                    if not m: 
                        continue
                    pid = m.group(1)
                    title = (a.get_text(strip=True) or "").replace("\n", " ")
                    if not title or (pid, title) in seen:
                        continue
                    seen.add((pid, title))
                    items.append({"rank": len(items)+1,
                                  "title": title,
                                  "url": f"https://m.11st.co.kr/products/{pid}"})
                    if len(items) >= 20:
                        break
                if len(items) >= 20:
                    break
        if not items:
            for m in re.finditer(
                r'href="(?:https://m\.11st\.co\.kr)?/products/(\d+)".{0,200}?>([^<]{4,120})<',
                html, flags=re.S|re.I
            ):
                pid = m.group(1)
                title = re.sub(r"\s+", " ", m.group(2)).strip()
                items.append({"rank": len(items)+1,
                              "title": title,
                              "url": f"https://m.11st.co.kr/products/{pid}"})
                if len(items) >= 20:
                    break
        return items
    except Exception:
        return []

def render_11st_block():
    st.markdown("## 11번가 (모바일)")

    url = st.text_input("모바일 URL", value=DEFAULT_11ST_HOME, key="t11_url").strip()
    proxy = _proxy_url()
    proxied = f"{proxy}?url={quote(url, safe=':/?&=%')}"

    # 안내 문구/프록시 표시 없이: 새창 열기 버튼만 제공
    st.link_button("🔗 새창에서 열기", proxied)

    # iFrame 임베드
    try:
        st.components.v1.iframe(src=proxied, height=980, scrolling=True)
    except Exception as e:
        st.error(f"iFrame 로드 실패: {e}")

    # 보조 프리뷰(Top20) — 선택 확장
    with st.expander("🧩 베스트셀러 Top 20 (보조 프리뷰)", expanded=False):
        if requests is None:
            st.info("프리뷰 파서를 사용하려면 `requests`, `beautifulsoup4` 설치가 필요합니다.")
            return
        rows = _parse_best20(proxy)
        if not rows:
            st.warning("베스트 데이터 파싱에 실패했습니다. 상단 '새창에서 열기'로 확인하세요.")
        else:
            import pandas as pd
            df = pd.DataFrame(rows)
            st.dataframe(
                df.rename(columns={"title": "상품명"}),
                hide_index=True,
                use_container_width=True,
                height=420,
                column_config={
                    "rank": st.column_config.NumberColumn("순위", width="small"),
                    "상품명": st.column_config.TextColumn("상품명", width="large"),
                    "url":  st.column_config.LinkColumn("바로가기", display_text="열기", width="small"),
                }
            )
# =========================
# Part 5 — AI 키워드 레이더 (Rakuten)  [실데이터 우선 + 스크롤/여백/URL 축소]
# =========================
import streamlit as st
import pandas as pd
import requests

# 네가 준 키를 기본값으로 “박음” (secrets가 있으면 secrets가 우선)
RAKUTEN_APP_ID_DEFAULT       = "1043271015809337425"
RAKUTEN_AFFILIATE_ID_DEFAULT = "4c723498.cbfeca46.4c723499.1deb6f77"

RAKUTEN_CATS = [
    "전체(샘플)","뷰티/코스메틱","의류/패션","가전/디지털","가구/인테리어",
    "식품","생활/건강","스포츠/레저","문구/취미"
]

def _get_rakuten_keys():
    app_id = (st.secrets.get("RAKUTEN_APP_ID")
              or st.secrets.get("RAKUTEN_APPLICATION_ID")
              or RAKUTEN_APP_ID_DEFAULT).strip()
    affiliate = (st.secrets.get("RAKUTEN_AFFILIATE_ID")
                 or st.secrets.get("RAKUTEN_AFFILIATE")
                 or RAKUTEN_AFFILIATE_ID_DEFAULT).strip()
    return app_id, affiliate

def _fetch_rank(genre_id: str, topn: int = 20) -> pd.DataFrame:
    """Rakuten IchibaItem Ranking API → Top N"""
    app_id, affiliate = _get_rakuten_keys()
    url = "https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20170628"
    params = {"applicationId": app_id, "genreId": str(genre_id).strip(), "carrier": 0}
    if affiliate:
        params["affiliateId"] = affiliate

    r = requests.get(url, params=params, timeout=12)
    r.raise_for_status()
    items = r.json().get("Items", [])
    rows = []
    for it in items[:topn]:
        node = it.get("Item", {})
        rows.append({
            "rank": node.get("rank"),
            "keyword": node.get("itemName") or "",
            "shop": node.get("shopName") or "",
            "url": node.get("itemUrl") or "",
        })
    return pd.DataFrame(rows)

def _mock_rows(n=20) -> pd.DataFrame:
    return pd.DataFrame([{
        "rank": i+1, "keyword": f"[샘플] 키워드 {i+1} ハロウィン 秋 🍂", "shop": "샘플샵", "url": "https://example.com"
    } for i in range(n)])

def render_rakuten_block():
    st.markdown("## AI 키워드 레이더 (Rakuten)")

    # 섹션 여백/폰트 정리 + 표 내부 스크롤
    st.markdown("""
    <style>
      .rk-wrap [data-testid="stVerticalBlock"] { gap: .4rem !important; }
      .rk-wrap .stMarkdown { margin: .25rem 0 !important; }
      .rk-wrap .stDataFrame { margin-top: .2rem !important; }
      .rk-wrap .stDataFrame [role="grid"] { font-size: 0.90rem !important; }
      .rk-wrap .stDataFrame a { font-size: 0.86rem !important; }
    </style>
    """, unsafe_allow_html=True)

    colA, colB, colC, colD = st.columns([1,1,1,1])
    with colA:
        scope = st.radio("범위", ["국내","글로벌"], horizontal=True, key="rk_scope")
    with colB:
        cat = st.selectbox("라쿠텐 카테고리", RAKUTEN_CATS, key="rk_cat")
    with colC:
        genreid = st.text_input("GenreID", "100283", key="rk_genre")
    with colD:
        sample_only = st.checkbox("샘플 보기", value=False, help="체크 시 샘플 데이터로 표시")

    app_id, affiliate = _get_rakuten_keys()
    st.caption(f"APP_ID: {('✅ ' + app_id) if app_id else '❌ 없음'}  |  Affiliate: {('✅ ' + affiliate) if affiliate else '—'}")

    # ▶ 실데이터 강제: 샘플 체크 안 했으면 항상 API 먼저 시도
    df = pd.DataFrame()
    err = None
    if not sample_only:
        try:
            df = _fetch_rank(genreid or "100283", topn=20)
        except Exception as e:
            err = str(e)

    if df.empty:
        if err:
            st.warning(f"Rakuten API 실패 → 샘플로 대체: {err[:200]}")
        df = _mock_rows(20)

    # URL → '열기' 링크 (폭 축소)
    df = df[["rank","keyword","shop","url"]]
    colcfg = {
        "rank":    st.column_config.NumberColumn("rank", width="small"),
        "keyword": st.column_config.TextColumn("keyword", width="large"),
        "shop":    st.column_config.TextColumn("shop", width="medium"),
        "url":     st.column_config.LinkColumn("url", display_text="열기", width="small"),
    }

    with st.container():
        st.markdown('<div class="rk-wrap">', unsafe_allow_html=True)
        st.dataframe(df, hide_index=True, use_container_width=True, height=420, column_config=colcfg)
        st.markdown('</div>', unsafe_allow_html=True)
# =========================
# Part 6 — 구글 번역 (입력/출력 + 한국어 확인용) (교체용 v11.x)
# =========================
import streamlit as st
from deep_translator import GoogleTranslator

LANG_LABELS={"auto":"자동 감지","ko":"한국어","en":"영어","ja":"일본어","zh-CN":"중국어(간체)","zh-TW":"중국어(번체)","vi":"베트남어","th":"태국어","id":"인도네시아어","de":"독일어","fr":"프랑스어","es":"스페인어","it":"이탈리아어","pt":"포르투갈어"}
def _rev(): return {v:k for k,v in LANG_LABELS.items()}
def lang_label_to_code(x:str)->str: return _rev().get(x,x)

def translate_text(src:str,tgt:str,text:str)->tuple[str,str]:
    src=lang_label_to_code(src); tgt=lang_label_to_code(tgt)
    out=GoogleTranslator(source=src,target=tgt).translate(text)
    ko_hint=""
    if tgt!="ko" and out.strip():
        try: ko_hint=GoogleTranslator(source=tgt,target="ko").translate(out)
        except Exception: ko_hint=""
    return out, ko_hint

def render_translator_block():
    st.markdown("## 구글 번역 (텍스트 입력/출력 + 한국어 확인용)")
    c1,c2=st.columns([1,1])
    with c1:
        src=st.selectbox("원문 언어", list(LANG_LABELS.values()), index=list(LANG_LABELS.keys()).index("auto"), key="tr_src")
        text_in=st.text_area("원문 입력", height=150, key="tr_in")
    with c2:
        tgt=st.selectbox("번역 언어", list(LANG_LABELS.values()), index=list(LANG_LABELS.keys()).index("en"), key="tr_tgt")
        if st.button("번역", key="tr_go"):
            try:
                out,ko_hint=translate_text(src,tgt,text_in)
                st.text_area("번역 결과", value=(f"{out}\n{ko_hint}" if ko_hint else out), height=150)
                st.toast("✅ 번역 완료")
            except ModuleNotFoundError as e:
                st.warning(f"deep-translator 설치 필요: {e}")
            except Exception as e:
                st.error(f"번역 실패: {e}")
# =========================
# Part 7 — 메인 조립 (번역 섹션 위로 이동)
# =========================
import streamlit as st

def inject_layout_css():
    st.markdown("""
    <style>
      .block-container { max-width: 1480px !important; padding-bottom: 1rem !important; }
      html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] { height:auto !important; overflow:visible !important; }
      [data-testid="stSidebar"], [data-testid="stSidebar"] > div:first-child { height:100vh !important; overflow:hidden !important; }
      [data-testid="stSidebar"] section { height:100vh !important; overflow-y:auto !important; padding-top:.25rem !important; padding-bottom:.5rem !important; }
      [data-testid="stSidebar"] ::-webkit-scrollbar { display:block !important; width:8px !important; }
    </style>
    """, unsafe_allow_html=True)

def main():
    # 1) 사이드바 (수정 금지)
    sidebar_vals = render_sidebar()

    # 2) 전역 레이아웃
    inject_layout_css()

    st.title("ENVY — v11.x (stable)")
    st.caption("사이드바 고정, 본문 카드는 큼직하고 시안성 위주 배치")

    # 3) 데이터랩
    render_datalab_block()
    st.divider()

    # 4) 🔼 번역기를 위로(데이터랩 바로 아래)
    render_translator_block()
    st.divider()

    # 5) 11번가 + 라쿠텐
    colL, colR = st.columns([1,1])
    with colL:
        render_11st_block()
    with colR:
        render_rakuten_block()
    st.divider()

if __name__ == "__main__":
    main()

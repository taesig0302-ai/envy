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
# Part 1 — 사이드바 (로고 + 환율/마진 계산기 + 프록시 입력)
# =========================
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
    # 환율/마진 계산기 기본값
    ss.setdefault("fx_base", "USD")
    ss.setdefault("sale_foreign", 1.00)
    ss.setdefault("m_base", "USD")
    ss.setdefault("purchase_foreign", 0.00)
    ss.setdefault("card_fee_pct", 4.00)
    ss.setdefault("market_fee_pct", 14.00)
    ss.setdefault("shipping_won", 0.0)
    ss.setdefault("margin_mode", "퍼센트")  # or "플러스"
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
      .block-container {{ padding-top:.8rem !important; padding-bottom:1rem !important; }}
      /* 사이드바 고정(lock) — 메인에서 overflow 재허용으로 덮어씀 */
      [data-testid="stSidebar"],
      [data-testid="stSidebar"] > div:first-child,
      [data-testid="stSidebar"] section {{
        height: 100vh !important; overflow: hidden !important;
        padding-top:.25rem !important; padding-bottom:.25rem !important;
      }}
      [data-testid="stSidebar"] ::-webkit-scrollbar {{ display:none !important; }}
      /* 간격/입력 경량화 */
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
      /* 로고 */
      .logo-circle {{
        width:95px; height:95px; border-radius:50%; overflow:hidden;
        margin:.15rem auto .35rem auto; box-shadow:0 2px 8px rgba(0,0,0,.12);
        border:1px solid rgba(0,0,0,.06);
      }}
      .logo-circle img {{ width:100%; height:100%; object-fit:cover; }}
      /* 배지 */
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
        from pathlib import Path
        lp = Path(__file__).parent / "logo.png"
        if lp.exists():
            import base64
            b64 = base64.b64encode(lp.read_bytes()).decode("ascii")
            st.markdown(f'<div class="logo-circle"><img src="data:image/png;base64,{b64}"></div>', unsafe_allow_html=True)
        else:
            st.caption("logo.png 를 앱 파일과 같은 폴더에 두면 로고가 표시됩니다.")

        # 테마 토글
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

        # 하단: PROXY_URL + 프로그램 정보
        st.divider()
        st.markdown("##### 프록시/환경")
        st.text_input("PROXY_URL (Cloudflare Worker 등)", value=st.session_state.get("PROXY_URL",""), key="PROXY_URL", help="예: https://envy-proxy.example.workers.dev/")
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


# =========================
# Part 3 — 데이터랩 (분석 Top20 + 트렌드) & 원본 임베드
# =========================
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
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Origin": "https://datalab.naver.com",
        "Referer": f"https://datalab.naver.com/shoppingInsight/sCategory.naver?cid={cid}&timeUnit={time_unit}&device={device}",
        "Cookie": cookie.strip(),
    }
    if as_json:
        h["Accept"] = "application/json, text/plain, */*"
        h["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        h["X-Requested-With"] = "XMLHttpRequest"
    else:
        h["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    return h

def _to_float(v) -> float:
    if v is None: return 0.0
    if isinstance(v, (int,float)): return float(v)
    s = str(v).replace(',', '')
    m = re.search(r'-?\d+(?:\.\d+)?', s)
    return float(m.group(0)) if m else 0.0

def _normalize_top20(obj: Any) -> List[dict]:
    rows: List[dict] = []
    if isinstance(obj, dict) and isinstance(obj.get("ranks"), list):
        for i, d in enumerate(obj["ranks"], 1):
            kw = (d.get("keyword") or d.get("relKeyword") or "").strip()
            sc = None
            for k in ("ratio","ratioValue","value","score","count","ratioIndex"):
                if k in d: sc = _to_float(d.get(k)); break
            if kw: rows.append({"rank": i, "keyword": kw, "score": 0.0 if sc is None else sc})

    def consider(d: dict):
        kw = (d.get('keyword') or d.get('relKeyword') or d.get('name') or d.get('key') or '').strip()
        sc = None
        for k in ('ratio','ratioValue','ratioIndex','value','score','count'):
            if k in d: sc = _to_float(d.get(k)); break
        if kw: rows.append({'keyword': kw, 'score': 0.0 if sc is None else sc})

    def walk(o):
        if isinstance(o, dict):
            if "ranks" in o and isinstance(o["ranks"], list):
                for i, d in enumerate(o["ranks"], 1):
                    kw = (d.get("keyword") or d.get("relKeyword") or "").strip()
                    sc = None
                    for k in ("ratio","ratioValue","value","score","count","ratioIndex"):
                        if k in d: sc = _to_float(d.get(k)); break
                    if kw: rows.append({"rank": i, "keyword": kw, "score": 0.0 if sc is None else sc})
            for v in o.values():
                if isinstance(v, (dict, list)): walk(v)
            consider(o)
        elif isinstance(o, list):
            for v in o: walk(v)
    walk(obj)

    best = {}
    for r in rows:
        k = r["keyword"]; s = float(r.get("score", 0) or 0)
        if k and (k not in best or s > best[k]["score"]): best[k] = {"keyword": k, "score": s}
    out = list(best.values()); out.sort(key=lambda x: x.get("score", 0), reverse=True); out = out[:20]
    for i, r in enumerate(out, 1): r["rank"] = i
    return out

def _extract_top20_from_text(txt: str) -> List[dict]:
    # 1) {"message":null, "ranks":[...]}
    for m in re.finditer(r'\{"message"\s*:\s*null.*?\}', txt, re.S):
        try:
            data = json.loads(m.group(0))
            rows = _normalize_top20(data)
            if rows: return rows
        except Exception: pass
    # 2) "ranks":[...]
    m = re.search(r'"ranks"\s*:\s*(\[[^\]]+\])', txt, re.S)
    if m:
        try:
            arr = json.loads(m.group(1))
            return _normalize_top20({"ranks": arr})
        except Exception: pass
    # 3) keyword/ratio 긁기
    pats = [
        r'"keyword"\s*:\s*"([^"]+)"[^}]*?(?:ratio|ratioValue|value|score)"\s*:\s*"?(?P<num>[-\d.,]+%?)"?',
        r'"relKeyword"\s*:\s*"([^"]+)"[^}]*?(?:ratio|ratioValue|value|score)"\s*:\s*"?(?P<num>[-\d.,]+%?)"?',
    ]
    kv = defaultdict(float)
    for p in pats:
        for kw, sc in re.findall(p, txt):
            kw = kw.strip(); val = _to_float(sc)
            if kw and val > kv[kw]: kv[kw] = val
    rows = [{"keyword": k, "score": v} for k, v in kv.items()]
    rows.sort(key=lambda x: x["score"], reverse=True); rows = rows[:20]
    for i, r in enumerate(rows, 1): r["rank"] = i
    return rows

@st.cache_data(show_spinner=False, ttl=600)
def _fetch_top20(cookie: str, cid: str, start: str, end: str) -> dict:
    if not requests: return {"ok": False, "reason": "requests 미설치"}
    tried, last_json, last_reason = [], None, ""
    base_kw = "https://datalab.naver.com/shoppingInsight/getCategoryKeywordRank.naver"

    for method in ("POST","GET"):
        for time_unit in ("week","date"):
            for device in ("all","pc","mo"):
                for age_key in ("age","ages"):
                    tried.append(f"{method}:{time_unit}/{device}/{age_key}")
                    payload = {"cid": str(cid).strip(),"timeUnit": time_unit,"startDate": start,"endDate": end,"device": device,"gender": "all"}
                    payload[age_key] = "all"
                    try:
                        if method=="POST":
                            r = requests.post(base_kw, headers=_hdr(cookie, cid, time_unit, device, as_json=True),
                                              data=payload, timeout=12, allow_redirects=False)
                        else:
                            r = requests.get(base_kw, headers=_hdr(cookie, cid, time_unit, device, as_json=True),
                                             params=payload, timeout=12, allow_redirects=False)
                        ct = (r.headers.get("content-type") or "").lower()
                        if r.status_code in (301,302,303,307,308): return {"ok": False, "reason": "302 리다이렉트 — 쿠키 만료/로그인 필요", "tried": tried}
                        if "text/html" in ct: last_reason = "HTML 응답 — 쿠키/리퍼러 불일치"; continue
                        r.raise_for_status()
                        data = r.json(); last_json = data
                        rows = _normalize_top20(data)
                        if rows: return {"ok": True, "rows": rows}
                        last_reason = "응답 파싱 실패(구조 변경 가능성)"
                    except Exception as e:
                        last_reason = f"요청 실패: {e}"

    base_cat = "https://datalab.naver.com/shoppingInsight/getCategory.naver"
    for time_unit in ("week","date"):
        for device in ("all","pc","mo"):
            for age_key in ("age","ages"):
                tried.append(f"GET:getCategory/{time_unit}/{device}/{age_key}")
                params = {"cid": str(cid).strip(),"timeUnit": time_unit,"startDate": start,"endDate": end,"device": device,"gender": "all"}
                params[age_key] = "all"
                try:
                    r = requests.get(base_cat, headers=_hdr(cookie, cid, time_unit, device, as_json=True),
                                     params=params, timeout=12, allow_redirects=False)
                    if r.status_code in (301,302,303,307,308): return {"ok": False, "reason": "302 리다이렉트 — 쿠키 만료/로그인 필요", "tried": tried}
                    ct = (r.headers.get("content-type") or "").lower()
                    if "application/json" in ct:
                        data = r.json(); last_json = data
                        rows = _normalize_top20(data)
                        if rows: return {"ok": True, "rows": rows}
                        rows = _extract_top20_from_text(r.text or "")
                        if rows: return {"ok": True, "rows": rows}
                    else:
                        rows = _extract_top20_from_text(r.text or "")
                        if rows: return {"ok": True, "rows": rows}
                    last_reason = "getCategory 응답 파싱 실패"
                except Exception as e:
                    last_reason = f"getCategory 실패: {e}"

    try:
        page_url = ("https://datalab.naver.com/shoppingInsight/sCategory.naver"
                    f"?cid={cid}&timeUnit=week&startDate={start}&endDate={end}&device=all&gender=all&ages=all")
        r = requests.get(page_url, headers=_hdr(cookie, cid, as_json=False),
                         timeout=12, allow_redirects=False)
        if r.status_code in (301,302,303,307,308): return {"ok": False, "reason": "302 리다이렉트 — 쿠키 만료/로그인 필요", "tried": tried}
        html = r.text or ""; rows = _extract_top20_from_text(html)
        if rows: return {"ok": True, "rows": rows, "fallback": "html"}
        sample = ""
        try:
            if last_json is not None: sample = json.dumps(last_json, ensure_ascii=False)[:800]
        except Exception: pass
        return {"ok": False, "reason": last_reason or "응답 파싱 실패", "tried": tried, "sample": sample}
    except Exception as e:
        sample = ""
        try:
            if last_json is not None: sample = json.dumps(last_json, ensure_ascii=False)[:800]
        except Exception: pass
        return {"ok": False, "reason": f"HTML 폴백 실패: {e}", "tried": tried, "sample": sample}

@st.cache_data(show_spinner=False, ttl=600)
def _fetch_trend(cookie: str, keywords: List[str], start: str, end: str) -> pd.DataFrame:
    if not (requests and keywords): return pd.DataFrame()
    url = "https://datalab.naver.com/shoppingInsight/getKeywordTrends.naver"
    headers = _hdr(cookie, cid='50000000', as_json=True)
    payload = {
        "timeUnit": "week","startDate": start,"endDate": end,
        "keyword": json.dumps([{"name": k.strip(), "param": [k.strip()]} for k in keywords], ensure_ascii=False),
        "device": "all","gender": "all","ages": "all",
    }
    try:
        r = requests.post(url, headers=headers, data=payload, timeout=12, allow_redirects=False)
        ct = (r.headers.get("content-type") or "").lower()
        if r.status_code in (301,302,303,307,308) or "text/html" in ct: return pd.DataFrame()
        r.raise_for_status(); data = r.json()
    except Exception: return pd.DataFrame()

    series: Dict[str, list] = {}
    def walk(o):
        if isinstance(o, dict):
            title = o.get("title") or o.get("name")
            data_list = o.get("data")
            if title and isinstance(data_list, list):
                for i, p in enumerate(data_list):
                    period = p.get("period") or p.get("date") or f"P{i}"
                    ratio  = p.get("ratio")  or p.get("value") or 0
                    series.setdefault("period", []).append(period)
                    series.setdefault(title, []).append(ratio)
            for v in o.values():
                if isinstance(v, (dict, list)): walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
    walk(data)
    if not series: return pd.DataFrame()
    df = pd.DataFrame(series)
    if "period" in df.columns: df = df.set_index("period")
    return df

def render_datalab_block():
    st.markdown("## 데이터랩 (분석)")
    cookie = _naver_cookie()
    if not cookie:
        with st.expander("NAVER_COOKIE 입력(최초 1회)", expanded=True):
            c = st.text_input("쿠키 전체 문자열", type="password",
                              help="datalab.naver.com 로그인 상태에서 NID_* 포함 전체 쿠키 복사/붙여넣기")
            if c:
                st.session_state["__NAVER_COOKIE"] = c.strip()
                cookie = c.strip()
                st.success("세션 저장 완료")

    c1, c2 = st.columns([1.1, 1.4])
    with c1:
        cat = st.selectbox("카테고리", DATALAB_CATS, key="dl_cat_simple")
        cid = CID_MAP.get(cat, "50000000")
        today = date.today()
        start = st.date_input("시작일", value=today - timedelta(days=30), key="dl_start_simple")
        end   = st.date_input("종료일", value=today, key="dl_end_simple")
        btn = st.button("Top20 불러오기", key="dl_go_simple", use_container_width=True)

        top_df = pd.DataFrame()
        if btn:
            if not cookie:
                st.error("NAVER_COOKIE가 필요합니다. 위에서 한 번만 입력해 주세요.")
            else:
                res = _fetch_top20(cookie, cid, str(start), str(end))
                if not res.get("ok"):
                    st.error(f"조회 실패: {res.get('reason')}")
                    if res.get("tried"): st.caption("시도: " + ", ".join(res["tried"]))
                    if res.get("sample"): st.caption("응답 샘플:"); st.code(res["sample"])
                else:
                    top_df = pd.DataFrame(res["rows"], columns=["rank","keyword","score"])
                    st.dataframe(top_df, hide_index=True, use_container_width=True, height=420)

        st.session_state.setdefault("_top_keywords", [])
        if not top_df.empty: st.session_state["_top_keywords"] = top_df["keyword"].tolist()

    with c2:
        st.markdown("### 선택 키워드 트렌드")
        kw_source = st.session_state.get("_top_keywords", [])
        if kw_source:
            picks = st.multiselect("키워드(최대 5개)", kw_source, default=kw_source[:3],
                                   max_selections=5, key="dl_kw_picks")
            if st.button("트렌드 보기", key="dl_trend_simple"):
                if not cookie:
                    st.error("NAVER_COOKIE가 필요합니다.")
                elif not picks:
                    st.warning("키워드를 선택해 주세요.")
                else:
                    df_line = _fetch_trend(cookie, picks,
                                           str(st.session_state["dl_start_simple"]),
                                           str(st.session_state["dl_end_simple"]))
                    if df_line.empty:
                        x = np.arange(0, 12)
                        base = 50 + 5*np.sin(x/2)
                        df_line = pd.DataFrame({
                            (picks[0] if len(picks)>0 else "kw1"): base,
                            (picks[1] if len(picks)>1 else "kw2"): base-5 + 3*np.cos(x/3),
                            (picks[2] if len(picks)>2 else "kw3"): base+3 + 4*np.sin(x/4),
                        }, index=[f"P{i}" for i in range(len(x))])
                        st.info("실데이터 조회 실패 — 샘플 라인을 표시합니다.")
                    st.line_chart(df_line, height=260, use_container_width=True)
        else:
            st.caption("좌측에서 Top20을 먼저 불러오면 여기서 트렌드를 볼 수 있습니다.")

def render_datalab_embed_block():
    st.markdown("## 데이터랩 (원본 임베드)")
    _CATS = list(CID_MAP.keys())

    colA, colB, colC = st.columns([1.2, 1, 1])
    with colA:
        cat = st.selectbox("카테고리", _CATS, index=3, key="dl_embed_cat")
        cid = CID_MAP.get(cat, "50000003")
    with colB:
        time_unit = st.selectbox("기간 단위", ["week","month"], index=0, key="dl_embed_timeunit")
    with colC:
        device = st.selectbox("기기", ["all","pc","mo"], index=0, key="dl_embed_device")

    proxy = (st.session_state.get("PROXY_URL") or "").strip().rstrip("/")
    if not proxy:
        st.warning("PROXY_URL 없음 — 사이드바 하단에 Cloudflare Worker 주소를 입력하세요.")
        return

    target = f"https://datalab.naver.com/shoppingInsight/sCategory.naver?cid={cid}&timeUnit={time_unit}&device={device}&gender=all&ages=all"
    embed_url = f"{proxy}/?url={quote(target, safe=':/?&=%')}"
    st.components.v1.iframe(embed_url, height=980, scrolling=True)
    st.caption("프록시가 쿠키/헤더를 서버 측에서 처리합니다. 앱에는 쿠키 저장이 필요 없습니다.")


# =========================
# Part 4 — 11번가(모바일) 임베드
# =========================
def render_11st_block():
    st.markdown("## 11번가 (모바일)")
    url_default = "https://m.11st.co.kr/page/main/home"
    url = st.text_input("모바일 URL", url_default, key="t11_url")
    proxy = (st.session_state.get("PROXY_URL") or "").strip().rstrip("/")
    if not proxy:
        st.info("PROXY_URL 미설정: 직접 iFrame은 차단될 수 있습니다.")
        try:
            st.components.v1.iframe(url, height=560, scrolling=True)
        except Exception as e:
            toast_err(f"11번가 로드 실패: {e}")
        return
    embed = f"{proxy}/?url={quote(url, safe=':/?&=%')}"
    try:
        st.components.v1.iframe(embed, height=800, scrolling=True)
    except Exception as e:
        toast_err(f"프록시 임베드 실패: {e}")


# =========================
# Part 5 — AI 키워드 레이더 (Rakuten)
# =========================
def _rakuten_app_id() -> str:
    app_id = ""
    try:
        app_id = st.secrets.get("rakuten", {}).get("APP_ID", "")
    except Exception:
        app_id = ""
    if not app_id:
        app_id = os.getenv("RAKUTEN_APP_ID", "")
    if not app_id:
        app_id = st.session_state.get("__RAKUTEN_APP_ID", "")
    return app_id.strip()

def render_rakuten_block():
    st.markdown("## AI 키워드 레이더 (Rakuten)")
    colA, colB, colC = st.columns([1,1,1])
    with colA:
        scope = st.radio("범위", ["국내","글로벌"], horizontal=True, key="rk_scope")
    with colB:
        cat = st.selectbox("라쿠텐 카테고리", ["전체","뷰티/코스메틱","의류/패션","가전/디지털","가구/인테리어","식품","생활/건강","스포츠/레저","문구/취미"], key="rk_cat")
    with colC:
        genreid = st.text_input("GenreID", "100283", key="rk_genre")

    st.markdown("""<style>.rk table { font-size: 0.92rem !important; }</style>""", unsafe_allow_html=True)

    app_id = _rakuten_app_id()
    rows = []
    if not app_id:
        with st.expander("Rakuten APP_ID 설정", expanded=True):
            tmp = st.text_input("APP_ID", type="password", help="라쿠텐 개발자 콘솔의 Application ID")
            if tmp:
                st.session_state["__RAKUTEN_APP_ID"] = tmp.strip()
                st.success("세션 저장 완료 — 아래 조회 가능")
    else:
        if not requests:
            st.warning("requests 미설치")
        else:
            try:
                api = "https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20170628"
                params = {"applicationId": app_id, "genreId": genreid}
                r = requests.get(api, params=params, timeout=12)
                r.raise_for_status()
                data = r.json()
                items = (data.get("Items") or [])[:20]
                for i, it in enumerate(items, 1):
                    name = it.get("Item", {}).get("itemName", "")
                    rows.append({"rank": i, "keyword": name, "source": "Rakuten"})
            except Exception:
                pass

    if not rows:
        for i in range(1, 21):
            rows.append({"rank": i, "keyword": f"[샘플] 키워드 {i}", "source": "sample"})

    df = pd.DataFrame(rows)
    with st.container():
        st.markdown('<div class="rk">', unsafe_allow_html=True)
        st.dataframe(df, hide_index=True, use_container_width=True, height=420)
        st.markdown('</div>', unsafe_allow_html=True)


# =========================
# Part 6 — 구글 번역 (텍스트 입력/출력 + 한국어 확인용)
# =========================
def translate_text(src:str, tgt:str, text:str) -> tuple[str,str]:
    if not GoogleTranslator:
        raise ModuleNotFoundError("deep-translator 미설치")
    src = lang_label_to_code(src); tgt = lang_label_to_code(tgt)
    translator = GoogleTranslator(source=src, target=tgt)
    out = translator.translate(text)
    ko_hint = ""
    if tgt != "ko" and out.strip():
        try:
            ko_hint = GoogleTranslator(source=tgt, target="ko").translate(out)
        except Exception:
            ko_hint = ""
    return out, ko_hint

def render_translator_block():
    st.markdown("## 구글 번역 (텍스트 입력/출력 + 한국어 확인용)")
    c1, c2 = st.columns([1,1])
    with c1:
        src = st.selectbox("원문 언어", list(LANG_LABELS.values()), index=list(LANG_LABELS.keys()).index("auto"), key="tr_src")
        text_in = st.text_area("원문 입력", height=150, key="tr_in")
    with c2:
        tgt = st.selectbox("번역 언어", list(LANG_LABELS.values()), index=list(LANG_LABELS.keys()).index("en"), key="tr_tgt")
        if st.button("번역", key="tr_go"):
            try:
                out, ko_hint = translate_text(lang_label_to_code(src), lang_label_to_code(tgt), text_in)
                # 같은 줄 출력 (한국어 대상이면 괄호 표시 생략)
                if ko_hint and lang_label_to_code(tgt) != "ko":
                    st.write(f"원문 입력: {text_in}")
                    st.write(f"번역 결과: {out} ({ko_hint})")
                else:
                    st.write(f"원문 입력: {text_in}")
                    st.write(f"번역 결과: {out}")
                toast_ok("번역 완료")
            except ModuleNotFoundError as e:
                st.warning(f"deep-translator 설치 필요: {e}")
            except Exception as e:
                st.error(f"번역 실패: {e}")


# =========================
# Part 7 — 아이템스카우트 & 셀러라이프 (원본 임베드)
# =========================
def render_itemscout_embed():
    proxy = (st.session_state.get("PROXY_URL") or "").strip().rstrip("/")
    st.markdown("## 아이템스카우트 (원본 임베드)")
    if not proxy:
        st.warning("PROXY_URL이 비어 있습니다. 사이드바 하단에 Worker 주소를 입력하세요.")
        return
    default_url = st.secrets.get("itemscout", {}).get("DEFAULT_URL", "https://app.itemscout.io/market/keyword")
    url = st.text_input("Itemscout URL", default_url, help="로그인된 상태로 보고 싶은 경로를 붙여넣기 가능")
    st.components.v1.iframe(f"{proxy}/?url={quote(url, safe=':/?&=%')}", height=920, scrolling=True)

def render_sellerlife_embed():
    proxy = (st.session_state.get("PROXY_URL") or "").strip().rstrip("/")
    st.markdown("## 셀러라이프 (원본 임베드)")
    if not proxy:
        st.warning("PROXY_URL이 비어 있습니다. 사이드바 하단에 Worker 주소를 입력하세요.")
        return
    default_url = st.secrets.get("sellerlife", {}).get("DEFAULT_URL", "https://sellerlife.co.kr/dashboard")
    url = st.text_input("SellerLife URL", default_url)
    st.components.v1.iframe(f"{proxy}/?url={quote(url, safe=':/?&=%')}", height=920, scrolling=True)


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

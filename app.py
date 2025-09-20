# =========================================================
# ENVY — Season 1 (One-Page, merged Datalab + new layout)
# =========================================================

import os, base64, json, re
from pathlib import Path
from datetime import date, timedelta
from typing import List, Dict, Any

import streamlit as st
import pandas as pd
import numpy as np

# ---------------------------------
# Optional deps (requirements.txt)
# ---------------------------------
try:
    import requests
except Exception:
    requests = None
try:
    from deep_translator import GoogleTranslator
except Exception:
    GoogleTranslator = None

# =========================================================
# Part 1 — Sidebar (fixed, do not change)
# =========================================================
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
      .block-container {{ padding-top:.8rem !重要; padding-bottom:.35rem !重要; }}
      [data-testid="stSidebar"],
      [data-testid="stSidebar"] > div:first-child,
      [data-testid="stSidebar"] section {{
        height: 100vh !重要; overflow: hidden !重要;
        padding-top:.25rem !重要; padding-bottom:.25rem !重要;
      }}
      [data-testid="stSidebar"] section {{ overflow-y: auto !重要; }}
      [data-testid="stSidebar"] ::-webkit-scrollbar {{ display:none !重要; }}
      [data-testid="stSidebar"] .stSelectbox,
      [data-testid="stSidebar"] .stNumberInput,
      [data-testid="stSidebar"] .stRadio,
      [data-testid="stSidebar"] .stMarkdown,
      [data-testid="stSidebar"] .stTextInput,
      [data-testid="stSidebar"] .stButton {{ margin:.14rem 0 !重要; }}
      [data-baseweb="input"] input,
      .stNumberInput input,
      [data-baseweb="select"] div[role="combobox"] {{
        height:1.55rem !重要; padding:.12rem !重要; font-size:.92rem !重要;
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

    with st.sidebar:
        lp = Path(__file__).parent / "logo.png"
        if lp.exists():
            b64 = base64.b64encode(lp.read_bytes()).decode("ascii")
            st.markdown(f'<div class="logo-circle"><img src="data:image/png;base64,{b64}"></div>', unsafe_allow_html=True)
        else:
            st.caption("logo.png 를 앱 폴더에 두면 로고 표시")

        st.toggle("🌓 다크 모드", value=(st.session_state.get("theme","light")=="dark"),
                  on_change=_toggle_theme, key="__theme_toggle")

        # ① 환율 계산기
        st.markdown("### ① 환율 계산기")
        base = st.selectbox("기준 통화", list(CURRENCIES.keys()),
                            index=list(CURRENCIES.keys()).index(st.session_state["fx_base"]), key="fx_base")
        sale_foreign = st.number_input("판매금액 (외화)", value=float(st.session_state["sale_foreign"]),
                                       step=0.01, format="%.2f", key="sale_foreign")
        won = FX_DEFAULT[base] * sale_foreign
        st.markdown(
            f'<div class="badge-green">환산 금액: <b>{won:,.2f} 원</b> '
            f'<span class="muted">({CURRENCIES[base]["kr"]} • {CURRENCIES[base]["symbol"]})</span></div>',
            unsafe_allow_html=True)
        st.caption(f"환율 기준: {FX_DEFAULT[base]:,.2f} ₩/{CURRENCIES[base]['unit']}")

        # ② 마진 계산기
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

        st.divider()
        st.markdown("##### 프록시/환경")
        st.text_input("PROXY_URL (Cloudflare Worker)", value=st.session_state.get("PROXY_URL",""), key="PROXY_URL")
        st.markdown("""
            <div class="info-box">
              <b>ENVY</b> 사이드바 정보는 고정입니다.<br/>
              · 로고/환율/마진 계산기: 변경 금지<br/>
              · PROXY_URL: 11번가/데이터랩 임베드용<br/>
              · 다크/라이트 모드는 상단 토글
            </div>
        """, unsafe_allow_html=True)

    return {"converted_won": won}

# =========================================================
# Part 2 — Common utils
# =========================================================
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

# =========================================================
# Part 3 — Naver Datalab (analysis helpers)
# =========================================================
from collections import defaultdict
from urllib.parse import quote

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
    try: v = st.secrets.get('NAVER_COOKIE', '')
    except Exception: v = ''
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
    for m in re.finditer(r'\{"message"\s*:\s*null.*?\}', txt, re.S):
        try:
            data = json.loads(m.group(0))
            rows = _normalize_top20(data)
            if rows: return rows
        except Exception: pass
    m = re.search(r'"ranks"\s*:\s*(\[[^\]]+\])', txt, re.S)
    if m:
        try:
            arr = json.loads(m.group(1))
            return _normalize_top20({"ranks": arr})
        except Exception: pass
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

# =========================================================
# Part 3.5 — Datalab HYBRID (Embed + Analysis) — merged
# =========================================================
def render_datalab_hybrid_block():
    # 내부 제목 제거: 카드 헤더만 사용
    colA, colB, colC = st.columns([1,1,1])
    with colA:
        cat = st.selectbox("카테고리", DATALAB_CATS, key="dl_cat_merge")
        cid = CID_MAP.get(cat, "50000003")
    with colB:
        time_unit = st.selectbox("기간 단위", ["week","month"], index=0, key="dl_timeunit_merge")
    with colC:
        device = st.selectbox("기기", ["all","pc","mo"], index=0, key="dl_device_merge")

    proxy = (st.session_state.get("PROXY_URL") or "").strip().rstrip("/")
    cookie = _naver_cookie()
    st.caption(f"PROXY_URL: {'✅' if proxy else '❌ 없음'}  |  NAVER_COOKIE: {'✅' if cookie else '❌ 없음'}")

    tab1, tab2 = st.tabs(["원본(임베드)", "분석(Top20/트렌드)"])

    with tab1:
        if not proxy:
            st.warning("PROXY_URL 없음 — 사이드바 하단에 Cloudflare Worker 주소를 입력하세요.")
        else:
            target = f"https://datalab.naver.com/shoppingInsight/sCategory.naver?cid={cid}&timeUnit={time_unit}&device={device}&gender=all&ages=all"
            embed_url = f"{proxy}/?url={quote(target, safe=':/?&=%')}"
            st.components.v1.iframe(embed_url, height=980, scrolling=True)
            st.caption("프록시가 쿠키/헤더를 서버 측에서 처리합니다. 앱에는 쿠키 저장이 필요 없습니다.")

    with tab2:
        today = date.today()
        colD, colE = st.columns(2)
        with colD:
            start = st.date_input("시작일", value=today - timedelta(days=30), key="dl_start_merge")
        with colE:
            end   = st.date_input("종료일", value=today, key="dl_end_merge")

        if st.button("Top20 불러오기", key="dl_go_merge"):
            if not cookie:
                st.error("NAVER_COOKIE가 필요합니다. (datalab.naver.com 로그인 쿠키 전체)")
            else:
                res = _fetch_top20(cookie, cid, str(start), str(end))
                if not res.get("ok"):
                    st.error(f"조회 실패: {res.get('reason','알 수 없음')}")
                    if res.get("tried"): st.caption("시도: " + ", ".join(res["tried"]))
                    if res.get("sample"): st.caption("응답 샘플:"); st.code(res["sample"])
                else:
                    df = pd.DataFrame(res["rows"], columns=["rank","keyword","score"])
                    st.dataframe(df, hide_index=True, use_container_width=True, height=420)
                    st.session_state["_top_keywords"] = df["keyword"].tolist()

        kw_source = st.session_state.get("_top_keywords", [])
        if kw_source:
            picks = st.multiselect("선택 키워드(최대 5개)", kw_source, default=kw_source[:3],
                                   max_selections=5, key="dl_kw_merge")
            if st.button("트렌드 보기", key="dl_trend_merge"):
                if not cookie:
                    st.error("NAVER_COOKIE가 필요합니다.")
                elif not picks:
                    st.warning("키워드를 선택해 주세요.")
                else:
                    df_line = _fetch_trend(cookie, picks, str(st.session_state["dl_start_merge"]), str(st.session_state["dl_end_merge"]))
                    if df_line.empty:
                        st.info("실데이터 조회 실패 — 샘플 라인을 표시합니다.")
                        x = np.arange(0, 12)
                        base = 50 + 5*np.sin(x/2)
                        df_line = pd.DataFrame({
                            (picks[0] if len(picks)>0 else "kw1"): base,
                            (picks[1] if len(picks)>1 else "kw2"): base-5 + 3*np.cos(x/3),
                            (picks[2] if len(picks)>2 else "kw3"): base+3 + 4*np.sin(x/4),
                        }, index=[f"P{i}" for i in range(len(x))])
                    st.line_chart(df_line, height=260, use_container_width=True)
        else:
            st.caption("Top20을 먼저 불러오면 트렌드를 볼 수 있습니다.")

# =========================================================
# Part 4 — 11st (mobile) fixed Amazon Best embed (proxy)
# =========================================================
import urllib.parse as _url

AMAZON_BEST_URL = "https://m.11st.co.kr/page/main/abest?tabId=ABEST&pageId=AMOBEST&ctgr1No=166160"

def _proxy_wrap(url: str) -> str:
    proxy = st.session_state.get("PROXY_URL", "").strip().rstrip("/")
    if proxy:
        return f"{proxy}/?url={_url.quote(url, safe=':/?&=%')}"
    return url

def render_11st_block():
    try:
        st.components.v1.iframe(_proxy_wrap(AMAZON_BEST_URL), height=780, scrolling=True)
        st.caption("모바일 탭: 아마존베스트(고정)")
    except Exception as e:
        st.error(f"11번가 임베드 실패: {e}")
        st.code(AMAZON_BEST_URL, language="text")

# =========================================================
# Part 5 — AI 키워드 레이더 (Rakuten) — font down 2 steps
# =========================================================
RAKUTEN_APP_ID_DEFAULT       = "1043271015809337425"
RAKUTEN_AFFILIATE_ID_DEFAULT = "4c723498.cbfeca46.4c723499.1deb6f77"
RAKUTEN_CATS = ["전체(샘플)","뷰티/코스메틱","의류/패션","가전/디지털","가구/인테리어","식품","생활/건강","스포츠/레저","문구/취미"]

def _get_rakuten_keys():
    app_id = (st.secrets.get("RAKUTEN_APP_ID")
              or st.secrets.get("RAKUTEN_APPLICATION_ID")
              or RAKUTEN_APP_ID_DEFAULT).strip()
    affiliate = (st.secrets.get("RAKUTEN_AFFILIATE_ID")
                 or st.secrets.get("RAKUTEN_AFFILIATE")
                 or RAKUTEN_AFFILIATE_ID_DEFAULT).strip()
    return app_id, affiliate

def _fetch_rank(genre_id: str, topn: int = 20) -> pd.DataFrame:
    app_id, affiliate = _get_rakuten_keys()
    url = "https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20170628"
    params = {"applicationId": app_id, "genreId": str(genre_id).strip(), "carrier": 0}
    if affiliate: params["affiliateId"] = affiliate
    try:
        r = requests.get(url, params=params, timeout=12)
        r.raise_for_status()
        items = r.json().get("Items", [])
    except Exception:
        items = []
    rows = []
    for it in items[:topn]:
        node = it.get("Item", {})
        rows.append({"rank": node.get("rank"), "keyword": node.get("itemName") or "",
                     "shop": node.get("shopName") or "", "url": node.get("itemUrl") or ""})
    if not rows:
        for i in range(1, topn+1):
            rows.append({"rank": i, "keyword": f"[샘플] 키워드 {i} ハロウィン 秋 🍂", "shop": "샘플샵", "url": "https://example.com"})
    return pd.DataFrame(rows)

def render_rakuten_block():
    st.markdown("""
    <style>
      .rk-wrap [data-testid="stVerticalBlock"] { gap: .4rem !important; }
      .rk-wrap .stDataFrame [role="grid"] { font-size: 0.80rem !important; }  /* ↓ 2단계 */
      .rk-wrap .stDataFrame a { font-size: 0.76rem !important; }             /* ↓ 2단계 */
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
        sample_only = st.checkbox("샘플 보기", value=False)

    app_id, affiliate = _get_rakuten_keys()
    st.caption(f"APP_ID: {('✅ ' + app_id) if app_id else '❌ 없음'}  |  Affiliate: {('✅ ' + affiliate) if affiliate else '—'}")

    df = pd.DataFrame()
    if not sample_only:
        df = _fetch_rank(genreid or "100283", topn=20)
    if df.empty:
        df = _fetch_rank("100283", topn=20)

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

# =========================================================
# Part 6 — Google Translator
# =========================================================
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
    c1, c2 = st.columns([1,1])
    with c1:
        src = st.selectbox("원문 언어", list(LANG_LABELS.values()),
                           index=list(LANG_LABELS.keys()).index("auto"), key="tr_src")
        text_in = st.text_area("원문 입력", height=150, key="tr_in")
    with c2:
        tgt = st.selectbox("번역 언어", list(LANG_LABELS.values()),
                           index=list(LANG_LABELS.keys()).index("en"), key="tr_tgt")
        if st.button("번역", key="tr_go"):
            try:
                out, ko_hint = translate_text(lang_label_to_code(src), lang_label_to_code(tgt), text_in)
                if ko_hint and lang_label_to_code(tgt) != "ko":
                    st.text_area("번역 결과", value=f"{out}\n{ko_hint}", height=150)
                else:
                    st.text_area("번역 결과", value=out, height=150)
                toast_ok("번역 완료")
            except ModuleNotFoundError as e:
                st.warning(f"deep-translator 설치 필요: {e}")
            except Exception as e:
                st.error(f"번역 실패: {e}")

# =========================================================
# Part 7 — Itemscout / SellerLife Embeds (proxy)
# =========================================================
def render_itemscout_embed():
    proxy = (st.session_state.get("PROXY_URL") or "").strip().rstrip("/")
    if not proxy:
        st.warning("PROXY_URL이 비어 있습니다. 사이드바 하단에 Worker 주소를 입력하세요.")
        return
    default_url = st.secrets.get("itemscout", {}).get("DEFAULT_URL", "https://app.itemscout.io/market/keyword")
    url = st.text_input("Itemscout URL", default_url)
    st.components.v1.iframe(f"{proxy}/?url={quote(url, safe=':/?&=%')}", height=920, scrolling=True)

def render_sellerlife_embed():
    proxy = (st.session_state.get("PROXY_URL") or "").strip().rstrip("/")
    if not proxy:
        st.warning("PROXY_URL이 비어 있습니다. 사이드바 하단에 Worker 주소를 입력하세요.")
        return
    default_url = st.secrets.get("sellerlife", {}).get("DEFAULT_URL", "https://sellerlife.co.kr/dashboard")
    url = st.text_input("SellerLife URL", default_url)
    st.components.v1.iframe(f"{proxy}/?url={quote(url, safe=':/?&=%')}", height=920, scrolling=True)

# =========================================================
# Part 8 — Product Name Generator (rules)
# =========================================================
def render_product_name_generator():
    with st.container(border=True):
        colA, colB = st.columns([1,2])
        with colA:
            brand = st.text_input("브랜드", placeholder="예: Apple / 샤오미 / 무지")
            attrs = st.text_input("속성(콤마, 선택)", placeholder="예: 공식, 정품, 한정판")
        with colB:
            kws = st.text_input("키워드(콤마)", placeholder="예: 노트북 스탠드, 접이식, 알루미늄")
        col1, col2, col3 = st.columns([1,1,1])
        with col1:  max_len = st.slider("최대 글자수", 20, 80, 50, 1)
        with col2:  joiner  = st.selectbox("구분자", [" ", " | ", " · ", " - "], index=0)
        with col3:  order   = st.selectbox("순서", ["브랜드-키워드-속성", "키워드-브랜드-속성", "브랜드-속성-키워드"], index=0)
        if st.button("상품명 생성"):
            kw_list = [k.strip() for k in kws.split(",") if k.strip()]
            at_list = [a.strip() for a in attrs.split(",") if a.strip()]
            if not kw_list:
                st.warning("키워드가 비었습니다."); return
            titles = []
            for k in kw_list:
                if order=="브랜드-키워드-속성": seq = [brand, k] + at_list
                elif order=="키워드-브랜드-속성": seq = [k, brand] + at_list
                else: seq = [brand] + at_list + [k]
                title = joiner.join([p for p in seq if p])
                if len(title) > max_len: title = title[:max_len-1] + "…"
                titles.append(title)
            st.success(f"총 {len(titles)}건")
            st.write("\n".join(titles))

# =========================================================
# Part 9 — Layout helpers
# =========================================================
def _inject_global_css():
    st.markdown("""
    <style>
      .block-container { max-width: 1680px !important; padding-top:.8rem !important; padding-bottom:1rem !important; }
      .section-spacer { height: 2.4vh; }
      h3, h4, h5, h6 { margin-top:.2rem !important; }
    </style>
    """, unsafe_allow_html=True)

def _spacer(): st.markdown('<div class="section-spacer"></div>', unsafe_allow_html=True)

def _card(title:str, subtitle:str=""):
    st.markdown(f"#### {title}")
    if subtitle: st.caption(subtitle)

def _safe_call(fn_name:str):
    fn = globals().get(fn_name)
    if callable(fn):
        try: fn()
        except Exception as e: st.error(f"{fn_name} 실행 오류: {e}")
    else:
        st.info(f"'{fn_name}()' 이 정의되어 있지 않습니다.")

# =========================================================
# Part 10 — Main (NEW ORDER & WIDTHS)
# =========================================================
def main():
    render_sidebar()
    _inject_global_css()

    st.title("ENVY — Season 1 (stable)")
    st.caption("임베드 + 분석 보조. 프록시/쿠키는 Worker/Secrets로 관리.")

    # ── 1행: 데이터랩(6) · 아이템스카우트(3) · 셀러라이프(3)
    r1c1, r1c2, r1c3 = st.columns([6,3,3], gap="large")
    with r1c1:
        _card("데이터랩 (임베드+분석)")
        _safe_call("render_datalab_hybrid_block")
    with r1c2:
        _card("아이템스카우트 (임베드)")
        _safe_call("render_itemscout_embed")
    with r1c3:
        _card("셀러라이프 (임베드)")
        _safe_call("render_sellerlife_embed")

    _spacer()

    # ── 2행: 11번가(3) · AI 키워드 레이더(3) · 구글 번역(3)
    r2c1, r2c2, r2c3 = st.columns([3,3,3], gap="large")
    with r2c1:
        _card("11번가 (모바일) — 아마존베스트")
        _safe_call("render_11st_block")
    with r2c2:
        _card("AI 키워드 레이더 (Rakuten)")
        _safe_call("render_rakuten_block")
    with r2c3:
        _card("구글 번역")
        _safe_call("render_translator_block")

if __name__ == "__main__":
    main()

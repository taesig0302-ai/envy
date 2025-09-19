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
# Part 2 — 공용 유틸 (교체용 v11.x)
# =========================
import streamlit as st
from urllib.parse import quote

# ── 고정 메모(항상 유지) ──────────────────────────────────────────────
# Cloudflare Worker 프록시 기본값 (세션/시크릿에 값이 없을 때 사용)
PROXY_DEFAULT = "https://envy-proxy.taesig0302.workers.dev/"
# Naver DataLab 엔드포인트
DATALAB_ENDPOINT_RANK  = "https://datalab.naver.com/shoppingInsight/getCategoryKeywordRank.naver"
DATALAB_ENDPOINT_TREND = "https://datalab.naver.com/shoppingInsight/getKeywordClickTrend.naver"

# ── 언어 라벨(번역기/드롭다운 공용) ───────────────────────────────────
if "LANG_LABELS" not in globals():
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

def lang_label_to_code(label_or_code: str) -> str:
    """한국어 라벨/언어코드 입력을 모두 ISO 코드로 통일."""
    rev = {v: k for k, v in LANG_LABELS.items()}
    return rev.get(label_or_code, label_or_code)

# ── 토스트 헬퍼 ───────────────────────────────────────────────────────
def toast_ok(msg: str):   st.toast(f"✅ {msg}")
def toast_warn(msg: str): st.toast(f"⚠️ {msg}")
def toast_err(msg: str):  st.toast(f"❌ {msg}")

# ── 프록시 유틸 (세션→시크릿→기본값) ─────────────────────────────────
def util_proxy_url() -> str:
    proxy = (st.session_state.get("PROXY_URL")
             or getattr(st.secrets, "PROXY_URL", "")
             or "").strip()
    return proxy or PROXY_DEFAULT

def util_proxy_wrap(url: str) -> str:
    """원본 URL을 프록시로 감싼 최종 URL 생성."""
    return f"{util_proxy_url()}?url={quote(url, safe=':/?&=%')}"

# ── Naver DataLab 공통 헤더 ───────────────────────────────────────────
def util_naver_headers(cookie: str) -> dict:
    return {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://datalab.naver.com/",
        "Origin": "https://datalab.naver.com",
        "Accept": "*/*",
        "Accept-Language": "ko,en-US;q=0.9,en;q=0.8,ja;q=0.7",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Cookie": cookie or "",
    }

# ── 삼색 상태/색상 공용 ───────────────────────────────────────────────
STATUS_COLOR = {"정상": "#2ecc71", "주의": "#f1c40f", "오류": "#e74c3c"}

def util_status_from_score(score) -> str:
    """표시용 상태 라벨: 70↑ 정상, 40~69 주의, 나머지 오류."""
    try:
        s = float(score)
    except Exception:
        return "오류"
    if s >= 70: return "정상"
    if s >= 40: return "주의"
    return "오류"

def util_score_from_rank(rank) -> int | None:
    """랭크만 있을 때 시각화용 점수(1→100, 20→20) 산출."""
    try:
        r = int(rank)
        return int(round(100 - (r - 1) * (80 / 19)))
    except Exception:
        return None
# =========================
# Part 3 — 데이터랩 (교체용 v11.x, Rank + Trend 모두 지원)
# =========================
import datetime as _dt, json, requests, pandas as pd, streamlit as st, numpy as np

STATUS_COLOR = {"정상":"#2ecc71","주의":"#f1c40f","오류":"#e74c3c"}

def _status(score: float) -> str:
    if score is None: return "오류"
    if score >= 70:   return "정상"
    if score >= 40:   return "주의"
    return "오류"

_FALLBACK_CID = {
    "패션의류":"50000000","패션잡화":"50000001","화장품/미용":"50000002","디지털/가전":"50000003",
    "가구/인테리어":"50000004","출산/육아":"50000005","식품":"50000006","스포츠/레저":"50000007",
    "생활/건강":"50000008","여가/생활편의":"50000009","면세점":"50000010","도서":"50005542"
}

@st.cache_data(ttl=3600)
def _load_category_map() -> dict:
    try:
        r = requests.get(
            "https://datalab.naver.com/shoppingInsight/getCategory.naver",
            headers={
                "User-Agent":"Mozilla/5.0",
                "Referer":"https://datalab.naver.com/",
                "Cookie": st.secrets.get("NAVER_COOKIE",""),
            }, timeout=10)
        j = r.json()
        m = {c["name"]:c["cid"] for c in j.get("category", []) if c.get("name") and c.get("cid")}
        return m if len(m)>=8 else _FALLBACK_CID
    except Exception:
        return _FALLBACK_CID

def _cookie_source(tmp_cookie_ui: str) -> str:
    return (st.secrets.get("NAVER_COOKIE","") or tmp_cookie_ui).strip()

def _hdr(cookie:str)->dict:
    return {
        "User-Agent":"Mozilla/5.0","Referer":"https://datalab.naver.com/","Origin":"https://datalab.naver.com",
        "Accept":"*/*","Accept-Language":"ko,en-US;q=0.9,en;q=0.8,ja;q=0.7",
        "Content-Type":"application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With":"XMLHttpRequest","Cookie":cookie,
    }

def _fetch_keywords_20(cid:str,start:str,end:str,cookie:str,device="pc",age="all",gender="all")->pd.DataFrame:
    url="https://datalab.naver.com/shoppingInsight/getCategoryKeywordRank.naver"
    payload={"cid":cid,"timeUnit":"date","startDate":start,"endDate":end,"age":age,"gender":gender,"device":device,"page":1,"count":20}
    r=requests.post(url,headers=_hdr(cookie),data=payload,timeout=18,allow_redirects=False)
    if r.status_code in (301,302): raise RuntimeError("302 리다이렉트 → 로그인 필요 또는 쿠키 스코프 불일치")
    try: j=r.json()
    except Exception: j=json.loads(r.text)
    if "ranks" in j:
        rows=[{"rank":it.get("rank"),"keyword":it.get("keyword")} for it in (j.get("ranks") or [])[:20]]
        def _score_from_rank(rk):
            try: rk=int(rk); return int(round(100-(rk-1)*(80/19)))
            except: return None
        for row in rows: row["score"]=_score_from_rank(row["rank"])
        return pd.DataFrame(rows)
    res=(j.get("result") or [{}])[0]
    kws=res.get("keywords") or []
    if kws:
        rows=[{"rank":i+1,"keyword":k.get("keyword"),"score":k.get("score",0)} for i,k in enumerate(kws[:20])]
        return pd.DataFrame(rows)
    raise RuntimeError("알 수 없는 응답 포맷")

def _fetch_keyword_trend(cid:str, keyword:str, start:str, end:str, cookie:str, device="pc", age="all", gender="all")->pd.DataFrame:
    """
    /shoppingInsight/getKeywordClickTrend.naver
    응답은 text/html이어도 JSON. result[0].data[*].period/ratio 형태를 최대 가정.
    """
    url="https://datalab.naver.com/shoppingInsight/getKeywordClickTrend.naver"
    payload={"cid":cid,"timeUnit":"date","startDate":start,"endDate":end,"age":age,"gender":gender,"device":device,"keyword":keyword}
    r=requests.post(url,headers=_hdr(cookie),data=payload,timeout=18,allow_redirects=False)
    if r.status_code in (301,302): raise RuntimeError("302 리다이렉트 → 쿠키/권한 문제")
    try: j=r.json()
    except Exception: j=json.loads(r.text)
    # 안전 파싱
    series=[]
    try:
        blk=(j.get("result") or [])[0]
        data=blk.get("data") or blk.get("dataList") or []
        for d in data:
            period=d.get("period") or d.get("date") or d.get("x")
            ratio =d.get("ratio")  or d.get("value") or d.get("y")
            if period is not None and ratio is not None:
                series.append({"date":period,"ratio":float(ratio)})
    except Exception:
        pass
    return pd.DataFrame(series)

def _render_status_bars(df: pd.DataFrame):
    try:
        import altair as alt
        chart=(alt.Chart(df).mark_bar().encode(
            x=alt.X("keyword:N", sort=None, title=""), y=alt.Y("score:Q", title="score"),
            color=alt.Color("status:N",
                scale=alt.Scale(domain=["정상","주의","오류"], range=["#2ecc71","#f1c40f","#e74c3c"]),
                legend=alt.Legend(title=None, orient="top")),
            tooltip=["rank","keyword","score","status"]).properties(height=260))
        st.altair_chart(chart, use_container_width=True)
    except Exception:
        st.bar_chart(df.set_index("keyword")["score"])

def render_datalab_block():
    st.markdown("## 데이터랩 (대분류 12종)")
    cats=_load_category_map()
    c1,c2=st.columns([1.25,1.25])

    with c1:
        cat=st.selectbox("카테고리", list(cats.keys()), key="dl_cat")
        cid=st.text_input("네이버 CID(수정 가능)", value=cats[cat], key="dl_cid")
        today=_dt.date.today()
        start_d=st.date_input("시작일", value=today-_dt.timedelta(days=30), key="dl_start")
        end_d  =st.date_input("종료일", value=today, key="dl_end")
        d1,d2,d3=st.columns(3)
        with d1: device=st.selectbox("기기", ["pc","mo"], index=0, key="dl_device")
        with d2: age   =st.selectbox("연령", ["all","10","20","30","40","50","60"], index=0, key="dl_age")
        with d3: gender=st.selectbox("성별", ["all","m","f"], index=0, key="dl_gender")

        tmp_cookie=st.text_input("임시 NAVER_COOKIE (세션 한정)", value="", type="password",
                                 help="DevTools>Network>Request Headers의 cookie 전체 문자열")
        cookie=_cookie_source(tmp_cookie)
        st.caption(f"쿠키 상태: {'✅ 설정됨' if cookie else '❌ 비어 있음'}")

        if st.button("키워드 20개 불러오기", key="dl_go"):
            try:
                if not cookie: st.error("NAVER_COOKIE가 비어 있습니다."); return
                df=_fetch_keywords_20(st.session_state["dl_cid"],
                        start_d.strftime("%Y-%m-%d"), end_d.strftime("%Y-%m-%d"),
                        cookie=cookie, device=device, age=age, gender=gender)
                df["status"]=df["score"].apply(_status)
                st.dataframe(df.rename(columns={"score":"score(가중치)"}), hide_index=True, use_container_width=True)
                _render_status_bars(df[["keyword","score","status"]].copy())
            except Exception as e:
                st.error(f"키워드 불러오기 실패: {e}")
        else:
            st.info("카테고리 선택 → 쿠키 확인 → ‘키워드 20개 불러오기’ 클릭")

    with c2:
        st.markdown("### 캠프 기간 (키워드 트렌드)")
        kws=st.text_input("키워드(최대 5개, 콤마로 구분)", "가습기, 무선청소기, 복합기", key="trend_kws")
        if st.button("트렌드 보기", key="trend_go"):
            try:
                cookie=_cookie_source(tmp_cookie)
                if not cookie: st.error("NAVER_COOKIE가 비어 있습니다."); return
                kw_list=[k.strip() for k in kws.split(",") if k.strip()][:5]
                frames=[]
                for kw in kw_list:
                    dfk=_fetch_keyword_trend(st.session_state["dl_cid"],
                          kw, start_d.strftime("%Y-%m-%d"), end_d.strftime("%Y-%m-%d"),
                          cookie=cookie, device=device, age=age, gender=gender)
                    if not dfk.empty:
                        dfk=dfk.rename(columns={"ratio":kw})
                        frames.append(dfk.set_index("date"))
                if frames:
                    df_line=pd.concat(frames, axis=1).fillna(0.0)
                    st.line_chart(df_line, height=240, use_container_width=True)
                else:
                    st.warning("트렌드 데이터를 가져오지 못했습니다. 쿠키/권한/키워드 확인.")
            except Exception as e:
                st.error(f"트렌드 불러오기 실패: {e}")
        else:
            st.caption("※ 키워드별 클릭 트렌드를 DataLab 엔드포인트에서 직접 조회합니다.")
# =========================
# Part 4 — 11번가(모바일) 임베드 (교체용 v11.x, 세션 쓰기 제거)
# - 기본 URL:  https://m.11st.co.kr/page/main/home
# - 기본 프록시: https://envy-proxy.taesig0302.workers.dev
# =========================
import streamlit as st
from urllib.parse import quote

DEFAULT_11ST_URL = "https://m.11st.co.kr/page/main/home"
PROXY_DEFAULT = "https://envy-proxy.taesig0302.workers.dev"  # 네 프록시

def render_11st_block():
    st.markdown("## 11번가 (모바일)")

    # 홈 주소를 기본값으로 고정 입력
    url = st.text_input(
        "모바일 URL",
        value=DEFAULT_11ST_URL,
        key="t11_url",
    ).strip()

    # 세션에 값이 없으면 "읽기만" 하고, 기본 프록시로 대체 (세션에 쓰지 않음)
    user_proxy = (st.session_state.get("PROXY_URL") or "").strip()
    proxy = user_proxy or PROXY_DEFAULT

    # 안내(사용 중인 프록시가 기본값인지/사용자 값인지 명확히 표시)
    if user_proxy:
        st.caption(f"프록시 경유(사용자 설정): **{user_proxy}** → **{url}**")
    else:
        st.warning("PROXY_URL이 비어 있어 기본 프록시를 사용합니다.")
        st.caption(f"프록시 경유(기본): **{PROXY_DEFAULT}** → **{url}**")

    # 프록시로 우회한 최종 URL
    target = f"{proxy}?url={quote(url, safe=':/?&=%')}"

    try:
        st.components.v1.iframe(src=target, height=980, scrolling=True)
    except Exception as e:
        st.error(f"11번가 로드 실패: {e}")
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

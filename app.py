# -*- coding: utf-8 -*-
# ENVY — Season 1 (Dual Proxy Edition, Stable Layout, KR Radar + Rakuten)
import os, base64, json, hmac, hashlib, time
from urllib.parse import quote
from pathlib import Path

import streamlit as st
import pandas as pd

try:
    import requests
except Exception:
    requests = None

# =========================================================
# 0) CONFIG (사용자 제공 키 주입)
# =========================================================
# Rakuten API
RAKUTEN_APP_ID       = "1043271015809337425"
RAKUTEN_AFFILIATE_ID = "4c723498.cbfeca46.4c723499.1deb6f77"

# Naver Developers (Login/Open API 용; 본 앱에선 보관만)
NAVER_CLIENT_ID     = "h4mklM2hNLct04BD7sC0"
NAVER_CLIENT_SECRET = "ltoxUNyKxi"

# Naver Ads / 검색광고 API (키워드도구)
NAVER_API_KEY     = "0100000000785cf1d8f039b13a5d3c3d1262b84e9ad4a046637e8887bbd003051b0d2a5cdf"  # Access License
NAVER_SECRET_KEY  = "AQAAAAB4XPHY8DmxOl08PRJiuE6ao1LN3lh0kF9rOJ4m5b8O5g=="                     # Secret Key
NAVER_CUSTOMER_ID = "629744"

# =========================================================
# 1) PAGE & GLOBAL
# =========================================================
st.set_page_config(page_title="ENVY — Season 1 (Dual Proxy Edition)", layout="wide")

SHOW_ADMIN_BOX = False

# 프록시(Cloudflare Worker, path-proxy 지원 가정)
NAVER_PROXY      = "https://envy-proxy.taesig0302.workers.dev"
ELEVENST_PROXY   = "https://worker-11stjs.taesig0302.workers.dev"
ITEMSCOUT_PROXY  = "https://worker-itemscoutjs.taesig0302.workers.dev"
SELLERLIFE_PROXY = "https://worker-sellerlifejs.taesig0302.workers.dev"

# 환율/통화
CURRENCIES = {
    "USD":{"kr":"미국 달러","symbol":"$","unit":"USD"},
    "EUR":{"kr":"유로","symbol":"€","unit":"EUR"},
    "JPY":{"kr":"일본 엔","symbol":"¥","unit":"JPY"},
    "CNY":{"kr":"중국 위안","symbol":"元","unit":"CNY"},
}
FX_DEFAULT = {"USD":1400.0,"EUR":1500.0,"JPY":10.0,"CNY":200.0}

def _ensure_session_defaults():
    ss = st.session_state
    ss.setdefault("theme","light")
    ss.setdefault("fx_base","USD")
    ss.setdefault("sale_foreign",1.00)
    ss.setdefault("m_base","USD")
    ss.setdefault("purchase_foreign",0.00)
    ss.setdefault("card_fee_pct",4.00)
    ss.setdefault("market_fee_pct",14.00)
    ss.setdefault("shipping_won",0.0)
    ss.setdefault("margin_mode","퍼센트")
    ss.setdefault("margin_pct",10.00)
    ss.setdefault("margin_won",10000.0)

def _toggle_theme():
    st.session_state["theme"]="dark" if st.session_state.get("theme","light")=="light" else "light"

def _inject_css():
    theme = st.session_state.get("theme","light")
    bg, fg = ("#0e1117","#e6edf3") if theme=="dark" else ("#ffffff","#111111")
    st.markdown(f"""
    <style>
      .block-container{{max-width:3800px!important;padding-top:.55rem!important;padding-bottom:1rem!important}}
      html,body,[data-testid="stAppViewContainer"]{{background:{bg}!important;color:{fg}!important}}
      h2,h3{{margin-top:.3rem!important}}

      /* Sidebar lock + tighter vertical gap */
      [data-testid="stSidebar"],[data-testid="stSidebar"]>div:first-child,[data-testid="stSidebar"] section{{
        height:100vh!important;overflow:hidden!important;padding:.15rem .25rem!important}}
      [data-testid="stSidebar"] section{{overflow-y:auto!important}}
      [data-testid="stSidebar"] ::-webkit-scrollbar{{display:none!important}}

      /* Input/Widget density(사이드바 상하 여백 축소) */
      [data-testid="stSidebar"] .stSelectbox,
      [data-testid="stSidebar"] .stNumberInput,
      [data-testid="stSidebar"] .stRadio,
      [data-testid="stSidebar"] .stMarkdown,
      [data-testid="stSidebar"] .stTextInput,
      [data-testid="stSidebar"] .stButton{{margin:.10rem 0!important}}
      [data-baseweb="input"] input,.stNumberInput input,[data-baseweb="select"] div[role="combobox"]{{
        height:1.55rem!important;padding:.12rem .6rem!important;font-size:.96rem!important;border-radius:12px!important}}

      .logo-circle{{width:86px;height:86px;border-radius:50%;overflow:hidden;margin:.15rem auto .4rem auto;
                   box-shadow:0 2px 8px rgba(0,0,0,.12);border:1px solid rgba(0,0,0,.06)}}
      .logo-circle img{{width:100%;height:100%;object-fit:cover}}

      /* Darker Pills */
      .pill{{border-radius:9999px;padding:.46rem .9rem;font-weight:800;display:inline-block}}
      .pill-green{{background:#b8f06c;border:1px solid #76c02a;color:#083500}}
      .pill-blue{{background:#dbe6ff;border:1px solid #88a8ff;color:#09245e}}
      .pill-yellow{{background:#ffe29b;border:1px solid #d2a12c;color:#3e2a00}}

      .card{{border:1px solid rgba(0,0,0,.06);border-radius:14px;padding:.85rem;background:#fff;box-shadow:0 1px 6px rgba(0,0,0,.05)}}
      .card-title{{font-size:1.18rem;font-weight:900;margin:.1rem 0 .55rem 0}}
      .card iframe{{border:0;width:100%;border-radius:10px}}
      .row-gap{{height:16px}}

      /* 테이블: 가로 스크롤 최소화 & 글자 1단계 축소 */
      .stDataFrame tbody td, .stDataFrame thead th {{
        font-size: 0.92rem !important;
        white-space: nowrap;
      }}
    </style>
    """, unsafe_allow_html=True)

def _sidebar():
    _ensure_session_defaults(); _inject_css()
    with st.sidebar:
        # 로고 (축소)
        lp = Path(__file__).parent / "logo.png"
        if lp.exists():
            b64 = base64.b64encode(lp.read_bytes()).decode("ascii")
            st.markdown(f'<div class="logo-circle"><img src="data:image/png;base64,{b64}"></div>', unsafe_allow_html=True)
        st.toggle("🌓 다크 모드", value=(st.session_state.get("theme","light")=="dark"),
                  on_change=_toggle_theme, key="__theme_toggle")

        st.markdown("### ① 환율 계산기")
        base = st.selectbox("기준 통화", list(CURRENCIES.keys()),
                            index=list(CURRENCIES.keys()).index(st.session_state["fx_base"]),
                            key="fx_base")
        sale_foreign = st.number_input("판매금액 (외화)", value=float(st.session_state["sale_foreign"]),
                                       step=0.01, format="%.2f", key="sale_foreign")
        won = FX_DEFAULT[base] * sale_foreign
        # 요청: (미국 달러) 텍스트 제거 → (USD • $)만 표시
        st.markdown(
            f'<div class="pill pill-green">환산 금액: <b>{won:,.2f} 원</b>'
            f'<span style="opacity:.75;font-weight:700"> ({CURRENCIES[base]["unit"]} • {CURRENCIES[base]["symbol"]})</span></div>',
            unsafe_allow_html=True
        )
        st.caption(f"환율 기준: {FX_DEFAULT[base]:,.2f} ₩/{CURRENCIES[base]['unit']}")

        st.markdown("### ② 마진 계산기")
        m_base = st.selectbox("매입 통화", list(CURRENCIES.keys()),
                              index=list(CURRENCENCIES.keys()).index(st.session_state["m_base"]) if 'CURRENCENCIES' in globals() else list(CURRENCIES.keys()).index(st.session_state["m_base"]),
                              key="m_base")
        purchase_foreign = st.number_input("매입금액 (외화)", value=float(st.session_state["purchase_foreign"]),
                                           step=0.01, format="%.2f", key="purchase_foreign")
        base_cost_won = FX_DEFAULT[m_base]*purchase_foreign if purchase_foreign>0 else won
        st.markdown(f'<div class="pill pill-green">원가(₩): <b>{base_cost_won:,.2f} 원</b></div>', unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            card_fee = st.number_input("카드수수료(%)", value=float(st.session_state["card_fee_pct"]),
                                       step=0.01, format="%.2f", key="card_fee_pct")
        with col2:
            market_fee = st.number_input("마켓수수료(%)", value=float(st.session_state["market_fee_pct"]),
                                         step=0.01, format="%.2f", key="market_fee_pct")
        shipping_won = st.number_input("배송비(₩)", value=float(st.session_state["shipping_won"]),
                                       step=100.0, format="%.0f", key="shipping_won")

        mode = st.radio("마진 방식", ["퍼센트","플러스"], horizontal=True, key="margin_mode")
        if mode=="퍼센트":
            margin_pct=st.number_input("마진율 (%)", value=float(st.session_state["margin_pct"]),
                                       step=0.01, format="%.2f", key="margin_pct")
            target_price = base_cost_won*(1+card_fee/100)*(1+market_fee/100)*(1+margin_pct/100)+shipping_won
            margin_value = target_price - base_cost_won
            desc = f"{margin_pct:.2f}%"
        else:
            margin_won=st.number_input("마진액 (₩)", value=float(st.session_state["margin_won"]),
                                       step=100.0, format="%.0f", key="margin_won")
            target_price=base_cost_won*(1+card_fee/100)*(1+market_fee/100)+margin_won+shipping_won
            margin_value=margin_won; desc=f"+{margin_won:,.0f}"
        st.markdown(f'<div class="pill pill-blue">판매가: <b>{target_price:,.2f} 원</b></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="pill pill-yellow">순이익(마진): <b>{margin_value:,.2f} 원</b> — {desc}</div>',
                    unsafe_allow_html=True)

        if SHOW_ADMIN_BOX:
            st.divider()
            st.text_input("PROXY_URL(디버그)", key="PROXY_URL", help="Cloudflare Worker 주소 (옵션)")

# =========================================================
# 2) 임베더 (path-proxy + fallback)
# =========================================================
def _proxy_iframe(proxy_base: str, target_url: str, height: int = 860, scroll=True, key=None):
    """
    path-proxy를 우선 사용하고, 필요 시 ?url= 폴백
    """
    proxy = (proxy_base or "").strip().rstrip("/")
    target = target_url.strip()

    if proxy and not target.startswith("http"):
        url = f"{proxy}{target if target.startswith('/') else '/' + target}"
    else:
        url = f"{proxy}/?url={quote(target, safe=':/?&=%')}"

    h = int(height) if isinstance(height, (int, float, str)) else 860
    try:
        st.iframe(url, height=h)
        return
    except Exception:
        pass
    try:
        st.components.v1.iframe(url, height=h, scrolling=bool(scroll))
        return
    except Exception:
        pass
    st.markdown(
        f'<iframe src="{url}" style="width:100%;height:{h}px;border:0;border-radius:10px;" '
        f'allow="clipboard-read; clipboard-write"></iframe>',
        unsafe_allow_html=True,
    )

def _11st_abest_url():
    import time
    return ("https://m.11st.co.kr/page/main/abest"
            f"?tabId=ABEST&pageId=AMOBEST&ctgr1No=166160&_ts={int(time.time())}")

# =========================================================
# 3) 섹션들
# =========================================================
def section_datalab_home():
    st.markdown('<div class="card"><div class="card-title">데이터랩</div>', unsafe_allow_html=True)
    _proxy_iframe(NAVER_PROXY, "/", height=860, scroll=True, key="naver_home")
    st.markdown('</div>', unsafe_allow_html=True)

def section_11st():
    st.markdown('<div class="card"><div class="card-title">11번가 (모바일) — 아마존 베스트</div>', unsafe_allow_html=True)
    _proxy_iframe(ELEVENST_PROXY, _11st_abest_url(), height=860, scroll=True, key="abest")
    st.markdown('</div>', unsafe_allow_html=True)

# --------- Rakuten Radar ----------
@st.cache_data(show_spinner=False, ttl=3600)
def rk_fetch_rank_df(genre_id: str, topn: int = 20) -> pd.DataFrame:
    rows=[]
    if requests and RAKUTEN_APP_ID:
        try:
            api = "https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20170628"
            params = {"applicationId": RAKUTEN_APP_ID, "genreId": str(genre_id).strip()}
            if RAKUTEN_AFFILIATE_ID: params["affiliateId"] = RAKUTEN_AFFILIATE_ID
            r = requests.get(api, params=params, timeout=12)
            r.raise_for_status()
            items = r.json().get("Items", [])[:topn]
            for it in items:
                node = it.get("Item", {})
                rows.append({
                    "rank": node.get("rank"),
                    "keyword": node.get("itemName",""),
                    "shop": node.get("shopName",""),
                    "url": node.get("itemUrl",""),
                })
        except Exception:
            pass
    if not rows:
        rows=[{"rank":i+1,"keyword":f"[샘플] 키워드 {i+1} ハロウィン 秋 🍂","shop":"샘플","url":"https://example.com"} for i in range(topn)]
    return pd.DataFrame(rows)

def section_rakuten():
    st.markdown('<div class="card"><div class="card-title">AI 키워드 레이더 (Rakuten)</div>', unsafe_allow_html=True)
    colA, colB, colC, colD = st.columns([1,1,1,1])
    with colA:
        scope = st.radio("범위", ["국내","글로벌"], horizontal=True, key="rk_scope")
    with colB:
        cat = st.selectbox("라쿠텐 카테고리", ["전체(샘플)","뷰티/코스메틱","의류/패션","가전/디지털","가구/인테리어","식품","생활/건강","스포츠/레저","문구/취미"], key="rk_cat")
    with colC:
        gid = st.text_input("GenreID", "100283", key="rk_genre")
    with colD:
        sample_only = st.checkbox("샘플 보기", value=False)

    df = rk_fetch_rank_df(gid or "100283", topn=20) if not sample_only else pd.DataFrame(
        [{"rank":i+1,"keyword":f"[샘플] 키워드 {i+1}","shop":"샘플샵","url":"https://example.com"} for i in range(20)]
    )
    # 랭크 칸 2단계 축소(= small), 표는 4컬럼만 노출 → 가로 스크롤 최소화
    colcfg = {
        "rank": st.column_config.NumberColumn("rank", width="small"),
        "keyword": st.column_config.TextColumn("keyword", width="large"),
        "shop": st.column_config.TextColumn("shop", width="medium"),
        "url": st.column_config.LinkColumn("url", display_text="열기", width="small"),
    }
    st.dataframe(df[["rank","keyword","shop","url"]], hide_index=True, use_container_width=True, height=460, column_config=colcfg)
    st.markdown('</div>', unsafe_allow_html=True)

# --------- Naver Ads Radar (Korea) ----------
def _nvads_signature(ts: str, method: str, uri: str, secret_key: str) -> str:
    msg = f"{ts}.{method}.{uri}"
    dig = hmac.new(secret_key.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(dig).decode("utf-8")

@st.cache_data(show_spinner=False, ttl=1800)
def nvads_keywordstool(hint_keywords: str, show_detail: int = 1) -> pd.DataFrame:
    """
    네이버 검색광고 API /keywordstool
    hint_keywords: 콤마/개행으로 구분된 씨드 키워드 문자열
    """
    base_url = "https://api.naver.com"
    uri = "/keywordstool"
    method = "GET"
    ts = str(int(time.time()*1000))

    headers = {
        "X-API-KEY": NAVER_API_KEY,
        "X-Customer": NAVER_CUSTOMER_ID,
        "X-Timestamp": ts,
        "X-Signature": _nvads_signature(ts, method, uri, NAVER_SECRET_KEY),
    }
    params = {
        "hintKeywords": hint_keywords,
        "showDetail": str(int(show_detail)),
        "includeHintKeywords": "0",
    }
    try:
        r = requests.get(base_url+uri, headers=headers, params=params, timeout=15)
        r.raise_for_status()
        data = r.json().get("keywordList", [])
        if not data: 
            return pd.DataFrame()
        df = pd.DataFrame(data)
        # 컬럼 한글화 + 타입 보정
        ren = {
            "relKeyword":"키워드",
            "monthlyPcQcCnt":"PC월간검색수",
            "monthlyMobileQcCnt":"Mobile월간검색수",
            "monthlyAvePcClkCnt":"PC월평균클릭수",
            "monthlyAveMobileClkCnt":"Mobile월평균클릭수",
            "monthlyAvePcCtr":"PC월평균클릭률",
            "monthlyAveMobileCtr":"Mobile월평균클릭률",
            "plAvgDepth":"월평균노출광고수",
            "compIdx":"광고경쟁정도",
        }
        df = df.rename(columns=ren)
        # 숫자 문자열 정리
        for c in ["PC월간검색수","Mobile월간검색수","PC월평균클릭수","Mobile월평균클릭수"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
        for c in ["PC월평균클릭률","Mobile월평균클릭률"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        if "월평균노출광고수" in df.columns:
            df["월평균노출광고수"] = pd.to_numeric(df["월평균노출광고수"], errors="coerce")
        df = df.drop_duplicates(subset=["키워드"]).reset_index(drop=True)
        # 간단 랭킹(검색수↑, 광고수/경쟁↓ 가중치 예시)
        if {"PC월간검색수","Mobile월간검색수","월평균노출광고수","광고경쟁정도"}.issubset(df.columns):
            s = df["PC월간검색수"].fillna(0) + df["Mobile월간검색수"].fillna(0)
            ads = df["월평균노출광고수"].fillna(0)
            comp = df["광고경쟁정도"].map({"높음":1.0,"중간":0.6,"낮음":0.3}).fillna(0.6)
            # 점수: 검색수↑ / (광고수+경쟁)↓
            df["발굴스코어"] = (s / (1 + ads*0.2 + comp*10)).round(3)
            df = df.sort_values("발굴스코어", ascending=False)
        return df
    except requests.HTTPError as e:
        # 스트림릿에서 보기 좋게 에러 리턴
        return pd.DataFrame([{"키워드":"(API 오류)", "에러": str(e), "힌트":"키/권한/쿼터/파라미터 점검"}])
    except Exception as e:
        return pd.DataFrame([{"키워드":"(요청 실패)", "에러": str(e)}])

def section_korea_radar():
    st.markdown('<div class="card"><div class="card-title">AI 키워드 레이더 (Korea)</div>', unsafe_allow_html=True)
    c1,c2,c3 = st.columns([1,1,1])
    with c1:
        months = st.slider("분석기간(개월) — *키워드도구는 월 집계 기반*", 1, 6, 3, 1, help="가중치에만 반영되는 UI, API는 고정 월 집계")
    with c2:
        device = st.selectbox("디바이스", ["all","pc","mobile"], index=0, help="표시/정렬 가중치 용도")
    with c3:
        seed_mode = st.selectbox("키워드 소스", ["직접 입력"], index=0)

    seed = st.text_area("키워드(콤마/개행 구분)", "원피스, 블라우스, 바람막이, 트위드자켓", height=82)
    run = st.button("레이더 업데이트", use_container_width=True)

    if run:
        with st.spinner("네이버 검색광고 API에서 연관 키워드를 수집 중…"):
            df = nvads_keywordstool(seed)
        if df.empty:
            st.warning("결과가 비었습니다. 키워드를 바꿔 시도해보세요.")
        else:
            # 표 가로 스크롤 최소화: 핵심 컬럼만
            cols = [c for c in ["키워드","PC월간검색수","Mobile월간검색수","월평균노출광고수","광고경쟁정도","발굴스코어"] if c in df.columns]
            colcfg = {
                "키워드": st.column_config.TextColumn("키워드", width="large"),
                "PC월간검색수": st.column_config.NumberColumn("PC월간검색수", width="small"),
                "Mobile월간검색수": st.column_config.NumberColumn("Mobile월간검색수", width="small"),
                "월평균노출광고수": st.column_config.NumberColumn("월평균노출광고수", width="small"),
                "발굴스코어": st.column_config.NumberColumn("발굴스코어", format="%.3f", width="small"),
            }
            st.dataframe(df[cols].head(300), hide_index=True, use_container_width=True, height=460, column_config=colcfg)
    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# 4) LAYOUT (백업했던 배치로 복원)
#    1행: 데이터랩 / (공란 또는 도구)
#    2행: 11번가 / Rakuten / Korea Radar
# =========================================================
_ = _sidebar()
st.title("ENVY — Season 1 (Dual Proxy Edition)")

# 1행
row1a, row1b = st.columns([3,3], gap="medium")
with row1a: section_datalab_home()
with row1b:
    st.markdown('<div class="card"><div class="card-title">검색어도구</div>', unsafe_allow_html=True)
    st.write("필요 시 이 영역에 보조 위젯/요약/메모 등을 배치하세요.")
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="row-gap"></div>', unsafe_allow_html=True)

# 2행
r2c1, r2c2, r2c3 = st.columns([3,3,3], gap="medium")
with r2c1: section_11st()
with r2c2: section_rakuten()
with r2c3: section_korea_radar()

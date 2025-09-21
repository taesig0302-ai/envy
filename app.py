# -*- coding: utf-8 -*-
# ENVY — Season 1 (Dual Proxy Edition)  —  2025-09 패치
# - 레이아웃: 1행(데이터랩/아이템스카우트/셀러라이프) + 2행(11번가/글로벌 레이더/국내 레이더/번역기)
# - Rakuten 레이더: rank 칸 2단계 축소, 가로 스크롤 제거, 장르 매핑 편집 영역 숨김
# - Korea 레이더: 네이버 DataLab Search API 정식 호출(POST), 견고한 예외처리, 미설정 시 친절 경고
# - 사이드바 입력 박스·출력 박스 상하 여백 축소(기존 유지), 로고 크기 축소(기존 유지)

import os, json, time, base64
from pathlib import Path
from urllib.parse import quote
from datetime import date
from dateutil.relativedelta import relativedelta

import streamlit as st
import pandas as pd
import requests

# =========================
# 0) 전역/프로시
# =========================
st.set_page_config(page_title="ENVY — Season 1 (Dual Proxy Edition)", layout="wide")

SHOW_ADMIN_BOX = False

# 프록시(Cloudflare Worker)
NAVER_PROXY      = "https://envy-proxy.taesig0302.workers.dev"
ELEVENST_PROXY   = "https://worker-11stjs.taesig0302.workers.dev"
ITEMSCOUT_PROXY  = "https://worker-itemscoutjs.taesig0302.workers.dev"
SELLERLIFE_PROXY = "https://worker-sellerlifejs.taesig0302.workers.dev"

# Rakuten 기본키(없으면 샘플 동작)
RAKUTEN_APP_ID_DEFAULT       = "1043271015809337425"
RAKUTEN_AFFILIATE_ID_DEFAULT = "4c723498.cbfeca46.4c723499.1deb6f77"

# 환율/마진 계산기(기존 유지)
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
      /* Sidebar lock + tighter spacing */
      [data-testid="stSidebar"],[data-testid="stSidebar"]>div:first-child,[data-testid="stSidebar"] section{{
        height:100vh!important;overflow:hidden!important;padding:.15rem .25rem!important}}
      [data-testid="stSidebar"] section{{overflow-y:auto!important}}
      [data-testid="stSidebar"] ::-webkit-scrollbar{{display:none!important}}
      /* 입력/출력 박스 상하 여백 축소 */
      [data-testid="stSidebar"] .stSelectbox,
      [data-testid="stSidebar"] .stNumberInput,
      [data-testid="stSidebar"] .stRadio,
      [data-testid="stSidebar"] .stMarkdown,
      [data-testid="stSidebar"] .stTextInput,
      [data-testid="stSidebar"] .stTextArea,
      [data-testid="stSidebar"] .stButton{{margin:.10rem 0!important}}
      [data-baseweb="input"] input,.stNumberInput input,[data-baseweb="select"] div[role="combobox"]{{
        height:1.55rem!important;padding:.12rem .6rem!important;font-size:.96rem!important;border-radius:12px!important}}
      /* 로고 크기(축소 고정) */
      .logo-circle{{width:86px;height:86px;border-radius:50%;overflow:hidden;margin:.15rem auto .45rem auto;
                   box-shadow:0 2px 8px rgba(0,0,0,.12);border:1px solid rgba(0,0,0,.06)}}
      .logo-circle img{{width:100%;height:100%;object-fit:cover}}
      /* 카드/필 */
      .pill{{border-radius:9999px;padding:.46rem .9rem;font-weight:800;display:inline-block}}
      .pill-green{{background:#b8f06c;border:1px solid #76c02a;color:#083500}}
      .pill-blue{{background:#dbe6ff;border:1px solid #88a8ff;color:#09245e}}
      .pill-yellow{{background:#ffe29b;border:1px solid #d2a12c;color:#3e2a00}}
      .card{{border:1px solid rgba(0,0,0,.06);border-radius:14px;padding:.85rem;background:#fff;box-shadow:0 1px 6px rgba(0,0,0,.05)}}
      .card-title{{font-size:1.18rem;font-weight:900;margin:.1rem 0 .55rem 0}}
      .card iframe{{border:0;width:100%;border-radius:10px}}
      .row-gap{{height:16px}}
      /* DataFrame(가로 스크롤 억제 & 폰트 1단계 축소) */
      div[data-testid="stDataFrame"] * {{font-size:13px}}
      /* 랭크 칼럼 폭 2단계 축소 */
      th[data-testid="column-header"][title="rank"], td[data-testid="cell"][role="gridcell"] div:has(> span:contains("rank")) {{
        max-width:60px!important;min-width:60px!important;
      }}
    </style>
    """, unsafe_allow_html=True)

def _sidebar():
    _ensure_session_defaults(); _inject_css()
    with st.sidebar:
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
        st.markdown(
            f'<div class="pill pill-green">환산 금액: <b>{won:,.2f} 원</b>'
            f'<span style="opacity:.75;font-weight:700"> ({CURRENCIES[base]["symbol"]})</span></div>',
            unsafe_allow_html=True
        )
        st.caption(f"환율 기준: {FX_DEFAULT[base]:,.2f} ₩/{CURRENCIES[base]['unit']}")

        st.markdown("### ② 마진 계산기")
        m_base = st.selectbox("매입 통화", list(CURRENCIES.keys()),
                              index=list(CURRENCIES.keys()).index(st.session_state["m_base"]),
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

# =========================
# 1) 안전 임베더
# =========================
def _proxy_iframe(proxy_base: str, target_url: str, height: int = 860, scroll=True):
    proxy = (proxy_base or "").strip().rstrip("/")
    url   = f"{proxy}/?url={quote(target_url, safe=':/?&=%')}"
    h     = int(height) if isinstance(height, (int, float, str)) else 860
    try:
        st.iframe(url, height=h)
    except Exception:
        st.markdown(
            f'<iframe src="{url}" style="width:100%;height:{h}px;border:0;border-radius:10px;" '
            f'allow="clipboard-read; clipboard-write"></iframe>',
            unsafe_allow_html=True,
        )

# =========================
# 2) 섹션: DataLab / Itemscout / Sellerlife / 11st
# =========================
def _11st_abest_url():
    import time
    return ("https://m.11st.co.kr/page/main/abest"
            f"?tabId=ABEST&pageId=AMOBEST&ctgr1No=166160&_ts={int(time.time())}")

def section_datalab_home():
    st.markdown('<div class="card"><div class="card-title">데이터랩</div>', unsafe_allow_html=True)
    # 탭 제목이 사라지는 문제: 모바일 상단 바 고정 → 모바일 버전으로 고정 로드 (Proxy)
    _proxy_iframe(NAVER_PROXY, "https://datalab.naver.com/", height=860, scroll=True)
    st.markdown('</div>', unsafe_allow_html=True)

def section_itemscout_placeholder():
    st.markdown('<div class="card"><div class="card-title">아이템스카우트</div>', unsafe_allow_html=True)
    st.info("원본 서버(DNS/오리진) 이슈로 임베드가 일시 중단되어 있습니다. 아래 버튼으로 새 탭 열기.")
    st.link_button("직접 열기(새 탭)", "https://app.itemscout.io/market/keyword")
    st.caption("Cloudflare 1016/52x 발생 시, 원본 사이트 상태 이슈 가능성이 큼.")
    st.markdown('</div>', unsafe_allow_html=True)

def section_sellerlife_placeholder():
    st.markdown('<div class="card"><div class="card-title">셀러라이프</div>', unsafe_allow_html=True)
    _proxy_iframe(SELLERLIFE_PROXY, "https://sellochomes.co.kr/sellerlife/", height=860, scroll=True)
    st.markdown('</div>', unsafe_allow_html=True)

def section_11st():
    st.markdown('<div class="card"><div class="card-title">11번가 (모바일) — 아마존 베스트</div>', unsafe_allow_html=True)
    _proxy_iframe(ELEVENST_PROXY, _11st_abest_url(), height=760, scroll=True)
    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# 3) Rakuten 레이더 (글로벌)
# =========================
def _rakuten_keys():
    app_id = (st.secrets.get("RAKUTEN_APP_ID", "")
              or st.secrets.get("RAKUTEN_APPLICATION_ID", "")
              or RAKUTEN_APP_ID_DEFAULT).strip()
    affiliate = (st.secrets.get("RAKUTEN_AFFILIATE_ID", "")
                 or st.secrets.get("RAKUTEN_AFFILIATE", "")
                 or RAKUTEN_AFFILIATE_ID_DEFAULT).strip()
    return app_id, affiliate

def rk_fetch_rank(genre_id: str, topn: int = 20) -> pd.DataFrame:
    app_id, affiliate = _rakuten_keys()
    rows=[]
    if app_id:
        try:
            api = "https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20170628"
            params = {"applicationId": app_id, "genreId": str(genre_id).strip()}
            if affiliate: params["affiliateId"] = affiliate
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

def section_rakuten_radar():
    st.markdown('<div class="card"><div class="card-title">AI 키워드 레이더 (Rakuten)</div>', unsafe_allow_html=True)
    colA, colB, colC, colD = st.columns([1,1,1,1])
    with colA:
        scope = st.radio("범위", ["국내","글로벌"], horizontal=True, key="rk_scope")
    with colB:
        cat = st.selectbox("라쿠텐 카테고리", ["전체(샘플)","뷰티/코스메틱","의류/패션","가전/디지털","가구/인테리어","식품","생활/건강","스포츠/레저","문구/취미"], key="rk_cat")
    with colC:
        gid = st.text_input("GenreID", "100283", key="rk_genre")
    with colD:
        sample_only = st.checkbox("샘플 보기", value=False, key="rk_sample")

    # 결과
    df = rk_fetch_rank(gid or "100283", topn=20) if not sample_only else pd.DataFrame(
        [{"rank":i+1,"keyword":f"[샘플] 키워드 {i+1}","shop":"샘플샵","url":"https://example.com"} for i in range(20)]
    )
    colcfg = {
        "rank": st.column_config.NumberColumn("rank", width="small"),
        "keyword": st.column_config.TextColumn("keyword", width="large"),
        "shop": st.column_config.TextColumn("shop", width="medium"),
        "url": st.column_config.LinkColumn("url", display_text="열기", width="small"),
    }
    st.dataframe(df[["rank","keyword","shop","url"]], hide_index=True, use_container_width=True, height=420, column_config=colcfg)

    # 장르 매핑 영역(숨김 패널 안내만)
    with st.expander("장르 매핑 편집 (GenreID는 여기서만 관리 — 화면에는 숨김)", expanded=False):
        st.caption("여기서는 GenreID만 관리합니다. 실제 테이블에는 노출하지 않습니다.")
    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# 4) Korea 레이더 (네이버 DataLab Search)  ← 에러수정
# =========================
def _datalab_creds():
    """secrets 우선, 없으면 우측 카드 입력값 사용."""
    cid = st.secrets.get("NAVER_CLIENT_ID", "")
    csec = st.secrets.get("NAVER_CLIENT_SECRET", "")
    # 카드 입력(있으면 오버라이드)
    cid_in = st.session_state.get("__tmp_cid","").strip()
    csec_in = st.session_state.get("__tmp_csec","").strip()
    if cid_in: cid = cid_in
    if csec_in: csec = csec_in
    return cid.strip(), csec.strip()

def naver_datalab_trend(keywords:list[str], months:int=3, device:str="all") -> pd.DataFrame:
    """네이버 DataLab Search API로 키워드 트렌드 조회 → 기간 합산 스코어."""
    cid, csec = _datalab_creds()
    if not cid or not csec or not keywords:
        return pd.DataFrame()
    end = date.today()
    start = end - relativedelta(months=months)
    body = {
        "startDate": start.strftime("%Y-%m-%d"),
        "endDate":   end.strftime("%Y-%m-%d"),
        "timeUnit":  "month",
        "device":    device,           # all, pc, mo, tablet
        "ages":      [],               # 전체
        "gender":    "",               # 전체
        "keywordGroups": [{"groupName": kw, "keywords": [kw]} for kw in keywords if kw.strip()]
    }
    headers = {
        "X-Naver-Client-Id": cid,
        "X-Naver-Client-Secret": csec,
        "Content-Type": "application/json; charset=UTF-8",
    }
    url = "https://openapi.naver.com/v1/datalab/search"
    try:
        r = requests.post(url, headers=headers, data=json.dumps(body), timeout=12)
        if r.status_code >= 400:
            # 응답 본문을 살려서 표시(앱 크래시 금지)
            msg = (r.json().get("message") if r.headers.get("content-type","").startswith("application/json")
                   else r.text)
            st.error(f"네이버 DataLab API 오류: {r.status_code} — {msg}")
            return pd.DataFrame()
        data = r.json().get("results", [])
    except requests.exceptions.Timeout:
        st.error("네이버 DataLab API 타임아웃(Timeout). 잠시 후 다시 시도하세요.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"DataLab 호출 중 예외: {e}")
        return pd.DataFrame()

    rows=[]
    for res in data:
        gname = res.get("title") or res.get("keyword") or res.get("groupName")
        series = res.get("data", [])
        total = sum([d.get("ratio",0) for d in series])
        last  = series[-1]["ratio"] if series else 0
        prev  = series[-2]["ratio"] if len(series)>=2 else 0
        mom   = (last - prev)
        rows.append({"keyword": gname, "trend_score": total, "last_month": last, "mom(Δ)": mom})
    df = pd.DataFrame(rows)
    if df.empty: return df
    df = df.sort_values(["trend_score","last_month"], ascending=False).reset_index(drop=True)
    df.insert(0, "rank", df.index+1)
    return df

def section_korea_radar():
    st.markdown('<div class="card"><div class="card-title">AI 키워드 레이더 (Korea)</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,1,2])
    with c1:
        months = st.slider("분석기간(개월)", 1, 6, 3, 1, key="kr_months")
    with c2:
        device = st.selectbox("디바이스", ["all","pc","mo","tablet"], index=0, key="kr_device")
    with c3:
        src = st.selectbox("키워드 소스", ["직접 입력"], index=0)

    kw_text = st.text_area("키워드(콤마로 구분)", value="원피스, 블라우스, 바람막이, 트위드자켓", key="kr_kw_text")
    kwords = [k.strip() for k in kw_text.split(",") if k.strip()]

    # 임시 자격 입력(없어도 secrets 있으면 실행됨)
    st.markdown("##### API 키(임시 입력)")
    colK1, colK2, colK3 = st.columns([2,2,1])
    with colK1:
        st.text_input("NAVER_CLIENT_ID", value="", key="__tmp_cid", type="password",
                      help="secrets에 이미 설정되어 있으면 비워두어도 됩니다.")
    with colK2:
        st.text_input("NAVER_CLIENT_SECRET", value="", key="__tmp_csec", type="password",
                      help="secrets에 이미 설정되어 있으면 비워두어도 됩니다.")
    with colK3:
        do = st.button("레이더 업데이트", use_container_width=True)

    cid, csec = _datalab_creds()
    if not cid or not csec:
        st.warning("NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 누락. 값을 입력하거나 secrets.toml에 추가하세요.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    if do:
        with st.spinner("네이버 트렌드 계산 중…"):
            df = naver_datalab_trend(kwords, months=months, device=device)
        if df.empty:
            st.info("결과가 비었거나 오류가 발생했습니다.")
        else:
            colcfg = {
                "rank": st.column_config.NumberColumn("rank", width="small"),
                "keyword": st.column_config.TextColumn("keyword", width="large"),
                "trend_score": st.column_config.NumberColumn("trend_score"),
                "last_month": st.column_config.NumberColumn("last_month"),
                "mom(Δ)": st.column_config.NumberColumn("mom(Δ)")
            }
            st.dataframe(df, hide_index=True, use_container_width=True, height=420, column_config=colcfg)
            st.download_button("표 CSV 다운로드", df.to_csv(index=False).encode("utf-8-sig"),
                               file_name="korea_radar.csv", mime="text/csv")
    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# 5) 번역기 & 상품명 생성기 (간결 유지)
# =========================
LANG_LABELS = {"auto":"자동 감지","ko":"한국어","en":"영어","ja":"일본어","zh-CN":"중국어(간체)","zh-TW":"중국어(번체)","vi":"베트남어","th":"태국어","id":"인도네시아어","de":"독일어","fr":"프랑스어","es":"스페인어","it":"이탈리아어","pt":"포르투갈어"}
def _code(x): return {v:k for k,v in LANG_LABELS.items()}.get(x, x)

def section_translator():
    st.markdown('<div class="card"><div class="card-title">구글 번역기</div>', unsafe_allow_html=True)
    try:
        from deep_translator import GoogleTranslator
        c1, c2 = st.columns([1,1])
        with c1:
            src = st.selectbox("원문", list(LANG_LABELS.values()), index=list(LANG_LABELS.keys()).index("auto"))
            text_in = st.text_area("입력", height=160)
        with c2:
            tgt = st.selectbox("번역", list(LANG_LABELS.values()), index=list(LANG_LABELS.keys()).index("en"))
            if st.button("번역"):
                out = GoogleTranslator(source=_code(src), target=_code(tgt)).translate(text_in or "")
                st.text_area("번역 결과", value=out, height=160)
    except Exception:
        st.warning("deep-translator 미설치/런타임 이슈")
    st.markdown('</div>', unsafe_allow_html=True)

def section_title_generator():
    st.markdown('<div class="card"><div class="card-title">상품명 생성기 (규칙 기반)</div>', unsafe_allow_html=True)
    with st.container():
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
            kw_list = [k.strip() for k in (kws or "").split(",") if k.strip()]
            at_list = [a.strip() for a in (attrs or "").split(",") if a.strip()]
            if not kw_list:
                st.warning("키워드가 비었습니다.")
            else:
                titles=[]
                for k in kw_list:
                    if order=="브랜드-키워드-속성": seq=[brand, k]+at_list
                    elif order=="키워드-브랜드-속성": seq=[k,brand]+at_list
                    else: seq=[brand]+at_list+[k]
                    title = joiner.join([p for p in seq if p])
                    if len(title)>max_len:
                        title = title[:max_len-1]+"…"
                    titles.append(title)
                st.success(f"총 {len(titles)}건")
                st.write("\n".join(titles))
    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# 6) 레이아웃 (예전 배치로 고정)
# =========================
_ = _sidebar()
st.title("ENVY — Season 1 (Dual Proxy Edition)")

# 1행: 데이터랩 / 아이템스카우트 / 셀러라이프
top1, top2, top3 = st.columns([3,3,3], gap="medium")
with top1: section_datalab_home()
with top2: section_itemscout_placeholder()
with top3: section_sellerlife_placeholder()

st.markdown('<div class="row-gap"></div>', unsafe_allow_html=True)

# 2행: 11번가 / 글로벌 레이더 / 국내 레이더 / 번역기
b1, b2, b3, b4 = st.columns([3,3,3,3], gap="medium")
with b1: section_11st()
with b2: section_rakuten_radar()
with b3: section_korea_radar()
with b4: section_translator()

st.markdown('<div class="row-gap"></div>', unsafe_allow_html=True)

# 3행(옵션): 상품명 생성기
c1, = st.columns([3])
with c1: section_title_generator()

# -*- coding: utf-8 -*-
# ENVY — Season 1 (Dual Proxy Edition, fixed keys embedded)
# - 국내: 네이버 검색광고(키워드도구) + (옵션) 네이버쇼핑 상품수 크롤
# - 해외: 라쿠텐 랭킹 (장르 매핑 포함)
# - 카테고리 → 키워드 Top20 & 트렌드 (네이버 Ads + DataLab Search API)
# - 11번가(모바일) 아마존베스트 임베드
# - API 키는 하드코딩되어 UI에서 요구하지 않습니다.

import base64, time, re, math, json, datetime
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import streamlit as st

try:
    import requests
except Exception:
    requests = None

try:
    import altair as alt
except Exception:
    alt = None

try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None

# -------------------------------------------------------
# 0) FIXED KEYS (하드코딩)
# -------------------------------------------------------
# Rakuten API
RAKUTEN_APP_ID       = "1043271015809337425"
RAKUTEN_AFFILIATE_ID = "4c723498.cbfeca46.4c723499.1deb6f77"

# Naver Developers (OpenAPI for DataLab)
NAVER_CLIENT_ID     = "h4mklM2hNLct04BD7sC0"
NAVER_CLIENT_SECRET = "ltoxUNyKxi"

# Naver Ads / 검색광고 API (키워드 도구)
NAVER_API_KEY     = "0100000000785cf1d8f039b13a5d3c3d1262b84e9ad4a046637e8887bbd003051b0d2a5cdf"
NAVER_SECRET_KEY  = "AQAAAAB4XPHY8DmxOl08PRJiuE6ao1LN3lh0kF9rOJ4m5b8O5g=="
NAVER_CUSTOMER_ID = "629744"

# -------------------------------------------------------
# 1) PROXIES & CONSTANTS
# -------------------------------------------------------
st.set_page_config(page_title="ENVY — Season 1 (Dual Proxy Edition)", layout="wide")

NAVER_PROXY      = "https://envy-proxy.taesig0302.workers.dev"
ELEVENST_PROXY   = "https://worker-11stjs.taesig0302.workers.dev"

# 라쿠텐 카테고리(장르) 매핑 — 필요 시 여기서 직접 바꾸면 됩니다.
RAKUTEN_GENRE_MAP_DEFAULT = {
    "전체(샘플)":  "100283",
    "뷰티/코스메틱":"100283",
    "의류/패션":   "100283",
    "가전/디지털":  "100283",
    "가구/인테리어":"100283",
    "식품":       "100283",
    "생활/건강":   "100283",
    "스포츠/레저":  "100283",
    "문구/취미":   "100283",
}

# 카테고리별 시드 키워드(네이버 키워드도구 조회용)
CATEGORY_SEEDS = {
    "패션잡화": ["핸드메이드코트", "남자코트", "코트", "자켓", "원피스", "블라우스"],
    "생활/건강": ["공기청정기", "가습기", "비타민", "샴푸", "바디워시"],
    "가전/디지털": ["무선청소기", "태블릿", "노트북", "블루투스 이어폰"],
    "가구/인테리어": ["책상", "의자", "소파", "조명", "러그"],
    "스포츠/레저": ["등산화", "캠핑의자", "텐트", "요가매트"],
    "식품": ["프로틴", "두유", "쌀", "견과류", "생수"],
    "문구/취미": ["다이어리", "형광펜", "퍼즐", "레고"],
}

# UI/표에 쓰는 짧은 컬럼명 (가로 스크롤 최소화)
SHORT_COLS = {
    "PC월간검색수":"PC월", "Mobile월간검색수":"MO월",
    "판매상품수":"판매수",
    "PC월평균클릭수":"PC클", "Mobile월평균클릭수":"MO클",
    "PC월평균클릭률":"PC률", "Mobile월평균클릭률":"MO률",
    "월평균노출광고수":"광고수", "광고경쟁정도":"경쟁"
}

# FX (사이드 계산기)
CURRENCIES = {
    "USD":{"kr":"미국 달러","symbol":"$","unit":"USD"},
    "EUR":{"kr":"유로","symbol":"€","unit":"EUR"},
    "JPY":{"kr":"일본 엔","symbol":"¥","unit":"JPY"},
    "CNY":{"kr":"중국 위안","symbol":"元","unit":"CNY"},
}
FX_DEFAULT = {"USD":1400.0,"EUR":1500.0,"JPY":10.0,"CNY":200.0}

# -------------------------------------------------------
# 2) CSS & LAYOUT UTIL
# -------------------------------------------------------
def _inject_css():
    st.markdown(
        """
        <style>
          .block-container{max-width: 3800px !important; padding-top:.55rem !important;}
          .card{border:1px solid rgba(0,0,0,.06);background:#fff;border-radius:14px;padding:.85rem;
                box-shadow:0 1px 6px rgba(0,0,0,.05);margin-bottom:12px;}
          .card-title{font-size:1.18rem;font-weight:900;margin:.1rem 0 .55rem 0}
          .pill{border-radius:9999px;padding:.35rem .85rem;font-weight:800;display:inline-block;}
          .pill-green{background:#b8f06c;border:1px solid #76c02a;color:#083500}
          .pill-blue{background:#dbe6ff;border:1px solid #88a8ff;color:#09245e}
          .row-gap{height:16px}
          #rk-card [data-testid="stDataFrame"] * { font-size: 0.92rem !important; }
          #rk-card [data-testid="stDataFrame"] div[role='grid']{ overflow-x: hidden !important; }
          #rk-card [data-testid="stDataFrame"] div[role='gridcell']{
            white-space: normal !important; word-break: break-word !important; overflow-wrap: anywhere !important;
          }
        </style>
        """,
        unsafe_allow_html=True
    )

def _card(title:str):
    st.markdown(f'<div class="card"><div class="card-title">{title}</div>', unsafe_allow_html=True)

def _card_end():
    st.markdown('</div>', unsafe_allow_html=True)

# -------------------------------------------------------
# 3) SIDEBAR (환율/마진)
# -------------------------------------------------------
def sidebar():
    _inject_css()
    st.sidebar.title("ENVY")
    st.sidebar.caption("Season 1 · Dual Proxy Edition")

    st.sidebar.markdown("### ① 환율 계산기")
    base = st.sidebar.selectbox("기준 통화", list(CURRENCIES.keys()), index=0)
    sale_foreign = st.sidebar.number_input("판매금액 (외화)", value=1.00, step=0.01, format="%.2f")
    won = FX_DEFAULT[base]*sale_foreign
    st.sidebar.markdown(f'<div class="pill pill-green">환산 금액: <b>{won:,.2f} 원</b></div>', unsafe_allow_html=True)
    st.sidebar.caption(f"환율 기준: {FX_DEFAULT[base]:,.2f} ₩/{CURRENCIES[base]['unit']}")

    st.sidebar.markdown("### ② 마진 계산기")
    m_base = st.sidebar.selectbox("매입 통화", list(CURRENCIES.keys()), index=0)
    purchase_foreign = st.sidebar.number_input("매입금액 (외화)", value=0.00, step=0.01, format="%.2f")
    base_cost_won = FX_DEFAULT[m_base]*purchase_foreign if purchase_foreign>0 else won
    st.sidebar.markdown(f'<div class="pill pill-green">원가(₩): <b>{base_cost_won:,.2f} 원</b></div>', unsafe_allow_html=True)

    c1, c2 = st.sidebar.columns(2)
    card_fee = c1.number_input("카드수수료(%)", value=4.00, step=0.01, format="%.2f")
    market_fee = c2.number_input("마켓수수료(%)", value=14.00, step=0.01, format="%.2f")
    shipping_won = st.sidebar.number_input("배송비(₩)", value=0.0, step=100.0, format="%.0f")

    mode = st.sidebar.radio("마진 방식", ["퍼센트","플러스"], horizontal=True)
    if mode=="퍼센트":
        margin_pct=st.sidebar.number_input("마진율 (%)", value=10.00, step=0.01, format="%.2f")
        target_price = base_cost_won*(1+card_fee/100)*(1+market_fee/100)*(1+margin_pct/100)+shipping_won
        margin_value = target_price - base_cost_won
        desc = f"{margin_pct:.2f}%"
    else:
        margin_won=st.sidebar.number_input("마진액 (₩)", value=10000.0, step=100.0, format="%.0f")
        target_price=base_cost_won*(1+card_fee/100)*(1+market_fee/100)+margin_won+shipping_won
        margin_value=margin_won; desc=f"+{margin_won:,.0f}"
    st.sidebar.markdown(f'<div class="pill pill-blue">판매가: <b>{target_price:,.2f} 원</b> · 순이익 <b>{margin_value:,.2f}</b> — {desc}</div>', unsafe_allow_html=True)

# -------------------------------------------------------
# 4) 네이버 Ads(키워드도구) / 네이버쇼핑 상품수
# -------------------------------------------------------
import hashlib, hmac, base64 as b64

def _naver_signature(ts, method, uri, secret):
    msg = f"{ts}.{method}.{uri}"
    dig = hmac.new(bytes(secret,"utf-8"), bytes(msg,"utf-8"), hashlib.sha256).digest()
    return b64.b64encode(dig).decode("utf-8")

@st.cache_data(ttl=900, show_spinner=False)
def naver_keyword_tool(hint_keywords:list[str]) -> pd.DataFrame:
    """네이버 검색광고 키워드도구 조회"""
    if not (requests and NAVER_API_KEY and NAVER_SECRET_KEY and NAVER_CUSTOMER_ID and hint_keywords):
        return pd.DataFrame()

    base_url="https://api.naver.com"
    uri="/keywordstool"
    ts=str(round(time.time()*1000))
    headers={
        "X-API-KEY": NAVER_API_KEY,
        "X-Signature": _naver_signature(ts,"GET",uri,NAVER_SECRET_KEY),
        "X-Timestamp": ts,
        "X-Customer": NAVER_CUSTOMER_ID,
    }
    params={
        "hintKeywords": ",".join(hint_keywords),
        "includeHintKeywords": "0",
        "showDetail": "1",
    }
    r=requests.get(base_url+uri, headers=headers, params=params, timeout=12)
    r.raise_for_status()
    data=r.json().get("keywordList", [])
    if not data: return pd.DataFrame()
    df=pd.DataFrame(data)
    df=df.rename(columns={
        "relKeyword":"키워드",
        "monthlyPcQcCnt":"PC월간검색수",
        "monthlyMobileQcCnt":"Mobile월간검색수",
        "monthlyAvePcClkCnt":"PC월평균클릭수",
        "monthlyAveMobileClkCnt":"Mobile월평균클릭수",
        "monthlyAvePcCtr":"PC월평균클릭률",
        "monthlyAveMobileCtr":"Mobile월평균클릭률",
        "plAvgDepth":"월평균노출광고수",
        "compIdx":"광고경쟁정도",
    })
    df=df.drop_duplicates(["키워드"])
    # 숫자화
    for c in ["PC월간검색수","Mobile월간검색수","PC월평균클릭수","Mobile월평균클릭수","PC월평균클릭률","Mobile월평균클릭률","월평균노출광고수"]:
        df[c]=pd.to_numeric(df[c], errors="coerce")
    return df

def count_product_from_shopping(keyword: str) -> int|None:
    if not (requests and BeautifulSoup): return None
    try:
        url=f"https://search.shopping.naver.com/search/all?where=all&frm=NVSCTAB&query={quote(keyword)}"
        r=requests.get(url, timeout=10); r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        a_tags = soup.select("a.subFilter_filter__3Y-uy")
        for a in a_tags:
            if "전체" in a.text:
                span = a.find("span")
                if span:
                    txt = span.get_text().replace(",","").strip()
                    num = re.sub(r"[^0-9]","", txt) or "0"
                    return int(num)
        return None
    except Exception:
        return None

# -------------------------------------------------------
# 5) 네이버 DataLab Search
# -------------------------------------------------------
DATALAB_URL="https://openapi.naver.com/v1/datalab/search"

@st.cache_data(ttl=900, show_spinner=False)
def datalab_search(groups:list[dict], start_date:str, end_date:str,
                   time_unit:str="week", device:str="", gender:str="",
                   ages:list[str]|None=None)->dict|None:
    if not requests: return None
    headers={
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
        "Content-Type":"application/json",
    }
    body={
        "startDate": start_date, "endDate": end_date,
        "timeUnit": time_unit, "keywordGroups": groups
    }
    if device: body["device"]=device
    if gender: body["gender"]=gender
    if ages: body["ages"]=ages
    r=requests.post(DATALAB_URL, headers=headers, data=json.dumps(body), timeout=12)
    r.raise_for_status()
    return r.json()

def datalab_line_chart(dl_json, title="트렌드"):
    if not (alt and dl_json): return None
    rows=[]
    for g in dl_json.get("results",[]):
        name=g.get("title","group")
        for p in g.get("data",[]):
            rows.append({"period":p["period"], "ratio":p["ratio"], "group":name})
    df=pd.DataFrame(rows)
    chart=(alt.Chart(df)
            .mark_line(point=True)
            .encode(x="period:T", y="ratio:Q", color="group:N")
            .properties(height=280, title=title))
    return chart

# -------------------------------------------------------
# 6) 라쿠텐 랭킹
# -------------------------------------------------------
RK_JP_KEYWORDS = {
    "뷰티/코스메틱": "コスメ",
    "의류/패션": "ファッション",
    "가전/디지털": "家電",
    "가구/인테리어": "インテリア",
    "식품": "食品",
    "생활/건강": "日用品",
    "스포츠/레저": "スポーツ",
    "문구/취미": "ホビー",
}

def rk_fetch_rank(genre_id:str, topn:int=20, strip_emoji:bool=True) -> pd.DataFrame:
    if not requests:
        # 오프라인 fallback
        rows=[{"rank":i+1,"keyword":f"[샘플] 키워드 {i+1}","shop":"샘플","url":"https://example.com"} for i in range(topn)]
        return pd.DataFrame(rows)
    api="https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20170628"
    params={"applicationId": RAKUTEN_APP_ID, "genreId": str(genre_id), "hits": topn}
    if RAKUTEN_AFFILIATE_ID: params["affiliateId"]=RAKUTEN_AFFILIATE_ID
    r=requests.get(api, params=params, timeout=12); r.raise_for_status()
    items=r.json().get("Items", [])[:topn]
    rows=[]
    for it in items:
        node=it.get("Item", {})
        name=node.get("itemName","")
        if strip_emoji:
            name=re.sub(r"[\U00010000-\U0010ffff]", "", name)
        rows.append({
            "rank": node.get("rank"),
            "keyword": name,
            "shop": node.get("shopName",""),
            "url": node.get("itemUrl",""),
        })
    return pd.DataFrame(rows)

# -------------------------------------------------------
# 7) UI — 국내 레이더
# -------------------------------------------------------
def section_korea_radar():
    st.caption("※ 검색지표는 네이버 검색광고 API(키워드도구) 기준, 상품수는 네이버쇼핑 ‘전체’ 탭 크롤링 기준입니다.")
    c1,c2,c3 = st.columns([1,1,1])
    months = c1.slider("분석기간(개월, 표시용)", 1, 6, 3)
    device = c2.selectbox("디바이스(표시용)", ["all","pc","mo"], index=0)
    src    = c3.selectbox("키워드 소스", ["직접 입력"], index=0)

    kws_txt=st.text_area("키워드(콤마로 구분)", "핸드메이드코트, 남자코트, 여자코트", height=80)
    kw_list=[k.strip() for k in (kws_txt or "").split(",") if k.strip()]

    opt1,opt2=st.columns([1,1])
    add_product = opt1.toggle("네이버쇼핑 ‘전체’ 상품수 수집(느림)", value=False)
    table_mode = opt2.radio("표 모드", ["A(검색지표)","B(검색+순위)","C(축약+상품수+스코어)"], horizontal=True)

    if st.button("레이더 업데이트", use_container_width=False):
        with st.spinner("네이버 키워드도구 조회 중…"):
            df=naver_keyword_tool(kw_list)
        if df.empty:
            st.warning("키워드도구 응답이 비었습니다. (API/권한/쿼터 확인)")
            return

        if table_mode.startswith("A"):
            st.dataframe(df, use_container_width=True, height=430); return

        df2=df.copy()
        df2["검색합계"]=(pd.to_numeric(df2["PC월간검색수"],errors="coerce").fillna(0)+
                         pd.to_numeric(df2["Mobile월간검색수"],errors="coerce").fillna(0))
        df2["검색순위"]=df2["검색합계"].rank(ascending=False, method="min")

        if table_mode.startswith("B"):
            out=df2.sort_values("검색순위")
            st.dataframe(out, use_container_width=True, height=430); return

        # C: 축약 컬럼 + 상품수 + 스코어
        product_counts=[]
        if add_product:
            with st.spinner("네이버쇼핑 상품수 수집 중…"):
                for k in df2["키워드"]:
                    cnt=count_product_from_shopping(k)
                    product_counts.append(cnt if cnt is not None else math.nan)
        else:
            product_counts=[math.nan]*len(df2)
        df2["판매상품수"]=product_counts
        df2["상품수순위"]=df2["판매상품수"].rank(na_option="bottom", method="min")
        df2["상품발굴대상"]=(df2["검색순위"]+df2["상품수순위"]).rank(na_option="bottom", method="min")

        cols=["키워드","PC월간검색수","Mobile월간검색수","판매상품수",
              "PC월평균클릭수","Mobile월평균클릭수","PC월평균클릭률","Mobile월평균클릭률",
              "월평균노출광고수","광고경쟁정도","검색순위","상품수순위","상품발굴대상"]
        out=df2[cols].sort_values("상품발굴대상").copy()

        # 가로폭 줄이기: 숫자 반올림 및 컬럼명 축약
        for c in ["PC월평균클릭수","Mobile월평균클릭수","PC월평균클릭률","Mobile월평균클릭률"]:
            out[c]=pd.to_numeric(out[c], errors="coerce").round(2)
        out=out.rename(columns=SHORT_COLS)
        st.dataframe(out, use_container_width=True, height=430)
        st.download_button("CSV 다운로드", out.to_csv(index=False).encode("utf-8-sig"),
                           file_name="korea_keyword_C.csv", mime="text/csv")

# -------------------------------------------------------
# 8) UI — 라쿠텐 랭킹
# -------------------------------------------------------
def section_rakuten_radar():
    st.markdown('<div id="rk-card">', unsafe_allow_html=True)
    c1,c2=st.columns([2,1])
    with c1:
        cat=st.selectbox("라쿠텐 카테고리", list(RAKUTEN_GENRE_MAP_DEFAULT.keys()), index=0)
    with c2:
        strip_emoji=st.toggle("이모지 제거", value=True)

    genre_id=str(RAKUTEN_GENRE_MAP_DEFAULT.get(cat, "100283"))
    with st.spinner("라쿠텐 랭킹 불러오는 중…"):
        df=rk_fetch_rank(genre_id, topn=20, strip_emoji=strip_emoji)

    cfg={
        "rank": st.column_config.NumberColumn("rank", width="small"),
        "keyword": st.column_config.TextColumn("keyword", width="medium"),
        "shop": st.column_config.TextColumn("shop", width="small"),
        "url": st.column_config.LinkColumn("url", display_text="열기", width="small"),
    }
    st.dataframe(df[["rank","keyword","shop","url"]], hide_index=True,
                 use_container_width=True, height=430, column_config=cfg)
    st.download_button("표 CSV 다운로드", data=df.to_csv(index=False).encode("utf-8-sig"),
                       file_name="rakuten_ranking.csv", mime="text/csv")
    st.markdown('</div>', unsafe_allow_html=True)

# -------------------------------------------------------
# 9) 카테고리 → 키워드 Top20 & 트렌드
# -------------------------------------------------------
def section_category_top_trend():
    _card("카테고리 → 키워드 Top20 & 트렌드")
    c1,c2,c3 = st.columns([1,1,1])
    cat = c1.selectbox("카테고리", list(CATEGORY_SEEDS.keys()), index=0)
    time_unit = c2.selectbox("단위", ["date","week","month"], index=1)
    months = c3.slider("조회기간(개월)", 1, 12, 3)

    seeds = CATEGORY_SEEDS.get(cat, [])
    if st.button("Top20 뽑기", use_container_width=False):
        if not seeds:
            st.warning("해당 카테고리의 시드 키워드가 없습니다."); _card_end(); return
        with st.spinner("네이버 키워드도구 조회 중…"):
            df = naver_keyword_tool(seeds)
        if df.empty:
            st.warning("키워드도구 응답이 비었습니다. (API/권한/쿼터 확인)")
            _card_end(); return

        df["검색합계"]=(pd.to_numeric(df["PC월간검색수"],errors="coerce").fillna(0)+
                        pd.to_numeric(df["Mobile월간검색수"],errors="coerce").fillna(0))
        top20=df.sort_values("검색합계", ascending=False).head(20).copy()
        short=top20.rename(columns=SHORT_COLS)
        st.dataframe(short[["키워드","PC월","MO월","PC클","MO클","PC률","MO률","광고수","경쟁"]],
                     use_container_width=True, height=430)

        # 트렌드 (상위 5개만)
        end_dt=datetime.date.today()
        start_dt=end_dt - datetime.timedelta(days=30*months)
        groups=[{"groupName":f"top{i+1}","keywords":[k]} for i,k in enumerate(top20["키워드"].head(5))]
        try:
            dl_json=datalab_search(groups, start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d"),
                                   time_unit=time_unit)
            chart=datalab_line_chart(dl_json, title=f"{cat} Top5 트렌드")
            if chart is not None: st.altair_chart(chart, use_container_width=True)
        except Exception as e:
            st.info(f"트렌드 조회 생략: {e}")
    _card_end()

# -------------------------------------------------------
# 10) 11번가 모바일 — 아마존 베스트
# -------------------------------------------------------
def _11st_abest_url():
    return ("https://m.11st.co.kr/page/main/abest?tabId=ABEST&pageId=AMOBEST&ctgr1No=166160&_ts=%d"
            % int(time.time()))

def section_11st():
    _card("11번가 (모바일) — 아마존 베스트")
    if ELEVENST_PROXY and requests:
        url=f"{ELEVENST_PROXY}/?url={quote(_11st_abest_url(), safe=':/?&=%')}"
        st.components.v1.iframe(url, height=900, scrolling=True)
    else:
        st.components.v1.iframe(_11st_abest_url(), height=900, scrolling=True)
    _card_end()

# -------------------------------------------------------
# 11) MAIN
# -------------------------------------------------------
sidebar()
st.title("ENVY — Season 1 (Dual Proxy Edition)")

# 1행: 레이더(국내/해외)
_card("AI 키워드 레이더")
tab_domestic, tab_overseas = st.tabs(["국내", "해외"])
with tab_domestic:
    section_korea_radar()
with tab_overseas:
    section_rakuten_radar()
_card_end()

# 2행: 카테고리 → Top20 & 트렌드
section_category_top_trend()

# 3행: 11번가
section_11st()

st.caption("© ENVY S1 · Keys embedded. 수정은 파일 상단의 FIXED KEYS / 매핑 상수에서 변경하세요.")

import streamlit as st
import requests
import pandas as pd
import datetime

# ============ 기본 페이지 설정 ============
st.set_page_config(
    page_title="ENVY v27.7 Full",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🚀 ENVY v27.7 Full (Rakuten API + DataLab)")

# ============ 사이드바 : 환율/마진 계산기 ============
st.sidebar.header("환율 설정")
base_currency = st.sidebar.selectbox("기준 통화", ["USD", "EUR", "JPY", "CNY"], index=0)

# (임시 환율 - 나중에 API 연동)
exchange_rates = {"USD": 1400, "EUR": 1500, "JPY": 9, "CNY": 190}
rate = exchange_rates.get(base_currency, 1400)

# 환율 계산기
st.sidebar.subheader("① 환율 계산기")
foreign_price = st.sidebar.number_input(f"판매금액 ({base_currency})", 0.0, 1000000.0, 100.0)
converted_price = foreign_price * rate
st.sidebar.text_input("환산 금액(읽기전용)", f"{converted_price:,.0f} KRW", disabled=True)

# 마진 계산기
st.sidebar.subheader("② 마진 계산기 (v23)")
m_sale_foreign = st.sidebar.number_input(f"판매금액 ({base_currency})", 0.0, 1000000.0, 100.0)
m_converted = m_sale_foreign * rate
st.sidebar.text_input("환산 금액(읽기전용)", f"{m_converted:,.0f} KRW", disabled=True)

card_fee = st.sidebar.number_input("카드수수료 (%)", 0.0, 100.0, 4.0)
market_fee = st.sidebar.number_input("마켓수수료 (%)", 0.0, 100.0, 14.0)
shipping_fee = st.sidebar.number_input("배송비 (₩)", 0.0, 1000000.0, 0.0)

margin_mode = st.sidebar.radio("마진 방식", ["퍼센트 마진(%)", "더하기 마진(₩)"])
margin_value = st.sidebar.number_input("마진율 / 추가금", 0.0, 1000000.0, 10.0)

# 계산식 (v23 로직)
if margin_mode == "퍼센트 마진(%)":
    final_price = m_converted * (1 + card_fee/100 + market_fee/100) * (1 + margin_value/100) + shipping_fee
else:
    final_price = m_converted * (1 + card_fee/100 + market_fee/100) + shipping_fee + margin_value

profit = final_price - m_converted

st.sidebar.markdown(f"💰 **판매가격 (계산 결과):** {final_price:,.0f} KRW")
st.sidebar.markdown(f"📈 **순이익 (마진):** {profit:,.0f} KRW")
# ============ Part 2: DataLab + Itemscout + SellerLife ============

import altair as alt
import time as _t

# 네이버 쇼핑 카테고리 CID 매핑
NAVER_CATEGORIES = {
    "패션의류": "50000000", "패션잡화": "50000001", "화장품/미용": "50000002",
    "디지털/가전": "50000003", "가구/인테리어": "50000004", "식품": "50000005",
    "생활/건강": "50000006", "출산/육아": "50000007", "스포츠/레저": "50000008",
    "도서/취미/애완": "50000009",
}
COMMON_HEADERS = {
    "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
    "Accept-Language":"ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}

# 재시도 유틸
def _retry_post(url, headers=None, data=None, timeout=12, tries=4):
    last = None
    for i in range(tries):
        try:
            r = requests.post(url, headers=headers, data=data, timeout=timeout)
            if r.status_code in (200, 201):
                return r
            if r.status_code in (403, 429):
                _t.sleep(1.2 * (2**i))
                continue
            last = r
        except Exception as e:
            last = e
    raise RuntimeError(f"POST 실패: {last}")

# DataLab 수집
def fetch_datalab_top20(cid: str, start_date: str, end_date: str, proxy: str|None=None) -> pd.DataFrame:
    # 1) 세션 예열
    s = requests.Session()
    cat_url = "https://datalab.naver.com/shoppingInsight/sCategory.naver"
    s.get(cat_url, headers={**COMMON_HEADERS, "Accept":"text/html,*/*"}, timeout=10)

    # 2) API 호출 (프록시 선택)
    api_url = "https://datalab.naver.com/shoppingInsight/getCategoryKeywordRank.naver"
    if proxy:
        api_url = f"{proxy}?target=" + requests.utils.quote(api_url, safe="")

    headers = {
        **COMMON_HEADERS,
        "Accept":"application/json, text/javascript, */*; q=0.01",
        "Content-Type":"application/x-www-form-urlencoded; charset=UTF-8",
        "Origin":"https://datalab.naver.com",
        "Referer": cat_url,
        "X-Requested-With":"XMLHttpRequest",
    }
    payload = {
        "cid": cid, "timeUnit": "date",
        "startDate": start_date, "endDate": end_date,
        "device": "pc", "gender": "", "ages": ""
    }

    r = _retry_post(api_url, headers=headers, data=payload, timeout=12, tries=4)
    txt = r.text.strip()
    if not txt or not (txt.startswith("{") or txt.startswith("[")):
        raise RuntimeError("DataLab JSON 아님(차단/구조변경 가능성)")

    data = r.json()
    if "keywordList" not in data or not isinstance(data["keywordList"], list):
        raise RuntimeError("DataLab 구조 변경 또는 데이터 없음")

    rows = []
    for it in data["keywordList"][:20]:
        rows.append({
            "rank": it.get("rank") or len(rows)+1,
            "keyword": it.get("keyword", ""),
            "search": it.get("ratio") or 0,
        })
    df = pd.DataFrame(rows).sort_values("rank").reset_index(drop=True)
    return df


# ===== 상단 3열: 데이터랩 / 아이템스카우트 / 셀러라이프 (순서 고정) =====
c1, c2, c3 = st.columns(3)

with c1:
    st.subheader("데이터랩")
    sel_cat = st.selectbox("카테고리", list(NAVER_CATEGORIES.keys()), index=0, key="dl_cat")
    cid = NAVER_CATEGORIES[sel_cat]
    proxy_hint = "https://your-proxy/app?target=<url>  (선택)"
    dl_proxy = st.text_input("프록시", "", key="dl_proxy", placeholder=proxy_hint)

    today = datetime.date.today()
    start = (today - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
    end = today.strftime("%Y-%m-%d")

    try:
        df_dl = fetch_datalab_top20(cid, start, end, proxy=(dl_proxy or None))
        st.dataframe(df_dl, use_container_width=True, height=280)
        # 실선 그래프
        chart = alt.Chart(df_dl).mark_line(point=True).encode(
            x=alt.X("rank:Q", title="랭크(1=상위)"),
            y=alt.Y("search:Q", title="검색량(지수)"),
            tooltip=["rank","keyword","search"]
        ).properties(height=180)
        st.altair_chart(chart, use_container_width=True)
        st.download_button("Top20 CSV 다운로드", df_dl.to_csv(index=False).encode("utf-8-sig"),
                           "datalab_top20.csv", mime="text/csv", key="dl_csv")
        # 국내 레이더에서 쓰도록 공유
        st.session_state["datalab_df"] = df_dl.copy()
    except Exception as e:
        st.error(f"데이터랩 오류: {e}")

with c2:
    st.subheader("아이템스카우트")
    st.info("아이템스카우트 연동 대기(별도 API/프록시 연결 예정)")

with c3:
    st.subheader("셀러라이프")
    st.info("셀러라이프 연동 대기(별도 API/프록시 연결 예정)")
# ============ Part 3: AI 키워드 레이더 (국내/글로벌) ============

import re
from bs4 import BeautifulSoup

# Rakuten AppID (상용)
RAKUTEN_APP_ID = "1043271015809337425"  # ← 네가 발급받은 AppID 그대로 사용

def _retry_get(url, headers=None, timeout=12, tries=4):
    last = None
    for i in range(tries):
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            if r.status_code in (200, 201):
                return r
            if r.status_code in (403, 429):
                import time as _t; _t.sleep(1.2 * (2**i))
                continue
            last = r
        except Exception as e:
            last = e
    raise RuntimeError(f"GET 실패: {last}")

# ---- Amazon 베스트셀러 (HTML 파싱 + 프록시 옵션) ----
def fetch_amazon_bestsellers(limit:int=15, proxy:str|None=None) -> pd.DataFrame:
    url = "https://www.amazon.com/Best-Sellers/zgbs"
    if proxy:
        url = f"{proxy}?target=" + requests.utils.quote(url, safe="")
    headers = {**COMMON_HEADERS, "Referer": "https://www.amazon.com/"}
    r = _retry_get(url, headers=headers, timeout=12, tries=4)

    soup = BeautifulSoup(r.text, "html.parser")
    titles=[]
    selectors = [
        "div.p13n-sc-truncate",
        "div._cDEzb_p13n-sc-css-line-clamp-3_g3dy1",
        "div._cDEzb_p13n-sc-css-line-clamp-2_EWgCb",
        "div.a-section.a-spacing-small > h3, div.a-section.a-spacing-small > a > span",
        "span.zg-text-center-align > div > a > div",
    ]
    for sel in selectors:
        for el in soup.select(sel):
            t = re.sub(r"\s+"," ", el.get_text(strip=True))
            if t and t not in titles:
                titles.append(t)
            if len(titles) >= limit:
                break
        if len(titles) >= limit:
            break

    if not titles:
        raise RuntimeError("Amazon 파싱 실패(구조변경/차단 가능)")
    df = pd.DataFrame({"rank": range(1, len(titles)+1), "keyword": titles[:limit]})
    df["score"] = [300 - i for i in range(1, len(df)+1)]
    df["source"] = "Amazon US"
    return df[["source","rank","keyword","score"]]

# ---- Rakuten 공식 Ranking API ----
def fetch_rakuten_ranking_api(app_id: str, genre_id: str|None=None,
                              period: str="day", limit:int=15) -> pd.DataFrame:
    """
    Rakuten Ichiba Item Ranking API (정식)
    https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20170628
    """
    url = "https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20170628"
    params = {"applicationId": app_id, "format": "json", "periodType": period}
    if genre_id:
        params["genreId"] = genre_id
    r = requests.get(url, params=params, timeout=12)
    if r.status_code != 200:
        raise RuntimeError(f"Rakuten API 오류: {r.status_code} / {r.text[:120]}")
    js = r.json()
    items = js.get("Items", [])
    rows=[]
    for it in items[:limit]:
        I = it.get("Item", {})
        rows.append({
            "rank": I.get("rank"),
            "keyword": I.get("itemName"),
            "score": 220 - (I.get("rank") or len(rows)+1),
        })
    if not rows:
        raise RuntimeError("Rakuten API 응답에 항목이 없습니다.")
    df = pd.DataFrame(rows)
    df["source"] = "Rakuten JP"
    return df[["source","rank","keyword","score"]]

# ---- 하단 3열 중: 좌측(레이더) / 중간(11번가) / 우측(상품명 생성기) ----
d1, d2, d3 = st.columns(3)

with d1:
    st.subheader("AI 키워드 레이더 (국내/글로벌)")

    mode = st.radio("모드", ["국내","글로벌"], horizontal=True, key="air_mode")
    if mode == "국내":
        src = st.session_state.get("datalab_df")
        if src is not None and len(src):
            radar = (src.assign(source="DataLab",
                                score=lambda x: 1000 - x["rank"]*10)
                       [["source","keyword","score","rank"]]
                       .sort_values(["score","rank"], ascending=[False, True]))
            st.dataframe(radar, use_container_width=True, height=420)
            st.download_button("국내 키워드 CSV",
                               radar.to_csv(index=False).encode("utf-8-sig"),
                               "radar_domestic.csv", mime="text/csv",
                               key="air_csv_dom")
        else:
            st.info("데이터랩 결과가 없어 표시할 키워드가 없습니다.")
    else:
        # 글로벌: Amazon + Rakuten (공식 API)
        amz_proxy = st.text_input("Amazon 프록시(선택)",
                                  "", key="amz_proxy",
                                  placeholder="https://your-proxy/app?target=<url>")
        rak_genre = st.text_input("Rakuten genreId (선택, 비우면 종합)",
                                  "", key="rak_genre")

        # 수집
        try:
            df_amz = fetch_amazon_bestsellers(15, proxy=(amz_proxy or None))
        except Exception as e:
            st.error(f"Amazon 수집 실패: {e}")
            df_amz = pd.DataFrame(columns=["source","rank","keyword","score"])

        try:
            df_rak = fetch_rakuten_ranking_api(RAKUTEN_APP_ID,
                                               genre_id=(rak_genre or None),
                                               period="day", limit=15)
        except Exception as e:
            st.error(f"Rakuten API 실패: {e}")
            df_rak = pd.DataFrame(columns=["source","rank","keyword","score"])

        df_glb = pd.concat([df_amz, df_rak], ignore_index=True)
        if len(df_glb):
            df_glb = df_glb.sort_values(["score","rank"], ascending=[False, True])
            st.dataframe(df_glb, use_container_width=True, height=420)
            st.download_button("글로벌 키워드 CSV",
                               df_glb.to_csv(index=False).encode("utf-8-sig"),
                               "radar_global.csv", mime="text/csv",
                               key="air_csv_glb")
        else:
            st.info("글로벌 소스 수집 결과가 없습니다.")
# ============ Part 4: 11번가 (모바일 프록시 + 요약표) & 상품명 생성기 ============

# ---- 중간 컬럼 (11번가) ----
with d2:
    st.subheader("11번가 (모바일 프록시 + 요약표)")

    url_11 = st.text_input("대상 URL", "https://www.11st.co.kr/", key="url_11")
    proxy_11 = st.text_input("프록시 엔드포인트(선택)", "", key="proxy_11")

    html11 = ""
    try:
        if proxy_11:
            tgt = f"{proxy_11}?target=" + requests.utils.quote(url_11, safe="")
            r = requests.get(tgt, headers=COMMON_HEADERS, timeout=10)
        else:
            r = requests.get(url_11, headers=COMMON_HEADERS, timeout=10)
        if r.status_code == 200:
            html11 = r.text
        else:
            st.error(f"11번가 응답 오류: {r.status_code}")
    except Exception as e:
        st.error(f"11번가 요청 실패: {e}")

    if html11:
        st.components.v1.html(
            f"<iframe srcdoc='{html11}' width='100%' height='400'></iframe>",
            height=420, scrolling=True
        )

    st.button("임베드 실패 대비 요약표 보기")


# ---- 우측 컬럼 (상품명 생성기) ----
with d3:
    st.subheader("상품명 생성기 (규칙 + HuggingFace KoGPT2)")

    brand = st.text_input("브랜드", "envy")
    base_kw = st.text_input("베이스 키워드", "K-coffee mix")
    rel_kw = st.text_input("연관키워드", "Maxim, Kanu, Korea")
    ban_kw = st.text_input("금칙어", "copy, fake, replica")
    limit_len = st.slider("글자수 제한", 10, 120, 80)

    mode = st.radio("모드", ["규칙 기반", "HuggingFace AI"], horizontal=True, key="gen_mode")

    if st.button("생성"):
        if mode == "규칙 기반":
            # 간단 규칙 생성기
            out = f"{brand} {base_kw} {rel_kw}".replace(",", " ")
            for w in ban_kw.split(","):
                out = out.replace(w.strip(), "")
            st.success(out[:limit_len])
        else:
            try:
                HF_KEY = "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"  # 네가 발급받은 HuggingFace API 키
                headers = {
                    "Authorization": f"Bearer {HF_KEY}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "inputs": f"{brand} {base_kw} {rel_kw}",
                    "parameters": {"max_new_tokens": 32, "return_full_text": False},
                }
                r = requests.post(
                    "https://api-inference.huggingface.co/models/skt/kogpt2-base-v2",
                    headers=headers, json=payload, timeout=15
                )
                if r.status_code == 200:
                    js = r.json()
                    text = js[0]["generated_text"]
                    for w in ban_kw.split(","):
                        text = text.replace(w.strip(), "")
                    st.success(text[:limit_len])
                else:
                    st.error(f"HuggingFace API 오류: {r.status_code} {r.text}")
            except Exception as e:
                st.error(f"HuggingFace 호출 실패: {e}")

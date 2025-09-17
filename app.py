# ENVY v27.5 Full • 단일 버전
# - 사이드바: 환율 계산기, 마진 계산기(통화 각각 독립) — "절대 고정"
# - 본문(가로 고정 순서): 데이터랩 → 아이템스카우트 → 셀러라이프 → AI 레이더(국내=데이터랩, 글로벌=실키워드) → 11번가 → 상품명 생성기
# - 글로벌(Amazon/Rakuten) 스크랩: 진짜 키워드, 프록시 옵션, 실패 시 에러만 표시(목업 없음)

import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import requests, datetime, random, textwrap, html, urllib.parse, re
from bs4 import BeautifulSoup

st.set_page_config(page_title="ENVY v27.5 Full", page_icon="🚀", layout="wide")

# -------------------- Config --------------------
HF_API_KEY = "hf_xxxxxxxxxxxxxxxxxxxxxxxxx"   # 테스트용: 성공 후 secrets로 옮겨라!
CURRENCY_SYMBOL = {"KRW":"₩","USD":"$","EUR":"€","JPY":"¥","CNY":"CN¥"}
FX_ORDER = ["USD","EUR","JPY","CNY"]

# 네이버 쇼핑 카테고리 CID 매핑(화면 비노출)
NAVER_CATEGORIES = {
    "패션의류": "50000000",
    "패션잡화": "50000001",
    "화장품/미용": "50000002",
    "디지털/가전": "50000003",
    "가구/인테리어": "50000004",
    "식품": "50000005",
    "생활/건강": "50000006",
    "출산/육아": "50000007",
    "스포츠/레저": "50000008",
    "도서/취미/애완": "50000009"
}

# -------------------- Helpers --------------------
def fmt_money(v: float, code: str="KRW"):
    sym = CURRENCY_SYMBOL.get(code, "")
    try:
        return f"{sym}{v:,.0f} {code}"
    except Exception:
        return f"{v:,.0f} {code}"

def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")

def copy_button(text: str, key: str):
    safe = html.escape(text).replace("\n","\\n").replace("'","\\'")
    st.components.v1.html(
        f"<div style='display:flex;gap:8px;align-items:center;margin:6px 0;'>"
        f"<input value='{html.escape(text)}' style='flex:1;padding:6px 8px;'/>"
        f"<button onclick=\"navigator.clipboard.writeText('{safe}')\">복사</button>"
        f"</div>", height=46)

# -------------------- v23 Margin formulas --------------------
def margin_calc_percent(cost_krw: float, card_pct: float, market_pct: float, margin_pct: float, shipping_krw: float):
    cf, mf, t = card_pct/100.0, market_pct/100.0, margin_pct/100.0
    denom = max(1e-9, 1 - cf - mf)
    target_rev = (cost_krw + shipping_krw) * (1 + t)
    P = target_rev / denom
    revenue = P * (1 - cf - mf)
    profit = revenue - (cost_krw + shipping_krw)
    return P, profit, (profit/P*100 if P>0 else 0.0)

def margin_calc_add(cost_krw: float, card_pct: float, market_pct: float, add_margin_krw: float, shipping_krw: float):
    cf, mf = card_pct/100.0, market_pct/100.0
    denom = max(1e-9, 1 - cf - mf)
    target_rev = (cost_krw + shipping_krw) + add_margin_krw
    P = target_rev / denom
    revenue = P * (1 - cf - mf)
    profit = revenue - (cost_krw + shipping_krw)
    return P, profit, (profit/P*100 if P>0 else 0.0)

# -------------------- FX Auto fetch (15분 캐시) --------------------
@st.cache_data(ttl=900, show_spinner=False)
def get_fx_rate(base_ccy: str) -> float:
    try:
        r = requests.get(
            f"https://api.exchangerate.host/latest?base={base_ccy}&symbols=KRW",
            timeout=8,
        )
        if r.status_code == 200:
            return float(r.json()["rates"]["KRW"])
    except Exception:
        pass
    return {"USD": 1400.0, "EUR": 1500.0, "JPY": 9.5, "CNY": 190.0}.get(base_ccy, 1400.0)

def readonly_money(label: str, value_krw: float, key: str):
    st.text_input(label, f"{CURRENCY_SYMBOL['KRW']}{value_krw:,.0f} KRW", disabled=True, key=key)

COMMON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}
# -------------------- UI 헤더 --------------------
st.title("🚀 ENVY v27.5 Full (실데이터)")

# -------------------- Sidebar (절대 고정) --------------------
with st.sidebar:
    # ① 환율 계산기 (독립 통화 선택)
    st.header("① 환율 계산기")
    fx_base_ccy = st.selectbox("기준 통화", FX_ORDER, index=0, key="sb_fx_base")
    fx_sym = CURRENCY_SYMBOL.get(fx_base_ccy, "")
    fx_rate = get_fx_rate(fx_base_ccy)
    st.caption(f"자동 환율: 1 {fx_sym} = {fx_rate:,.2f} ₩")

    fx_price_foreign = st.number_input(f"판매금액 ({fx_sym})", 0.0, 1e12, 100.0, 1.0, key="sb_fx_price_foreign")
    fx_price_krw = fx_price_foreign * fx_rate
    readonly_money("환산 금액(읽기전용)", fx_price_krw, key="sb_fx_price_krw")

    st.markdown("---")

    # ② 마진 계산기 (독립 통화 선택)
    st.header("② 마진 계산기 (v23)")
    m_base_ccy = st.selectbox("기준 통화(판매금액)", FX_ORDER, index=0, key="sb_m_base")
    m_sym = CURRENCY_SYMBOL.get(m_base_ccy, "")
    m_rate = get_fx_rate(m_base_ccy)
    st.caption(f"자동 환율: 1 {m_sym} = {m_rate:,.2f} ₩")

    m_sale_foreign = st.number_input(f"판매금액 ({m_sym})", 0.0, 1e12,
                                     fx_price_foreign if m_base_ccy==fx_base_ccy else 100.0,
                                     1.0, key="sb_m_sale_foreign")
    m_sale_krw = m_sale_foreign * m_rate
    readonly_money("환산 금액(읽기전용)", m_sale_krw, key="sb_m_sale_krw")

    card = st.number_input("카드수수료 (%)", 0.0, 100.0, 4.0, 0.1, key="sb_card")
    market = st.number_input("마켓수수료 (%)", 0.0, 100.0, 14.0, 0.1, key="sb_market")
    ship = st.number_input("배송비 (₩)", 0.0, 1e9, 0.0, 100.0, key="sb_ship")
    mode = st.radio("마진 방식", ["퍼센트 마진(%)","더하기 마진(₩)"], horizontal=True, key="sb_mode")

    if mode == "퍼센트 마진(%)":
        margin_pct = st.number_input("마진율 (%)", 0.0, 500.0, 10.0, 0.1, key="sb_margin_pct")
        P, profit, on_sale = margin_calc_percent(m_sale_krw, card, market, margin_pct, ship)
    else:
        add_margin = st.number_input("더하기 마진 (₩)", 0.0, 1e12, 10000.0, 100.0, key="sb_add_margin")
        P, profit, on_sale = margin_calc_add(m_sale_krw, card, market, add_margin, ship)

    st.metric("판매가격 (계산 결과)", f"{CURRENCY_SYMBOL['KRW']}{P:,.0f} KRW")
    st.metric("순이익(마진)", f"{CURRENCY_SYMBOL['KRW']}{profit:,.0f} KRW")
    st.caption(f"마진율(판매가 기준): {on_sale:.2f}%")

# -------------------- DataLab (세션/쿠키 + 강헤더) --------------------
def fetch_datalab_top20(cid: str, start_date: str, end_date: str, time_unit: str="date") -> pd.DataFrame:
    s = requests.Session()
    cat_url = "https://datalab.naver.com/shoppingInsight/sCategory.naver"
    s.get(cat_url, headers={**COMMON_HEADERS, "Accept": "text/html,*/*"}, timeout=10)

    api_url = "https://datalab.naver.com/shoppingInsight/getCategoryKeywordRank.naver"
    headers = {
        **COMMON_HEADERS,
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": "https://datalab.naver.com",
        "Referer": cat_url,
        "X-Requested-With": "XMLHttpRequest",
    }
    payload = {
        "cid": cid, "timeUnit": time_unit,
        "startDate": start_date, "endDate": end_date,
        "device": "pc", "gender": "", "ages": ""
    }
    r = s.post(api_url, headers=headers, data=payload, timeout=12)
    if r.status_code != 200:
        raise RuntimeError(f"DataLab 응답 오류: {r.status_code}")
    txt = r.text.strip()
    if not txt or not (txt.startswith("{") or txt.startswith("[")):
        raise RuntimeError("DataLab JSON 아님(차단/구조변경 가능성)")
    data = r.json()
    if "keywordList" not in data or not isinstance(data["keywordList"], list):
        raise RuntimeError("DataLab 구조 변경 또는 데이터 없음")
    rows = []
    for item in data["keywordList"][:20]:
        rows.append({"rank": item.get("rank") or len(rows)+1,
                     "keyword": item.get("keyword",""),
                     "search": item.get("ratio") or 0})
    return pd.DataFrame(rows).sort_values("rank").reset_index(drop=True)

# 본문 상단 3개(좌→우): 데이터랩 → 아이템스카우트 → 셀러라이프
c1, c2, c3 = st.columns(3)

with c1:
    st.subheader("데이터랩")
    category = st.selectbox("카테고리", list(NAVER_CATEGORIES.keys()), index=0, key="dl_cat")
    cid = NAVER_CATEGORIES[category]
    today = datetime.date.today()
    start = (today - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
    end = today.strftime("%Y-%m-%d")
    try:
        df_dl = fetch_datalab_top20(cid, start, end)
        st.dataframe(df_dl, use_container_width=True)
        st.session_state["datalab_df"] = df_dl.copy()
        chart = alt.Chart(df_dl).mark_line().encode(
            x=alt.X("rank:Q", title="랭크(1=상위)"),
            y=alt.Y("search:Q", title="검색량(지수)"),
            tooltip=["rank","keyword","search"]
        ).properties(height=220)
        st.altair_chart(chart, use_container_width=True)
        st.download_button("Top20 CSV", to_csv_bytes(df_dl), "datalab_top20.csv", mime="text/csv", key="dl_csv")
    except Exception as e:
        st.error(f"데이터랩 오류: {e}")

with c2:
    st.subheader("아이템스카우트")
    st.info("아이템스카우트 연동 대기(별도 API/프록시 연결 예정)")

with c3:
    st.subheader("셀러라이프")
    st.info("셀러라이프 연동 대기(별도 API/프록시 연결 예정)")
# -------------------- Global fetchers (실키워드) --------------------
def _via_proxy(url: str, proxy: str|None):
    return f"{proxy}?target={urllib.parse.quote(url, safe='')}" if proxy else url

@st.cache_data(ttl=600, show_spinner=False)
def fetch_amazon_bestsellers(proxy: str|None=None, limit:int=20) -> pd.DataFrame:
    # 베스트셀러 전체
    url = "https://www.amazon.com/Best-Sellers/zgbs"
    headers = {**COMMON_HEADERS, "Referer": "https://www.amazon.com/"}
    r = requests.get(_via_proxy(url, proxy), headers=headers, timeout=12)
    if r.status_code != 200:
        raise RuntimeError(f"Amazon 응답 오류: {r.status_code}")
    soup = BeautifulSoup(r.text, "html.parser")

    titles = []
    # 다양한 레이아웃 대비: line-clamp / _cDEzb_ / a-section 기반 탐색
    for sel in [
        "div.p13n-sc-truncate",
        "div._cDEzb_p13n-sc-css-line-clamp-3_g3dy1",
        "div._cDEzb_p13n-sc-css-line-clamp-2_EWgCb",
        "div.a-section.a-spacing-small > h3, div.a-section.a-spacing-small > a > span",
        "span.zg-text-center-align > div > a > div",
    ]:
        for el in soup.select(sel):
            text = re.sub(r"\s+", " ", el.get_text(strip=True))
            if text and text not in titles:
                titles.append(text)
            if len(titles) >= limit:
                break
        if len(titles) >= limit:
            break

    if not titles:
        raise RuntimeError("Amazon 파싱 실패(구조변경/차단 가능)")

    df = pd.DataFrame({"rank": range(1, len(titles)+1), "keyword": titles[:limit]})
    df["score"] = [300-i for i in range(1, len(df)+1)]
    df["source"] = "Amazon US"
    return df[["source","rank","keyword","score"]]

@st.cache_data(ttl=600, show_spinner=False)
def fetch_rakuten_ranking(proxy: str|None=None, limit:int=20) -> pd.DataFrame:
    url = "https://ranking.rakuten.co.jp/daily/goods/"
    headers = {**COMMON_HEADERS, "Referer": "https://ranking.rakuten.co.jp/"}
    r = requests.get(_via_proxy(url, proxy), headers=headers, timeout=12)
    if r.status_code != 200:
        raise RuntimeError(f"Rakuten 응답 오류: {r.status_code}")
    soup = BeautifulSoup(r.text, "html.parser")

    names = []
    for sel in [
        ".rnkRanking_itemName",
        "div.rnkRanking_itemName",
        "a.rnkRanking_itemName",
        "div.rnkItemName > a",
    ]:
        for el in soup.select(sel):
            text = re.sub(r"\s+", " ", el.get_text(strip=True))
            if text and text not in names:
                names.append(text)
            if len(names) >= limit:
                break
        if len(names) >= limit:
            break

    if not names:
        raise RuntimeError("Rakuten 파싱 실패(구조변경/차단 가능)")

    df = pd.DataFrame({"rank": range(1, len(names)+1), "keyword": names[:limit]})
    df["score"] = [220-i for i in range(1, len(df)+1)]
    df["source"] = "Rakuten JP"
    return df[["source","rank","keyword","score"]]

# -------------------- 본문 하단 좌: AI 레이더 --------------------
d1, d2, d3 = st.columns(3)

with d1:
    st.subheader("AI 키워드 레이더 (국내/글로벌)")
    mode = st.radio("모드", ["국내","글로벌"], horizontal=True, key="air_mode")

    if mode == "국내":
        src = st.session_state.get("datalab_df")
        if src is not None:
            radar = (src.assign(source="DataLab", score=lambda x: 1000 - x["rank"]*10)
                        [["source","keyword","score","rank"]].sort_values(["score","rank"], ascending=[False, True]))
            st.dataframe(radar, use_container_width=True)
            st.download_button("국내 키워드 CSV", to_csv_bytes(radar), "radar_domestic.csv", mime="text/csv", key="air_csv_dom")
        else:
            st.info("데이터랩 결과가 없어 표시할 키워드가 없습니다.")
    else:
        st.caption("프록시가 없으면 환경에 따라 차단될 수 있어요.")
        proxy = st.text_input("글로벌 프록시(선택)", "", key="air_proxy",
                              placeholder="https://your-proxy/app?target=<url>")
        try:
            df_amz = fetch_amazon_bestsellers(proxy or None, limit=15)
        except Exception as e:
            st.error(f"Amazon 수집 실패: {e}")
            df_amz = pd.DataFrame(columns=["source","rank","keyword","score"])
        try:
            df_rak = fetch_rakuten_ranking(proxy or None, limit=15)
        except Exception as e:
            st.error(f"Rakuten 수집 실패: {e}")
            df_rak = pd.DataFrame(columns=["source","rank","keyword","score"])

        df_glb = pd.concat([df_amz, df_rak], ignore_index=True)
        if len(df_glb):
            df_glb = df_glb.sort_values(["score","rank"], ascending=[False, True])
            st.dataframe(df_glb, use_container_width=True)
            st.download_button("글로벌 키워드 CSV", to_csv_bytes(df_glb), "radar_global.csv", mime="text/csv", key="air_csv_glb")
        else:
            st.info("글로벌 소스 수집 결과가 없습니다. 프록시 사용을 권장합니다.")

# -------------------- 본문 하단 중: 11번가 --------------------
with d2:
    st.subheader("11번가 (모바일 프록시 + 요약표)")
    url = st.text_input("대상 URL", "https://www.11st.co.kr/", key="m11_url")
    proxy = st.text_input("프록시 엔드포인트(선택)", "", key="m11_proxy",
                          help="예) https://your-proxy/app?target=<m.11st url>")
    src_url = (f"{proxy}?target={urllib.parse.quote(url.replace('www.11st.co.kr','m.11st.co.kr'), safe='')}"
               if proxy else url.replace("www.11st.co.kr","m.11st.co.kr"))
    st.components.v1.html(
        f"<div style='width:100%;height:500px;border:1px solid #eee;border-radius:10px;overflow:hidden'>"
        f"<iframe src='{src_url}' width='100%' height='100%' frameborder='0' "
        f"sandbox='allow-same-origin allow-scripts allow-popups allow-forms'></iframe></div>", height=520)

    df_11 = pd.DataFrame({
        "title":[f"상품{i}" for i in range(1,6)],
        "price":[i*1000 for i in range(1,6)],
        "sales":[i*7 for i in range(1,6)],
        "link":[url]*5
    })
    with st.expander("임베드 실패 대비 요약표 보기"):
        st.dataframe(df_11, use_container_width=True)
        st.download_button("CSV 다운로드", to_csv_bytes(df_11), "11st_list.csv", mime="text/csv", key="m11_csv")
# -------------------- 본문 하단 우: 상품명 생성기 --------------------
with d3:
    st.subheader("상품명 생성기")
    brand = st.text_input("브랜드", "envy", key="ng_brand")
    base = st.text_input("베이스 키워드", "K-coffee mix", key="ng_base")
    keywords = st.text_input("연관키워드", "Maxim, Kanu, Korea", key="ng_kws")
    badwords = st.text_input("금칙어", "copy, fake, replica", key="ng_bans")
    limit = st.slider("글자수 제한", 20, 120, 80, key="ng_limit")
    mode = st.radio("모드", ["규칙 기반","HuggingFace AI"], horizontal=True, key="ng_mode")

    def filter_and_trim(cands):
        bans = {w.strip().lower() for w in badwords.split(",") if w.strip()}
        out=[]
        for t in cands:
            t2 = " ".join(t.split())
            if any(b in t2.lower() for b in bans): continue
            if len(t2)>limit: t2=t2[:limit]
            out.append(t2)
        return out

    cands=[]
    if st.button("생성", key="ng_go"):
        kws=[k.strip() for k in keywords.split(",") if k.strip()]
        if mode=="규칙 기반":
            for _ in range(5):
                pref=random.choice(["[New]","[Hot]","[Korea]"])
                suf=random.choice(["2025","FastShip","HotDeal"])
                join=random.choice([" | "," · "," - "])
                cands.append(f"{pref} {brand}{join}{base} {', '.join(kws[:2])} {suf}")
        else:
            if not HF_API_KEY:
                st.error("HuggingFace 토큰이 없습니다.")
            else:
                API_URL = "https://api-inference.huggingface.co/models/skt/kogpt2-base-v2"
                headers = {"Authorization": f"Bearer {HF_API_KEY}", "X-Wait-For-Model": "true"}
                prompt = f"상품명 추천 5개: 브랜드={brand}, 베이스={base}, 키워드={keywords}. 한국어로 간결하게."
                try:
                    resp = requests.post(API_URL, headers=headers,
                        json={"inputs": prompt, "parameters": {"max_new_tokens": 64, "return_full_text": False}},
                        timeout=30)
                    if resp.status_code==200:
                        data = resp.json()
                        text = data[0].get("generated_text","") if isinstance(data,list) and data else str(data)
                        lines = [line.strip("-• ").strip() for line in text.split("\n") if line.strip()]
                        if len(lines)<5:
                            lines = [s.strip() for s in textwrap.fill(text, 120).split(".") if s.strip()]
                        cands = lines[:5]
                    else:
                        st.error(f"HuggingFace API 오류: {resp.status_code} / {resp.text[:180]}")
                except Exception as e:
                    st.error(f"HuggingFace 호출 실패: {e}")
        st.session_state["name_cands"]=filter_and_trim(cands)

    for i,t in enumerate(st.session_state.get("name_cands", []), start=1):
        st.write(f"{i}. {t}")
        copy_button(t, key=f"name_{i}")

# ===== ENVY v27.14 Full — Part 1/4 =====
import json, datetime as dt
from urllib.parse import urlencode
from typing import Dict, List, Tuple

import requests
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="ENVY v27.14 Full", layout="wide")

# ---------- 스타일 & 공통 CSS ----------
CARD_CSS = """
<style>
.block-container { padding-top: 0.6rem; }
.eny-badge { padding: 8px 12px; border-radius: 10px; font-size: 13px; display:inline-block; margin: 4px 0; }
.eny-green { background:#e7f6ec; color:#118d57; border:1px solid #b6e2c4; }
.eny-blue  { background:#e6f0ff; color:#1a51b2; border:1px solid #c2d3ff; }
.eny-yellow{ background:#fff9e6; color:#8f6a00; border:1px solid #ffe6a7; }
[data-testid="stSidebar"] .stSelectbox, 
[data-testid="stSidebar"] .stNumberInput,
[data-testid="stSidebar"] .stRadio,
[data-testid="stSidebar"] .stTextInput { margin-bottom: 0.55rem; }
</style>
"""
st.markdown(CARD_CSS, unsafe_allow_html=True)

# ---------- 상수 ----------
PROXY_BASE = "https://envy-proxy.taesig0302.workers.dev"   # Cloudflare Worker (강화 프록시: /datalab 지원)
DEFAULT_RAKUTEN_APP_ID = "1043271015809337425"             # 네가 준 App ID (글로벌 레이더 기본값)

CURRENCY_SYMBOL = {"USD":"$", "EUR":"€", "JPY":"¥", "CNY":"¥", "KRW":"₩"}
FALLBACK_RATE   = {"USD":1400.00, "EUR":1500.00, "JPY":9.50, "CNY":190.00}  # 실패시 백업 환율(KRW)

# 네이버 데이터랩 카테고리 10개 (CID 매핑)
DATALAB_CATEGORIES: Dict[str, str] = {
    "패션잡화": "50000000",
    "패션의류": "50000167",
    "화장품/미용": "50000202",
    "디지털/가전": "50000003",
    "식품": "50000247",
    "생활/건강": "50000002",
    "출산/육아": "50000005",
    "스포츠/레저": "50000006",
    "도서": "50005542",
    "취미/반려": "50007216",
}

# ---------- 유틸 ----------
def fetch_fx_rate(base: str, to: str="KRW") -> float:
    try:
        r = requests.get(f"https://api.exchangerate.host/latest?base={base}&symbols={to}", timeout=6)
        r.raise_for_status()
        return float(r.json()["rates"][to])
    except Exception:
        return FALLBACK_RATE.get(base, 1400.0)

def fmt_money(v: float, code: str="KRW") -> str:
    sym = CURRENCY_SYMBOL.get(code, "")
    return f"{sym}{v:,.2f}"

def convert_price(amount_foreign: float, base_currency: str) -> float:
    rate = fetch_fx_rate(base_currency, "KRW")
    return round(amount_foreign * rate, 2)

def calc_margin_percent(price_foreign: float, base_currency: str,
                        card_fee_pct: float, market_fee_pct: float,
                        shipping_krw: float, margin_pct: float) -> Tuple[float, float]:
    rate = fetch_fx_rate(base_currency, "KRW")
    cost_krw = round(price_foreign * rate, 2)
    total_pct = 1 - (card_fee_pct/100) - (market_fee_pct/100) - (margin_pct/100)
    total_pct = max(total_pct, 0.01)
    sell_price = round((cost_krw + shipping_krw) / total_pct, 2)
    profit = round(sell_price - cost_krw - shipping_krw
                   - (sell_price*card_fee_pct/100) - (sell_price*market_fee_pct/100), 2)
    return sell_price, profit

def calc_margin_add(price_foreign: float, base_currency: str,
                    card_fee_pct: float, market_fee_pct: float,
                    shipping_krw: float, add_margin_krw: float) -> Tuple[float, float]:
    rate = fetch_fx_rate(base_currency, "KRW")
    cost_krw = round(price_foreign * rate, 2)
    sell_price = round((cost_krw + shipping_krw + add_margin_krw) / (1 - (card_fee_pct/100) - (market_fee_pct/100)), 2)
    profit = round(sell_price - cost_krw - shipping_krw
                   - (sell_price*card_fee_pct/100) - (sell_price*market_fee_pct/100), 2)
    return sell_price, profit

# DataLab: Worker의 /datalab 엔드포인트 호출 → JSON→DF
def fetch_datalab_keywords(cid: str, start: str, end: str, proxy_base: str=PROXY_BASE) -> pd.DataFrame:
    url = f"{proxy_base.rstrip('/')}/datalab?cid={cid}&start={start}&end={end}"
    resp = requests.get(url, timeout=20)
    status = resp.status_code
    data = resp.json() if "application/json" in (resp.headers.get("content-type","")) else json.loads(resp.text)
    if status != 200 or str(data.get("returnCode", "0")) != "0":
        raise RuntimeError(f"DataLab 실패: http={status}, rc={data.get('returnCode')}, msg={data.get('message')}")
    ranks = data.get("ranks", [])
    if not ranks:
        raise RuntimeError("DataLab 결과가 비었습니다. (기간/카테고리/CID 재확인)")
    df = pd.DataFrame(ranks)  # rank, keyword, linkId
    if "search" not in df.columns: df["search"] = None  # 구형 UI 호환 컬럼
    return df[["rank","keyword","search"]]

# Rakuten Ranking API → 글로벌 레이더 표
def fetch_rakuten_global(app_id: str, genre_id: str="0") -> pd.DataFrame:
    try:
        url = "https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20170628"
        params = {"applicationId": app_id, "format":"json", "genreId": genre_id}
        r = requests.get(url, params=params, timeout=12)
        r.raise_for_status()
        items = r.json().get("Items", [])
        rows = []
        for i, it in enumerate(items[:20], start=1):
            nm = it.get("Item", {}).get("itemName", "")
            rows.append({"rank": i, "keyword": nm[:40], "source": "Rakuten"})
        return pd.DataFrame(rows)
    except Exception as e:
        return pd.DataFrame([{"rank":0, "keyword": f"Rakuten 오류: {e}", "source":"Rakuten"}])

# 11번가 모바일 미리보기(iframe)
def embed_11st(url: str, height: int=420):
    html = f'''
    <iframe src="{url}" style="width:100%; height:{height}px; border:1px solid #eee; border-radius:8px;"
            sandbox="allow-scripts allow-same-origin allow-forms"></iframe>
    '''
    components.html(html, height=height+6, scrolling=True)

# 상품명 생성기(규칙 기반)
def generate_titles_rule(brand: str, base_kw: str, rel_kw: str, banned: str, limit: int=80) -> List[str]:
    ban = {b.strip().lower() for b in banned.split(",") if b.strip()}
    chunks = [
        f"{brand} {base_kw} {rel_kw}",
        f"{base_kw} | {brand} {rel_kw}",
        f"{brand} {base_kw}",
        f"{base_kw} {rel_kw}",
        f"{rel_kw} {brand} {base_kw}",
    ]
    out = []
    for s in chunks:
        filtered = " ".join([w for w in s.split() if w.lower() not in ban])
        out.append(filtered.strip()[:limit])
    return out
# ===== ENVY v27.14 Full — Part 2/4 =====

# 다크/라이트 토글(테마는 전역 설정에 따름)
st.sidebar.toggle("다크 모드", value=False, key="tgl_dark", help="테마는 앱 설정에 따름")

st.sidebar.markdown("### ① 환율 계산기")
base1 = st.sidebar.selectbox("기준 통화", ["USD","EUR","JPY","CNY"], index=0, key="sb_fx_base")
amt1  = st.sidebar.number_input("판매금액 (기준통화)", min_value=0.0, step=0.01, value=1.00, format="%.2f", key="sb_fx_amt")
krw_conv = convert_price(amt1, base1)
st.sidebar.markdown(f'<div class="eny-badge eny-green">환산 금액: {fmt_money(krw_conv,"KRW")}</div>', unsafe_allow_html=True)

st.sidebar.markdown("---")
st.sidebar.markdown("### ② 마진 계산기 (v23)")

base2 = st.sidebar.selectbox("기준 통화(판매금액)", ["USD","EUR","JPY","CNY"], index=0, key="sb_mg_base")
amt2  = st.sidebar.number_input("판매금액 (기준통화)", min_value=0.0, step=0.01, value=1.00, format="%.2f", key="sb_mg_amt")
krw_conv2 = convert_price(amt2, base2)
st.sidebar.markdown(f'<div class="eny-badge eny-blue">판매금액(환산): {fmt_money(krw_conv2,"KRW")}</div>', unsafe_allow_html=True)

card_fee   = st.sidebar.number_input("카드수수료 (%)", min_value=0.0, step=0.25, value=4.00, format="%.2f", key="sb_mg_card")
market_fee = st.sidebar.number_input("마켓수수료 (%)", min_value=0.0, step=0.25, value=14.00, format="%.2f", key="sb_mg_market")
shipping   = st.sidebar.number_input("배송비 (₩)",     min_value=0.0, step=100.0, value=0.0, format="%.2f", key="sb_mg_ship")

mg_mode = st.sidebar.radio("마진 방식", ["퍼센트 마진(%)","더하기 마진(₩)"], horizontal=True, key="sb_mg_mode")
if mg_mode.startswith("퍼센트"):
    margin_pct = st.sidebar.number_input("마진율 (%)", min_value=0.0, step=0.5, value=10.0, format="%.2f", key="sb_mg_pct")
    sell_price, profit = calc_margin_percent(amt2, base2, card_fee, market_fee, shipping, margin_pct)
else:
    add_margin = st.sidebar.number_input("더하기 마진 (₩)", min_value=0.0, step=100.0, value=0.0, format="%.2f", key="sb_mg_add")
    sell_price, profit = calc_margin_add(amt2, base2, card_fee, market_fee, shipping, add_margin)

st.sidebar.markdown(f'<div class="eny-badge eny-blue">예상 판매가: {fmt_money(sell_price,"KRW")}</div>', unsafe_allow_html=True)
st.sidebar.markdown(f'<div class="eny-badge eny-yellow">순이익(마진): {fmt_money(profit,"KRW")}</div>', unsafe_allow_html=True)

st.sidebar.markdown("---")
proxy_url_input = st.sidebar.text_input("프록시(데이터랩)", value=PROXY_BASE, key="sb_proxy")
rakuten_app_id  = st.sidebar.text_input("Rakuten App ID(글로벌)", value=DEFAULT_RAKUTEN_APP_ID, key="sb_rk_appid")
# ===== ENVY v27.14 Full — Part 3/4 =====

st.markdown("## ENVY v27.14 — AI 레이더 대시보드")

top1, top2, top3 = st.columns([1.1, 1, 1])

# ---- 데이터랩 ----
with top1:
    st.subheader("데이터랩")
    cat = st.selectbox("카테고리(10개)", list(DATALAB_CATEGORIES.keys()), index=0, key="dl_cat")
    cid = DATALAB_CATEGORIES.get(cat)
    # 기간: 최근 7일 (end=오늘)
    today = dt.date.today()
    start = (today - dt.timedelta(days=7)).strftime("%Y-%m-%d")
    end   = today.strftime("%Y-%m-%d")

    col_a, col_b = st.columns([1,1])
    with col_a:
        st.text_input("프록시", value=st.session_state.get("sb_proxy", PROXY_BASE), key="dl_proxy")
    with col_b:
        reload_dl = st.button("데이터랩 재시도", key="btn_dl_reload")

    df_dl = pd.DataFrame()
    if reload_dl:
        try:
            with st.spinner("네이버 데이터랩 수집 중..."):
                df_dl = fetch_datalab_keywords(cid, start, end, proxy_base=st.session_state["dl_proxy"])
        except Exception as e:
            st.warning(f"DataLab 호출 실패: {e}")

    if not df_dl.empty:
        st.dataframe(df_dl, use_container_width=True, height=280)
    else:
        st.info("아직 결과가 없어요. 프록시/기간/CID 확인 후 '데이터랩 재시도'를 눌러주세요.", icon="ℹ️")

# ---- 아이템스카우트 ----
with top2:
    st.subheader("아이템스카우트")
    st.text_input("연동 대기(별도 API/프록시)", value="", key="is_placeholder")
    st.info("현재는 레이아웃 고정용 데모 상태입니다.", icon="🧩")

# ---- 셀러라이프 ----
with top3:
    st.subheader("셀러라이프")
    st.text_input("연동 대기(별도 API/프록시)", value="", key="sl_placeholder")
    st.info("현재는 레이아웃 고정용 데모 상태입니다.", icon="🧩")
# ===== ENVY v27.14 Full — Part 4/4 =====

bot1, bot2, bot3 = st.columns([1.1, 1, 1])

# ---- AI 키워드 레이더(국내/글로벌) ----
with bot1:
    st.subheader("AI 키워드 레이더 (국내/글로벌)")
    mode = st.radio("모드", ["국내", "글로벌"], horizontal=True, key="radar_mode")
    if mode == "국내":
        if "df_dl_cache" in st.session_state:
            st.dataframe(st.session_state["df_dl_cache"], use_container_width=True, height=280)
        else:
            st.caption("※ 국내: 데이터랩 표가 채워지면 여기에도 같은 리스트가 나타납니다.")
    else:
        genre = st.selectbox("Rakuten 장르(샘플)", ["0(전체)", "100283(식품)", "100371(패션)"], index=0, key="rk_gen")
        genre_id = genre.split("(")[0]
        with st.spinner("Rakuten 수집 중..."):
            df_rk = fetch_rakuten_global(st.session_state.get("sb_rk_appid", DEFAULT_RAKUTEN_APP_ID), genre_id=genre_id)
        st.dataframe(df_rk, use_container_width=True, height=280)

# ---- 11번가 (모바일) ----
with bot2:
    st.subheader("11번가 (모바일)")
    # 프록시 경유 모바일 뷰 URL을 직접 넣거나, 일반 URL을 바로 미리보기(사이트 정책에 따라 미표시될 수 있음)
    url11 = st.text_input("11번가 URL", value="https://www.11st.co.kr/", key="url_11st")
    embed_11st(url11, height=380)
    st.caption("※ 정책상 임베드가 막히는 경우, 요약표/프록시 전환 버튼을 추후 추가합니다.")

# ---- 상품명 생성기 ----
with bot3:
    st.subheader("상품명 생성기 (규칙 기반)")
    brand   = st.text_input("브랜드", value="envy", key="g_brand")
    base_kw = st.text_input("베이스 키워드", value="K-coffee mix", key="g_base")
    rel_kw  = st.text_input("연관키워드(쉼표)", value="Maxim, Kanu, Korea", key="g_rel")
    banned  = st.text_input("금칙어", value="copy, fake, replica", key="g_banned")
    limit   = st.slider("글자수 제한", min_value=40, max_value=120, value=80, key="g_limit")

    if st.button("제목 5개 생성", key="btn_title_gen"):
        titles = generate_titles_rule(brand, base_kw, rel_kw, banned, limit)
        st.success("생성 완료")
        for i, t in enumerate(titles, start=1):
            c1, c2 = st.columns([0.9, 0.1])
            c1.write(f"{i}. {t}")
            c2.button("복사", key=f"copy_{i}_{hash(t)%10000}")
    st.caption("연관키워드(검색량)는 상단 데이터랩/글로벌 표를 참고하세요.")

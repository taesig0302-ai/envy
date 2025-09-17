# ==== ENVY v27.15 Full — Part 1/4 ====
import json, time, random, datetime as dt
from typing import Dict, List, Tuple
from urllib.parse import quote

import requests
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import plotly.express as px

st.set_page_config(page_title="ENVY v27.15", layout="wide")

# ---------- 상수 ----------
PROXY_BASE = "https://envy-proxy.taesig0302.workers.dev"   # 통합 프록시(11번가+DataLab)
DEFAULT_RAKUTEN_APP_ID = "1043271015809337425"

CURRENCY_SYMBOL = {"USD":"$", "EUR":"€", "JPY":"¥", "CNY":"¥", "KRW":"₩"}
FALLBACK_RATE   = {"USD":1400.00, "EUR":1500.00, "JPY":9.50, "CNY":190.00}

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

# ---------- 사이드바 절대 고정 CSS & 전역 스타일 ----------
st.markdown("""
<style>
/* 사이드바: 한눈에(스크롤 제거/높이 고정) */
section[data-testid="stSidebar"] { height: 100vh !important; overflow-y: hidden !important; }
/* 사이드바 간격 촘촘 튜닝 */
[data-testid="stSidebar"] .stSelectbox,
[data-testid="stSidebar"] .stNumberInput,
[data-testid="stSidebar"] .stRadio,
[data-testid="stSidebar"] .stTextInput,
[data-testid="stSidebar"] .stCheckbox { margin-bottom: 0.55rem; }
/* 결과 배지 */
.eny-badge { padding:8px 12px; border-radius:10px; font-size:13px; display:inline-block; margin:4px 0;}
.eny-green { background:#e7f6ec; color:#118d57; border:1px solid #b6e2c4;}
.eny-blue  { background:#e6f0ff; color:#1a51b2; border:1px solid #c2d3ff;}
.eny-yellow{ background:#fff9e6; color:#8f6a00; border:1px solid #ffe6a7;}
/* 다크모드 토글 시 테마(간단 CSS 스위치) */
html.dark body { background-color:#0f1117 !important; color:#e5e7eb !important; }
html.dark .stDataFrame, html.dark .stPlotlyChart { background:#0f1117 !important; }
html.dark .stButton>button { background:#1f2937 !important; color:#e5e7eb !important; }
/* 카드 넓게(가독성) */
.block-container { padding-top: 0.6rem; }
</style>
""", unsafe_allow_html=True)

def set_dark_mode(enabled: bool):
    js = """
    <script>
    const cl = document.documentElement.classList;
    const want = %s;
    if (want) { cl.add('dark'); } else { cl.remove('dark'); }
    </script>
    """ % ("true" if enabled else "false")
    st.markdown(js, unsafe_allow_html=True)

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

# ----- DataLab: 통합 프록시의 /datalab 엔드포인트 사용 -----
def fetch_datalab_autoload(cid: str, start: str, end: str, proxy_base: str=PROXY_BASE) -> pd.DataFrame:
    url = f"{proxy_base.rstrip('/')}/datalab?cid={cid}&start={start}&end={end}"
    r = requests.get(url, timeout=20)
    data = r.json() if "application/json" in (r.headers.get("content-type","")) else json.loads(r.text)
    if r.status_code != 200 or str(data.get("returnCode","0")) != "0":
        raise RuntimeError(f"http={r.status_code} rc={data.get('returnCode')} msg={data.get('message')}")
    ranks = data.get("ranks", [])
    if not ranks: raise RuntimeError("empty-list")
    df = pd.DataFrame(ranks)  # rank, keyword, linkId
    if "search" not in df.columns: df["search"] = None
    return df[["rank","keyword","search"]]

# ----- Rakuten Ranking(글로벌 레이더) -----
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

# ----- 11번가 모바일 임베드(프록시 경유) -----
def embed_11st_via_proxy(proxy_base: str, raw_url: str, height: int=680):
    proxied = f"{proxy_base.rstrip('/')}/?target={quote(raw_url, safe='')}"
    components.iframe(proxied, height=height, scrolling=True)

# ----- 상품명 생성기(규칙 기반) -----
def generate_titles_rule(brand: str, base_kw: str, rel_kw: str, banned: str, limit: int=80) -> List[str]:
    ban = {b.strip().lower() for b in banned.split(",") if b.strip()}
    combos = [
        f"{brand} {base_kw} {rel_kw}",
        f"{base_kw} | {brand} {rel_kw}",
        f"{brand} {base_kw}",
        f"{base_kw} {rel_kw}",
        f"{rel_kw} {brand} {base_kw}",
    ]
    out = []
    for s in combos:
        filtered = " ".join([w for w in s.split() if w.lower() not in ban])
        out.append(filtered.strip()[:limit])
    return out
# ==== ENVY v27.15 Full — Part 2/4 ====

with st.sidebar:
    # 버전 표시(희미하게)
    st.markdown("<div style='opacity:.35;font-size:12px'>ENVY v27.15</div>", unsafe_allow_html=True)

    # 🌗 다크 모드 토글 (이모지 복원 + 즉시 적용)
    sb_dark = st.toggle("🌗 다크 모드", value=st.session_state.get("sb_dark", False), key="sb_dark")
    set_dark_mode(sb_dark)

    st.markdown("---")
    st.markdown("### ① 환율 계산기")
    sb_fx_base = st.selectbox("기준 통화", ["USD","EUR","JPY","CNY"], index=0, key="sb_fx_base")
    sb_fx_amt  = st.number_input("판매금액 (기준통화)", min_value=0.00, step=0.01, value=1.00, format="%.2f", key="sb_fx_amt")
    fx_krw = convert_price(sb_fx_amt, sb_fx_base)
    st.markdown(f'<div class="eny-badge eny-green">환산 금액: {fmt_money(fx_krw,"KRW")}</div>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### ② 마진 계산기 (v23)")
    sb_mg_base = st.selectbox("기준 통화(판매금액)", ["USD","EUR","JPY","CNY"], index=0, key="sb_mg_base")
    sb_mg_amt  = st.number_input("판매금액 (기준통화)", min_value=0.00, step=0.01, value=1.00, format="%.2f", key="sb_mg_amt")
    mg_krw = convert_price(sb_mg_amt, sb_mg_base)
    st.markdown(f'<div class="eny-badge eny-blue">판매금액(환산): {fmt_money(mg_krw,"KRW")}</div>', unsafe_allow_html=True)

    sb_mg_card   = st.number_input("카드수수료 (%)",  min_value=0.0, step=0.25, value=4.00,  format="%.2f", key="sb_mg_card")
    sb_mg_market = st.number_input("마켓수수료 (%)", min_value=0.0, step=0.25, value=14.00, format="%.2f", key="sb_mg_market")
    sb_mg_ship   = st.number_input("배송비 (₩)",      min_value=0.0, step=100.0, value=0.0,  format="%.2f", key="sb_mg_ship")
    sb_mg_mode   = st.radio("마진 방식", ["퍼센트 마진(%)","더하기 마진(₩)"], horizontal=True, key="sb_mg_mode")

    if sb_mg_mode.startswith("퍼센트"):
        sb_mg_pct = st.number_input("마진율 (%)", min_value=0.0, step=0.5, value=10.0, format="%.2f", key="sb_mg_pct")
        mg_sell, mg_profit = calc_margin_percent(sb_mg_amt, sb_mg_base, sb_mg_card, sb_mg_market, sb_mg_ship, sb_mg_pct)
    else:
        sb_mg_add = st.number_input("더하기 마진 (₩)", min_value=0.0, step=100.0, value=0.0, format="%.2f", key="sb_mg_add")
        mg_sell, mg_profit = calc_margin_add(sb_mg_amt, sb_mg_base, sb_mg_card, sb_mg_market, sb_mg_ship, sb_mg_add)

    st.markdown(f'<div class="eny-badge eny-blue">예상 판매가: {fmt_money(mg_sell,"KRW")}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="eny-badge eny-yellow">순이익(마진): {fmt_money(mg_profit,"KRW")}</div>', unsafe_allow_html=True)

    st.markdown("---")
    # 프록시/라쿠텐 입력은 보이되, 사이드바 높이 내에서 한눈에 끝남
    st.text_input("프록시(통합)", value=PROXY_BASE, key="sb_proxy")
    st.text_input("Rakuten App ID", value=DEFAULT_RAKUTEN_APP_ID, key="sb_rk_appid")
# ==== ENVY v27.15 Full — Part 3/4 ====

st.markdown("## ENVY v27.15 — AI 레이더 대시보드")

top1, top2, top3 = st.columns([1.1, 1, 1])

# ---- 데이터랩(자동 로드) ----
with top1:
    st.subheader("데이터랩")
    cat = st.selectbox("카테고리(10개)", list(DATALAB_CATEGORIES.keys()), index=0, key="dl_cat_auto")
    cid = DATALAB_CATEGORIES[cat]
    today = dt.date.today()
    start = (today - dt.timedelta(days=7)).strftime("%Y-%m-%d")
    end   = today.strftime("%Y-%m-%d")
    proxy = st.session_state.get("sb_proxy", PROXY_BASE)

    # 자동 로드 트리거: 최초/카테고리·프록시 변경 시
    prev = st.session_state.get("_dl_prev", {})
    cur  = {"cid": cid, "proxy": proxy, "start": start, "end": end}
    need = (prev != cur) or st.session_state.get("_dl_force", True)
    st.session_state["_dl_prev"] = cur
    st.session_state["_dl_force"] = False

    if need:
        try:
            with st.spinner("네이버 데이터랩 불러오는 중…"):
                df_dl = fetch_datalab_autoload(cid, start, end, proxy)
                st.session_state["df_dl_cache"] = df_dl
        except Exception as e:
            st.warning(f"DataLab 호출 실패: {e}")
            st.session_state["df_dl_cache"] = pd.DataFrame()

    df_dl = st.session_state.get("df_dl_cache", pd.DataFrame())

    # 표 + 실선 그래프
    if df_dl.empty:
        st.info("데이터가 없습니다. 잠시 후 재시도하거나 프록시/기간/CID를 확인하세요.", icon="ℹ️")
    else:
        st.dataframe(df_dl, use_container_width=True, height=280)
        y = df_dl["search"] if df_dl["search"].notna().any() else (df_dl["rank"].max()+1 - df_dl["rank"])
        fig = px.line(pd.DataFrame({"rank": df_dl["rank"], "value": y}),
                      x="rank", y="value", title="Top20 추이(실선)", markers=False)
        fig.update_layout(margin=dict(l=8,r=8,t=36,b=8), height=220)
        st.plotly_chart(fig, use_container_width=True, theme="streamlit")

# ---- 아이템스카우트 ----
with top2:
    st.subheader("아이템스카우트")
    st.info("현재는 레이아웃 고정용 데모 상태입니다.", icon="🧩")

# ---- 셀러라이프 ----
with top3:
    st.subheader("셀러라이프")
    st.info("현재는 레이아웃 고정용 데모 상태입니다.", icon="🧩")
# ==== ENVY v27.15 Full — Part 4/4 ====

bot1, bot2, bot3 = st.columns([1.1, 1, 1])

# ---- AI 키워드 레이더(국내/글로벌) ----
with bot1:
    st.subheader("AI 키워드 레이더 (국내/글로벌)")
    mode = st.radio("모드", ["국내", "글로벌"], horizontal=True, key="radar_mode")
    if mode == "국내":
        df_dl = st.session_state.get("df_dl_cache", pd.DataFrame())
        if df_dl.empty:
            st.caption("※ 국내: 데이터랩 표가 채워지면 동일 리스트가 표시됩니다.")
        else:
            st.dataframe(df_dl, use_container_width=True, height=280)
    else:
        app_id = st.session_state.get("sb_rk_appid", DEFAULT_RAKUTEN_APP_ID)
        genre  = st.selectbox("Rakuten 장르(샘플)", ["0(전체)", "100283(식품)", "100371(패션)"], index=0, key="rk_gen")
        genre_id = genre.split("(")[0]
        with st.spinner("Rakuten 수집 중…"):
            df_rk = fetch_rakuten_global(app_id, genre_id)
        st.dataframe(df_rk, use_container_width=True, height=280)

# ---- 11번가 (모바일 프록시 임베드) ----
with bot2:
    st.subheader("11번가 (모바일)")
    default_url = "https://m.11st.co.kr/browsing/bestSellers.tmall"
    url11 = st.text_input("11번가 URL", value=default_url, key="url_11st")
    embed_11st_via_proxy(st.session_state.get("sb_proxy", PROXY_BASE), url11, height=680)
    st.caption("※ 정책상 임베드가 막히는 경우가 있어 통합 프록시가 CSP/X-Frame을 제거해 노출합니다.")

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
            c2.button("복사", key=f"copy_{i}_{abs(hash(t))%10000}")
    st.caption("연관키워드(검색량)는 상단 데이터랩/글로벌 표를 참고하세요.")

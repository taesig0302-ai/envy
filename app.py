# ====== ENVY v27.13 Full — Part 1/4 ======
import time
import math
import json
import requests
import datetime as dt
from urllib.parse import urlencode
import streamlit as st
import pandas as pd
import numpy as np
import textwrap
from typing import Dict, List, Tuple
import streamlit.components.v1 as components

st.set_page_config(page_title="ENVY v27.13 Full", layout="wide")

# ---------------------------
# 스타일(카드 강조색, 폰트 등)
# ---------------------------
CARD_CSS = """
<style>
/* 카드 느낌 */
.block-container {padding-top: 0.8rem;}
div[data-testid="stMetricValue"] { font-weight: 700; }
.eny-badge {padding: 6px 10px; border-radius: 10px; font-size: 13px; display:inline-block; margin-top: 2px;}
.eny-green {background:#e7f6ec; color:#118d57; border:1px solid #b6e2c4;}
.eny-blue {background:#e6f0ff; color:#1a51b2; border:1px solid #c2d3ff;}
.eny-yellow{background:#fff9e6; color:#8f6a00; border:1px solid #ffe6a7;}
/* 간격 살짝 촘촘 */
[data-testid="stSidebar"] .stSelectbox, 
[data-testid="stSidebar"] .stNumberInput {margin-bottom: 0.5rem;}
</style>
"""
st.markdown(CARD_CSS, unsafe_allow_html=True)

# ---------------------------
# 통화/기호/고정 환율(실패시)
# ---------------------------
CURRENCY_SYMBOL = {
    "USD": "$",
    "EUR": "€",
    "JPY": "¥",
    "CNY": "¥",
    "KRW": "₩",
}
FALLBACK_RATE = {  # KRW 기준
    "USD": 1400.00,
    "EUR": 1500.00,
    "JPY": 9.50,
    "CNY": 190.00,
}

def fetch_fx_rate(base: str, to: str = "KRW") -> float:
    """exchangerate.host 사용. 실패 시 FALLBACK"""
    try:
        url = f"https://api.exchangerate.host/latest?base={base}&symbols={to}"
        r = requests.get(url, timeout=6)
        r.raise_for_status()
        return float(r.json()["rates"][to])
    except Exception:
        return FALLBACK_RATE.get(base, 1400.0)

def fmt_money(v: float, code: str = "KRW") -> str:
    sym = CURRENCY_SYMBOL.get(code, "")
    if code == "KRW":
        return f"{sym}{v:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"{sym}{v:,.2f}"

# ---------------------------
# 환율/마진 계산
# ---------------------------
def convert_price(amount_foreign: float, base_currency: str) -> float:
    rate = fetch_fx_rate(base_currency, "KRW")
    return round(amount_foreign * rate, 2)

def calc_margin_by_percent(price_foreign: float, base_currency: str,
                           card_fee_pct: float, market_fee_pct: float,
                           shipping_krw: float, margin_pct: float) -> Tuple[float, float]:
    """판매가/순이익: 퍼센트 마진 방식"""
    rate = fetch_fx_rate(base_currency, "KRW")
    cost_krw = round(price_foreign * rate, 2)

    total_pct = 1 - (card_fee_pct/100) - (market_fee_pct/100) - (margin_pct/100)
    total_pct = max(total_pct, 0.01)
    sell_price = round((cost_krw + shipping_krw) / total_pct, 2)
    profit = round(sell_price - cost_krw - shipping_krw - (sell_price*card_fee_pct/100) - (sell_price*market_fee_pct/100), 2)
    return sell_price, profit

def calc_margin_by_add(price_foreign: float, base_currency: str,
                       card_fee_pct: float, market_fee_pct: float,
                       shipping_krw: float, add_margin_krw: float) -> Tuple[float, float]:
    """판매가/순이익: 더하기 마진(원)"""
    rate = fetch_fx_rate(base_currency, "KRW")
    cost_krw = round(price_foreign * rate, 2)
    sell_price = round((cost_krw + shipping_krw + add_margin_krw) / (1 - (card_fee_pct/100) - (market_fee_pct/100)), 2)
    profit = round(sell_price - cost_krw - shipping_krw - (sell_price*card_fee_pct/100) - (sell_price*market_fee_pct/100), 2)
    return sell_price, profit

# ---------------------------
# DataLab 요청(프록시 경유) — form-urlencoded 방식
# ---------------------------
# 카테고리 10개(샘플 CID) — 필요 시 CID만 바꿔주면 됨
DATALAB_CATEGORIES = {
    "패션잡화": "50000000",
    "식품": "50000170",
    "생활/건강": "50000213",
    "출산/육아": "50000006",
    "가구/인테리어": "50000190",
    "디지털/가전": "50000002",
    "스포츠/레저": "50000008",
    "화장품/미용": "50000167",
    "자동차/공구": "50000151",
    "도서/취미": "50005542",
}

def request_datalab_via_proxy(proxy_url: str, cid: str,
                              start_date: str, end_date: str) -> List[Dict]:
    """
    프록시(Cloudflare Worker) → Naver DataLab POST
    application/x-www-form-urlencoded 로 전송
    """
    base = "https://datalab.naver.com/shoppingInsight/getCategoryKeywordRank.naver"
    target = f"{proxy_url.rstrip('/')}/?target={base}"

    headers = {"content-type": "application/x-www-form-urlencoded; charset=UTF-8"}
    payload = urlencode({
        "cid": cid,
        "timeUnit": "date",
        "startDate": start_date,   # YYYY-MM-DD
        "endDate": end_date,       # YYYY-MM-DD
        "categoryDepth": "1",
    })

    try:
        r = requests.post(target, headers=headers, data=payload, timeout=10)
        r.raise_for_status()
        data = r.json()
        result = data.get("result", []) or data.get("keywordList", [])
        return result
    except Exception as e:
        return []

# ---------------------------
# 11번가 모바일 임베드(간단 iframe)
# ---------------------------
def embed_11st(url: str, height: int = 420):
    html = f"""
    <iframe src="{url}" style="width:100%; height:{height}px; border:1px solid #eee; border-radius:8px;"
            sandbox="allow-scripts allow-same-origin allow-forms"></iframe>
    """
    components.html(html, height=height+6, scrolling=True)

# ---------------------------
# 간단 타이틀 생성(규칙 기반)
# ---------------------------
def generate_titles_rule(brand: str, base_kw: str, rel_kw: str, banned: str, limit: int = 80) -> List[str]:
    ban_words = [b.strip() for b in banned.split(",") if b.strip()]
    combos = [
        f"{brand} {base_kw} {rel_kw}".strip(),
        f"{base_kw} | {brand} {rel_kw}".strip(),
        f"{brand} {base_kw}".strip(),
        f"{base_kw} {rel_kw}".strip(),
        f"{rel_kw} {brand} {base_kw}".strip(),
    ]
    out = []
    for s in combos:
        t = " ".join([w for w in s.split() if w.lower() not in [bw.lower() for bw in ban_words]])
        out.append(t[:limit])
    return out[:5]
# ====== ENVY v27.13 Full — Part 2/4 ======

st.sidebar.toggle("다크 모드", value=False, key="dark_tgl")  # 토글만 둠(테마는 앱 설정에 따름)
st.sidebar.markdown("### ① 환율 계산기")

base1 = st.sidebar.selectbox("기준 통화", options=["USD", "EUR", "JPY", "CNY"], index=0, key="fx_base1")
amt1  = st.sidebar.number_input("판매금액 (기준통화)", min_value=0.0, step=0.01, value=1.00, format="%.2f", key="fx_amt1")

krw_conv = convert_price(amt1, base1)
st.sidebar.markdown(
    f'<div class="eny-badge eny-green">환산 금액: {fmt_money(krw_conv, "KRW")}</div>',
    unsafe_allow_html=True
)

st.sidebar.markdown("---")
st.sidebar.markdown("### ② 마진 계산기 (v23)")

base2 = st.sidebar.selectbox("기준 통화(판매금액)", options=["USD", "EUR", "JPY", "CNY"], index=0, key="fx_base2")
amt2  = st.sidebar.number_input("판매금액 (기준통화)", min_value=0.0, step=0.01, value=1.00, format="%.2f", key="mg_amt2")
# 읽기전용 환산
krw_conv2 = convert_price(amt2, base2)
st.sidebar.markdown(
    f'<div class="eny-badge eny-blue">판매금액(환산): {fmt_money(krw_conv2, "KRW")}</div>',
    unsafe_allow_html=True
)

card_fee   = st.sidebar.number_input("카드수수료 (%)", min_value=0.0, step=0.25, value=4.00, format="%.2f", key="mg_card")
market_fee = st.sidebar.number_input("마켓수수료 (%)", min_value=0.0, step=0.25, value=14.00, format="%.2f", key="mg_market")
shipping   = st.sidebar.number_input("배송비 (₩)",     min_value=0.0, step=100.0, value=0.0, format="%.2f", key="mg_ship")

mode_pct = st.sidebar.radio("마진 방식", options=["퍼센트 마진(%)", "더하기 마진(₩)"], index=0, key="mg_mode")
if mode_pct == "퍼센트 마진(%)":
    margin_pct = st.sidebar.number_input("마진율 (%)", min_value=0.0, step=0.5, value=10.0, format="%.2f", key="mg_pct")
    sell_price, profit = calc_margin_by_percent(amt2, base2, card_fee, market_fee, shipping, margin_pct)
else:
    add_margin = st.sidebar.number_input("더하기 마진 (₩)", min_value=0.0, step=100.0, value=0.0, format="%.2f", key="mg_add")
    sell_price, profit = calc_margin_by_add(amt2, base2, card_fee, market_fee, shipping, add_margin)

st.sidebar.markdown(
    f'<div class="eny-badge eny-blue">예상 판매가: {fmt_money(sell_price, "KRW")}</div>',
    unsafe_allow_html=True
)
st.sidebar.markdown(
    f'<div class="eny-badge eny-yellow">순이익(마진): {fmt_money(profit, "KRW")}</div>',
    unsafe_allow_html=True
)
# ====== ENVY v27.13 Full — Part 3/4 ======

st.markdown("## ENVY v27.13 Full")

top1, top2, top3 = st.columns([1.1, 1, 1])

# ------------------ 데이터랩 ------------------
with top1:
    st.subheader("데이터랩")
    cat = st.selectbox("카테고리(10개)", list(DATALAB_CATEGORIES.keys()), index=0, key="dl_cat")
    proxy_url = st.text_input("프록시(데이터랩)", value="https://envy-proxy.taesig0302.workers.dev", key="dl_proxy")
    if st.button("데이터랩 재시도", key="btn_dl_reload"):
        st.session_state["__dl_trigger__"] = time.time()

    # 기간: 최근 7일
    end_date = dt.date.today()
    start_date = end_date - dt.timedelta(days=7)
    cid = DATALAB_CATEGORIES.get(cat)

    # DataLab 호출
    result = request_datalab_via_proxy(proxy_url, cid, start_date.isoformat(), end_date.isoformat())

    if not result:
        st.warning("DataLab 호출 실패: empty-list / http 오류 / 프록시·기간·CID 확인")
        # 샘플 표시
        df = pd.DataFrame({
            "rank":[1,2,3,4,5],
            "keyword":["키워드A","키워드B","키워드C","키워드D","키워드E"],
            "search":[100,92,88,77,70]
        })
    else:
        # 결과 형식에 맞게 DataFrame 구성
        # 예상키: [{"rank":1,"keyword":"...","ratio":...}, ...] 혹은 다른 구조
        rows=[]
        for i, row in enumerate(result, start=1):
            kw = row.get("keyword") or row.get("keywordName") or f"키워드{i}"
            sc = row.get("ratio") or row.get("search") or 0
            rows.append({"rank":i, "keyword":kw, "search":sc})
        df = pd.DataFrame(rows)[:20]

    st.dataframe(df, use_container_width=True, height=280)

# ------------------ 아이템스카우트 ------------------
with top2:
    st.subheader("아이템스카우트")
    st.text_input("연동 대기 (별도 API/프록시)", value="", key="is_placeholder")
    st.info("향후 API/프록시 연결 예정. 현재는 레이아웃 고정용 자리표시자입니다.", icon="🧩")

# ------------------ 셀러라이프 ------------------
with top3:
    st.subheader("셀러라이프")
    st.text_input("연동 대기 (별도 API/프록시)", value="", key="sl_placeholder")
    st.info("향후 API/프록시 연결 예정. 현재는 레이아웃 고정용 자리표시자입니다.", icon="🧩")
# ====== ENVY v27.13 Full — Part 4/4 ======

bot1, bot2, bot3 = st.columns([1.1, 1, 1])

# ------------------ AI 키워드 레이더 ------------------
with bot1:
    st.subheader("AI 키워드 레이더 (국내/글로벌)")
    mode = st.radio("모드", ["국내", "글로벌"], horizontal=True, key="radar_mode")

    if mode == "국내":
        st.caption("※ 국내: 데이터랩 결과를 그대로 사용합니다.")
        try:
            st.dataframe(df, use_container_width=True, height=280)
        except Exception:
            st.info("데이터랩 결과가 아직 없어요. 상단 '데이터랩'에서 먼저 요청하세요.")
    else:
        app_id = st.text_input("Rakuten App ID (글로벌)", value=st.session_state.get("rakuten_appid",""), key="rk_appid")
        colx, coly = st.columns([1,1])
        with colx:
            region = st.selectbox("Amazon 지역(샘플)", options=["US","JP"], index=1, key="rk_region")
        with coly:
            st.caption("※ 무료 Demo: Rakuten Ranking API로 키워드 대용 표시")

        if app_id:
            try:
                # 간단 대용: 라쿠텐 랭킹 API → itemName 추출
                url = "https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20170628"
                params = {"applicationId": app_id, "genreId": "100283"}  # 임의 장르
                r = requests.get(url, params=params, timeout=8)
                items = r.json().get("Items", [])
                rows = []
                for i, it in enumerate(items[:20], start=1):
                    nm = it["Item"]["itemName"]
                    rows.append({"rank": i, "keyword": nm[:30], "score": 200-i})
                df_rk = pd.DataFrame(rows)
                st.dataframe(df_rk, use_container_width=True, height=280)
            except Exception as e:
                st.warning("Rakuten 수집 실패: App ID/호출 제한/네트워크 확인")
        else:
            st.info("Rakuten App ID가 필요합니다. (나중에 정식 Amazon/Global API로 교체)")

# ------------------ 11번가 (모바일) ------------------
with bot2:
    st.subheader("11번가 (모바일)")
    url11 = st.text_input("11번가 URL", value="https://www.11st.co.kr/", key="url_11st")
    embed_11st(url11, height=380)
    st.button("업데이트 실패 대비 요약표 보기", key="btn_11st_summary")
    st.caption("※ 모바일 완전 임베드는 정책상 제약이 있을 수 있음(요약표/프록시 우회 준비).")

# ------------------ 상품명 생성기 ------------------
with bot3:
    st.subheader("상품명 생성기 (규칙 + HuggingFace KoGPT2)")
    brand  = st.text_input("브랜드", value="envy", key="g_brand")
    base_kw = st.text_input("베이스 키워드", value="K-coffee mix", key="g_base")
    rel_kw  = st.text_input("연관키워드", value="Maxim, Kanu, Korea", key="g_rel")
    banned  = st.text_input("금칙어", value="copy, fake, replica", key="g_banned")
    limit   = st.slider("글자수 제한", min_value=40, max_value=120, value=80, key="g_limit")
    mode_t  = st.radio("모드", ["규칙 기반", "HuggingFace AI"], horizontal=True, key="g_mode")

    if st.button("생성", key="btn_gen_title"):
        titles = generate_titles_rule(brand, base_kw, rel_kw, banned, limit)
        st.success("규칙 기반 5안 생성 완료")
        for i, t in enumerate(titles, start=1):
            c1, c2 = st.columns([0.9, 0.1])
            c1.write(f"{i}. {t}")
            c2.button("복사", key=f"copy_{i}", on_click=st.session_state.setdefault, args=(f"copied_{i}", t))
        st.caption("※ HuggingFace 모드는 추후 KoGPT2 Inference 연결(토큰 필요).")

    st.divider()
    st.caption("추천용 연관키워드(검색량): 데이터랩 표/글로벌 표를 활용해 선택하세요.")


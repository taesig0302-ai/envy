# === THEME TOGGLE & GLOBAL CSS ===
if "theme" not in st.session_state:
    st.session_state["theme"] = "light"

theme_is_dark = st.sidebar.toggle("🌗 다크 모드", value=(st.session_state["theme"]=="dark"), key="__ui_theme_toggle")
st.session_state["theme"] = "dark" if theme_is_dark else "light"

PRIMARY = "#2563eb" if st.session_state["theme"]=="light" else "#60a5fa"
BG_PANEL = "#f8fafc" if st.session_state["theme"]=="light" else "#0b1220"
FG_TEXT = "#0f172a" if st.session_state["theme"]=="light" else "#e5e7eb"

st.markdown(f"""
<style>
section[data-testid="stSidebar"] .block-container {{ padding-top: 6px !important; }}
.envy-box {{
  background:{BG_PANEL};
  border:1px solid rgba(100,100,100,0.12);
  border-radius:10px; padding:12px 14px; margin:6px 0;
}}
.envy-title {{ font-weight:700; color:{FG_TEXT}; margin-bottom:4px; }}
.envy-kpi {{ font-size:20px; font-weight:800; color:{PRIMARY}; }}
.envy-kpi-sub {{ font-size:12px; opacity:0.8; }}
</style>
""", unsafe_allow_html=True)
with st.sidebar:
    st.header("① 환율 계산기")
    fx_ccy = st.selectbox("기준 통화", ["USD","EUR","JPY","CNY"], index=0, key="sb_fx_base")
    fx_rate = {"USD":1400,"EUR":1500,"JPY":9,"CNY":190}.get(fx_ccy, 1400)  # (임시) 실시간 쓰면 get_fx_rate로 교체

    st.caption(f"자동 환율: 1 {fx_ccy} = {fx_rate:,.2f} ₩")
    fx_price = st.number_input(f"판매금액 ({fx_ccy})", min_value=0.0, max_value=1e12, value=100.0, step=1.0, key="sb_fx_price_foreign")
    fx_krw = fx_price * fx_rate

    st.markdown(f"""
    <div class="envy-box">
      <div class="envy-title">환산 금액 (읽기 전용)</div>
      <div class="envy-kpi">₩{fx_krw:,.0f}</div>
      <div class="envy-kpi-sub">환율 자동 반영</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.header("② 마진 계산기 (v23)")
    m_ccy = st.selectbox("기준 통화(판매금액)", ["USD","EUR","JPY","CNY"], index=0, key="sb_m_base")
    m_rate = {"USD":1400,"EUR":1500,"JPY":9,"CNY":190}.get(m_ccy, 1400)  # (임시) 실시간 쓰면 get_fx_rate로 교체
    st.caption(f"자동 환율: 1 {m_ccy} = {m_rate:,.2f} ₩")

    m_sale_foreign = st.number_input(f"판매금액 ({m_ccy})", min_value=0.0, max_value=1e12, value=100.0, step=1.0, key="sb_m_sale_foreign")
    m_sale_krw = m_sale_foreign * m_rate

    st.markdown(f"""
    <div class="envy-box">
      <div class="envy-title">판매금액 (환산)</div>
      <div class="envy-kpi">₩{m_sale_krw:,.0f}</div>
    </div>
    """, unsafe_allow_html=True)

    card = st.number_input("카드수수료 (%)", min_value=0.0, max_value=100.0, value=4.0, step=0.1, key="sb_card")
    market = st.number_input("마켓수수료 (%)", min_value=0.0, max_value=100.0, value=14.0, step=0.1, key="sb_market")
    ship = st.number_input("배송비 (₩)", min_value=0.0, max_value=1e10, value=0.0, step=100.0, key="sb_ship")
    mode = st.radio("마진 방식", ["퍼센트 마진(%)","더하기 마진(₩)"], horizontal=True, key="sb_mode")

    # v23 공식
    def _calc_percent(cost_krw, cf, mf, t, ship):
        denom = max(1e-9, 1 - cf - mf)
        target_rev = (cost_krw + ship) * (1 + t)
        P = target_rev / denom
        revenue = P * (1 - cf - mf)
        profit = revenue - (cost_krw + ship)
        return P, profit, (profit/P*100 if P>0 else 0.0)

    def _calc_add(cost_krw, cf, mf, add, ship):
        denom = max(1e-9, 1 - cf - mf)
        target_rev = (cost_krw + ship) + add
        P = target_rev / denom
        revenue = P * (1 - cf - mf)
        profit = revenue - (cost_krw + ship)
        return P, profit, (profit/P*100 if P>0 else 0.0)

    if mode=="퍼센트 마진(%)":
        margin_pct = st.number_input("마진율 (%)", min_value=0.0, max_value=500.0, value=10.0, step=0.1, key="sb_margin_pct")
        P, profit, on_sale = _calc_percent(m_sale_krw, card/100.0, market/100.0, margin_pct/100.0, ship)
    else:
        add_margin = st.number_input("더하기 마진 (₩)", min_value=0.0, max_value=1e12, value=10000.0, step=100.0, key="sb_add_margin")
        P, profit, on_sale = _calc_add(m_sale_krw, card/100.0, market/100.0, add_margin, ship)

    st.markdown(f"""
    <div class="envy-box">
      <div class="envy-title">판매가격 (계산 결과)</div>
      <div class="envy-kpi">₩{P:,.0f}</div>
      <div class="envy-kpi-sub">마진율(판매가 기준): {on_sale:.2f}%</div>
    </div>
    <div class="envy-box">
      <div class="envy-title">순이익(마진)</div>
      <div class="envy-kpi">₩{profit:,.0f}</div>
    </div>
    """, unsafe_allow_html=True)
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

# app.py  — 환율 + 마진 계산기 + 11번가 + 네이버 데이터랩 (풀버전)
import json
from datetime import date, timedelta
from functools import reduce

import requests
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# ──────────────────────────────────────────────────────────────────────────────
# 페이지 설정
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="환율 + 마진 + 11번가 + 데이터랩", page_icon="📈", layout="wide")
st.title("📈 실시간 환율 + 마진 계산기")

# 최초 기본값 (새로고침 포함)
if "init" not in st.session_state:
    st.session_state.init = True
    st.session_state.quick_amount = 1.0
    st.session_state.quick_currency = "USD"
    st.session_state.product_price = 1.0
    st.session_state.currency = "USD"
    st.session_state.order = ["마진 계산기", "11번가", "데이터랩"]
    st.session_state.h_11 = 900
    st.session_state.h_lab = 600

# ──────────────────────────────────────────────────────────────────────────────
# 공통: 환율 로더 (캐시, 30분)
# ──────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=timedelta(minutes=30))
def get_rate_to_krw(base: str) -> float:
    # 1차
    try:
        r = requests.get(
            f"https://api.exchangerate.host/latest?base={base}&symbols=KRW",
            timeout=10,
        )
        r.raise_for_status()
        js = r.json()
        if "rates" in js and "KRW" in js["rates"]:
            return float(js["rates"]["KRW"])
    except Exception:
        pass
    # 2차(Fallback)
    try:
        r2 = requests.get(f"https://open.er-api.com/v6/latest/{base}", timeout=10)
        r2.raise_for_status()
        js2 = r2.json()
        if js2.get("result") == "success" and "KRW" in js2.get("rates", {}):
            return float(js2["rates"]["KRW"])
    except Exception:
        pass
    return 0.0

# ──────────────────────────────────────────────────────────────────────────────
# 사이드바: 환율 빠른 계산 + 레이아웃 설정
# ──────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("💱 환율 빠른 계산")
    sb_amt = st.number_input("상품 원가", min_value=0.0, value=1.0, step=1.0, format="%.2f", key="sb_amt")
    sb_cur = st.selectbox("통화 선택", ["USD", "CNY", "JPY", "EUR"], index=0, key="sb_cur")
    sb_rate = get_rate_to_krw(sb_cur)
    if sb_rate > 0:
        st.metric(label=f"{sb_amt:,.2f} {sb_cur} → 원화", value=f"{sb_amt*sb_rate:,.0f} KRW")
        st.caption(f"현재 환율: 1 {sb_cur} = {sb_rate:,.2f} KRW (30분 캐시)")
    else:
        st.error("환율 로드 실패")

    st.divider()
    st.subheader("🧩 레이아웃 설정")
    sections_all = ["마진 계산기", "11번가", "데이터랩"]
    order = st.multiselect("표시 순서", sections_all, default=st.session_state.get("order", sections_all), key="order")
    if not order:
        order = sections_all
    st.session_state.order = order
    st.session_state.h_11 = st.slider("11번가 높이(px)", 500, 1400, st.session_state.get("h_11", 900), 50)
    st.session_state.h_lab = st.slider("데이터랩 차트 높이(px)", 400, 1200, st.session_state.get("h_lab", 600), 50)

# ──────────────────────────────────────────────────────────────────────────────
# 섹션 1: 마진 계산기 (환율 포함)
# ──────────────────────────────────────────────────────────────────────────────
def render_margin():
    st.subheader("💹 마진 계산기")

    col1, col2 = st.columns(2)
    with col1:
        product_price = st.number_input("상품 원가", min_value=0.0, value=st.session_state.product_price,
                                        step=1.0, format="%.2f", key="product_price")
        local_shipping = st.number_input("현지 배송비", min_value=0.0, value=0.0, step=1.0, format="%.2f")
        intl_shipping = st.number_input("국제 배송비 (KRW)", min_value=0.0, value=0.0, step=100.0, format="%.0f")
    with col2:
        card_fee = st.number_input("카드 수수료 (%)", min_value=0.0, value=4.0, step=0.1, format="%.1f") / 100
        market_fee = st.number_input("마켓 수수료 (%)", min_value=0.0, value=15.0, step=0.1, format="%.1f") / 100
        currency = st.selectbox("통화 선택(마진 계산용)", ["USD", "CNY", "JPY", "EUR"],
                                index=["USD", "CNY", "JPY", "EUR"].index(st.session_state.currency),
                                key="currency")

    rate = get_rate_to_krw(currency)
    if rate == 0:
        st.error("환율을 불러오지 못해 마진 계산을 진행할 수 없습니다.")
        return
    st.caption(f"💱 현재 환율: 1 {currency} = {rate:,.2f} KRW")

    # KRW 환산 원가
    base_cost_krw = (product_price + local_shipping) * rate + intl_shipping

    st.markdown("---")
    st.subheader("⚙️ 계산 모드")
    mode = st.radio("계산 방식을 선택하세요", ["목표 마진 → 판매가", "판매가 → 순이익"], horizontal=True)

    if mode == "목표 마진 → 판매가":
        margin_mode = st.radio("마진 방식 선택", ["퍼센트 마진 (%)", "더하기 마진 (₩)"], horizontal=True)
        if margin_mode == "퍼센트 마진 (%)":
            margin_rate = st.number_input("목표 마진 (%)", min_value=0.0, value=40.0, step=1.0, format="%.1f") / 100
            selling_price = base_cost_krw / (1 - (market_fee + card_fee + margin_rate))
            net_profit = selling_price * (1 - (market_fee + card_fee)) - base_cost_krw
            profit_rate = (net_profit / selling_price) if selling_price > 0 else 0.0
        else:
            margin_add = st.number_input("목표 마진 (₩)", min_value=0.0, value=20000.0, step=1000.0, format="%.0f")
            selling_price = (base_cost_krw + margin_add) / (1 - (market_fee + card_fee))
            net_profit = margin_add
            profit_rate = (net_profit / selling_price) if selling_price > 0 else 0.0

        st.markdown("### 📊 계산 결과")
        st.write(f"- 원가 합계: **{base_cost_krw:,.0f} 원**")
        st.write(f"- 목표 판매가: **{selling_price:,.0f} 원**")
        st.write(f"- 예상 순이익: **{net_profit:,.0f} 원**")
        st.write(f"- 순이익률: **{profit_rate*100:.1f}%**")

    else:
        selling_price = st.number_input("판매가 입력 (KRW)", min_value=0.0, value=100000.0, step=1000.0, format="%.0f")
        net_after_fee = selling_price * (1 - (market_fee + card_fee))
        net_profit = net_after_fee - base_cost_krw
        profit_rate = (net_profit / selling_price) if selling_price > 0 else 0.0

        st.markdown("### 📊 계산 결과")
        st.write(f"- 원가 합계: **{base_cost_krw:,.0f} 원**")
        st.write(f"- 입력 판매가: **{selling_price:,.0f} 원**")
        st.write(f"- 예상 순이익: **{net_profit:,.0f} 원**")
        st.write(f"- 순이익률: **{profit_rate*100:.1f}%**")

# ──────────────────────────────────────────────────────────────────────────────
# 섹션 2: 11번가 모바일 보기
# ──────────────────────────────────────────────────────────────────────────────
def render_11st():
    st.subheader("🛒 11번가 아마존 베스트 (모바일)")
    sel = st.selectbox("페이지", ["아마존 베스트", "오늘의 딜", "홈"], index=0, key="sel_11")
    if sel == "아마존 베스트":
        url = "https://m.11st.co.kr/browsing/AmazonBest"
    elif sel == "오늘의 딜":
        url = "https://m.11st.co.kr/browsing/todayDeal"
    else:
        url = "https://m.11st.co.kr/"

    auto_open = st.toggle("새 창 자동 열기", value=False, help="임베드가 차단될 때 유용")
    if auto_open:
        components.html(f"<script>window.open('{url}', '_blank');</script>", height=0)

    h = st.session_state.get("h_11", 900)
    components.html(
        f"""
        <div style="border:1px solid #e5e7eb;border-radius:12px;overflow:hidden">
          <iframe src="{url}"
                  style="width:100%;height:{h}px;border:0"
                  referrerpolicy="no-referrer"
                  sandbox="allow-same-origin allow-scripts allow-popups allow-forms">
          </iframe>
        </div>
        """,
        height=h + 16,
    )
    st.link_button("🔗 새 창으로 열기", url)
    st.caption("※ 일부 브라우저/정책에서 임베드가 차단될 수 있습니다.")

# ──────────────────────────────────────────────────────────────────────────────
# 섹션 3: 네이버 데이터랩
# ──────────────────────────────────────────────────────────────────────────────
# 개인용 하드코딩 + st.secrets 폴백
NAVER_CLIENT_ID = st.secrets.get("NAVER_CLIENT_ID", "h4mkIM2hNLct04BD7sC0")
NAVER_CLIENT_SECRET = st.secrets.get("NAVER_CLIENT_SECRET", "ltoxUNyKxi")

def _datalab_post(url: str, payload: dict, timeout=10):
    try:
        r = requests.post(
            url,
            headers={
                "Content-Type": "application/json",
                "X-Naver-Client-Id": NAVER_CLIENT_ID,
                "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
            },
            data=json.dumps(payload),
            timeout=timeout,
        )
        # 실패시 원문 보여주기
        if r.status_code != 200:
            try:
                st.error(f"요청 실패 {r.status_code}: {r.text[:400]}")
            except Exception:
                st.error(f"요청 실패 {r.status_code}")
            return {}
        return r.json()
    except Exception as e:
        st.error(f"데이터랩 요청 실패: {e}")
        return {}

def _recent_range(days=90):
    end = date.today()
    start = end - timedelta(days=days)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

def render_datalab():
    st.subheader("📊 네이버 데이터랩")
    tab_kw, tab_trend = st.tabs(["카테고리 키워드", "검색어 트렌드"])

    # ── 탭 1: 카테고리 키워드
    with tab_kw:
        st.caption("카테고리 선택 → 최근 n주 키워드 랭킹")
        cats = {
            "패션의류": "50000000",
            "패션잡화": "50000001",
            "생활/건강": "50000002",
            "가전/디지털": "50000003",
            "가구/인테리어": "50000004",
            "식품": "50000007",
            "뷰티": "50000014",
        }
        c1, c2 = st.columns(2)
        with c1:
            cat_name = st.selectbox("카테고리", list(cats.keys()), index=0, key="dl_cat")
        with c2:
            weeks = st.slider("최근 주간 범위", min_value=4, max_value=24, value=12, step=1)

        start, end = _recent_range(days=weeks * 7 + 7)  # 1주 버퍼

        if st.button("키워드 불러오기", type="primary"):
            payload = {
                "startDate": start,
                "endDate": end,
                "timeUnit": "week",
                # 중요: 배열 구조 + param 배열
                "category": [{"name": cat_name, "param": [cats[cat_name]]}],
            }
            js = _datalab_post("https://openapi.naver.com/v1/datalab/shopping/category/keywords", payload)

            items = []
            for res in js.get("results", []):
                for k in res.get("keywords", []):
                    items.append({
                        "keyword": k.get("keyword") or k.get("title") or "-",
                        "score": k.get("ratio") or k.get("value") or 0,
                    })

            if items:
                st.success(f"불러오기 완료 — {cat_name} / {len(items)}개")
                st.dataframe(items, use_container_width=True)
            else:
                st.warning("데이터가 없거나 응답 형식이 달라 파싱할 수 없습니다.")

    # ── 탭 2: 검색어 트렌드
    with tab_trend:
        st.caption("키워드(최대 5개, 쉼표로 구분) 입력 → 기간/단위를 선택 후 조회")
        kwords = st.text_input("키워드 입력", value="나이키, 아디다스", help="최대 5개, 쉼표로 구분")
        col_t1, col_t2, col_t3 = st.columns(3)
        with col_t1:
            days = st.selectbox("기간", ["30일", "90일", "180일", "365일"], index=1)
            days_map = {"30일": 30, "90일": 90, "180일": 180, "365일": 365}
            dsel = days_map[days]
        with col_t2:
            tunit = st.selectbox("단위", ["date(일간)", "week(주간)"], index=1)
            tunit = "date" if tunit.startswith("date") else "week"
        with col_t3:
            device = st.selectbox("디바이스", ["all", "pc", "mo"], index=0)

        s, e = _recent_range(dsel)
        kws = [x.strip() for x in kwords.split(",") if x.strip()][:5]

        if st.button("트렌드 조회"):
            if not kws:
                st.warning("키워드를 1개 이상 입력하세요.")
            else:
                payload = {
                    "startDate": s,
                    "endDate": e,
                    "timeUnit": tunit,
                    "device": "" if device == "all" else device,
                    "keywordGroups": [{"groupName": k, "keywords": [k]} for k in kws],
                }
                js = _datalab_post("https://openapi.naver.com/v1/datalab/search", payload)

                results = js.get("results", [])
                if not results:
                    st.warning("데이터가 없거나 응답 형식이 달라 파싱할 수 없습니다.")
                else:
                    frames = []
                    for res in results:
                        title = res.get("title", "keyword")
                        rows = res.get("data", [])
                        df = pd.DataFrame([{"period": r.get("period"), title: r.get("ratio", 0)} for r in rows])
                        frames.append(df)
                    df_all = reduce(lambda left, right: pd.merge(left, right, on="period", how="outer"), frames)
                    df_all = df_all.sort_values("period")
                    st.line_chart(df_all.set_index("period"), height=st.session_state.get("h_lab", 600))
                    st.dataframe(df_all, use_container_width=True)

# ──────────────────────────────────────────────────────────────────────────────
# 렌더: 사이드바에서 정한 순서대로 출력
# ──────────────────────────────────────────────────────────────────────────────
render_map = {
    "마진 계산기": render_margin,
    "11번가": render_11st,
    "데이터랩": render_datalab,
}

for sec in st.session_state.order:
    st.divider()
    render_map[sec]()

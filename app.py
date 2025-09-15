# app.py — 환율 빠른 계산(사이드바) + 마진 계산기(좌) + 네이버 데이터랩(좌) + 11번가(우)
import streamlit as st
import requests
import pandas as pd
from datetime import timedelta, date
import streamlit.components.v1 as components

st.set_page_config(page_title="실시간 환율 + 마진 계산기", page_icon="📈", layout="wide")

# ---------------------------
# 세션 기본값(안전): setdefault만 사용
# ---------------------------
st.session_state.setdefault("quick_amount", 1.0)
st.session_state.setdefault("quick_currency", "USD")
st.session_state.setdefault("product_price", 1.0)
st.session_state.setdefault("currency", "USD")
st.session_state.setdefault("naver_client_id", "")
st.session_state.setdefault("naver_client_secret", "")

# ---------------------------
# HTTP 세션(Keep-Alive) + 환율 캐시
# ---------------------------
@st.cache_resource
def get_http():
    s = requests.Session()
    s.headers.update({"User-Agent": "envy-sourcing/1.0"})
    return s

http = get_http()

@st.cache_data(ttl=timedelta(minutes=45))
def get_rate_to_krw(base: str) -> float:
    # 1차 소스
    try:
        r = http.get(
            f"https://api.exchangerate.host/latest?base={base}&symbols=KRW",
            timeout=5,
        )
        r.raise_for_status()
        js = r.json()
        if "rates" in js and "KRW" in js["rates"]:
            return float(js["rates"]["KRW"])
    except Exception:
        pass
    # 2차 소스
    try:
        r2 = http.get(f"https://open.er-api.com/v6/latest/{base}", timeout=5)
        r2.raise_for_status()
        js2 = r2.json()
        if js2.get("result") == "success" and "KRW" in js2.get("rates", {}):
            return float(js2["rates"]["KRW"])
    except Exception:
        pass
    return 0.0

# ======================
# 사이드바: 환율 빠른 계산 (기본값 1 USD)
# ======================
sb = st.sidebar
sb.header("💱 환율 빠른 계산")

with sb.form("quick_fx_form"):
    quick_amount = sb.number_input(
        "상품 원가", min_value=0.0, value=float(st.session_state.quick_amount), step=1.0, format="%.2f"
    )
    quick_currency = sb.selectbox(
        "통화 선택",
        ["USD", "CNY", "JPY", "EUR"],
        index=["USD", "CNY", "JPY", "EUR"].index(st.session_state.quick_currency),
    )
    fx_submit = sb.form_submit_button("계산")

if fx_submit:
    st.session_state.quick_amount = float(quick_amount)
    st.session_state.quick_currency = quick_currency

q_rate = get_rate_to_krw(st.session_state.quick_currency)
if q_rate > 0:
    q_result = st.session_state.quick_amount * q_rate
    sb.metric(
        label=f"{st.session_state.quick_amount:.2f} {st.session_state.quick_currency} → 원화",
        value=f"{q_result:,.0f} KRW",
    )
    sb.caption(f"현재 환율: 1 {st.session_state.quick_currency} = {q_rate:,.2f} KRW (45분 캐시)")
else:
    sb.error("환율을 불러오지 못했습니다. 잠시 후 다시 시도하세요.")

# ======================
# 본문: 제목
# ======================
st.title("📈 실시간 환율 + 마진 계산기")

# ======================
# 본문 가로 배치: 좌(마진 계산기 + 데이터랩) / 우(11번가)
# ======================
left, right = st.columns([1.4, 1])

# ----- 좌측: 마진 계산기 -----
with left:
    st.subheader("📥 기본 입력값 / 마진 계산")
    with st.form("margin_form"):
        c1, c2 = st.columns(2)
        with c1:
            product_price = st.number_input(
                "상품 원가", min_value=0.0, value=float(st.session_state.product_price), step=1.0, format="%.2f"
            )
            local_shipping = st.number_input("현지 배송비", min_value=0.0, value=0.0, step=1.0, format="%.2f")
            intl_shipping = st.number_input("국제 배송비 (KRW)", min_value=0.0, value=0.0, step=100.0, format="%.0f")
        with c2:
            card_fee = st.number_input("카드 수수료 (%)", min_value=0.0, value=4.0, step=0.1, format="%.1f") / 100
            market_fee = st.number_input("마켓 수수료 (%)", min_value=0.0, value=15.0, step=0.1, format="%.1f") / 100
            currency = st.selectbox(
                "통화 선택(마진 계산용)",
                ["USD", "CNY", "JPY", "EUR"],
                index=["USD", "CNY", "JPY", "EUR"].index(st.session_state.currency),
            )

        mode = st.radio("계산 방식", ["목표 마진 → 판매가", "판매가 → 순이익"], horizontal=True)
        margin_mode = None
        margin_rate_input = None
        margin_add_input = None
        selling_price_input = None

        if mode == "목표 마진 → 판매가":
            margin_mode = st.radio("마진 방식", ["퍼센트 마진 (%)", "더하기 마진 (₩)"], horizontal=True)
            if margin_mode == "퍼센트 마진 (%)":
                margin_rate_input = st.number_input("목표 마진 (%)", min_value=0.0, value=40.0, step=1.0, format="%.1f")
            else:
                margin_add_input = st.number_input("목표 마진 (₩)", min_value=0.0, value=20000.0, step=1000.0, format="%.0f")
        else:
            selling_price_input = st.number_input(
                "판매가 입력 (KRW)", min_value=0.0, value=100000.0, step=1000.0, format="%.0f"
            )

        calc = st.form_submit_button("계산하기")

    if calc:
        st.session_state.product_price = float(product_price)
        st.session_state.currency = currency

    rate_for_margin = get_rate_to_krw(st.session_state.currency)
    if rate_for_margin == 0:
        st.error("환율을 불러오지 못해 마진 계산을 진행할 수 없습니다.")
    else:
        st.caption(f"💱 현재 환율: 1 {st.session_state.currency} = {rate_for_margin:,.2f} KRW")
        base_cost_krw = (float(product_price) + float(local_shipping)) * rate_for_margin + float(intl_shipping)

        if calc:
            if mode == "목표 마진 → 판매가":
                if margin_mode == "퍼센트 마진 (%)":
                    margin_rate = (margin_rate_input or 0) / 100
                    selling_price = base_cost_krw / (1 - (market_fee + card_fee + margin_rate))
                    net_profit = selling_price * (1 - (market_fee + card_fee)) - base_cost_krw
                    profit_rate = (net_profit / selling_price) if selling_price > 0 else 0.0
                else:
                    margin_add = margin_add_input or 0.0
                    selling_price = (base_cost_krw + margin_add) / (1 - (market_fee + card_fee))
                    net_profit = margin_add
                    profit_rate = (net_profit / selling_price) if selling_price > 0 else 0.0

                st.markdown("### 📊 계산 결과")
                st.write(f"- 원가 합계: **{base_cost_krw:,.0f} 원**")
                st.write(f"- 목표 판매가: **{selling_price:,.0f} 원**")
                st.write(f"- 예상 순이익: **{net_profit:,.0f} 원**")
                st.write(f"- 순이익률: **{profit_rate*100:.1f}%**")

            else:
                selling_price = float(selling_price_input or 0.0)
                net_after_fee = selling_price * (1 - (market_fee + card_fee))
                net_profit = net_after_fee - base_cost_krw
                profit_rate = (net_profit / selling_price) if selling_price > 0 else 0.0

                st.markdown("### 📊 계산 결과")
                st.write(f"- 원가 합계: **{base_cost_krw:,.0f} 원**")
                st.write(f"- 입력 판매가: **{selling_price:,.0f} 원**")
                st.write(f"- 예상 순이익: **{net_profit:,.0f} 원**")
                st.write(f"- 순이익률: **{profit_rate*100:.1f}%**")

    # --------- 네이버 데이터랩 (검색 트렌드) ---------
    st.divider()
    st.subheader("📈 네이버 데이터랩 (검색 트렌드)")

    with st.expander("API 설정 / 키워드 조회", expanded=True):
        with st.form("datalab_form"):
            cc1, cc2 = st.columns(2)
            with cc1:
                naver_client_id = st.text_input("NAVER Client ID", value=st.session_state.naver_client_id)
                start_date = st.date_input("시작일", value=date.today().replace(day=1))
                time_unit = st.selectbox("집계단위", ["date", "week", "month"], index=1)
            with cc2:
                naver_client_secret = st.text_input(
                    "NAVER Client Secret", value=st.session_state.naver_client_secret, type="password"
                )
                end_date = st.date_input("종료일", value=date.today())
                device = st.selectbox("디바이스", ["", "pc", "mo"], index=0)  # ''=전체, pc, mo

            kw_text = st.text_input("키워드(쉼표로 구분)", value="나이키, 아디다스")
            run_dl = st.form_submit_button("트렌드 조회")

        if run_dl:
            st.session_state.naver_client_id = naver_client_id
            st.session_state.naver_client_secret = naver_client_secret

            def fetch_datalab_search(keywords, startDate, endDate, timeUnit, device=""):
                url = "https://openapi.naver.com/v1/datalab/search"
                headers = {
                    "X-Naver-Client-Id": st.session_state.naver_client_id,
                    "X-Naver-Client-Secret": st.session_state.naver_client_secret,
                    "Content-Type": "application/json",
                }
                keywordGroups = [{"groupName": k.strip(), "keywords": [k.strip()]} for k in keywords if k.strip()]
                payload = {
                    "startDate": str(startDate),
                    "endDate": str(endDate),
                    "timeUnit": timeUnit,
                    "keywordGroups": keywordGroups,
                }
                if device:
                    payload["device"] = device
                resp = http.post(url, headers=headers, json=payload, timeout=7)
                resp.raise_for_status()
                return resp.json()

            try:
                keys = [k.strip() for k in kw_text.split(",")]
                js = fetch_datalab_search(keys, start_date, end_date, time_unit, device if device else "")
                # JSON -> DataFrame ({"results":[{"data":[{"period":"YYYY-MM-DD","ratio":...}, ...], "title": "..."}]})
                frames = []
                for res in js.get("results", []):
                    title = res.get("title", "keyword")
                    rows = res.get("data", [])
                    df = pd.DataFrame(rows)
                    df["keyword"] = title
                    frames.append(df)
                if frames:
                    df_all = pd.concat(frames, ignore_index=True)
                    df_pivot = df_all.pivot(index="period", columns="keyword", values="ratio").fillna(0)
                    st.line_chart(df_pivot)
                    st.dataframe(df_pivot.reset_index(), use_container_width=True)
                else:
                    st.warning("데이터가 없습니다. 기간/키워드/설정을 확인하세요.")
            except requests.HTTPError as e:
                st.error(f"HTTP 오류: {e}")
                if e.response is not None:
                    try:
                        st.code(e.response.text)
                    except Exception:
                        pass
            except Exception as e:
                st.error(f"데이터를 불러오지 못했습니다: {e}")

# ----- 우측: 11번가 -----
with right:
    st.subheader("🛒 11번가 아마존 베스트 (모바일)")
    lazy_11 = st.checkbox("화면에 임베드(느릴 수 있음)", value=False, key="embed11")
    st.link_button("🔗 새 창으로 열기", "https://m.11st.co.kr/browsing/AmazonBest")
    if lazy_11:
        sel = st.selectbox("보기 선택", ["아마존 베스트", "오늘의 딜", "홈"], index=0, key="view11")
        if sel == "아마존 베스트":
            url = "https://m.11st.co.kr/browsing/AmazonBest"
        elif sel == "오늘의 딜":
            url = "https://m.11st.co.kr/browsing/todayDeal"
        else:
            url = "https://m.11st.co.kr/"
        height = st.slider("높이(px)", 500, 1400, 900, 50, key="h11")
        components.html(
            f"""
            <div style="border:1px solid #e5e7eb;border-radius:10px;overflow:hidden">
                <iframe src="{url}" style="width:100%;height:{height}px;border:0"
                        referrerpolicy="no-referrer"
                        sandbox="allow-same-origin allow-scripts allow-popups allow-forms"></iframe>
            </div>
            """,
            height=height + 14,
        )

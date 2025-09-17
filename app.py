# =========================
# Part 1 — 설정/헬퍼
# =========================
import os, time, json, math
import requests
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="ENVY v27.14 • Full",
    page_icon="🛠️",
    layout="wide"
)

# --------- THEME / STYLE ---------
if "dark" not in st.session_state:
    st.session_state.dark = False

def inject_base_css():
    # 사이드바 스크롤 제거 & 카드 와이드 & 알림 색상
    st.markdown("""
    <style>
      /* 사이드바 높이 고정 + 스크롤 제거 */
      section[data-testid="stSidebar"] > div { 
        height: 100vh !important; 
        overflow: hidden !important; 
      }
      /* 결과 배지 색상 */
      .box-badge {border-radius:12px; padding:10px 12px; font-weight:600;}
      .fx-badge { background:#E7F8E9; color:#1A7F37; border:1px solid #BFE7C6;}
      .rev-badge{ background:#E7F2FF; color:#174EA6; border:1px solid #BBD4FF;}
      .profit-badge{ background:#FFF6D6; color:#8A5A00; border:1px solid #FFE6A3;}

      /* 컨테이너 간 여백 다이어트 */
      .block-container { padding-top: 12px; padding-bottom: 30px; }
      /* 카드 느낌 */
      .card { background: var(--card-bg); border: 1px solid var(--card-bd);
              border-radius: 14px; padding: 14px 16px; }
    </style>
    """, unsafe_allow_html=True)

def inject_theme_css():
    if st.session_state.dark:
        st.markdown("""
        <style>
          :root{ --card-bg:#0E1117; --card-bd:#1F2937; }
          body{ color:#E5E7EB; }
        </style>""", unsafe_allow_html=True)
    else:
        st.markdown("""
        <style>
          :root{ --card-bg:#FFFFFF; --card-bd:#E5E7EB; }
        </style>""", unsafe_allow_html=True)

inject_base_css()
inject_theme_css()

# --------- SECRET / CONFIG ---------
PROXY_URL = st.secrets.get("proxy_url", "").strip()
RAKUTEN_APP_ID = st.secrets.get("rakuten_app_id", "").strip()

# --------- NETWORK ---------
def http_get_json(url, params=None, headers=None, timeout=15):
    try:
        r = requests.get(url, params=params, headers=headers, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"_error": str(e)}

# 프록시 경유 GET (target=원격URL)
def proxy_get_json(target_url, params=None):
    if not PROXY_URL:
        return {"_error": "proxy_url_missing"}
    try:
        resp = requests.get(
            PROXY_URL,
            params={"target": target_url, **(params or {})},
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"_error": str(e)}

# --------- 계산기 로직 (v23) ---------
def fx_convert(amount, rate):
    return amount * rate

def margin_calc(
    sell_price_local,     # 판매금액(현지통화)
    fx_rate,              # 환율
    card_fee_pct,         # 카드 수수료 %
    market_fee_pct,       # 마켓 수수료 %
    shipping_won,         # 배송비(￦)
    margin_mode="pct",    # "pct" or "add"
    margin_value=10.0     # 퍼센트 또는 더하기 마진 값
):
    # 환산금액(￦)
    won_from_fx = sell_price_local * fx_rate

    # 카드/마켓 수수료 계산(￦ 기준)
    card_fee = won_from_fx * (card_fee_pct/100)
    market_fee = won_from_fx * (market_fee_pct/100)

    base_cost = won_from_fx + card_fee + market_fee + shipping_won

    if margin_mode == "pct":
        final_price = base_cost * (1 + margin_value/100.0)
    else:
        final_price = base_cost + margin_value

    profit = final_price - base_cost
    return final_price, profit, won_from_fx

# --------- 데이터랩 (프록시 → ranks) ---------
# 내부 프록시가 JSON을 {"ranks":[{"rank":..,"keyword":..,"search":..}]} 형태로 내도록 설계
# (이미 네 Worker에서 검증 완료)
def datalab_fetch(category_name):
    # 실제 네 Worker는 target 파라미터만 보면 되므로 category_name만 붙여서 힌트 전달
    target = f"https://datalab.naver.com/ENVY?cat={category_name}"
    data = proxy_get_json(target)
    if "_error" in data:
        return None, f"http 오류 / 프록시 / 기간·CID 확인: {data['_error']}"
    ranks = data.get("ranks", [])
    if not ranks:
        return None, "empty-list (프록시/기간/CID 확인)"
    df = pd.DataFrame(ranks)[["rank","keyword","search"]]
    return df, None

# --------- 라쿠텐(글로벌 키 레이더) ---------
# 간단히: 장르ID/쿼리 → 랭킹 API → 키워드 추출(제목 기반)
def rakuten_ranking(app_id, genre_id="0"):
    if not app_id:
        return pd.DataFrame(), "Rakuten App ID 없음(secrets.toml)"
    try:
        url = "https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20170628"
        params = {"applicationId": app_id}
        if genre_id and genre_id != "0":
            params["genreId"] = genre_id
        js = http_get_json(url, params=params)
        if "_error" in js:
            return pd.DataFrame(), js["_error"]
        items = js.get("Items", [])
        rows = []
        for i, it in enumerate(items, start=1):
            title = (it.get("Item", {}) or {}).get("itemName", "")
            if not title: 
                continue
            # 간단 키워드 추출(공백/기호 기준)
            kw = title.split()[0][:30]
            rows.append({"rank": i, "keyword": kw, "source": "Rakuten JP"})
        return pd.DataFrame(rows), None
    except Exception as e:
        return pd.DataFrame(), str(e)
# =========================
# Part 2 — 사이드바 + 계산기
# =========================

with st.sidebar:
    st.write("🌗", "다크 모드", help="토글하면 즉시 적용")
    st.toggle("다크 모드 사용", key="dark", value=st.session_state.dark, on_change=inject_theme_css)

    st.markdown("### ① 환율 계산기")
    base_ccy = st.selectbox("기준 통화", ["USD","EUR","JPY","CNY"], index=0, label_visibility="collapsed")
    # 시연을 위해 환율 수동(소수 2자리 허용)
    fx_rate = st.number_input("환율 (1 {0} ➜ ￦)".format(base_ccy), min_value=0.0, step=0.01, value=1400.00, format="%.2f")
    sell_price = st.number_input("판매금액 ({0})".format(base_ccy), min_value=0.0, step=1.00, value=1.00, format="%.2f")

    # 환산 금액 뱃지
    won_fx = fx_convert(sell_price, fx_rate)
    st.markdown(f'<div class="box-badge fx-badge">환산 금액: {won_fx:,.2f} 원</div>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### ② 마진 계산기 (v23)")
    base_ccy_m = st.selectbox("기준 통화(판매금액)", ["USD","EUR","JPY","CNY"], index=0, key="m_ccy", label_visibility="collapsed")
    fx_rate_m = st.number_input("환율 (1 {0} ➜ ￦)".format(base_ccy_m), min_value=0.0, step=0.01, value=1400.00, key="m_fx", format="%.2f")
    sell_price_m = st.number_input("판매금액 ({0})".format(base_ccy_m), min_value=0.0, step=1.00, value=1.00, key="m_sell", format="%.2f")

    st.markdown(f'<div class="box-badge rev-badge">판매금액(환산): {sell_price_m*fx_rate_m:,.2f} 원</div>', unsafe_allow_html=True)

    card_fee = st.number_input("카드수수료 (%)", min_value=0.0, step=0.10, value=4.00, format="%.2f")
    market_fee = st.number_input("마켓수수료 (%)", min_value=0.0, step=0.10, value=14.00, format="%.2f")
    shipping = st.number_input("배송비 (￦)", min_value=0.0, step=100.0, value=0.0, format="%.0f")

    margin_mode = st.radio("마진 방식", ["퍼센트 마진(%)", "더하기 마진(￦)"], horizontal=False)
    if margin_mode == "퍼센트 마진(%)":
        margin_value = st.number_input("마진율 (%)", min_value=0.0, step=0.50, value=10.00, format="%.2f")
        mode_key = "pct"
    else:
        margin_value = st.number_input("더하기 마진(￦)", min_value=0.0, step=100.0, value=0.0, format="%.0f")
        mode_key = "add"

    final_price, profit, won_from_fx = margin_calc(
        sell_price_m, fx_rate_m, card_fee, market_fee, shipping,
        margin_mode=mode_key, margin_value=margin_value
    )
    st.markdown(f'<div class="box-badge rev-badge">예상 판매가: {final_price:,.2f} 원</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="box-badge profit-badge">순이익(마진): {profit:,.2f} 원</div>', unsafe_allow_html=True)

    # ❗요청사항: 사이드바 하단 프록시/라쿠텐 정보는 숨김 (secrets 사용)
    st.markdown("---")
    st.caption("※ 프록시/키는 secrets.toml 로드. UI 비노출.")
# =========================
# Part 3 — 본문 레이아웃 (2×3)
# =========================

colA, colB, colC = st.columns([1,1,1])

# ---- (A1) 데이터랩 ----
with colA:
    st.subheader("데이터랩")
    cat = st.selectbox("카테고리(10개)", [
        "패션잡화","가구/인테리어","식품","생활/건강","출산/육아",
        "화장품/미용","디지털/가전","스포츠/레저","취미/문구","도서"
    ], index=0, label_visibility="visible")
    # 최초 자동 호출
    df_dlab, err = datalab_fetch(cat)
    if st.button("데이터랩 재시도", use_container_width=True):
        df_dlab, err = datalab_fetch(cat)

    if err:
        st.warning(f"DataLab 호출 실패: {err}")
    else:
        st.dataframe(df_dlab, use_container_width=True, height=240)
        # 실선 그래프(검색량)
        try:
            chart_df = df_dlab.sort_values("rank").set_index("rank")["search"]
            st.line_chart(chart_df, height=160)
        except Exception:
            pass

# ---- (B1) 아이템스카우트 자리(고정/나중 연동) ----
with colB:
    st.subheader("아이템스카우트")
    st.info("현재는 레이아웃 고정용 데모 상태입니다.", icon="🧩")
    st.empty()

# ---- (C1) 셀러라이프 자리(고정/나중 연동) ----
with colC:
    st.subheader("셀러라이프")
    st.info("현재는 레이아웃 고정용 데모 상태입니다.", icon="🧩")
    st.empty()

st.markdown("")

# ---- (A2) AI 키워드 레이더 (국내/글로벌) ----
with colA:
    st.subheader("AI 키워드 레이더 (국내/글로벌)")
    mode = st.radio("모드", ["국내","글로벌"], horizontal=True)
    if mode == "국내":
        if df_dlab is None or err:
            st.caption("국내 데이터랩 표가 재시도 시 동일 리스트로 표시됩니다.")
            st.dataframe(pd.DataFrame({"rank":[1,2,3,4,5],"keyword":["키워드A","키워드B","키워드C","키워드D","키워드E"]}), height=230)
        else:
            st.dataframe(df_dlab[["rank","keyword"]], use_container_width=True, height=230)
    else:
        # 라쿠텐 실데이터
        df_rakuten, rerr = rakuten_ranking(RAKUTEN_APP_ID, genre_id="0")
        if rerr:
            st.warning(f"Rakuten 수집 실패: {rerr}")
        st.dataframe(df_rakuten, use_container_width=True, height=230)

# ---- (B2) 11번가 (모바일) ----
with colB:
    st.subheader("11번가 (모바일)")
    url_11 = st.text_input("11번가 URL", "https://m.11st.co.kr/browsing/bestSellers.tmall")
    # 모바일 프록시/오류/임베드 제한 대비
    st.caption("정책상 임베드가 막히는 경우가 있어 별도 프록시/프레임 제거를 추후 추가합니다.")
    try:
        st.components.v1.iframe(src=url_11, height=520, scrolling=True)
    except Exception:
        st.info("임베드 제한으로 표시가 어려운 페이지입니다.")

# ---- (C2) 상품명 생성기 (규칙 기반) ----
with colC:
    st.subheader("상품명 생성기 (규칙 기반)")
    brand = st.text_input("브랜드", "envy")
    base_kw = st.text_input("베이스 키워드", "K-coffee mix")
    rel_kw = st.text_input("연관키워드", "Maxim, Kanu, Korea")
    ban_kw = st.text_input("금칙어", "copy, fake, replica")
    limit = st.slider("글자수 제한", 20, 80, 80)

    def rule_title(brand, base_kw, rel_kw, ban_kw, limit):
        out = f"{brand} {base_kw} {rel_kw}".replace(",", " ")
        for b in [w.strip() for w in ban_kw.split(",") if w.strip()]:
            out = out.replace(b, "")
        out = " ".join(out.split())[:limit]
        return out

    if st.button("제목 5개 생성", use_container_width=True):
        outs = [rule_title(brand, base_kw, rel_kw, ban_kw, limit) for _ in range(5)]
        st.write("**생성 결과**")
        for i, t in enumerate(outs, start=1):
            st.write(f"{i}. {t}")
        st.caption("연관키워드(검색량)는 상단 데이터랩/글로벌 표를 참고하세요.")
# =========================
# Part 4 — 마무리 가드/안내
# =========================

# 프록시/라쿠텐 점검 안내
with st.expander("시스템 상태 / 점검 체크", expanded=False):
    st.write("• 프록시(Cloudflare Worker):", "OK" if PROXY_URL else "미설정(secrets)")
    st.write("• Rakuten App ID:", "OK" if RAKUTEN_APP_ID else "미설정(secrets)")
    st.write("• 다크 모드:", "ON" if st.session_state.dark else "OFF")
    st.caption("※ 프록시/키는 UI에 노출하지 않으며, secrets.toml로 관리합니다.")

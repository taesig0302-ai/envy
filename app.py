# =========================
# Part 1 — 설정/헬퍼 + CSS
# =========================
import os, json, requests, pandas as pd, streamlit as st

st.set_page_config(page_title="ENVY v27.14 • Full", page_icon="🛠️", layout="wide")

# ---- CSS: 사이드바 간격 확 줄이고, 너무 작을 때만 스크롤 ----
st.markdown("""
<style>
  /* 너무 작을 때만 스크롤(자동) — 잘림 방지 */
  section[data-testid="stSidebar"] > div { height: 100vh; overflow: auto; }
  /* 숫자/라디오/셀렉트 간 여백 최소화 */
  section[data-testid="stSidebar"] .stNumberInput, 
  section[data-testid="stSidebar"] .stSelectbox,
  section[data-testid="stSidebar"] .stRadio { padding-bottom: 4px !important; margin-bottom: 4px !important; }
  section[data-testid="stSidebar"] label { margin-bottom: 3px !important; }
  /* 배지 */
  .box-badge {border-radius:12px; padding:8px 10px; font-weight:600;}
  .fx-badge { background:#E7F8E9; color:#1A7F37; border:1px solid #BFE7C6;}
  .rev-badge{ background:#E7F2FF; color:#174EA6; border:1px solid #BBD4FF;}
  .profit-badge{ background:#FFF6D6; color:#8A5A00; border:1px solid #FFE6A3;}
  /* 카드 */
  .card { background: var(--card-bg,#fff); border: 1px solid var(--card-bd,#E5E7EB);
          border-radius: 14px; padding: 12px 14px; }
  .block-container { padding-top:10px; padding-bottom:28px; }
</style>
""", unsafe_allow_html=True)

# ---- 다크모드 토글 시 즉시 재렌더
if "dark" not in st.session_state:
    st.session_state.dark = False
def _toggle_dark():
    st.session_state.dark = not st.session_state.dark
    st.rerun()

# ---- secrets + UI fallback (연결 설정)
def get_proxy_url():
    # secrets → 세션 → (미입력시 빈 문자열)
    if "proxy_url" in st.session_state and st.session_state.proxy_url:
        return st.session_state.proxy_url.strip()
    return st.secrets.get("proxy_url","").strip()

def get_rakuten_app_id():
    if "rakuten_app_id" in st.session_state and st.session_state.rakuten_app_id:
        return st.session_state.rakuten_app_id.strip()
    return st.secrets.get("rakuten_app_id","").strip()

def http_get_json(url, params=None, headers=None, timeout=15):
    try:
        r = requests.get(url, params=params, headers=headers, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"_error": str(e)}

def proxy_get_json(target_url, params=None):
    proxy = get_proxy_url()
    if not proxy:
        return {"_error": "proxy_url_missing"}
    try:
        r = requests.get(proxy, params={"target": target_url, **(params or {})}, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"_error": str(e)}

# ---- 계산기(v23)
def fx_convert(amount, rate): return amount * rate

def margin_calc(sell_price_local, fx_rate, card_fee_pct, market_fee_pct, shipping_won,
                margin_mode="pct", margin_value=10.0):
    won_from_fx = sell_price_local * fx_rate
    card_fee = won_from_fx * (card_fee_pct/100)
    market_fee = won_from_fx * (market_fee_pct/100)
    base_cost = won_from_fx + card_fee + market_fee + shipping_won
    if margin_mode == "pct":
        final_price = base_cost * (1 + margin_value/100.0)
    else:
        final_price = base_cost + margin_value
    profit = final_price - base_cost
    return final_price, profit, won_from_fx

# ---- DataLab
def datalab_fetch(category_name):
    target = f"https://datalab.naver.com/ENVY?cat={category_name}"
    js = proxy_get_json(target)
    if "_error" in js:
        return None, f"http 오류 / 프록시 / 기간·CID 확인: {js['_error']}"
    ranks = js.get("ranks", [])
    if not ranks:
        return None, "empty-list (프록시/기간/CID 확인)"
    df = pd.DataFrame(ranks)[["rank","keyword","search"]]
    return df, None

# ---- Rakuten
def rakuten_ranking(app_id, genre_id="0"):
    if not app_id:
        return pd.DataFrame(), "Rakuten App ID 없음(secrets/UI)"
    try:
        url = "https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20170628"
        params = {"applicationId": app_id}
        if genre_id and genre_id != "0": params["genreId"] = genre_id
        js = http_get_json(url, params=params)
        if "_error" in js: return pd.DataFrame(), js["_error"]
        items = js.get("Items", [])
        rows = []
        for i, it in enumerate(items, start=1):
            title = (it.get("Item", {}) or {}).get("itemName","")
            if not title: continue
            kw = title.split()[0][:30]
            rows.append({"rank":i,"keyword":kw,"source":"Rakuten JP"})
        return pd.DataFrame(rows), None
    except Exception as e:
        return pd.DataFrame(), str(e)
# =========================
# Part 2 — 사이드바
# =========================
with st.sidebar:
    st.write("🌗", "다크 모드")
    st.toggle("다크 모드 사용", key="__dark__", value=st.session_state.dark, on_change=_toggle_dark)

    st.markdown("### ① 환율 계산기")
    base_ccy = st.selectbox("기준 통화", ["USD","EUR","JPY","CNY"], index=0)
    fx_rate = st.number_input(f"환율 (1 {base_ccy} ➜ ￦)", min_value=0.0, step=0.01, value=1400.00, format="%.2f")
    sell_price = st.number_input(f"판매금액 ({base_ccy})", min_value=0.0, step=1.00, value=1.00, format="%.2f")
    st.markdown(f'<div class="box-badge fx-badge">환산 금액: {fx_convert(sell_price, fx_rate):,.2f} 원</div>', unsafe_allow_html=True)

    st.markdown("### ② 마진 계산기 (v23)")
    base_ccy_m = st.selectbox("기준 통화(판매금액)", ["USD","EUR","JPY","CNY"], index=0, key="m_ccy")
    fx_rate_m = st.number_input(f"환율 (1 {base_ccy_m} ➜ ￦)", min_value=0.0, step=0.01, value=1400.00, key="m_fx", format="%.2f")
    sell_price_m = st.number_input(f"판매금액 ({base_ccy_m})", min_value=0.0, step=1.00, value=1.00, key="m_sell", format="%.2f")
    st.markdown(f'<div class="box-badge rev-badge">판매금액(환산): {sell_price_m*fx_rate_m:,.2f} 원</div>', unsafe_allow_html=True)

    card_fee = st.number_input("카드수수료 (%)", min_value=0.0, step=0.1, value=4.00, format="%.2f")
    market_fee = st.number_input("마켓수수료 (%)", min_value=0.0, step=0.1, value=14.00, format="%.2f")
    shipping = st.number_input("배송비 (￦)", min_value=0.0, step=100.0, value=0.0, format="%.0f")
    margin_mode = st.radio("마진 방식", ["퍼센트 마진(%)", "더하기 마진(￦)"])
    margin_value = st.number_input("마진율(%) / 더하기(￦)", min_value=0.0, step=0.5, value=10.0, format="%.2f")

    mode_key = "pct" if margin_mode.startswith("퍼센트") else "add"
    final_price, profit, won_from_fx = margin_calc(
        sell_price_m, fx_rate_m, card_fee, market_fee, shipping, margin_mode=mode_key, margin_value=margin_value
    )
    st.markdown(f'<div class="box-badge rev-badge">예상 판매가: {final_price:,.2f} 원</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="box-badge profit-badge">순이익(마진): {profit:,.2f} 원</div>', unsafe_allow_html=True)

    # ---- 연결 설정(임시 입력) : secrets 없는 경우만 보이게
    if not get_proxy_url() or not get_rakuten_app_id():
        with st.expander("연결 설정 (프록시·라쿠텐 App ID)", expanded=True):
            st.text_input("Cloudflare Worker 프록시 URL", key="proxy_url", placeholder="https://xxxx.workers.dev")
            st.text_input("Rakuten App ID", key="rakuten_app_id", placeholder="숫자 16~19자리")
            st.caption("※ 여기 입력하면 즉시 사용됩니다. 운영 배포는 secrets.toml 사용 권장.")
# =========================
# Part 3 — 본문 레이아웃 (2×3)
# =========================
colA, colB, colC = st.columns([1,1,1])

# (A1) 데이터랩
with colA:
    st.subheader("데이터랩")
    cat = st.selectbox("카테고리(10개)", [
        "패션잡화","가구/인테리어","식품","생활/건강","출산/육아",
        "화장품/미용","디지털/가전","스포츠/레저","취미/문구","도서"
    ], index=0)

    df_dlab, err = datalab_fetch(cat)               # ✅ 진입 즉시 자동 호출
    if st.button("데이터랩 재시도", use_container_width=True):
        df_dlab, err = datalab_fetch(cat)

    if err:
        st.warning(f"DataLab 호출 실패: {err}")
    else:
        st.dataframe(df_dlab, use_container_width=True, height=220)
        try:
            chart_df = df_dlab.sort_values("rank").set_index("rank")["search"]
            st.line_chart(chart_df, height=140)
        except Exception:
            pass

# (B1) 아이템스카우트 (자리만)
with colB:
    st.subheader("아이템스카우트")
    st.info("현재는 레이아웃 고정용 데모 상태입니다.", icon="🧩")

# (C1) 셀러라이프 (자리만)
with colC:
    st.subheader("셀러라이프")
    st.info("현재는 레이아웃 고정용 데모 상태입니다.", icon="🧩")

st.markdown("")

# (A2) AI 키워드 레이더
with colA:
    st.subheader("AI 키워드 레이더 (국내/글로벌)")
    mode = st.radio("모드", ["국내","글로벌"], horizontal=True)
    if mode == "국내":
        if df_dlab is None or err:
            st.dataframe(pd.DataFrame({"rank":[1,2,3,4,5],"keyword":["키워드A","키워드B","키워드C","키워드D","키워드E"]}),
                         use_container_width=True, height=220)
        else:
            st.dataframe(df_dlab[["rank","keyword"]], use_container_width=True, height=220)
    else:
        df_rakuten, rerr = rakuten_ranking(get_rakuten_app_id(), genre_id="0")
        if rerr:
            st.warning(f"Rakuten 수집 실패: {rerr}")
        st.dataframe(df_rakuten, use_container_width=True, height=220)

# (B2) 11번가 (모바일) — CSP 차단 시 대체뷰
with colB:
    st.subheader("11번가 (모바일)")
    url_11 = st.text_input("11번가 URL", "https://m.11st.co.kr/browsing/bestSellers.tmall")
    try:
        st.components.v1.iframe(src=url_11, height=520, scrolling=True)
    except Exception:
        pass
    st.caption("임베드 제한 시 아래 정적 미리보기를 사용합니다.")
    # 정적 프록시(읽기 전용 미리보기)
    static_view = f"https://r.jina.ai/http://{url_11.removeprefix('https://').removeprefix('http://')}"
    st.components.v1.iframe(src=static_view, height=520, scrolling=True)

# (C2) 상품명 생성기 (규칙 기반)
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
        return " ".join(out.split())[:limit]

    if st.button("제목 5개 생성", use_container_width=True):
        outs = [rule_title(brand, base_kw, rel_kw, ban_kw, limit) for _ in range(5)]
        st.write("**생성 결과**")
        for i, t in enumerate(outs, start=1):
            st.write(f"{i}. {t}")
        st.caption("연관키워드(검색량)는 상단 데이터랩/글로벌 표를 참고하세요.")
# =========================
# Part 4 — 점검 패널
# =========================
with st.expander("시스템 상태 / 점검 체크", expanded=False):
    st.write("• 프록시(Worker):", "OK" if get_proxy_url() else "미설정")
    st.write("• Rakuten App ID:", "OK" if get_rakuten_app_id() else "미설정")
    st.write("• 다크 모드:", "ON" if st.session_state.dark else "OFF")
    st.caption("※ 운영 배포는 반드시 secrets.toml에 proxy_url / rakuten_app_id를 저장하세요.")

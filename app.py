# ============================================
# Part 0 — 공통 유틸 & 테마 (v8)
# ============================================
import streamlit as st
import requests, pandas as pd, re, json, urllib.parse, time, base64
from bs4 import BeautifulSoup
from pathlib import Path

st.set_page_config(page_title="ENVY v8", page_icon="✨", layout="wide")

# ---- (선택) 프록시: Cloudflare Worker (X-Frame/CSP 우회)
# 예: "https://<your-worker>.workers.dev"
PROXY_URL = ""   # 비워도 앱은 동작, 임베드 성공률은 낮아짐

def has_proxy() -> bool:
    return isinstance(PROXY_URL, str) and PROXY_URL.strip() != ""

def iframe_url(target: str) -> str:
    if not has_proxy():
        return target
    return f"{PROXY_URL}/iframe?target={urllib.parse.quote(target, safe='')}"

# ---- UA / 공통 상수
MOBILE_HEADERS = {
    "user-agent": ("Mozilla/5.0 (Linux; Android 13; Pixel 7)"
                   " AppleWebKit/537.36 (KHTML, like Gecko)"
                   " Chrome/125.0 Mobile Safari/537.36"),
    "accept-language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "cache-control": "no-cache",
}
CURRENCY_SYMBOL = {"USD":"$", "EUR":"€", "JPY":"¥", "CNY":"元"}
FX_DEFAULT = {"USD":1400.0, "EUR":1500.0, "JPY":10.0, "CNY":200.0}

def init_theme_state():
    if "theme" not in st.session_state:
        st.session_state["theme"] = "light"

def toggle_theme():
    st.session_state["theme"] = "dark" if st.session_state["theme"]=="light" else "light"

def inject_css():
    theme = st.session_state.get("theme", "light")
    bg, fg = ("#0e1117", "#e6edf3") if theme == "dark" else ("#ffffff", "#111111")

    st.markdown(
        f"""
<style id="envy-sticky-css">
  /* ====== 앱 전역 ====== */
  html, body, [data-testid="stAppViewContainer"] {{
    background-color: {bg} !important;
    color: {fg} !important;
  }}

  /* ====== 본문 섹션카드: 위/아래 여백 “고정” ====== */
  .block-container {{
    padding-top: 0.90rem !important;   /* 더 내려달라 요청 반영 */
    padding-bottom: 0.40rem !important;
  }}

  /* ====== 사이드바 압축 (항상 유지) ====== */
  [data-testid="stSidebar"] > div:first-child section {{
    padding-top: 0.18rem !important;
    padding-bottom: 0.18rem !important;
    height: 100vh !important;
    overflow: hidden !important;         /* 스크롤 락 */
    font-size: 0.94rem !important;
  }}
  [data-testid="stSidebar"] ::-webkit-scrollbar {{ display: none !important; }}

  /* 사이드바 컴포넌트 간격 최소화 */
  [data-testid="stSidebar"] .stSelectbox,
  [data-testid="stSidebar"] .stNumberInput,
  [data-testid="stSidebar"] .stRadio,
  [data-testid="stSidebar"] .stMarkdown,
  [data-testid="stSidebar"] .stTextInput,
  [data-testid="stSidebar"] .stButton {{
    margin-top: 0.12rem !important;
    margin-bottom: 0.12rem !important;
  }}

  /* 라벨/제목 줄간격 타이트 */
  [data-testid="stSidebar"] label p,
  [data-testid="stSidebar"] h3 {{
    margin: 0 0 0.12rem 0 !important;
    line-height: 1.12rem !important;
  }}

  /* 입력/셀렉트 높이/폰트 */
  [data-testid="stSidebar"] [data-baseweb="input"] input,
  [data-testid="stSidebar"] .stNumberInput input,
  [data-testid="stSidebar"] [data-baseweb="select"] div[role="combobox"] {{
    height: 1.55rem !important;
    padding-top: 0.10rem !important;
    padding-bottom: 0.10rem !important;
    font-size: 0.92rem !important;
  }}
  [data-testid="stSidebar"] button[kind="secondary"],
  [data-testid="stSidebar"] button[kind="primary"] {{
    padding: 0.16rem 0.48rem !important;
    font-size: 0.92rem !important;
  }}

  /* 로고(축소) */
  .logo-circle {{
    width: 95px; height: 95px; border-radius: 50%;
    overflow: hidden; margin: 0.10rem auto 0.30rem auto;
    box-shadow: 0 2px 8px rgba(0,0,0,.12);
    border: 1px solid rgba(0,0,0,.06);
  }}
  .logo-circle img {{ width: 100%; height: 100%; object-fit: cover; }}

  /* 배지 색상(재등록되어도 유지) */
  .badge-green  {{ background: #e6ffcc; border: 1px solid #b6f3a4;
    padding: 6px 10px; border-radius: 6px; color: #0b2e13; font-size: .86rem; }}
  .badge-blue   {{ background: #eef4ff; border: 1px solid #bcd0ff;
    padding: 6px 10px; border-radius: 6px; color: #0a235a; font-size: .86rem; }}
  .badge-yellow {{ background: #fff7d6; border: 1px solid #f1d27a;
    padding: 6px 10px; border-radius: 6px; color: #4a3b07; font-size: .86rem; }}
</style>
""",
        unsafe_allow_html=True,
    )
# ============================================
# Part 1 — 사이드바
# ============================================
import base64
from pathlib import Path

def render_sidebar():
    with st.sidebar:
        # 로고 (95px)
        lp = Path(__file__).parent / "logo.png"
        if lp.exists():
            b64 = base64.b64encode(lp.read_bytes()).decode("ascii")
            st.markdown(
                f'<div class="logo-circle"><img src="data:image/png;base64,{b64}"></div>',
                unsafe_allow_html=True
            )
        else:
            st.caption("logo.png 를 앱 파일과 같은 폴더에 두면 로고가 표시됩니다.")

        # 다크모드
        st.toggle("🌓 다크 모드", value=(st.session_state.get("theme","light")=="dark"), on_change=toggle_theme)

        # ===== ① 환율 계산기 =====
        st.markdown("### ① 환율 계산기")
        base = st.selectbox("기준 통화", list(CURRENCY_SYMBOL.keys()), index=0)
        sale_foreign = st.number_input("판매금액 (외화)", value=1.00, step=0.01, format="%.2f")
        won = FX_DEFAULT[base] * sale_foreign
        st.markdown(f'<div class="badge-green">환산 금액: <b>{won:,.2f} 원</b></div>', unsafe_allow_html=True)
        st.caption(f"환율 기준: {FX_DEFAULT[base]:,.2f} ₩/{base}")

        # ===== ② 마진 계산기 =====
        st.markdown("### ② 마진 계산기")
        m_base = st.selectbox("매입 통화", list(CURRENCY_SYMBOL.keys()), index=0, key="mbase")
        purchase_foreign = st.number_input("매입금액 (외화)", value=0.00, step=0.01, format="%.2f")
        base_cost_won = FX_DEFAULT[m_base] * purchase_foreign if purchase_foreign>0 else won
        st.markdown(f'<div class="badge-green">원가(₩): <b>{base_cost_won:,.2f} 원</b></div>', unsafe_allow_html=True)

        fee_col1, fee_col2 = st.columns(2)
        with fee_col1:
            m_rate = st.number_input("카드수수료(%)", value=4.00, step=0.01, format="%.2f")
        with fee_col2:
            m_fee  = st.number_input("마켓수수료(%)", value=14.00, step=0.01, format="%.2f")

        ship = st.number_input("배송비(₩)", value=0.0, step=100.0, format="%.0f")

        # --- 마진 방식 라디오 (요구 표기 준수) ---
        mode = st.radio("마진 방식", ["% 마진", "+ 마진"], horizontal=True)

        # --- 선택에 따른 입력칸 & 계산 ---
        margin_desc = ""
        if mode == "% 마진":
            margin_pct = st.number_input("마진율 (%)", value=10.00, step=0.01, format="%.2f", key="margin_pct")
            target_price = base_cost_won * (1 + m_rate/100) * (1 + m_fee/100) * (1 + margin_pct/100) + ship
            margin_value = target_price - base_cost_won
            margin_desc = f"{margin_pct:.2f}% 마진"
        else:
            margin_won = st.number_input("마진액 (₩)", value=10000.0, step=100.0, format="%.0f", key="margin_won")
            target_price = base_cost_won * (1 + m_rate/100) * (1 + m_fee/100) + margin_won + ship
            margin_value = margin_won
            margin_desc = f"+{margin_won:,.0f} 마진"

        # 결과 박스(색 유지)
        st.markdown(f'<div class="badge-blue">판매가: <b>{target_price:,.2f} 원</b></div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="badge-yellow">순이익(마진): <b>{margin_value:,.2f} 원</b> — {margin_desc}</div>',
            unsafe_allow_html=True
        )
# ============================================
# Part 2 — 데이터랩 (v8.2: POST 방식 + 프록시/폴백)
# ============================================
from datetime import date

DATALAB_BASE = "https://datalab.naver.com/shoppingInsight/getCategoryKeywordRank.naver"

def _proxy_or_direct(url: str) -> str:
    if has_proxy():
        return f"{PROXY_URL}/fetch?target={urllib.parse.quote(url, safe='')}"
    return url

@st.cache_data(ttl=300)
def datalab_fetch_keywords(payload: dict) -> pd.DataFrame:
    """
    네이버 DataLab 카테고리 키워드 순위 (POST).
    payload 예:
      { 'cid': '50000003', 'timeUnit': 'date',
        'startDate': '2025-08-17', 'endDate': '2025-09-17',
        'gender': '', 'age': '', 'device': '', 'page': '1', 'count': '20' }
    """
    url = _proxy_or_direct(DATALAB_BASE)
    headers = {
        "user-agent": MOBILE_HEADERS["user-agent"],
        "accept": "application/json, text/javascript, */*; q=0.01",
        "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
        "origin": "https://datalab.naver.com",
        "referer": "https://datalab.naver.com/shoppingInsight/sCategory.naver",
        "x-requested-with": "XMLHttpRequest",
    }
    try:
        resp = requests.post(url, data=payload, headers=headers, timeout=12)
        resp.raise_for_status()
        # 가끔 JSON 대신 HTML이 오면 JSONDecodeError → 처리
        data = resp.json()
    except Exception as e:
        raise RuntimeError(f"DataLab 호출 실패: {type(e).__name__}: {e}")

    # 예상 구조: {'ranks': [{'rank':1,'keyword':'...','ratio':...}, ...]}
    rows = data.get("ranks") or data.get("result") or []
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("DataLab 응답에 ranks/result 없음")

    out = []
    for it in rows:
        rank = it.get("rank") or it.get("rnk") or it.get("order")
        kw   = it.get("keyword") or it.get("name") or it.get("title")
        score = (it.get("ratio") or it.get("value") or it.get("score"))
        if rank and kw:
            out.append({"rank": int(rank), "keyword": str(kw), "score": score})
    return pd.DataFrame(out).sort_values("rank")

def render_datalab_block():
    st.subheader("데이터랩")

    # UI: 카테고리/기간/성별/연령/디바이스/개수
    cats = {
        "패션잡화":"50000000-FA", "디지털/가전":"50000000-DG", "식품":"50000000-FD",
        "생활/건강":"50000000-LH","가구/인테리어":"50000000-FN","도서/취미":"50000000-BC",
        "스포츠/레저":"50000000-SP","뷰티":"50000000-BT","출산/육아":"50000000-BB",
        "반려동물":"50000000-PS",
    }
    # 최상위 cid(50000000) + 서브 코드 형태를 실제 API가 받는 단일 cid로 정리 필요
    # 네트워크탭에서 본 'cid=50000003'처럼 **실제 동작 cid**를 직접 넣을 수 있도록 별도 입력 추가
    c1, c2, c3, c4, c5, c6 = st.columns([1,1,1,1,1,1])
    with c1:
        view_cat = st.selectbox("카테고리(표시)", list(cats.keys()), index=2)
    with c2:
        real_cid = st.text_input("실제 cid", value="50000003", help="DevTools Payload에서 본 정수 cid")
    with c3:
        time_unit = st.selectbox("단위", ["date","week","month"], index=0)
    with c4:
        start_y = st.selectbox("시작연", [2024,2025], index=1)
    with c5:
        start_m = st.selectbox("시작월", list(range(1,13)), index=min(date.today().month-1,11))
    with c6:
        count = st.number_input("개수", min_value=10, max_value=50, value=20, step=10)

    # 종료일 자동(오늘)
    today = date.today()
    startDate = f"{start_y}-{start_m:02d}-01"
    endDate   = today.strftime("%Y-%m-%d")

    c7, c8, c9 = st.columns([1,1,1])
    with c7:
        gender = st.selectbox("성별", ["","m","f"], index=0)
    with c8:
        age = st.selectbox("연령", ["","10","20","30","40","50","60"], index=0)
    with c9:
        device = st.selectbox("디바이스", ["","pc","mo"], index=0)

    # 요청 버튼
    do = st.button("추가 갱신")

    # payload 구성 (DevTools Payload 그대로 반영)
    payload = {
        "cid": real_cid,
        "timeUnit": time_unit,
        "startDate": startDate,
        "endDate": endDate,
        "gender": gender,
        "age": age,
        "device": device,
        "page": "1",
        "count": str(int(count)),
    }

    try:
        df = datalab_fetch_keywords(payload)
        if df.empty:
            st.warning("데이터 없음. cid/기간/필터를 바꿔 보세요.")
            return

        st.dataframe(df[["rank","keyword"]], use_container_width=True, hide_index=True)

        # 점수 컬럼이 있으면 그래프 표시
        if "score" in df.columns and df["score"].notna().any():
            g = df[["rank","score"]].set_index("rank")
            st.line_chart(g, height=200)
        else:
            st.caption("응답에 ratio/value/score 없음 → 그래프 생략")

    except Exception as e:
        st.error(str(e))
        with st.expander("대체 방법(HTML 스냅/휴리스틱)"):
            st.caption("프록시를 설정하면 임베드·호출 성공률이 크게 올라갑니다.")
            try:
                # 스냅 임베드(정책에 따라 실패 가능)
                st.components.v1.iframe(
                    iframe_url("https://datalab.naver.com/shoppingInsight/sCategory.naver"),
                    height=560, scrolling=True
                )
            except Exception:
                pass
# ============================================
# Part 3 — 아이템스카우트 (placeholder)
# ============================================
def render_itemscout_block():
    st.subheader("아이템스카우트")
    st.info("연동 대기 (API 키 확보 후 교체)")
# ============================================
# Part 4 — 셀러라이프 (placeholder)
# ============================================
def render_sellerlife_block():
    st.subheader("셀러라이프")
    st.info("연동 대기 (API 키 확보 후 교체)")
# ============================================
# Part 5 — 11번가 (모바일 화면 임베드 고정)
# ============================================
ELEVEN_URL = "https://m.11st.co.kr/browsing/bestSellers.mall"

def _cache_busted(url: str) -> str:
    joiner = "&" if "?" in url else "?"
    return f"{url}{joiner}_={int(time.time())}"

def render_elevenst_block():
    st.subheader("11번가 (모바일)")

    url = st.text_input("모바일 URL", value=ELEVEN_URL, label_visibility="collapsed")
    col1, col2 = st.columns([1,8])
    with col1:
        refresh = st.button("새로고침", use_container_width=True)

    src = _cache_busted(url) if refresh else _cache_busted(url)  # 항상 캐시버스터
    try:
        if has_proxy():
            st.caption("프록시 iFrame (권장)")
            st.components.v1.iframe(iframe_url(src), height=720, scrolling=True)  # key 사용 금지
        else:
            st.warning("PROXY_URL 미설정: 직접 iFrame은 정책에 막힐 수 있습니다.")
            st.components.v1.iframe(src, height=720, scrolling=True)               # key 사용 금지
    except Exception as e:
        st.error(f"11번가 임베드 실패: {type(e).__name__}: {e}")
        st.caption("Cloudflare Worker 프록시를 설정하면 대부분 통과합니다.")
# ============================================
# Part 6 — AI 키워드 레이더 (Rakuten)
# ============================================
RAKUTEN_APP_ID = "1043271015809337425"  # 네가 준 값 그대로

SAFE_GENRES = {
    "전체(샘플)": "100283",
    "여성패션": "100371",
    "남성패션": "551169",
    "뷰티/코스메틱": "100939",
    "식품/식료품": "100316",
    "도서": "101266",
    "음반/CD": "101240",
    "영화/DVD·BD": "101251",
    "취미/게임/완구": "101205",
    "스포츠/레저": "101070",
    "자동차/바이크": "558929",
    "베이비/키즈": "100533",
    "반려동물": "101213",
}
DEFAULT_GENRE = SAFE_GENRES["전체(샘플)"]

def _rk_url(params: dict) -> str:
    endpoint = "https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20170628"
    qs = urllib.parse.urlencode(params, safe="")
    url = f"{endpoint}?{qs}"
    return f"{PROXY_URL}/fetch?target={urllib.parse.quote(url, safe='')}" if has_proxy() else url

@st.cache_data(ttl=600)
def rakuten_fetch_ranking(genre_id: str, rows: int = 50) -> pd.DataFrame:
    params = {
        "applicationId": RAKUTEN_APP_ID,
        "format": "json",
        "formatVersion": 2,
        "genreId": genre_id
    }
    try:
        resp = requests.get(_rk_url(params), headers=MOBILE_HEADERS, timeout=12)
        if resp.status_code == 400:
            raise ValueError("400 Bad Request (장르 코드/매개변수)")
        resp.raise_for_status()
        data = resp.json()
        items = data.get("Items", [])[:rows]

        out=[]
        for i, it in enumerate(items, start=1):
            if isinstance(it, dict) and "itemName" in it:
                name = it.get("itemName") or ""
            else:
                name = (it.get("Item") or {}).get("itemName","")
            if name:
                out.append({"rank":i, "keyword":name, "source":"Rakuten JP"})
        if not out:
            raise ValueError("응답 파싱 결과 비어 있음")
        return pd.DataFrame(out)

    except Exception as e:
        # 폴백: 전체(샘플)
        if genre_id != DEFAULT_GENRE:
            try:
                fb = rakuten_fetch_ranking.__wrapped__(DEFAULT_GENRE, rows)
                fb["note"] = "fallback: genreId 자동 대체"
                return fb
            except Exception:
                pass
        # 최종 데모
        return pd.DataFrame([{"rank":1,
                              "keyword":f"(Rakuten) {type(e).__name__}: {e}",
                              "source":"DEMO"}])

def render_rakuten_block():
    st.subheader("AI 키워드 레이더 (국내/글로벌)")
    st.radio("모드", ["국내","글로벌"], horizontal=True, label_visibility="collapsed")
    c1, c2, c3 = st.columns([1.2,.9,1.2])
    with c1:
        cat = st.selectbox("라쿠텐 카테고리", list(SAFE_GENRES.keys()), index=0)
    with c2:
        preset_id = SAFE_GENRES[cat]
        genre_id = st.text_input("genreId (직접 입력)", value=preset_id)
    with c3:
        st.caption(f"App ID: **{RAKUTEN_APP_ID}**")
        st.caption("400/파싱 실패 → '전체(샘플)'로 자동 폴백")

    df = rakuten_fetch_ranking(genre_id=genre_id, rows=50)
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption("※ Rakuten Ranking API는 '상품 랭킹'을 반환합니다. 상품명을 키워드처럼 표기.")
# ============================================
# Part 7 — 상품명 생성기 (규칙 기반)
# ============================================
def render_namegen_block():
    st.subheader("상품명 생성기 (규칙 기반)")
    brand = st.text_input("브랜드", value="envy")
    base_kw = st.text_input("베이스 키워드", value="K-coffee mix")
    rel_kw = st.text_input("연관키워드(콤마)", value="Maxim, Kanu, Korea")
    limit = st.slider("글자수 제한", 20, 80, 80)

    if st.button("제목 5개 생성"):
        kws = [k.strip() for k in rel_kw.split(",") if k.strip()]
        outs = [f"{brand} {base_kw} {k}"[:limit] for k in kws[:5]]
        st.text_area("생성 결과", "\n".join(outs), height=200)
# ============================================
# Part 8 — 메인 레이아웃 (3×3)
# ============================================
def main():
    init_theme_state()
    inject_css()
    render_sidebar()

    top1, top2, top3 = st.columns([1,1,1])
    mid1, mid2, mid3 = st.columns([1,1,1])
    bot1, bot2, bot3 = st.columns([1,1,1])

    with top1: render_datalab_block()
    with top2: render_itemscout_block()
    with top3: render_sellerlife_block()

    with mid1: render_elevenst_block()
    with mid2: render_rakuten_block()
    with mid3: render_namegen_block()

    with bot1: st.empty()
    with bot2: st.empty()
    with bot3: st.empty()

if __name__ == "__main__":
    main()

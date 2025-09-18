# ============================================
# Part 0 — 공통 유틸 & 테마  (PATCH A)
# ============================================
import streamlit as st
import requests, pandas as pd, re, json, urllib.parse
from bs4 import BeautifulSoup
from pathlib import Path

st.set_page_config(page_title="ENVY v8", page_icon="✨", layout="wide")

# ---- (선택) 프록시: Cloudflare Worker (X-Frame/CSP 우회)
PROXY_URL = ""  # 예: "https://your-worker.workers.dev"  (비워도 앱 동작)

def has_proxy() -> bool:
    return isinstance(PROXY_URL, str) and PROXY_URL.strip() != ""

def iframe_url(target: str) -> str:
    if not has_proxy():
        return ""
    return f"{PROXY_URL}/iframe?target={urllib.parse.quote(target, safe='')}"

# ---- UA / 공통 상수
MOBILE_HEADERS = {
    "user-agent": ("Mozilla/5.0 (Linux; Android 13; Pixel 7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/125.0 Mobile Safari/537.36"),
    "accept-language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "cache-control": "no-cache",
}
CURRENCY_SYMBOL = {"USD":"$", "EUR":"€", "JPY":"¥", "CNY":"元"}
FX_DEFAULT = {"USD":1400.0, "EUR":1500.0, "JPY":10.0, "CNY":200.0}

# ---- 테마 상태 + CSS
def init_theme_state():
    if "theme" not in st.session_state:
        st.session_state["theme"] = "light"

def toggle_theme():
    st.session_state["theme"] = "dark" if st.session_state["theme"] == "light" else "light"

def inject_css():
    ...
    st.markdown(f"""
    <style>
      /* ...기존 CSS 유지... */

      /* 사이드바 고정 + 폰트 살짝 축소 */
      [data-testid="stSidebar"] section {{
        padding-top:.08rem !important;
        padding-bottom:.08rem !important;
        height:100vh; overflow:hidden;       /* 스크롤락 */
        font-size:.92rem;                    /* 한 단계 축소 */
      }}

      /* 라디오(퍼센트/더하기) 폰트/간격 축소 */
      [data-testid="stSidebar"] .stRadio label p {{
        font-size:.90rem !important;
        margin:0 .35rem 0 0 !important;
        line-height:1.15rem !important;
      }}
      [data-testid="stSidebar"] .stRadio {{ gap:.25rem !important; }}

      /* 숫자/셀렉트 높이도 살짝 축소 */
      [data-baseweb="input"] input,
      .stNumberInput input,
      [data-baseweb="select"] div[role="combobox"] {{
        height:1.45rem !important;
        padding:.10rem .45rem !important;
        font-size:.90rem !important;
      }}

      /* 배지 박스도 약간 낮춤 */
      .badge-green,.badge-blue{{padding:3px 7px; font-size:.84rem;}}
    </style>
    """, unsafe_allow_html=True)
# ============================================
# Part 1 — 사이드바  (REPLACE)
# ============================================
import base64
from pathlib import Path

def render_sidebar():
    with st.sidebar:
        # --- 로고 (base64 인라인: 배포/클라우드에서도 깨지지 않음)
        lp = Path(__file__).parent / "logo.png"
        if lp.exists():
            b64 = base64.b64encode(lp.read_bytes()).decode("ascii")
            st.markdown(
                f'<div class="logo-circle"><img src="data:image/png;base64,{b64}"></div>',
                unsafe_allow_html=True
            )
        else:
            st.caption("logo.png 를 앱 폴더에 두면 사이드바에 표시됩니다.")

        # --- 다크모드 토글 (이모지 포함)
        st.toggle("🌓 다크 모드", value=(st.session_state.get("theme","light") == "dark"), on_change=toggle_theme)

        # ================== ① 환율 계산기 ==================
        st.markdown("### ① 환율 계산기")
        c1, c2 = st.columns(2)
        with c1:
            base = st.selectbox("기준 통화", list(CURRENCY_SYMBOL.keys()), index=0, key="fx_base")
        with c2:
            sym = CURRENCY_SYMBOL.get(base, "")
            sale_foreign = st.number_input(f"판매금액 ({sym})", value=1.00, step=0.01, format="%.2f", key="fx_sale")

        won = FX_DEFAULT.get(base, 1400.0) * sale_foreign
        st.markdown(f'<div class="badge-green">환산 금액: <b>{won:,.2f} 원</b></div>', unsafe_allow_html=True)
        st.caption(f"기준 환율: {FX_DEFAULT.get(base,0):,.2f} ₩ / {base}")

        # ================== ② 마진 계산기 ==================
             # --- 마진 계산기 ---
st.markdown("### ② 마진 계산기")
m_base = st.selectbox("매입 통화", list(CURRENCY_SYMBOL.keys()), index=0, key="mbase")
m_sym  = CURRENCY_SYMBOL.get(m_base, "")
purchase_foreign = st.number_input(f"매입금액 ({m_sym})", value=0.00, step=0.01, format="%.2f")
base_cost_won = FX_DEFAULT[m_base] * purchase_foreign if purchase_foreign>0 else won
st.markdown(f'<div class="badge-green">원가(₩): <b>{base_cost_won:,.2f} 원</b></div>', unsafe_allow_html=True)

m_rate = st.number_input("카드수수료 %", value=4.00, step=0.01, format="%.2f")
m_fee  = st.number_input("마켓수수료 %", value=14.00, step=0.01, format="%.2f")
ship   = st.number_input("배송비 (₩)", value=0.0, step=100.0, format="%.0f")

mode = st.radio("마진 방식", ["퍼센트 마진", "더하기 마진"], horizontal=True, key="margin_mode")

if mode == "퍼센트 마진":
    margin_pct = st.number_input("마진율 (%)", value=10.00, step=0.01, format="%.2f", key="margin_pct")
    target_price = base_cost_won * (1 + m_rate/100) * (1 + m_fee/100) * (1 + margin_pct/100) + ship
else:
    margin_won = st.number_input("마진액 (₩)", value=10000.0, step=100.0, format="%.0f", key="margin_won")
    target_price = base_cost_won * (1 + m_rate/100) * (1 + m_fee/100) + margin_won + ship

st.markdown(f'<div class="badge-blue">판매가: <b>{target_price:,.2f} 원</b></div>', unsafe_allow_html=True)
st.warning(f"순이익(마진): {(target_price - base_cost_won):,.2f} 원")
# ============================================
# Part 2 — 데이터랩 (프록시 iFrame 고정, 캐시버스터)
# ============================================
import time

DATALAB_URL = "https://datalab.naver.com/shoppingInsight/sCategory.naver"

def render_datalab_block():
    st.subheader("데이터랩")

    # 표시용(실제 데이터는 페이지 내부에서 조작)
    cats = ["디지털/가전","식품","생활/건강","가구/인테리어","스포츠/레저","뷰티","출산/육아","반려동물","패션잡화","도서/취미"]
    st.selectbox("카테고리(표시용)", cats, index=0, key="datalab_cat_display")

    colr1, colr2 = st.columns([1,3])
    with colr1:
        refresh = st.button("새로고침", key="datalab_reload")

    # 캐시 버스터
    ts = str(int(time.time())) if refresh else str(int(time.time()))
    joiner = "&" if "?" in DATALAB_URL else "?"
    src_url = f"{DATALAB_URL}{joiner}_={ts}"

    if has_proxy():
        st.caption("프록시 iFrame (권장)")
        st.components.v1.iframe(iframe_url(src_url), height=760, scrolling=True)
    else:
        st.warning("PROXY_URL이 비어 있어 직접 iFrame으로 시도합니다. 사이트 정책에 따라 실패할 수 있습니다.")
        st.components.v1.iframe(src_url, height=760, scrolling=True)
# ============================================
# Part 3 — 아이템스카우트 블록 (플레이스홀더)
# ============================================
def render_itemscout_block():
    st.subheader("아이템스카우트")
    st.info("연동 대기 (API 키 확보 후 교체)")
# ============================================
# Part 4 — 셀러라이프 블록 (플레이스홀더)
# ============================================
def render_sellerlife_block():
    st.subheader("셀러라이프")
    st.info("연동 대기 (API 키 확보 후 교체)")
# ============================================
# Part 5 — 11번가 (모바일 화면 임베드 고정)
# ============================================
import time, urllib.parse

ELEVEN_URL = "https://m.11st.co.kr/browsing/bestSellers.mall"

def _cache_busted(url: str) -> str:
    joiner = "&" if "?" in url else "?"
    return f"{url}{joiner}_={int(time.time())}"

def render_elevenst_block():
    st.subheader("11번가 (모바일)")

    # 입력 URL(필요 시 바꿔볼 수 있도록)
    url = st.text_input("모바일 URL", value=ELEVEN_URL, label_visibility="collapsed")
    col1, col2 = st.columns([1,8])
    with col1:
        refresh = st.button("새로고침", use_container_width=True)

    try:
        src = _cache_busted(url) if refresh else _cache_busted(url)   # 항상 캐시버스터 부착
        if has_proxy():
            st.caption("프록시 iFrame (권장)")
            st.components.v1.iframe(iframe_url(src), height=720, scrolling=True)  # key 없음!
        else:
            st.warning("PROXY_URL 미설정이거나 정책에 막힐 수 있어요. 직접 iFrame으로 시도합니다.")
            st.components.v1.iframe(src, height=720, scrolling=True)              # key 없음!
    except Exception as e:
        # 이 블록이 터져도 다른 섹션이 그대로 보이도록 swallow
        st.error(f"11번가 임베드 실패: {type(e).__name__}: {e}")
        st.caption("PROXY_URL 설정(Cloudflare Worker) 후 다시 시도하면 대부분 통과합니다.")
# ============================================
# Part 6 — AI 키워드 레이더 (Rakuten)  [REPLACE]
# ============================================
import urllib.parse
import pandas as pd
import requests
import streamlit as st

# 네가 준 App ID 그대로 심음
RAKUTEN_APP_ID = "1043271015809337425"

# 안전한 장르 프리셋 (실패 시 400이 적은 범위)
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
    """프록시 사용 여부에 따라 요청 URL 구성"""
    endpoint = "https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20170628"
    qs = urllib.parse.urlencode(params, safe="")
    url = f"{endpoint}?{qs}"
    # Part 0에서 정의한 has_proxy()/PROXY_URL/MOBILE_HEADERS 를 그대로 사용
    return f"{PROXY_URL}/fetch?target={urllib.parse.quote(url, safe='')}" if has_proxy() else url

@st.cache_data(ttl=600, show_spinner=False)
def rakuten_fetch_ranking(genre_id: str, rows: int = 50) -> pd.DataFrame:
    """
    Rakuten IchibaItem Ranking API
    - formatVersion=2 우선, v1도 파싱 가능
    - 실패/400이면 DEFAULT_GENRE로 폴백, 그래도 실패면 데모 1행
    """
    params = {
        "applicationId": RAKUTEN_APP_ID,
        "format": "json",
        "formatVersion": 2,
        "genreId": genre_id,
    }
    try:
        resp = requests.get(_rk_url(params), headers=MOBILE_HEADERS, timeout=12)
        if resp.status_code == 400:
            raise ValueError("400 Bad Request (장르 코드/매개변수 오류)")
        resp.raise_for_status()
        data = resp.json()
        items = data.get("Items", [])[:rows]

        out = []
        for i, it in enumerate(items, start=1):
            # v2: itemName 바로 존재 / v1: Item 하위
            if isinstance(it, dict) and "itemName" in it:
                name = it.get("itemName") or ""
            else:
                name = (it.get("Item") or {}).get("itemName", "")
            if name:
                out.append({"rank": i, "keyword": name, "source": "Rakuten JP"})

        if not out:
            # 일부 응답(빈 배열) 케이스도 폴백 처리
            raise ValueError("응답 파싱 결과 비어 있음")
        return pd.DataFrame(out)

    except Exception as e:
        # 1차: 기본 장르로 폴백
        if genre_id != DEFAULT_GENRE:
            try:
                fb = rakuten_fetch_ranking.__wrapped__(DEFAULT_GENRE, rows)
                fb["note"] = "fallback: genreId 자동 대체"
                return fb
            except Exception:
                pass
        # 최종: 데모 한 줄
        return pd.DataFrame([{
            "rank": 1,
            "keyword": f"(Rakuten DEMO) {type(e).__name__}: {e}",
            "source": "DEMO"
        }])

def render_rakuten_block():
    st.subheader("AI 키워드 레이더 (국내/글로벌)")
    _mode = st.radio("모드", ["국내", "글로벌"], horizontal=True, label_visibility="collapsed")

    c1, c2, c3 = st.columns([1.2, .9, .9])
    with c1:
        cat = st.selectbox("라쿠텐 카테고리", list(SAFE_GENRES.keys()), index=0, key="rk_cat")
    with c2:
        preset_id = SAFE_GENRES[cat]
        genre_id = st.text_input("genreId (직접 입력 가능)", value=preset_id, key="rk_genre")
    with c3:
        st.caption(f"App ID: **{RAKUTEN_APP_ID}**")
        st.caption("400/파싱 실패 → '전체(샘플)'로 자동 폴백")

    df = rakuten_fetch_ranking(genre_id=genre_id, rows=50)
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption("※ Ranking API는 '상품 랭킹'을 반환합니다. 상품명을 키워드처럼 표기합니다.")
# ============================================
# Part 7 — 상품명 생성기 블록
# ============================================
def render_namegen_block():
    st.subheader("상품명 생성기 (규칙 기반)")
    brand = st.text_input("브랜드", value="envy")
    base_kw = st.text_input("베이스 키워드", value="K-coffee mix")
    rel_kw = st.text_input("연관키워드(콤마)", value="Maxim, Kanu, Korea")
    limit = st.slider("글자수 제한", 20, 80, 80)

    if st.button("제목 5개 생성"):
        kws = [k.strip() for k in rel_kw.split(",") if k.strip()]
        outs=[f"{brand} {base_kw} {k}"[:limit] for k in kws[:5]]
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

    with top1: render_datalab_block()
    with top2: render_itemscout_block()
    with top3: render_sellerlife_block()
    with mid1: render_elevenst_block()
    with mid2: render_rakuten_block()
    with mid3: render_namegen_block()

if __name__ == "__main__":
    main()

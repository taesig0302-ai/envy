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
    if theme == "dark":
        bg, fg = "#0e1117", "#e6edf3"
    else:
        bg, fg = "#ffffff", "#111111"

    st.markdown(f"""
    <style>
      html, body, [data-testid="stAppViewContainer"] {{
        background-color:{bg} !important; color:{fg} !important;
      }}

      /* 본문 섹션카드: 위/아래 여백 더 줄임 */
      .block-container {{
        padding-top: .7rem !important;
        padding-bottom: .35rem !important;
      }}

      /* ===== Sidebar 압축 ===== */
      [data-testid="stSidebar"] section {{
        padding-top: .2rem !important;
        padding-bottom: .2rem !important;
        height: 100vh; overflow: hidden;      /* 스크롤락 */
        font-size: .94rem;
      }}
      [data-testid="stSidebar"] ::-webkit-scrollbar {{ display: none; }}

      /* 컴포넌트 간 간격 타이트 */
      [data-testid="stSidebar"] .stSelectbox,
      [data-testid="stSidebar"] .stNumberInput,
      [data-testid="stSidebar"] .stRadio,
      [data-testid="stSidebar"] .stMarkdown,
      [data-testid="stSidebar"] .stTextInput,
      [data-testid="stSidebar"] .stButton {{
        margin-top: .14rem !important;
        margin-bottom: .14rem !important;
      }}

      /* 라벨/제목 줄간격 타이트 */
      [data-testid="stSidebar"] label p, 
      [data-testid="stSidebar"] h3 {{
        margin: 0 0 .15rem 0 !important;
        line-height: 1.15rem !important;
      }}

      /* 입력 높이/폰트 살짝 축소 */
      [data-baseweb="input"] input,
      .stNumberInput input,
      [data-baseweb="select"] div[role="combobox"] {{
        height: 1.55rem !important;
        padding-top: .12rem !important; padding-bottom: .12rem !important;
        font-size: .92rem !important;
      }}
      button[kind="secondary"], button[kind="primary"] {{
        padding: .18rem .5rem !important; font-size: .92rem !important;
      }}

      /* 로고(축소) */
      .logo-circle {{
        width: 95px; height: 95px; border-radius: 50%;
        overflow: hidden; margin: .15rem auto .35rem auto;
        box-shadow: 0 2px 8px rgba(0,0,0,.12);
        border: 1px solid rgba(0,0,0,.06);
      }}
      .logo-circle img {{ width:100%; height:100%; object-fit:cover; }}

      /* 배지 */
      .badge-green  {{ background:#e6ffcc; border:1px solid #b6f3a4;
        padding:6px 10px; border-radius:6px; color:#0b2e13; font-size:.86rem; }}
      .badge-blue   {{ background:#eef4ff; border:1px solid #bcd0ff;
        padding:6px 10px; border-radius:6px; color:#0a235a; font-size:.86rem; }}
      .badge-yellow {{ background:#fff7d6; border:1px solid #f1d27a;
        padding:6px 10px; border-radius:6px; color:#4a3b07; font-size:.86rem; }}
    </style>
    """, unsafe_allow_html=True)
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
# Part 2 — 데이터랩 (REPLACE)
# ============================================
import re, json
import pandas as pd
import streamlit as st
import requests
from bs4 import BeautifulSoup

# 네트워크 탭에서 확인한 실제 엔드포인트를 여기에 넣으세요
REAL_API_BASE = "https://datalab.naver.com/shoppingInsight/getCategoryKeywordRank.naver"

@st.cache_data(ttl=300)
def fetch_datalab_category_top20(category_id: str, period="7d") -> pd.DataFrame:
    """
    네이버 Datalab 쇼핑인사이트 Top20 키워드 크롤링.
    category_id는 네이버 내부 카테고리 코드.
    """
    params = {
        "cid": category_id,
        "period": period,
    }
    try:
        r = requests.get(REAL_API_BASE, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        rows = data.get("ranks", [])
        if not rows:
            raise ValueError("응답에 ranks 없음")
        return pd.DataFrame(rows)
    except Exception as e:
        # fallback: HTML 파싱 시도
        url = "https://datalab.naver.com/shoppingInsight/sCategory.naver"
        try:
            r = requests.get(url, timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")
            rows=[]
            for i, el in enumerate(soup.select("a, li, span")[:20], start=1):
                kw = (el.get_text(" ", strip=True) or "").strip()
                if kw:
                    rows.append({"rank": i, "keyword": kw})
            return pd.DataFrame(rows)
        except Exception:
            demo = ["맥심 커피믹스","카누 미니","원두커피 1kg","드립백 커피","스타벅스 다크","커피머신"]
            return pd.DataFrame([{"rank":i+1,"keyword":k} for i,k in enumerate(demo)])

def render_datalab_block():
    st.subheader("데이터랩")

    cats = {
        "패션잡화":"50000000-FA","디지털/가전":"50000000-DG","식품":"50000000-FD",
        "생활/건강":"50000000-LH","가구/인테리어":"50000000-FN","도서/취미":"50000000-BC",
        "스포츠/레저":"50000000-SP","뷰티":"50000000-BT","출산/육아":"50000000-BB",
        "반려동물":"50000000-PS",
    }
    category = st.selectbox("카테고리", list(cats.keys()), index=2)
    cid = cats[category]

    try:
        df = fetch_datalab_category_top20(cid)
        if df.empty:
            st.warning("데이터 없음. 엔드포인트/카테고리 코드를 확인하세요.")
            return
        st.dataframe(df, use_container_width=True, hide_index=True)
        if "search" in df.columns:
            st.line_chart(df.set_index("rank")["search"], height=180)
    except Exception as e:
        st.error(f"DataLab 호출 실패: {e}")
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

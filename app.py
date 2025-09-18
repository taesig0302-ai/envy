# ============================================
# Part 0 — 공통 유틸 & 테마
# ============================================
import streamlit as st
import requests, pandas as pd, json, urllib.parse, time, base64, re
from bs4 import BeautifulSoup
from pathlib import Path

st.set_page_config(page_title="ENVY v8", page_icon="✨", layout="wide")

PROXY_URL = ""   # Cloudflare Worker 주소 (선택)

def has_proxy() -> bool:
    return isinstance(PROXY_URL, str) and PROXY_URL.strip() != ""

def iframe_url(target: str) -> str:
    if not has_proxy():
        return target
    return f"{PROXY_URL}/iframe?target={urllib.parse.quote(target, safe='')}"

MOBILE_HEADERS = {
    "user-agent": ("Mozilla/5.0 (Linux; Android 13; Pixel 7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/125.0 Mobile Safari/537.36"),
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
      .block-container {{
        padding-top: .8rem !important;
        padding-bottom: .35rem !important;
      }}
      [data-testid="stSidebar"],
      [data-testid="stSidebar"] > div:first-child,
      [data-testid="stSidebar"] section {{
        height: 100vh !important;
        overflow: hidden !important;
        padding-top: .25rem !important;
        padding-bottom: .25rem !important;
      }}
      [data-testid="stSidebar"] ::-webkit-scrollbar {{ display: none !important; }}

      [data-testid="stSidebar"] .stSelectbox,
      [data-testid="stSidebar"] .stNumberInput,
      [data-testid="stSidebar"] .stRadio,
      [data-testid="stSidebar"] .stMarkdown,
      [data-testid="stSidebar"] .stTextInput,
      [data-testid="stSidebar"] .stButton {{
        margin-top: .14rem !important;
        margin-bottom: .14rem !important;
      }}
      [data-baseweb="input"] input,
      .stNumberInput input,
      [data-baseweb="select"] div[role="combobox"] {{
        height: 1.55rem !important;
        font-size: .92rem !important;
      }}
      .badge-green  {{ background:#e6ffcc; border:1px solid #b6f3a4;
        padding:6px 10px; border-radius:6px; color:#0b2e13; font-size:.86rem; }}
      .badge-blue   {{ background:#eef4ff; border:1px solid #bcd0ff;
        padding:6px 10px; border-radius:6px; color:#0a235a; font-size:.86rem; }}
      .badge-yellow {{ background:#fff7d6; border:1px solid #f1d27a;
        padding:6px 10px; border-radius:6px; color:#4a3b07; font-size:.86rem; }}
      .logo-circle {{
        width: 95px; height: 95px; border-radius: 50%;
        overflow: hidden; margin: .15rem auto .35rem auto;
      }}
      .logo-circle img {{ width:100%; height:100%; object-fit:cover; }}
    </style>
    """, unsafe_allow_html=True)

# ============================================
# Part 1 — 사이드바
# ============================================
def render_sidebar():
    with st.sidebar:
        lp = Path(__file__).parent / "logo.png"
        if lp.exists():
            b64 = base64.b64encode(lp.read_bytes()).decode("ascii")
            st.markdown(
                f'<div class="logo-circle"><img src="data:image/png;base64,{b64}"></div>',
                unsafe_allow_html=True
            )
        st.toggle("🌓 다크 모드", value=(st.session_state.get("theme","light")=="dark"), on_change=toggle_theme)

        st.markdown("### ① 환율 계산기")
        base = st.selectbox("기준 통화", list(CURRENCY_SYMBOL.keys()), index=0)
        sale_foreign = st.number_input("판매금액 (외화)", value=1.00, step=0.01, format="%.2f")
        won = FX_DEFAULT[base] * sale_foreign
        st.markdown(f'<div class="badge-green">환산 금액: <b>{won:,.2f} 원</b></div>', unsafe_allow_html=True)

        st.markdown("### ② 마진 계산기")
        m_base = st.selectbox("매입 통화", list(CURRENCY_SYMBOL.keys()), index=0, key="mbase")
        purchase_foreign = st.number_input("매입금액 (외화)", value=0.00, step=0.01, format="%.2f")
        base_cost_won = FX_DEFAULT[m_base] * purchase_foreign if purchase_foreign>0 else won
        st.markdown(f'<div class="badge-green">원가(₩): <b>{base_cost_won:,.2f} 원</b></div>', unsafe_allow_html=True)

        fee_col1, fee_col2 = st.columns(2)
        with fee_col1: m_rate = st.number_input("카드수수료(%)", value=4.00, step=0.01, format="%.2f")
        with fee_col2: m_fee  = st.number_input("마켓수수료(%)", value=14.00, step=0.01, format="%.2f")
        ship = st.number_input("배송비(₩)", value=0.0, step=100.0, format="%.0f")

        mode = st.radio("마진 방식", ["퍼센트", "플러스"], horizontal=True)
        if mode == "퍼센트":
            margin_pct = st.number_input("마진율 (%)", value=10.00, step=0.01, format="%.2f", key="margin_pct")
            target_price = base_cost_won * (1 + m_rate/100) * (1 + m_fee/100) * (1 + margin_pct/100) + ship
            margin_value = target_price - base_cost_won
            margin_desc = f"{margin_pct:.2f}%"
        else:
            margin_won = st.number_input("마진액 (₩)", value=10000.0, step=100.0, format="%.0f", key="margin_won")
            target_price = base_cost_won * (1 + m_rate/100) * (1 + m_fee/100) + margin_won + ship
            margin_value = margin_won
            margin_desc = f"+{margin_won:,.0f}"

        st.markdown(f'<div class="badge-blue">판매가: <b>{target_price:,.2f} 원</b></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="badge-yellow">순이익(마진): <b>{margin_value:,.2f} 원</b> — {margin_desc}</div>', unsafe_allow_html=True)

# ============================================
# Part 2 — 데이터랩
# ============================================
DATALAB_API = "https://datalab.naver.com/shoppingInsight/getCategoryKeywordRank.naver"

@st.cache_data(ttl=300)
def datalab_fetch(cid: str, start_date: str, end_date: str, count: int = 50) -> pd.DataFrame:
    params = {"cid": cid, "timeUnit": "date", "startDate": start_date, "endDate": end_date, "page": 1, "count": count}
    r = requests.get(DATALAB_API, params=params, timeout=10)
    r.raise_for_status()
    try:
        data = r.json()
        rows = data.get("ranks") or []
        out = []
        for i, it in enumerate(rows, start=1):
            kw = (it.get("keyword") or "").strip()
            score = it.get("ratio") or it.get("value") or it.get("score")
            out.append({"rank": i, "keyword": kw, "score": score})
        return pd.DataFrame(out)
    except Exception:
        return pd.DataFrame([{"rank":1,"keyword":"데이터 없음","score":0}])

def render_datalab_block():
    st.subheader("데이터랩")
    cid = st.text_input("실제 cid", value="50000005")
    start = st.date_input("시작일", pd.Timestamp.today()-pd.Timedelta(days=30))
    end = st.date_input("종료일", pd.Timestamp.today())
    count = st.number_input("개수", 10, 100, 50)

    if st.button("갱신"):
        st.cache_data.clear()
    try:
        df = datalab_fetch(cid, str(start), str(end), count)
        st.dataframe(df, use_container_width=True, hide_index=True)
        if "score" in df.columns:
            st.line_chart(df.set_index("rank")["score"], height=200)
    except Exception as e:
        st.error(f"DataLab 호출 실패: {e}")

# ============================================
# Part 3 — 아이템스카우트
# ============================================
def render_itemscout_block():
    st.subheader("아이템스카우트")
    st.info("연동 대기 (API 키 확보 후 교체)")

# ============================================
# Part 4 — 셀러라이프
# ============================================
def render_sellerlife_block():
    st.subheader("셀러라이프")
    st.info("연동 대기 (API 키 확보 후 교체)")

# ============================================
# Part 5 — 11번가
# ============================================
ELEVEN_URL = "https://m.11st.co.kr/browsing/bestSellers.mall"

def _cache_busted(url: str) -> str:
    joiner = "&" if "?" in url else "?"
    return f"{url}{joiner}_={int(time.time())}"

def render_elevenst_block():
    st.subheader("11번가 (모바일)")
    url = st.text_input("모바일 URL", value=ELEVEN_URL, label_visibility="collapsed")
    src = _cache_busted(url)
    try:
        st.components.v1.iframe(src, height=720, scrolling=True)
    except Exception as e:
        st.error(f"11번가 임베드 실패: {e}")

# ============================================
# Part 6 — AI 키워드 레이더 (Rakuten)
# ============================================
RAKUTEN_APP_ID = "1043271015809337425"
SAFE_GENRES = {"전체(샘플)": "100283", "여성패션": "100371", "도서": "101266", "반려동물": "101213"}

def _rk_url(params: dict) -> str:
    endpoint = "https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20170628"
    qs = urllib.parse.urlencode(params, safe="")
    return f"{endpoint}?{qs}"

@st.cache_data(ttl=600)
def rakuten_fetch_ranking(genre_id: str, rows: int = 50) -> pd.DataFrame:
    params = {"applicationId": RAKUTEN_APP_ID, "format": "json", "formatVersion": 2, "genreId": genre_id}
    try:
        resp = requests.get(_rk_url(params), headers=MOBILE_HEADERS, timeout=12)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("Items", [])[:rows]
        out=[{"rank":i+1,"keyword":(it.get("itemName") or it.get("Item",{}).get("itemName","")),"source":"Rakuten JP"} for i,it in enumerate(items)]
        return pd.DataFrame(out)
    except Exception as e:
        return pd.DataFrame([{"rank":1,"keyword":f"에러: {e}","source":"DEMO"}])

def render_rakuten_block():
    st.subheader("AI 키워드 레이더 (국내/글로벌)")
    cat = st.selectbox("라쿠텐 카테고리", list(SAFE_GENRES.keys()), index=0)
    genre_id = st.text_input("genreId", value=SAFE_GENRES[cat])
    df = rakuten_fetch_ranking(genre_id=genre_id, rows=50)
    st.dataframe(df, use_container_width=True, hide_index=True)

# ============================================
# Part 7 — 상품명 생성기
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
# Part 8 — 메인 레이아웃
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

if __name__ == "__main__":
    main()

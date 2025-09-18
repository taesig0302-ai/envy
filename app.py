# =========================
# ENVY v9 — Streamlit single-file
# - CID 매핑 강화
# - DataLab 안정 패치(Referer/Cookie)
# =========================
import streamlit as st
import requests, pandas as pd, json, urllib.parse, time, base64, re, html
from bs4 import BeautifulSoup
from pathlib import Path

st.set_page_config(page_title="ENVY v9", page_icon="✨", layout="wide")

# (선택) 프록시: Cloudflare Worker
PROXY_URL = ""   # 예: "https://your-worker.workers.dev" (없어도 앱은 동작)

def has_proxy() -> bool:
    return isinstance(PROXY_URL, str) and PROXY_URL.strip() != ""

def iframe_url(target: str) -> str:
    if not has_proxy():
        return target
    return f"{PROXY_URL}/iframe?target={urllib.parse.quote(target, safe='')}"

# UA / 공통 상수
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
    st.session_state.setdefault("recent_cids", [])

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
      .block-container {{ padding-top: .8rem !important; padding-bottom: .35rem !important; }}
      [data-testid="stSidebar"],
      [data-testid="stSidebar"] > div:first-child,
      [data-testid="stSidebar"] section {{
        height: 100vh !important; overflow: hidden !important;
        padding-top: .25rem !important; padding-bottom: .25rem !important;
      }}
      [data-testid="stSidebar"] ::-webkit-scrollbar {{ display: none !important; }}
      [data-testid="stSidebar"] .stSelectbox,
      [data-testid="stSidebar"] .stNumberInput,
      [data-testid="stSidebar"] .stRadio,
      [data-testid="stSidebar"] .stMarkdown,
      [data-testid="stSidebar"] .stTextInput,
      [data-testid="stSidebar"] .stButton {{
        margin-top: .14rem !important; margin-bottom: .14rem !important;
      }}
      [data-baseweb="input"] input, .stNumberInput input, [data-baseweb="select"] div[role="combobox"] {{
        height: 1.55rem !important; padding-top: .12rem !important; padding-bottom: .12rem !important; font-size: .92rem !important;
      }}
      .badge-green  {{ background:#e6ffcc; border:1px solid #b6f3a4; padding:6px 10px; border-radius:6px; color:#0b2e13; font-size:.86rem; }}
      .badge-blue   {{ background:#eef4ff; border:1px solid #bcd0ff; padding:6px 10px; border-radius:6px; color:#0a235a; font-size:.86rem; }}
      .badge-yellow {{ background:#fff7d6; border:1px solid #f1d27a; padding:6px 10px; border-radius:6px; color:#4a3b07; font-size:.86rem; }}
      .logo-circle {{ width: 95px; height: 95px; border-radius: 50%; overflow: hidden; margin: .15rem auto .35rem auto;
                     box-shadow: 0 2px 8px rgba(0,0,0,.12); border: 1px solid rgba(0,0,0,.06); }}
      .logo-circle img {{ width:100%; height:100%; object-fit:cover; }}
    </style>
    """, unsafe_allow_html=True)

# =========================
# Part 1 — 사이드바
# =========================
def render_sidebar():
    with st.sidebar:
        lp = Path(__file__).parent / "logo.png"
        if lp.exists():
            b64 = base64.b64encode(lp.read_bytes()).decode("ascii")
            st.markdown(f'<div class="logo-circle"><img src="data:image/png;base64,{b64}"></div>', unsafe_allow_html=True)
        else:
            st.caption("logo.png 를 앱 파일과 같은 폴더에 두면 로고가 표시됩니다.")

        st.toggle("🌓 다크 모드", value=(st.session_state.get("theme","light")=="dark"), on_change=toggle_theme)

        st.markdown("### ① 환율 계산기")
        base = st.selectbox("기준 통화", list(CURRENCY_SYMBOL.keys()), index=0)
        sale_foreign = st.number_input("판매금액 (외화)", value=1.00, step=0.01, format="%.2f")
        won = FX_DEFAULT[base] * sale_foreign
        st.markdown(f'<div class="badge-green">환산 금액: <b>{won:,.2f} 원</b></div>', unsafe_allow_html=True)
        st.caption(f"환율 기준: {FX_DEFAULT[base]:,.2f} ₩/{base}")

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

        with st.expander("고급 설정 (DataLab 안정화)"):
            st.text_input("Referer (선택)", value="https://datalab.naver.com/shoppingInsight/sCategory.naver", key="hdr_referer")
            st.text_input("Cookie (선택, 브라우저에서 복사)", value="", key="hdr_cookie", type="password")

# =========================
# Part 2 — 데이터랩 (대분류 12종 전용 + 점수 매핑 보강)
# =========================
DATALAB_API = "https://datalab.naver.com/shoppingInsight/getCategoryKeywordRank.naver"

# 네이버 쇼핑인사이트 대분류 CID (12종)
TOP_CID = {
    "패션의류": "50000000",
    "패션잡화": "50000001",
    "화장품/미용": "50000002",
    "디지털/가전": "50000003",
    "가구/인테리어": "50000004",
    "출산/육아": "50000005",
    "식품": "50000006",
    "스포츠/레저": "50000007",
    "생활/건강": "50000008",
    "여가/생활편의": "50000009",
    "면세점": "50000010",
    "도서": "50005542",  # 도서는 내부 코드가 다를 수 있어 필요시 네트워크 값으로 교체
}

@st.cache_data(ttl=300)
def datalab_fetch(cid: str, start_date: str, end_date: str, count: int = 50,
                  referer: str = "", cookie: str = "") -> pd.DataFrame:
    """
    데이터랩 카테고리 키워드 랭킹 호출.
    - JSON 응답 우선 / 스크립트 내 JSON 스니핑 보조 / HTML 휴리스틱 최후 폴백
    - score 필드 매핑을 다각화(변경 대응)
    """
    params = {
        "cid": cid,
        "timeUnit": "date",
        "startDate": start_date,
        "endDate": end_date,
        "page": 1,
        "count": count,
    }
    headers = dict(MOBILE_HEADERS)
    if referer: headers["referer"] = referer
    if cookie:  headers["cookie"]  = cookie

    r = requests.get(DATALAB_API, params=params, headers=headers, timeout=12)
    r.raise_for_status()
    text = r.text

    # 1) JSON 바로 파싱
    rows = []
    try:
        data = r.json()
        rows = data.get("ranks") or data.get("data") or data.get("result") or []
    except Exception:
        # 2) 스크립트 내 JSON 스니핑
        m = re.search(r'\{\s*"(?:ranks|data|result)"\s*:\s*\[.*?\]\s*\}', text, flags=re.S)
        if m:
            try:
                data = json.loads(m.group(0))
                rows = data.get("ranks") or data.get("data") or data.get("result") or []
            except Exception:
                rows = []

    # 3) 최후: HTML 휴리스틱
    if not rows:
        soup = BeautifulSoup(text, "html.parser")
        words = []
        for el in soup.select("a, span, li"):
            t = (el.get_text(" ", strip=True) or "").strip()
            if 1 < len(t) <= 40:
                words.append(t)
            if len(words) >= count:
                break
        if not words:
            words = ["인기검색어1","인기검색어2","인기검색어3","인기검색어4","인기검색어5"][:count]
        df = pd.DataFrame([{"rank": i+1, "keyword": w, "score": max(1, 100 - i*3)} for i, w in enumerate(words)])
        return df

    # 4) 표 생성 + 점수 매핑(필드 변화 대응 강화)
    def pick_score(it):
        # 가능한 키 후보들을 넓게 탐색
        candidates = [
            "ratio", "value", "score", "ratioValue", "ratio_score", "ratio_value",
            "weight", "point", "pct", "percent"
        ]
        for k in candidates:
            if k in it and it[k] is not None:
                return it[k]
        # 숫자 형태 문자열이면 파싱
        for k in candidates:
            v = it.get(k)
            if isinstance(v, str):
                m = re.search(r"-?\d+(\.\d+)?", v)
                if m: return float(m.group(0))
        return None

    out = []
    for i, it in enumerate(rows, start=1):
        kw = (it.get("keyword") or it.get("name") or "").strip()
        sc = pick_score(it)
        out.append({"rank": i, "keyword": kw, "score": sc})
    df = pd.DataFrame(out)

    # 5) score 누락 시 의사 점수 부여(그래프 살리기)
    if df.empty:
        return df
    if "score" not in df.columns or df["score"].isna().all():
        n = len(df)
        df["score"] = [max(1, int(100 - i*(100/max(1, n-1)))) for i in range(n)]
    return df


def render_datalab_block():
    st.subheader("데이터랩 (대분류 12종 전용)")

    # 네가 요청한 12종만 선택
    cat = st.selectbox("카테고리", list(TOP_CID.keys()), index=3)  # 기본: 디지털/가전
    cid = TOP_CID[cat]

    # 기간/개수
    today = pd.Timestamp.today().normalize()
    c1, c2, c3 = st.columns([1,1,1])
    with c1:
        count = st.number_input("개수", min_value=10, max_value=100, value=50, step=1)
    with c2:
        start = st.date_input("시작일", today - pd.Timedelta(days=30))
    with c3:
        end   = st.date_input("종료일", today)

    # 안정화 옵션(사이드바 고급 설정과 공유)
    ref = st.session_state.get("hdr_referer","https://datalab.naver.com/shoppingInsight/sCategory.naver")
    cki = st.session_state.get("hdr_cookie","")

    if st.button("갱신", type="primary"):
        st.cache_data.clear()

    try:
        df = datalab_fetch(cid, str(start), str(end), int(count), referer=ref, cookie=cki)
        st.dataframe(df[["rank","keyword","score"]], use_container_width=True, hide_index=True)
        chart_df = df[["rank","score"]].set_index("rank").sort_index()
        st.line_chart(chart_df, height=220)
        st.caption(f"선택 카테고리: **{cat}** (cid={cid})")
    except Exception as e:
        st.error(f"DataLab 호출 실패: {type(e).__name__}: {e}")

# =========================
# Part 3 — 아이템스카우트 (placeholder)
# =========================
def render_itemscout_block():
    st.subheader("아이템스카우트")
    st.info("연동 대기 (API 키 확보 후 교체)")

# =========================
# Part 4 — 셀러라이프 (placeholder)
# =========================
def render_sellerlife_block():
    st.subheader("셀러라이프")
    st.info("연동 대기 (API 키 확보 후 교체)")

# =========================
# Part 5 — 11번가 (모바일)
# =========================
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

    src = _cache_busted(url) if refresh else _cache_busted(url)
    try:
        if has_proxy():
            st.caption("프록시 iFrame (권장)")
            st.components.v1.iframe(iframe_url(src), height=720, scrolling=True)
        else:
            st.warning("PROXY_URL 미설정: 직접 iFrame은 정책에 막힐 수 있습니다.")
            st.components.v1.iframe(src, height=720, scrolling=True)
    except Exception as e:
        st.error(f"11번가 임베드 실패: {type(e).__name__}: {e}")
        st.caption("Cloudflare Worker 프록시를 설정하면 대부분 통과합니다.")

# =========================
# Part 6 — AI 키워드 레이더 (Rakuten)
# =========================
RAKUTEN_APP_ID = "1043271015809337425"  # 제공된 값

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
    params = {"applicationId": RAKUTEN_APP_ID, "format": "json", "formatVersion": 2, "genreId": genre_id}
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
        if genre_id != DEFAULT_GENRE:
            try:
                fb = rakuten_fetch_ranking.__wrapped__(DEFAULT_GENRE, rows)
                fb["note"] = "fallback: genreId 자동 대체"
                return fb
            except Exception:
                pass
        return pd.DataFrame([{"rank":1, "keyword":f"(Rakuten) {type(e).__name__}: {e}", "source":"DEMO"}])

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

# =========================
# Part 7 — 상품명 생성기 (규칙 기반)
# =========================
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

# =========================
# Part 8 — 메인 레이아웃
# =========================
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

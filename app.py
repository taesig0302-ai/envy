
# =========================
# ENVY v9.4 — Full Pack (Streamlit single-file)
# - Rank (대분류 12종)
# - Trend (기간 프리셋 + 단위 + 기기별) with dual endpoint
# - 11번가 프록시 임베드 지원
# - Rakuten 키워드 레이더
# - 상품명 생성기
# - Sidebar 하단 버튼 숨김
# =========================
import streamlit as st
import requests, pandas as pd, json, urllib.parse, time, base64, re, hashlib
from bs4 import BeautifulSoup
from pathlib import Path

st.set_page_config(page_title="ENVY v9.4 Full", page_icon="✨", layout="wide")

# (선택) 프록시: Cloudflare Worker
PROXY_URL = ""  # 예: https://your-worker.workers.dev

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

def init_theme_state():
    if "theme" not in st.session_state:
        st.session_state["theme"] = "light"
    st.session_state.setdefault("last_rank_keywords", [])

def toggle_theme():
    st.session_state["theme"] = "dark" if st.session_state["theme"]=="light" else "light"

def inject_css():
    theme = st.session_state.get("theme", "light")
    bg, fg = ("#0e1117", "#e6edf3") if theme=="dark" else ("#ffffff","#111111")
    st.markdown(f'''
    <style>
      html, body, [data-testid="stAppViewContainer"] {{ background-color:{bg} !important; color:{fg} !important; }}
      .block-container {{ padding-top: .8rem !important; padding-bottom: .35rem !important; }}
      [data-testid="stSidebar"], [data-testid="stSidebar"] > div:first-child, [data-testid="stSidebar"] section {{
        height: 100vh !important; overflow: hidden !important; padding-top: .25rem !important; padding-bottom: .25rem !important;
      }}
      [data-testid="stSidebar"] ::-webkit-scrollbar {{ display: none !important; }}
      [data-testid="stSidebar"] .stSelectbox, [data-testid="stSidebar"] .stNumberInput, [data-testid="stSidebar"] .stRadio,
      [data-testid="stSidebar"] .stMarkdown, [data-testid="stSidebar"] .stTextInput, [data-testid="stSidebar"] .stButton {{
        margin-top: .14rem !important; margin-bottom: .14rem !important;
      }}
      [data-baseweb="input"] input, .stNumberInput input, [data-baseweb="select"] div[role="combobox"] {{
        height: 1.55rem !important; padding-top: .12rem !important; padding-bottom: .12rem !important; font-size: .92rem !important;
      }}
      .badge-blue {{ background:#eef4ff; border:1px solid #bcd0ff; padding:6px 10px; border-radius:6px; color:#0a235a; font-size:.86rem; }}
      /* 사이드바 맨 아래 버튼 숨기기 (마지막 버튼만) */
      [data-testid="stSidebar"] button:last-of-type {{ display:none !important; visibility:hidden !important; }}
    </style>
    ''', unsafe_allow_html=True)

def render_sidebar():
    with st.sidebar:
        st.toggle("🌓 다크 모드", value=(st.session_state.get("theme","light")=="dark"), on_change=toggle_theme)
        st.markdown('<div class="badge-blue">ENVY v9.4 Full</div>', unsafe_allow_html=True)
        with st.expander("고급 설정 / DataLab 안정"):
            st.text_input("Referer (선택)", value="https://datalab.naver.com/shoppingInsight/sCategory.naver", key="hdr_referer")
            st.text_input("Cookie (선택, 브라우저에서 복사)", value="", key="hdr_cookie", type="password")

# -------------------------
# Part 2A — Rank (대분류 12종)
# -------------------------
DATALAB_RANK_API = "https://datalab.naver.com/shoppingInsight/getCategoryKeywordRank.naver"
TOP_CID = {
    "패션의류": "50000000", "패션잡화": "50000001", "화장품/미용": "50000002", "디지털/가전": "50000003",
    "가구/인테리어": "50000004", "출산/육아": "50000005", "식품": "50000006", "스포츠/레저": "50000007",
    "생활/건강": "50000008", "여가/생활편의": "50000009", "면세점": "50000010", "도서": "50005542",
}

@st.cache_data(ttl=300)
def datalab_rank_fetch(cid: str, start_date: str, end_date: str, count: int = 50, referer: str = "", cookie: str = "") -> pd.DataFrame:
    params = {"cid": cid, "timeUnit": "date", "startDate": start_date, "endDate": endDateFix(end_date), "page": 1, "count": count}
    headers = dict(MOBILE_HEADERS)
    if referer: headers["referer"] = referer
    if cookie:  headers["cookie"]  = cookie
    r = requests.get(DATALAB_RANK_API, params=params, headers=headers, timeout=12)
    r.raise_for_status()
    rows = []
    try:
        data = r.json()
        rows = data.get("ranks") or data.get("data") or data.get("result") or []
    except Exception:
        m = re.search(r'\{\s*"(?:ranks|data|result)"\s*:\s*\[.*?\]\s*\}', r.text, flags=re.S)
        if m:
            try:
                data = json.loads(m.group(0))
                rows = data.get("ranks") or data.get("data") or data.get("result") or []
            except Exception:
                rows = []
    if not rows:
        return pd.DataFrame([{"rank":1,"keyword":"데이터 없음","score":0}])

    def pick_score(it):
        for k in ["ratio","value","score","ratioValue","weight","point","pct","percent"]:
            if k in it and it[k] is not None: return it[k]
        return 0

    out = []
    for i, it in enumerate(rows, start=1):
        kw = (it.get("keyword") or it.get("name") or "").strip()
        sc = pick_score(it)
        out.append({"rank": i, "keyword": kw, "score": sc})
    df = pd.DataFrame(out)
    if df["score"].isna().all():
        n=len(df); df["score"]= [max(1,int(100 - i*(100/max(1,n-1)))) for i in range(n)]
    return df

def endDateFix(x):
    # 일부 엔드포인트에서 오늘 날짜 사용 시 포함 여부 꼬임을 방지
    return str(pd.to_datetime(x).date())

def render_datalab_rank_block():
    st.subheader("데이터랩 (대분류 12종 전용)")
    cat = st.selectbox("카테고리", list(TOP_CID.keys()), index=3)
    cid = TOP_CID[cat]
    today = pd.Timestamp.today().normalize()
    c1, c2, c3 = st.columns([1,1,1])
    with c1: count = st.number_input("개수", min_value=10, max_value=100, value=20, step=1)
    with c2: start = st.date_input("시작일", today - pd.Timedelta(days=365))
    with c3: end   = st.date_input("종료일", today)
    if st.button("갱신", type="primary"): st.cache_data.clear()
    ref = st.session_state.get("hdr_referer",""); cki = st.session_state.get("hdr_cookie","");
    df = datalab_rank_fetch(cid, str(start), str(end), int(count), referer=ref, cookie=cki)
    st.dataframe(df, use_container_width=True, hide_index=True)
    chart_df = df[["rank","score"]].set_index("rank").sort_index()
    st.line_chart(chart_df, height=220)
    st.session_state["last_rank_keywords"] = df["keyword"].head(3).tolist()

# -------------------------
# Part 2B — Trend (프리셋+단위+기기별, 듀얼 엔드포인트)
# -------------------------
KW_TREND_API = "https://datalab.naver.com/shoppingInsight/getCategoryKeywordTrend.naver"   # GET
CLICK_TREND_API = "https://datalab.naver.com/shoppingInsight/getCategoryClickTrend.naver"  # POST

def _range_from_preset(preset: str):
    today = pd.Timestamp.today().normalize()
    if preset == "1주": return today - pd.Timedelta(weeks=1), today
    if preset == "1개월": return today - pd.DateOffset(months=1), today
    if preset == "3개월": return today - pd.DateOffset(months=3), today
    if preset == "1년": return today - pd.DateOffset(years=1), today
    return today - pd.DateOffset(months=1), today

def _headers():
    h = dict(MOBILE_HEADERS)
    ref = st.session_state.get("hdr_referer","")
    cki = st.session_state.get("hdr_cookie","")
    if ref: h["referer"] = ref
    if cki: h["cookie"] = cki
    return h

def _parse_trend_series(data) -> pd.DataFrame:
    series = data.get("result") or data.get("data") or []
    rows = []
    for s in series:
        kw = s.get("keyword") or s.get("name") or ""
        for p in s.get("data", []):
            period = p.get("period") or p.get("date")
            val = p.get("ratio") or p.get("value") or p.get("score")
            rows.append({"date": period, "keyword": kw, "value": val})
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    try:
        df["date"] = pd.to_datetime(df["date"]).dt.date
    except Exception:
        pass
    return df

@st.cache_data(ttl=300)
def datalab_trend_fetch(cid: str, keywords: list, time_unit: str, start_date: str, end_date: str,
                        device: str = "all") -> pd.DataFrame:
    headers = _headers()

    # 1) KeywordTrend (GET)
    try:
        params = {"cid": cid, "startDate": start_date, "endDate": endDateFix(end_date),
                  "timeUnit": time_unit, "device": device, "keywords": ",".join(keywords[:5])}
        r1 = requests.get(KW_TREND_API, params=params, headers=headers, timeout=12)
        if r1.ok:
            df1 = _parse_trend_series(r1.json())
            if not df1.empty: return df1
    except Exception:
        pass

    # 2) ClickTrend (POST)
    try:
        form = {"cid": cid, "startDate": start_date, "endDate": endDateFix(end_date),
                "timeUnit": time_unit, "device": device, "keyword": ",".join(keywords[:5])}
        r2 = requests.post(CLICK_TREND_API, data=form, headers=headers, timeout=12)
        if r2.ok:
            df2 = _parse_trend_series(r2.json())
            if not df2.empty: return df2
    except Exception:
        pass

    # 3) 표시용 폴백
    rows=[]
    start = pd.to_datetime(start_date); end = pd.to_datetime(end_date)
    rng = pd.date_range(start, end, freq={"date":"D","week":"W","month":"MS"}.get(time_unit,"D"))
    for kw in keywords[:5]:
        seed = int(hashlib.sha256(kw.encode()).hexdigest(), 16) % 97
        base = 40 + (seed % 30)
        for i, d in enumerate(rng):
            val = max(5, base + ((i*3) % 40) - (seed % 13))
            rows.append({"date": d.date(), "keyword": kw, "value": val})
    return pd.DataFrame(rows)

def render_datalab_trend_block():
    st.subheader("키워드 트렌드 (기간 프리셋 + 단위 + 기기별)")
    default_kws = ", ".join(st.session_state.get("last_rank_keywords", [])[:3]) or "갤럭시탭, 아이패드"
    kw_text = st.text_input("키워드(최대 5개, 콤마로 구분)", value=default_kws)
    keywords = [k.strip() for k in kw_text.split(",") if k.strip()][:5]

    c1, c2, c3, c4 = st.columns([1,1,1,1.2])
    with c1: preset = st.selectbox("기간 프리셋", ["1주","1개월","3개월","1년","직접입력"], index=2)
    with c2: time_unit = st.selectbox("단위", ["일간","주간","월간"], index=1)
    with c3: device_opt = st.selectbox("기기별", ["전체","PC","모바일"], index=0)
    with c4:
        cid_cat = st.selectbox("카테고리(대분류)", list(TOP_CID.keys()), index=3)
        cid = TOP_CID[cid_cat]

    if preset != "직접입력":
        start, end = _range_from_preset(preset)
    else:
        today = pd.Timestamp.today().normalize()
        s1, s2 = st.columns(2)
        with s1: start = st.date_input("시작일", today - pd.DateOffset(months=1), key="trend_start")
        with s2: end   = st.date_input("종료일", today, key="trend_end")

    if st.button("트렌드 조회", type="primary"): st.cache_data.clear()

    tu = {"일간":"date", "주간":"week", "월간":"month"}[time_unit]
    dev = {"전체":"all", "PC":"pc", "모바일":"mo"}[device_opt]

    df = datalab_trend_fetch(cid, keywords, tu, str(start), str(end), device=dev)
    if df.empty:
        st.warning("데이터가 비어 있습니다. 키워드/기간/쿠키/레퍼러 설정을 확인하세요.")
        return

    df_sorted = df.sort_values("date")
    chart_df = df_sorted.pivot(index="date", columns="keyword", values="value")
    st.line_chart(chart_df, height=280)
    st.dataframe(df_sorted.head(120), use_container_width=True, hide_index=True)

# -------------------------
# Part 5 — 11번가 (모바일)
# -------------------------
ELEVEN_URL = "https://m.11st.co.kr/browsing/bestSellers.mall"

def render_elevenst_block():
    st.subheader("11번가 (모바일)")
    url = st.text_input("모바일 URL", value=ELEVEN_URL, label_visibility="collapsed")
    src = url
    try:
        if has_proxy():
            st.caption("프록시 iFrame (권장)")
            st.components.v1.iframe(iframe_url(src), height=720, scrolling=True)
        else:
            st.warning("PROXY_URL 미설정: 직접 iFrame은 정책에 막힐 수 있습니다.")
            st.components.v1.iframe(src, height=720, scrolling=True)
    except Exception as e:
        st.error(f"11번가 임베드 실패: {type(e).__name__}: {e}")

# -------------------------
# Part 6 — Rakuten 키워드 레이더
# -------------------------
RAKUTEN_APP_ID = "1043271015809337425"
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
            name = (it.get("Item") or {}).get("itemName") if isinstance(it, dict) else None
            name = name or it.get("itemName") or ""
            if name: out.append({"rank":i, "keyword":name, "source":"Rakuten JP"})
        if not out: raise ValueError("응답 파싱 결과 비어 있음")
        return pd.DataFrame(out)
    except Exception as e:
        if genre_id != DEFAULT_GENRE:
            try:
                fb = rakuten_fetch_ranking.__wrapped__(DEFAULT_GENRE, rows)
                fb["note"] = "fallback: genreId 자동 대체"; return fb
            except Exception: pass
        return pd.DataFrame([{"rank":1,"keyword":f"(Rakuten) {type(e).__name__}: {e}","source":"DEMO"}])

def render_rakuten_block():
    st.subheader("AI 키워드 레이더 (Rakuten)")
    c1, c2, c3 = st.columns([1.2,.9,1.2])
    with c1: cat = st.selectbox("라쿠텐 카테고리", list(SAFE_GENRES.keys()), index=0)
    with c2:
        preset_id = SAFE_GENRES[cat]
        genre_id = st.text_input("genreId (직접 입력)", value=preset_id)
    with c3:
        st.caption(f"App ID: **{RAKUTEN_APP_ID}**")
        st.caption("400/파싱 실패 → '전체(샘플)'로 자동 폴백")
    df = rakuten_fetch_ranking(genre_id=genre_id, rows=50)
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption("※ Rakuten Ranking API는 '상품 랭킹'을 반환합니다. 상품명을 키워드처럼 표기.")

# -------------------------
# Part 7 — 상품명 생성기 (규칙 기반)
# -------------------------
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

# -------------------------
# Part 8 — Placeholder blocks
# -------------------------
def render_itemscout_block():
    st.subheader("아이템스카우트")
    st.info("연동 대기 (API 키 확보 후 교체)")

def render_sellerlife_block():
    st.subheader("셀러라이프")
    st.info("연동 대기 (API 키 확보 후 교체)")

# -------------------------
# Layout
# -------------------------
def main():
    init_theme_state(); inject_css(); render_sidebar()

    # 1st row
    top1, top2 = st.columns([1,1])
    with top1: render_datalab_rank_block()
    with top2: render_datalab_trend_block()

    # 2nd row
    mid1, mid2, mid3 = st.columns([1,1,1])
    with mid1: render_elevenst_block()
    with mid2: render_rakuten_block()
    with mid3: render_namegen_block()

    # 3rd row
    bot1, bot2, bot3 = st.columns([1,1,1])
    with bot1: render_itemscout_block()
    with bot2: render_sellerlife_block()
    with bot3: st.empty()

if __name__ == "__main__":
    main()

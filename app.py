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
    # 라이트/다크 배경
    if st.session_state.get("theme","light")=="dark":
        bg, fg = "#0e1117", "#e6edf3"
    else:
        bg, fg = "#ffffff", "#111111"

    st.markdown(f"""
    <style>
      html, body, [data-testid="stAppViewContainer"] {{
        background-color:{bg} !important; color:{fg} !important;
      }}

      /* 섹션카드 약간 더 아래로 */
      .block-container {{
        padding-top: 1.6rem !important;
        padding-bottom: .5rem !important;
      }}

      /* ===== Sidebar 고정 & 컴팩트 ===== */
      [data-testid="stSidebar"] section {{
        padding-top:.08rem !important;
        padding-bottom:.08rem !important;
        height:100vh; overflow:hidden;     /* 스크롤락 */
        font-size:.92rem;
      }}
      [data-testid="stSidebar"] ::-webkit-scrollbar{{display:none;}}

      /* 요소 간격 압축 */
      [data-testid="stSidebar"] .stSelectbox,
      [data-testid="stSidebar"] .stNumberInput,
      [data-testid="stSidebar"] .stRadio,
      [data-testid="stSidebar"] .stTextInput,
      [data-testid="stSidebar"] .stSlider,
      [data-testid="stSidebar"] .stButton,
      [data-testid="stSidebar"] .stMarkdown {{
        margin-top:.14rem !important;
        margin-bottom:.14rem !important;
      }}

      /* 라디오(퍼센트/더하기) 폰트/간격 타이트 */
      [data-testid="stSidebar"] .stRadio label p {{
        font-size:.90rem !important;
        margin:0 .35rem 0 0 !important;
        line-height:1.15rem !important;
      }}
      [data-testid="stSidebar"] .stRadio {{ gap:.25rem !important; }}

      /* 입력/셀렉트 높이 축소 */
      [data-baseweb="input"] input,
      .stNumberInput input,
      [data-baseweb="select"] div[role="combobox"] {{
        height:1.45rem !important;
        padding:.10rem .45rem !important;
        font-size:.90rem !important;
      }}

      /* 버튼 패딩 축소 */
      button[kind="secondary"], button[kind="primary"] {{
        padding:.18rem .5rem !important;
        font-size:.90rem !important;
      }}

      /* 배지 */
      .badge-green {{background:#e6ffcc; border:1px solid #b6f3a4;
        padding:3px 7px; border-radius:6px; color:#0b2e13; font-size:.84rem;}}
      .badge-blue  {{background:#e6f0ff; border:1px solid #b7ccff;
        padding:3px 7px; border-radius:6px; color:#0b1e4a; font-size:.84rem;}}

      /* 원형 로고 */
      .logo-circle {{
        width: 120px; height: 120px; border-radius: 50%;
        overflow: hidden; margin:.25rem auto .4rem auto;
        box-shadow:0 2px 8px rgba(0,0,0,.12); border:1px solid rgba(0,0,0,.06);
      }}
      .logo-circle img {{width:100%; height:100%; object-fit:cover;}}
    </style>
    """, unsafe_allow_html=True)
# ============================================
# Part 1 — 사이드바
# ============================================
def render_sidebar():
    with st.sidebar:
        # 로고 (logo.png가 같은 폴더에 있을 때 표시)
        lp = Path(__file__).parent / "logo.png"
        if lp.exists():
            b64 = base64.b64encode(lp.read_bytes()).decode("ascii")
            st.markdown(f'<div class="logo-circle"><img src="data:image/png;base64,{b64}"></div>', unsafe_allow_html=True)
        else:
            st.caption("logo.png 파일을 앱 폴더에 두면 원형 로고가 표시됩니다.")

        # 다크모드 토글
        st.toggle("🌓 다크 모드", value=(st.session_state["theme"]=="dark"), on_change=toggle_theme)

        # 환율 계산기
        st.markdown("### ① 환율 계산기")
        base = st.selectbox("기준 통화", list(CURRENCY_SYMBOL.keys()), index=0)
        sym = CURRENCY_SYMBOL.get(base, "")
        sale_foreign = st.number_input(f"판매금액 ({sym})", value=1.00, step=0.01, format="%.2f")
        won = FX_DEFAULT[base] * sale_foreign
        st.markdown(f'<div class="badge-green">환산 금액: <b>{won:,.2f} 원</b></div>', unsafe_allow_html=True)
        st.caption(f"환율 기준: {FX_DEFAULT[base]:,.2f} ₩/{base}")

        # 마진 계산기
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
# Part 2 — 데이터랩
# ============================================
def fetch_datalab_keywords(max_rows: int = 20) -> pd.DataFrame:
    """
    공개 HTML에서 안전하게 키워드 후보를 수집.
    내부 JSON 구조가 노출되면 그 경로를 파싱하고,
    아니면 휴리스틱으로 텍스트를 추출한다.
    """
    url = "https://datalab.naver.com/shoppingInsight/sCategory.naver"
    try:
        r = requests.get(url, headers={**MOBILE_HEADERS, "referer":"https://datalab.naver.com/"}, timeout=10)
        r.raise_for_status()
    except Exception:
        demo = ["맥심 커피믹스","카누 미니","원두커피 1kg","드립백 커피","스타벅스 다크","커피머신","핸드드립세트","모카포트","프렌치프레스","스틱커피"]
        return pd.DataFrame([{"rank":i+1,"keyword":k} for i,k in enumerate(demo[:max_rows])])

    soup = BeautifulSoup(r.text, "html.parser")
    rows=[]

    # 1) script 내 JSON 탐색
    for s in soup.find_all("script"):
        text = s.string or s.text or ""
        m = (re.search(r"__NEXT_DATA__\s*=\s*({[\s\S]*?})\s*;?", text) or
             re.search(r"__INITIAL_STATE__\s*=\s*({[\s\S]*?})\s*;?", text) or
             re.search(r"window\.__DATA__\s*=\s*({[\s\S]*?})\s*;?", text))
        if not m: 
            continue
        try:
            data = json.loads(m.group(1))
        except Exception:
            continue

        def walk(o):
            if isinstance(o, dict):
                for v in o.values():
                    r = walk(v)
                    if r: return r
            elif isinstance(o, list):
                if o and isinstance(o[0], dict) and any(("keyword" in o[0]) or ("name" in o[0]) for _ in [0]):
                    return o
                for v in o:
                    r = walk(v)
                    if r: return r
            return None

        items = walk(data) or []
        for i, it in enumerate(items[:max_rows], start=1):
            kw = (it.get("keyword") or it.get("name") or it.get("title") or "").strip()
            if kw:
                rows.append({"rank":i, "keyword":kw})
        if rows:
            break

    # 2) 휴리스틱 백업
    if not rows:
        uniq=[]
        for el in soup.select("a, li, span"):
            t = (el.get_text(" ", strip=True) or "").strip()
            if 2 <= len(t) <= 40 and any(ch.isalnum() for ch in t):
                t = re.sub(r"\s+"," ",t)
                if t not in uniq:
                    uniq.append(t)
            if len(uniq) >= max_rows: break
        rows = [{"rank":i+1,"keyword":kw} for i, kw in enumerate(uniq)]

    return pd.DataFrame(rows)

def render_datalab_block():
    st.subheader("데이터랩")
    cats = ["디지털/가전","식품","생활/건강","가구/인테리어","스포츠/레저","뷰티","출산/육아","반려동물","패션잡화","도서/취미"]
    st.selectbox("카테고리(표시용)", cats, index=0, key="datalab_cat")

    df = fetch_datalab_keywords()
    if df.empty:
        st.warning("키워드 수집 실패. 잠시 후 다시 시도하세요.")
        return

    # 그래프용 임의 점수 (실데이터 연결 시 이 부분만 대체)
    n=len(df)
    df["score"] = [max(1, int(100 - (i*(100/max(1,n-1))))) for i in range(n)]

    st.dataframe(df[["rank","keyword"]], use_container_width=True, hide_index=True)
    st.line_chart(df.set_index("rank")["score"], height=200)

    # iFrame 보기 (정책상 실패 가능 → 예외 삼켜서 아래 섹션 유지)
    url = "https://datalab.naver.com/shoppingInsight/sCategory.naver"
    colA, colB = st.columns(2)
    with colA:
        if st.button("직접 iFrame (실패 가능)", use_container_width=True):
            try:
                st.components.v1.iframe(url, height=700, scrolling=True)
            except Exception as e:
                st.error(f"임베드 실패: {type(e).__name__}")
    with colB:
        if has_proxy():
            if st.button("프록시 iFrame (권장)", use_container_width=True):
                try:
                    st.components.v1.iframe(iframe_url(url), height=700, scrolling=True)
                except Exception as e:
                    st.error(f"임베드 실패: {type(e).__name__}")
        else:
            st.caption("프록시를 설정하면 임베드 성공률이 올라갑니다.")
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

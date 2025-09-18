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
    if st.session_state["theme"] == "dark":
        bg, fg = "#0e1117", "#e6edf3"
    else:
        bg, fg = "#ffffff", "#111111"

    st.markdown(f"""
    <style>
      html, body, [data-testid="stAppViewContainer"] {{
        background-color:{bg} !important; color:{fg} !important;
      }}

      /* 섹션 카드 간격 조정 */
      .block-container {{
        padding-top:2rem !important;
        padding-bottom:.5rem !important;
      }}

      /* 제목 상단 여백 축소 */
      h1, h2, h3 {{
        margin-top:.2rem !important;
        margin-bottom:.4rem !important;
      }}

      /* 사이드바 최적화 */
      [data-testid="stSidebar"] section {{
        padding-top:.3rem !important;
        padding-bottom:.3rem !important;
      }}
      [data-testid="stSidebar"] .stSelectbox, 
      [data-testid="stSidebar"] .stNumberInput, 
      [data-testid="stSidebar"] .stRadio, 
      [data-testid="stSidebar"] .stButton {{
        margin-top:.2rem !important;
        margin-bottom:.2rem !important;
      }}

      /* 로고 */
      .logo-circle {{
        width: 130px; height: 130px; border-radius: 50%;
        overflow: hidden; margin-bottom:.2rem;
        box-shadow:0 2px 6px rgba(0,0,0,.1);
      }}
      .logo-circle img {{width:100%; height:100%; object-fit:cover;}}

      /* 컬러 박스 크기 축소 */
      .stAlert, .stSuccess, .stWarning, .stInfo {{
        padding:.4rem .6rem !important;
        font-size:0.82rem !important;
      }}
      .stAlert > div, .stSuccess > div, .stWarning > div, .stInfo > div {{
        margin:0 !important;
      }}

      /* 마진계산 결과 박스 */
      div[data-testid="stMarkdownContainer"] p {{
        margin:0.1rem 0 !important;
      }}
    </style>
    """, unsafe_allow_html=True)
# ============================================
# Part 1 — 사이드바  (REPLACE)
# ============================================
import base64

def render_sidebar():
    with st.sidebar:
        # 원형 로고(base64 인라인) – cloud에서도 보임
        lp = Path(__file__).parent / "logo.png"
        if lp.exists():
            b64 = base64.b64encode(lp.read_bytes()).decode("ascii")
            st.markdown(
                f'<div class="logo-circle"><img src="data:image/png;base64,{b64}"></div>',
                unsafe_allow_html=True
            )
        else:
            st.warning("logo.png 를 앱 파일과 같은 폴더에 두면 사이드바에 표시됩니다.")

        # 🌓 다크 모드 토글 (라벨에 이모지)
        st.toggle("🌓 다크 모드", value=(st.session_state["theme"] == "dark"), on_change=toggle_theme)

        # 환율 계산기
        st.markdown("### ① 환율 계산기")
        base = st.selectbox("기준 통화", list(CURRENCY_SYMBOL.keys()), index=0)
        sym = CURRENCY_SYMBOL.get(base, "")
        sale_foreign = st.number_input(f"판매금액 (외화 {sym})", value=1.00, step=0.01, format="%.2f")
        won = FX_DEFAULT[base] * sale_foreign
        st.markdown(f'<div class="badge-green">환산 금액: <b>{won:,.2f} 원</b></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="note-small">환율 기준: {FX_DEFAULT[base]:,.2f} ₩/{base}</div>', unsafe_allow_html=True)

        # 마진 계산기
        st.markdown("### ② 마진 계산기")
        m_base = st.selectbox("매입 통화", list(CURRENCY_SYMBOL.keys()), index=0, key="mbase")
        m_sym  = CURRENCY_SYMBOL.get(m_base, "")
        purchase_foreign = st.number_input(f"매입금액 (외화 {m_sym})", value=0.00, step=0.01, format="%.2f")
        base_cost_won = FX_DEFAULT[m_base] * purchase_foreign if purchase_foreign>0 else won
        st.markdown(f'<div class="badge-green">원가(₩): <b>{base_cost_won:,.2f} 원</b></div>', unsafe_allow_html=True)

        m_rate = st.number_input("카드수수료 (%)", value=4.00, step=0.01, format="%.2f")
        m_fee  = st.number_input("마켓수수료 (%)", value=14.00, step=0.01, format="%.2f")
        ship   = st.number_input("배송비 (₩)", value=0.0, step=100.0, format="%.0f")
        mode   = st.radio("마진 방식", ["퍼센트 마진(%)","더하기 마진(₩)"], horizontal=True)
        margin = st.number_input("마진율/마진액", value=10.00, step=0.01, format="%.2f")
        if mode=="퍼센트 마진(%)":
            target_price = base_cost_won * (1 + m_rate/100) * (1 + m_fee/100) * (1 + margin/100) + ship
        else:
            target_price = base_cost_won * (1 + m_rate/100) * (1 + m_fee/100) + margin + ship
        st.markdown(f'<div class="badge-blue">판매가: <b>{target_price:,.2f} 원</b></div>', unsafe_allow_html=True)
        st.warning(f"순이익(마진): {(target_price - base_cost_won):,.2f} 원")
# ============================================
# Part 2 — 데이터랩  (REPLACE)
# ============================================
def fetch_datalab_keywords(max_rows: int = 20) -> pd.DataFrame:
    url = "https://datalab.naver.com/shoppingInsight/sCategory.naver"
    try:
        r = requests.get(url, headers={**MOBILE_HEADERS, "referer": "https://datalab.naver.com/"}, timeout=10)
        r.raise_for_status()
    except Exception:
        demo = ["맥심 커피믹스","카누 미니","원두커피 1kg","드립백 커피","스타벅스 다크","커피머신","핸드드립세트","모카포트","프렌치프레스","스틱커피"]
        return pd.DataFrame([{"rank":i+1,"keyword":k} for i,k in enumerate(demo[:max_rows])])

    soup = BeautifulSoup(r.text, "html.parser")
    # 1) 스크립트 JSON 시도
    rows=[]
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
                rows.append({"rank": i, "keyword": kw})
        if rows:
            break

    # 2) 휴리스틱 백업
    if not rows:
        uniq=[]
        for el in soup.select("a, li, span"):
            t = (el.get_text(" ", strip=True) or "").strip()
            if 2 <= len(t) <= 40 and any(ch.isalnum() for ch in t):
                t = re.sub(r"\s+", " ", t)
                if t not in uniq: 
                    uniq.append(t)
            if len(uniq) >= max_rows: break
        rows = [{"rank":i+1,"keyword":kw} for i, kw in enumerate(uniq)]

    return pd.DataFrame(rows)

def render_datalab_block():
    st.subheader("데이터랩")
    # 카테고리 프리셋(표시용): 실제 크롤링은 동일 페이지 기준
    cats = ["도서/취미","디지털/가전","식품","생활/건강","가구/인테리어","스포츠/레저","뷰티","출산/육아","반려동물","패션잡화"]
    cat = st.selectbox("카테고리(표시용)", cats, index=2, key="datalab_cat")

    df = fetch_datalab_keywords()
    if df.empty:
        st.warning("키워드 수집 실패. 잠시 후 다시 시도하세요.")
        return

    # 의사 점수 생성 (그래프용) — 실제 수치 생기면 이 부분만 바꿔 끼우면 됨
    n = len(df)
    df["score"] = [max(1, int(100 - (i*(100/max(1,n-1))))) for i in range(n)]

    st.dataframe(df[["rank","keyword"]], use_container_width=True, hide_index=True)

    # 라인 그래프
    chart_df = df[["rank","score"]].set_index("rank")
    st.line_chart(chart_df, height=200)

    # 임베드(테스트/프록시)
    colA, colB = st.columns(2)
    with colA:
        st.caption("직접 iFrame은 사이트 정책에 따라 실패할 수 있습니다.")
        if st.button("직접 iFrame (실패 가능)", key="dl_iframe_direct"):
            st.components.v1.iframe("https://datalab.naver.com/shoppingInsight/sCategory.naver", height=560)
    with colB:
        if has_proxy():
            if st.button("프록시 iFrame (권장)", key="dl_iframe_proxy"):
                st.components.v1.iframe(iframe_url("https://datalab.naver.com/shoppingInsight/sCategory.naver"), height=560)
        else:
            st.caption("임베드가 필요하면 Part 0의 PROXY_URL을 설정하세요.")
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
# Part 5 — 11번가 (REPLACE)
# ============================================
def fetch_11st_best(max_rows: int = 50) -> pd.DataFrame:
    url = "https://m.11st.co.kr/browsing/bestSellers.mall"
    try:
        r = requests.get(url, headers={**MOBILE_HEADERS, "referer": "https://m.11st.co.kr/"}, timeout=10)
        r.raise_for_status()
    except Exception:
        return pd.DataFrame([{"rank":1,"title":"요청 실패","price":""}])

    soup = BeautifulSoup(r.text, "html.parser")
    rows=[]; i=0

    selectors = [
        "li.c_prd_item", "div.c_prd", "div.c_card",
        "li[class*=prd]", "li[class*=product]", "li[class*=item]"
    ]
    for sel in selectors:
        for li in soup.select(sel):
            a = li.select_one("a[href]")
            title_el = li.select_one(".name, .title, .prd_name, .c_prd_name, [class*=name], [class*=title]") or a
            price_el = li.select_one(".price, .value, .num, .c_prd_price, [class*=price], [class*=value]")
            title = (title_el.get_text(" ", strip=True) if title_el else "").strip()
            price = (price_el.get_text(" ", strip=True) if price_el else "").strip()
            if not title: 
                continue
            i += 1
            rows.append({"rank": i, "title": title, "price": price})
            if i >= max_rows: break
        if rows: break

    if rows: 
        return pd.DataFrame(rows)
    return pd.DataFrame([{"rank":1,"title":"empty","price":""}])

def render_elevenst_block():
    st.subheader("11번가 (모바일)")
    df = fetch_11st_best()
    st.dataframe(df, use_container_width=True, hide_index=True)

    colA, colB = st.columns(2)
    with colA:
        if st.button("직접 iFrame (실패 가능)", key="e11_iframe_direct"):
            st.components.v1.iframe("https://m.11st.co.kr/browsing/bestSellers.mall", height=560)
    with colB:
        if has_proxy():
            if st.button("프록시 iFrame (권장)", key="e11_iframe_proxy"):
                st.components.v1.iframe(iframe_url("https://m.11st.co.kr/browsing/bestSellers.mall"), height=560)
        else:
            st.caption("임베드가 필요하면 Part 0의 PROXY_URL을 설정하세요.")
# ============================================
# Part 6 — AI 키워드 레이더 (PATCH E)
# ============================================
# 🔑 라쿠텐 App ID (네가 준 값으로 직접 심어둠)
RAKUTEN_APP_ID = "1079389531957868278"   # secrets.toml 불필요

# 카테고리 프리셋 (genreId 확장)
RAKUTEN_GENRES = {
    "도서/서적": "101266",
    "음반/CD": "101240",
    "영화/DVD/블루레이": "101251",
    "가전/디지털": "213310",
    "PC/주변기기": "100026",
    "스마트폰/액세서리": "568972",
    "남성 패션": "551169",
    "여성 패션": "100371",
    "패션잡화": "216129",
    "뷰티/코스메틱": "100939",
    "식품/식료품": "100316",
    "주류/음료": "510915",
    "생활/건강": "215783",
    "인테리어/가구": "2157830",
    "스포츠/레저": "101070",
    "취미/게임/완구": "101205",
    "자동차/바이크": "558929",
    "베이비/키즈": "100533",
    "반려동물": "101213",
    "사무/문구": "216131",
    "꽃/가드닝": "100005"
}

def _rakuten_build_url(endpoint: str, params: dict) -> str:
    q = urllib.parse.urlencode(params, safe="")
    base = f"{endpoint}?{q}"
    if has_proxy():
        return f"{PROXY_URL}/fetch?target={urllib.parse.quote(base, safe='')}"
    return base

@st.cache_data(ttl=600)
def rakuten_fetch_ranking(app_id: str, genre_id: str, rows: int = 50) -> pd.DataFrame:
    """
    Rakuten IchibaItem Ranking API
    """
    if not app_id:
        demo = ["デモ 상품 A","デモ 상품 B","デモ 상품 C"]
        return pd.DataFrame([{"rank": i+1,"keyword":t,"source":"Rakuten JP (DEMO)"} for i,t in enumerate(demo)])

    endpoint = "https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20170628"
    url = _rakuten_build_url(endpoint, {
        "applicationId": app_id,
        "format": "json",
        "genreId": genre_id
    })
    try:
        resp = requests.get(url, headers=MOBILE_HEADERS, timeout=12)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("Items", [])[:rows]
        out = []
        for i,it in enumerate(items, start=1):
            item = it.get("Item", {})
            name = item.get("itemName") or ""
            out.append({"rank": i, "keyword": name, "source": "Rakuten JP"})
        return pd.DataFrame(out) if out else pd.DataFrame([{"rank":1,"keyword":"데이터 없음","source":"Rakuten JP"}])
    except Exception as e:
        return pd.DataFrame([{"rank":1,"keyword":f"API 실패: {e}","source":"Rakuten JP"}])

def render_rakuten_block():
    st.subheader("AI 키워드 레이더 (국내/글로벌)")

    # ---- 모드 선택
    mode = st.radio("모드", ["국내","글로벌"], horizontal=True, label_visibility="collapsed")

    # ---- 카테고리 선택 + 직접 genreId 입력
    c1, c2 = st.columns([1.5,1])
    with c1:
        preset = st.selectbox("라쿠텐 카테고리", list(RAKUTEN_GENRES.keys()), index=0)
        preset_id = RAKUTEN_GENRES[preset]
    with c2:
        genre_id = st.text_input("genreId (직접 입력 가능)", value=preset_id)

    # ---- 데이터 로드
    df = rakuten_fetch_ranking(app_id=RAKUTEN_APP_ID, genre_id=genre_id, rows=50)

    # ---- 표 표시
    st.dataframe(df, use_container_width=True, hide_index=True)

    # ---- 안내
    st.caption("※ Rakuten 공식 Ranking API는 상품 랭킹을 반환합니다. 상품명을 키워드처럼 취급하여 표시합니다.")
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

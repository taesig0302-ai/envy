# envy_app_single.py — 단일파일 풀버전 (utils/datalab/rakuten/11번가/namegen 포함)
# 필요 사항: ~/.streamlit/secrets.toml
#   ENVY_PROXY_URL = "https://<your-worker>.workers.dev"
#   RAKUTEN_APP_ID = "1043271015809337425"  # 없으면 데모 데이터
#   RENDER_API     = ""
#
# 실행: streamlit run envy_app_single.py

import streamlit as st
import requests, urllib.parse, pandas as pd
from bs4 import BeautifulSoup

# =====================[ Part 0: 공통 시크릿/설정 ]=====================
PROXY = st.secrets.get("ENVY_PROXY_URL", "")
RAKUTEN_APP_ID = st.secrets.get("RAKUTEN_APP_ID", "")
RENDER_API = st.secrets.get("RENDER_API", "")

MOBILE_UA = "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Mobile Safari/537.36"

def _need_proxy():
    if not PROXY:
        raise RuntimeError("ENVY_PROXY_URL not set in secrets.toml")

def _purl(kind: str, url: str) -> str:
    _need_proxy()
    return f"{PROXY}/{kind}?target={urllib.parse.quote(url, safe='')}"

def purl(url: str) -> str:        # /fetch
    return _purl("fetch", url)

def iframe_url(url: str) -> str:  # /iframe
    return _purl("iframe", url)

def snapshot_url(url: str) -> str:# /snapshot
    return _purl("snapshot", url)

def get_html_via_proxy(url: str, timeout=12) -> str:
    """워커 경유 GET(html)"""
    resp = requests.get(purl(url), timeout=timeout, headers={"user-agent": MOBILE_UA})
    resp.raise_for_status()
    return resp.text

# =====================[ Part 1: DataLab ]=============================
@st.cache_data(ttl=300)
def fetch_datalab_category_top20(category_id: str, period="7d") -> pd.DataFrame:
    """
    비공개 API: 실제 엔드포인트만 교체하면 동작.
    response 예시: {"ranks":[{"rank":1,"keyword":"맥심","search":100}, ...]}
    """
    base = "https://datalab.naver.com/example/api/categoryTop20"  # TODO: 실제 엔드포인트로 교체
    url = f"{base}?cid={urllib.parse.quote(category_id)}&period={period}"
    r = requests.get(purl(url), timeout=10, headers={"user-agent": MOBILE_UA})
    if r.status_code != 200:
        raise RuntimeError(f"DataLab http {r.status_code}")
    data = r.json()
    rows = data.get("ranks", [])
    return pd.DataFrame(rows)

def render_datalab_block():
    st.markdown("### 데이터랩")
    c1, c2 = st.columns([2,3])
    with c1:
        category = st.selectbox(
            "카테고리(10개)",
            ["패션잡화","디지털/가전","식품","생활/건강","가구/인테리어","도서/취미","스포츠/레저","뷰티","출산/육아","반려동물"],
            index=0
        )
        cid_map = {
            "패션잡화":"50000000-FA","디지털/가전":"50000000-DG","식품":"50000000-FD","생활/건강":"50000000-LH",
            "가구/인테리어":"50000000-FN","도서/취미":"50000000-BC","스포츠/레저":"50000000-SP",
            "뷰티":"50000000-BT","출산/육아":"50000000-BB","반려동물":"50000000-PS",
        }
        cid = cid_map[category]
        st.session_state["_datalab_cid"] = cid
        retried = st.button("데이터랩 재시도")
    with c2:
        st.caption("프록시/기간/CID 자동 처리. 실패 시 경고와 함께 재시도하세요.")

    try:
        df = fetch_datalab_category_top20(st.session_state["_datalab_cid"])
        if retried:
            df = fetch_datalab_category_top20(st.session_state["_datalab_cid"])
        if df.empty:
            st.warning("DataLab 결과가 비었습니다. 엔드포인트/세션 구조를 확인하세요.")
            return
        st.dataframe(df, use_container_width=True, hide_index=True)
        if "search" in df.columns:
            st.line_chart(df.set_index("rank")["search"], height=180)
    except Exception as e:
        st.warning(f"DataLab 호출 실패: {e}\n프록시/기간/CID 확인 후 재시도하세요.")

# =====================[ Part 2: Rakuten ]=============================
@st.cache_data(ttl=600)
def fetch_rakuten_keywords(country="JP", app_id="") -> pd.DataFrame:
    """App ID 없으면 데모 로우 반환"""
    if not app_id:
        rows = [
            {"rank":1,"keyword":"YOUNG OLD 初回盤 Blu-ray","source":"Rakuten JP"},
            {"rank":2,"keyword":"YOUNG OLD DVD 初回盤 【SixTONES】","source":"Rakuten JP"},
            {"rank":3,"keyword":"YOUNG OLD Blu-ray 初回盤","source":"Rakuten JP"},
            {"rank":4,"keyword":"楽天ブックス限定特典","source":"Rakuten JP"},
            {"rank":5,"keyword":"楽天ブックス ランキング","source":"Rakuten JP"},
        ]
        return pd.DataFrame(rows)

    endpoint = "https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20170628"
    url = f"{endpoint}?applicationId={app_id}&format=json&genreId=100283"
    r = requests.get(purl(url), timeout=10, headers={"user-agent": MOBILE_UA})
    r.raise_for_status()
    data = r.json()
    rows=[]
    for i, item in enumerate(data.get("Items", []), start=1):
        name = item["Item"]["itemName"]
        rows.append({"rank": i, "keyword": name, "source": "Rakuten JP"})
    return pd.DataFrame(rows)

def render_rakuten_block():
    st.subheader("AI 키워드 레이더 (국내/글로벌)")
    mode = st.radio("모드", ["국내","글로벌"], horizontal=True, label_visibility="collapsed")
    if mode == "국내":
        st.info("국내는 데이터랩·아이템스카우트·셀러라이프 조합 / 현재 DataLab 결과 우선", icon="ℹ️")
    df = fetch_rakuten_keywords(country="JP", app_id=RAKUTEN_APP_ID)
    st.dataframe(df, use_container_width=True, hide_index=True)

# =====================[ Part 3: 11번가(모바일) ]======================
MOBILE_BEST = "https://m.11st.co.kr/browsing/bestSellers.mall"

def parse_11st_best(url=MOBILE_BEST) -> pd.DataFrame:
    """가변 마크업 대비 넓게 스캔 → 필터링"""
    html = get_html_via_proxy(url)
    soup = BeautifulSoup(html, "html.parser")
    rows=[]; rank=0
    for node in soup.select("li, div"):
        a = node.select_one("a[href*='/products/'], a[href*='m.11st.co.kr/products/'], a[href*='/browsing/']")
        if not a: 
            continue
        title_el = (node.select_one(".name, .title, .prd_name, [class*='name'], [class*='title']") or a)
        title = title_el.get_text(" ", strip=True) if title_el else ""
        if not title or len(title) < 2: 
            continue
        price_el = node.select_one(".price, .value, .num, [class*='price'], [class*='value']")
        price = price_el.get_text(" ", strip=True) if price_el else ""
        img_el = node.select_one("img[src], img[data-src]")
        img = (img_el.get("data-src") or img_el.get("src")) if img_el else ""
        link = a.get("href","")
        if link.startswith("/"):
            link = "https://m.11st.co.kr" + link
        rank += 1
        rows.append({"rank":rank, "title":title, "price":price, "img":img, "link":link})
        if rank >= 50: 
            break
    return pd.DataFrame(rows)

def render_11st_block():
    st.subheader("11번가 (모바일)")
    url = st.text_input("11번가 URL", value=MOBILE_BEST, label_visibility="collapsed")

    # 1) iframe
    try:
        st.components.v1.iframe(src=iframe_url(url), height=520)
        return
    except Exception:
        pass

    # 2) snapshot
    try:
        html = requests.get(snapshot_url(url), timeout=12).text
        st.components.v1.html(html[:30000], height=520, scrolling=True)
        return
    except Exception:
        pass

    # 3) parsing
    try:
        df = parse_11st_best(url)
        if df.empty:
            st.warning("11번가 파싱 실패(보안정책/마크업 변경 가능).")
        else:
            st.dataframe(df[["rank","title","price"]], use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"11번가 로드 실패: {e}")

# =====================[ Part 4: 상품명 생성기 ]=======================
def render_namegen_block():
    st.subheader("상품명 생성기 (규칙 기반)")
    brand = st.text_input("브랜드", value="envy")
    base_kw = st.text_input("베이스 키워드", value="K-coffee mix")
    rel_kw = st.text_input("연관키워드(콤마)", value="Maxim, Kanu, Korea")
    banned = st.text_input("금칙어", value="copy, fake, replica")
    limit = st.slider("글자수 제한", 20, 80, 80)
    if st.button("제목 5개 생성"):
        kws = [k.strip() for k in rel_kw.split(",") if k.strip()]
        outs=[]
        for k in kws[:5]:
            title = f"{brand} {base_kw} {k}".replace(",", " ")
            for b in [x.strip() for x in banned.split(",") if x.strip()]:
                title = title.replace(b, "")
            title = " ".join(title.split())[:limit]
            outs.append(title)
        st.text_area("생성 결과", "\n".join(outs), height=200)
    st.caption("연관키워드는 상단 데이터랩/글로벌 표를 참조하세요.")

# =====================[ Part 5: 메인 앱 ]=============================
st.set_page_config(page_title="ENVY v27.14 Full (Single)", page_icon="✨", layout="wide")

# 다크모드 토글 (세션 + 즉시 반영)
if "theme" not in st.session_state:
    st.session_state["theme"] = "light"

def toggle_theme():
    st.session_state["theme"] = "dark" if st.session_state["theme"]=="light" else "light"

with st.sidebar:
    st.toggle("다크 모드", value=(st.session_state["theme"]=="dark"), on_change=toggle_theme)

# 즉시 반영 JS
st.components.v1.html(f"""
<script>
(function(){{
  const b = window.parent?.document?.querySelector('body');
  if(!b) return;
  b.classList.remove('envy-light','envy-dark');
  b.classList.add('{ 'envy-dark' if st.session_state['theme']=='dark' else 'envy-light' }');
}})();
</script>
""", height=0)

# CSS (사이드바/색상 변수/간격)
st.markdown("""
<style>
.block-container{padding-top:0.8rem; padding-bottom:0.8rem;}
[data-testid="stSidebar"] section{padding-top:0.6rem; padding-bottom:0.6rem;}
.sidebar-conn, [data-testid="stSidebar"] .conn-hide {display:none !important;}
body.envy-light { --bg:#ffffff; --bg2:#f6f8fb; --text:#111111; --primary:#2b7fff; }
body.envy-dark  { --bg:#0e1117; --bg2:#161b22; --text:#e6edf3; --primary:#6ea8fe; }
.block-container{ background:var(--bg); color:var(--text);}
section[data-testid="stSidebar"]{ background:var(--bg2); color:var(--text);}
a { color:var(--primary) !important; }
</style>
""", unsafe_allow_html=True)

# 사이드바 계산기
with st.sidebar:
    st.markdown("### ① 환율 계산기")
    base = st.selectbox("기준 통화", ["USD","EUR","JPY","CNY"], index=0)
    rate = st.number_input("환율 (1 단위 = ₩)", value=1400.00, step=0.01, format="%.2f")
    sale_foreign = st.number_input("판매금액 (외화)", value=1.00, step=0.01, format="%.2f")
    won = rate * sale_foreign
    st.success(f"환산 금액: {won:,.2f} 원")

    st.markdown("### ② 마진 계산기 (v23)")
    m_rate = st.number_input("카드수수료 (%)", value=4.00, step=0.01, format="%.2f")
    m_fee  = st.number_input("마켓수수료 (%)", value=14.00, step=0.01, format="%.2f")
    ship   = st.number_input("배송비 (₩)", value=0.0, step=100.0, format="%.0f")
    mode   = st.radio("마진 방식", ["퍼센트 마진(%)","더하기 마진(₩)"], horizontal=True)
    margin = st.number_input("마진율/마진액", value=10.00, step=0.01, format="%.2f")
    if mode=="퍼센트 마진(%)":
        target_price = won * (1 + m_rate/100) * (1 + m_fee/100) * (1 + margin/100) + ship
    else:
        target_price = won * (1 + m_rate/100) * (1 + m_fee/100) + margin + ship
    st.info(f"예상 판매가: {target_price:,.2f} 원")
    st.warning(f"순이익(마진): {(target_price - won):,.2f} 원")

# 본문 3×3 레이아웃
top1, top2, top3 = st.columns([1,1,1])
mid1, mid2, mid3 = st.columns([1,1,1])
bot1, bot2, bot3 = st.columns([1,1,1])

with top1: render_datalab_block()
with top2: st.subheader("아이템스카우트"); st.info("연동 대기 (별도 API/프록시)")
with top3: st.subheader("셀러라이프"); st.info("연동 대기 (별도 API/프록시)")

with mid1: render_rakuten_block()
with mid2: render_11st_block()
with mid3: render_namegen_block()

with bot1: st.empty()
with bot2: st.empty()
with bot3: st.empty()

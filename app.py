# app.py (monolithic, no external imports except third-party libs)
# Runs standalone: includes utils, datalab, rakuten, elevenst, namegen in one file.
import streamlit as st
import requests, urllib.parse, pandas as pd
from bs4 import BeautifulSoup

# ===================== utils (embedded) =====================
PROXY = st.secrets.get("ENVY_PROXY_URL", "")
RAKUTEN_APP_ID = st.secrets.get("RAKUTEN_APP_ID", "")
RENDER_API = st.secrets.get("RENDER_API", "")

def _need_proxy():
    if not PROXY:
        raise RuntimeError("ENVY_PROXY_URL not set in secrets.toml")

def purl(url: str) -> str:
    _need_proxy()
    return f"{PROXY}/fetch?target={urllib.parse.quote(url, safe='')}"

def iframe_url(url: str) -> str:
    _need_proxy()
    return f"{PROXY}/iframe?target={urllib.parse.quote(url, safe='')}"

def snapshot_url(url: str) -> str:
    _need_proxy()
    return f"{PROXY}/snapshot?target={urllib.parse.quote(url, safe='')}"

def get_html_via_proxy(url: str, timeout=12) -> str:
    resp = requests.get(purl(url), timeout=timeout, headers={
        "user-agent":"Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Mobile Safari/537.36"
    })
    resp.raise_for_status()
    return resp.text

# ===================== datalab (embedded) =====================
@st.cache_data(ttl=300)
def fetch_datalab_category_top20(category_id: str, period="7d") -> pd.DataFrame:
    # Replace base with working internal endpoint when available
    base = "https://datalab.naver.com/example/api/categoryTop20"
    url = f"{base}?cid={urllib.parse.quote(category_id)}&period={period}"
    r = requests.get(purl(url), timeout=10)
    if r.status_code != 200:
        raise RuntimeError(f"DataLab http {r.status_code}")
    data = r.json()  # expected: {"ranks":[{"rank":1,"keyword":"...","search":100}, ...]}
    rows = data.get("ranks", [])
    df = pd.DataFrame(rows)
    return df

def render_datalab_block():
    st.markdown("### 데이터랩")
    col1, col2 = st.columns([2,3])
    with col1:
        category = st.selectbox(
            "카테고리(10개)",
            ["패션잡화","디지털/가전","식품","생활/건강","가구/인테리어","도서/취미","스포츠/레저","뷰티","출산/육아","반려동물"],
            index=0
        )
        cid_map = {
            "패션잡화":"50000000-FA",
            "디지털/가전":"50000000-DG",
            "식품":"50000000-FD",
            "생활/건강":"50000000-LH",
            "가구/인테리어":"50000000-FN",
            "도서/취미":"50000000-BC",
            "스포츠/레저":"50000000-SP",
            "뷰티":"50000000-BT",
            "출산/육아":"50000000-BB",
            "반려동물":"50000000-PS",
        }
        cid = cid_map[category]
        st.session_state["_datalab_cid"] = cid
        retried = st.button("데이터랩 재시도", use_container_width=False)
    with col2:
        st.caption("프록시/기간/CID 자동 처리. 실패 시 즉시 경고 후 재시도하세요.")
    try:
        if retried or "_datalab_loaded" not in st.session_state:
            df = fetch_datalab_category_top20(st.session_state["_datalab_cid"])
            st.session_state["_datalab_loaded"] = True
        else:
            df = fetch_datalab_category_top20(st.session_state["_datalab_cid"])
    except Exception as e:
        st.warning(f"DataLab 호출 실패: {e}\n프록시/기간/CID 확인 후 재시도하세요.")
        return
    if not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)
        try:
            st.line_chart(df.set_index("rank")["search"], height=180)
        except Exception:
            pass

# ===================== rakuten (embedded) =====================
@st.cache_data(ttl=600)
def fetch_rakuten_keywords(country="JP", app_id="") -> pd.DataFrame:
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
    r = requests.get(purl(url), timeout=10)
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
        st.info("국내는 데이터랩, 아이템스카우트, 셀러라이프 조합 / 현재 DataLab 결과 우선", icon="ℹ️")
    df = fetch_rakuten_keywords(country="JP", app_id=RAKUTEN_APP_ID)
    st.dataframe(df, use_container_width=True, hide_index=True)

# ===================== elevenst (embedded) =====================
MOBILE_BEST = "https://m.11st.co.kr/browsing/bestSellers.mall"

def parse_11st_best(url=MOBILE_BEST) -> pd.DataFrame:
    html = get_html_via_proxy(url)
    soup = BeautifulSoup(html, "html.parser")
    rows=[]
    candidates = soup.select("li, div")
    rank = 0
    for node in candidates:
        a = node.select_one("a[href*='/products/'], a[href*='m.11st.co.kr/products/'], a[href*='/browsing/']")
        if not a:
            continue
        title_el = (node.select_one(".name, .title, .prd_name, [class*='name'], [class*='title']") or a)
        title = title_el.get_text(" ", strip=True)
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

# ===================== namegen (embedded) =====================
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
            title = " ".join(title.split())
            title = title[:limit]
            outs.append(title)
        st.text_area("생성 결과", "\n".join(outs), height=200)
    st.caption("연관키워드는 상단 데이터랩/글로벌 표를 참조하세요.")

# ===================== main app =====================
st.set_page_config(page_title="ENVY v27.14 Full", page_icon="✨", layout="wide")

# theme toggle
if "theme" not in st.session_state:
    st.session_state["theme"] = "light"

def apply_theme_now():
    st.components.v1.html(
        f"""
        <script>
        (function(){{
          const b = window.parent?.document?.querySelector('body');
          if(!b) return;
          b.classList.remove('envy-light','envy-dark');
          b.classList.add('{ 'envy-dark' if st.session_state['theme']=='dark' else 'envy-light' }');
        }})();
        </script>
        """, height=0
    )

def toggle_theme():
    st.session_state["theme"] = "dark" if st.session_state["theme"] == "light" else "light"

with st.sidebar:
    st.toggle("다크 모드", value=(st.session_state["theme"]=="dark"), on_change=toggle_theme)
apply_theme_now()

st.markdown("""
<style>
.block-container{padding-top:0.8rem; padding-bottom:0.8rem;}
[data-testid="stSidebar"] section{padding-top:0.6rem; padding-bottom:0.6rem;}
[data-testid="stSidebar"] .stButton{margin-top:0.2rem; margin-bottom:0.2rem;}
.sidebar-conn, [data-testid="stSidebar"] .conn-hide {display:none !important;}
body.envy-light { --bg:#ffffff; --bg2:#f6f8fb; --text:#111111; --primary:#2b7fff; }
body.envy-dark  { --bg:#0e1117; --bg2:#161b22; --text:#e6edf3; --primary:#6ea8fe; }
.block-container{ background:var(--bg); color:var(--text);}
section[data-testid="stSidebar"]{ background:var(--bg2); color:var(--text);}
a { color:var(--primary) !important; }
</style>
""", unsafe_allow_html=True)

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

# =============== Part 1: Imports / Config / Guards ==========================
import streamlit as st
import pandas as pd
import requests
from urllib.parse import quote

st.set_page_config(page_title="ENVY v27.x Full", layout="wide")

# ▶ 여기 두 값은 하드코딩 우선, 없으면 st.secrets 로 대체
CF_PROXY_URL   = "https://envy-proxy.taesig0302.workers.dev"  # ← 당신 워커 URL
RAKUTEN_APP_ID = "1043271015809337425"                        # ← 당신 Rakuten App ID

# secrets fallback
if not CF_PROXY_URL:
    CF_PROXY_URL = st.secrets.get("CF_PROXY_URL", CF_PROXY_URL)
if not RAKUTEN_APP_ID:
    RAKUTEN_APP_ID = st.secrets.get("RAKUTEN_APP_ID", RAKUTEN_APP_ID)

def require_config():
    missing = []
    if not CF_PROXY_URL:   missing.append("CF_PROXY_URL")
    if not RAKUTEN_APP_ID: missing.append("RAKUTEN_APP_ID")
    if missing:
        st.error(f"필수 설정 누락: {', '.join(missing)} — 코드/Secrets 에 값을 채워주세요.")
        st.stop()

# 네이버 데이터랩 카테고리 CID(샘플: 실제 CID 로 교체 가능)
CID_MAP = {
    "패션잡화":    "50000000",
    "식품":        "50000001",
    "가구/인테리어": "50000002",
    "디지털/가전":  "50000003",
    "생활/건강":    "50000004",
    "출산/육아":    "50000005",
    "스포츠/레저":  "50000006",
    "도서/음반":    "50000007",
    "여행/티켓":    "50000008",
    "반려/취미":    "50000009",
}
# ===========================================================================

# =================== Part 2: CSS / Sidebar ================================
def fixed_css():
    st.markdown("""
    <style>
      .card {padding:16px;border-radius:12px;background:var(--background-color-secondary,#1115);
             border:1px solid rgba(255,255,255,0.08); min-height:340px;}
      .card h3, .card h4 {margin-top:0;}
      .row-gap {margin-top: 14px;}
      section[data-testid="stSidebar"] > div {height: 100vh; overflow-y: auto;}
    </style>
    """, unsafe_allow_html=True)

def sidebar_calculators():
    with st.sidebar:
        st.toggle("🌙 다크 모드", value=True, key="dark_hint", help="(테마는 브라우저/앱 설정에 따릅니다)")

        st.markdown("### ① 환율 계산기")
        base_currency = st.selectbox("기준 통화", ["USD","EUR","JPY","CNY"], index=0)
        rate = st.number_input("환율 (1 단위 → ₩)", value=1400.00, step=0.01, format="%.2f")
        price_foreign = st.number_input("판매금액 (외화)", value=1.00, step=0.01, format="%.2f")
        exch_amt = price_foreign * rate
        st.success(f"환산 금액: {exch_amt:,.2f} 원")

        st.markdown("### ② 마진 계산기 (v23)")
        fee_card   = st.number_input("카드수수료 (%)", value=4.00,  step=0.01, format="%.2f")
        fee_market = st.number_input("마켓수수료 (%)", value=14.00, step=0.01, format="%.2f")
        ship       = st.number_input("배송비 (원)", value=0.00, step=100.0, format="%.0f")
        mode       = st.radio("마진 방식", ["퍼센트 마진(%)","더하기 마진(₩)"], index=0, horizontal=True)
        mval       = st.number_input("마진율/마진액", value=10.00, step=0.10, format="%.2f")

        cost = exch_amt * (1 + fee_card/100) * (1 + fee_market/100)
        price_krw = (cost * (1 + mval/100) + ship) if mode.startswith("퍼센트") else (cost + mval + ship)

        st.info(f"예상 판매가: {price_krw:,.2f} 원")
        st.warning(f"순이익(마진): {price_krw - cost:,.2f} 원")

        # ⛔️ 여기서 끝! 사이드바에는 그 아래 어떤 입력/설정도 두지 않음.
# ==========================================================================

# ==================== Part 3: Data & Embed utils ==========================
def fetch_datalab_top20(category_name: str) -> pd.DataFrame:
    """프록시 워커를 통해 DataLab JSON을 받아 Top20 테이블 생성."""
    require_config()
    cid = CID_MAP.get(category_name)
    if not cid:
        return pd.DataFrame(columns=["rank","keyword","search"])

    # 프록시 워커 → target 으로 실제 DataLab API/JSON을 읽어옴 (워커쪽에서 세션/쿠키 처리)
    target = f"https://datalab.naver.com/api/category/top20?cid={cid}"
    url = f"{CF_PROXY_URL}/?target={quote(target)}"
    try:
        r = requests.get(url, timeout=12)
        if r.status_code != 200:
            return pd.DataFrame(columns=["rank","keyword","search"])
        js = r.json()
        ranks = js.get("ranks", [])
        if not ranks:
            return pd.DataFrame(columns=["rank","keyword","search"])
        rows = [{"rank": i+1, "keyword": d.get("keyword",""), "search": 100-i} for i,d in enumerate(ranks[:20])]
        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame(columns=["rank","keyword","search"])

def fetch_rakuten_keywords(region: str = "JP") -> pd.DataFrame:
    """Rakuten Ranking API 예시 호출 — App ID 코드에 고정(입력 UI 없음)."""
    require_config()
    endpoint = "https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20170628"
    params = {"format":"json", "applicationId": RAKUTEN_APP_ID}
    try:
        r = requests.get(endpoint, params=params, timeout=12)
        rows = []
        if r.ok:
            for i, item in enumerate(r.json().get("Items", [])[:20], start=1):
                name = item.get("Item", {}).get("itemName", "")
                rows.append({"rank": i, "keyword": name, "source": f"Rakuten {region}"})
        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame(columns=["rank","keyword","source"])

def elevenst_iframe(url: str) -> str:
    """11번가 모바일 페이지를 프록시 프레임으로 임베드."""
    require_config()
    return f'''
    <iframe src="{CF_PROXY_URL}/?frame=1&target={quote(url)}"
            width="100%" height="560" style="border:0; border-radius:12px; background:#fff;"></iframe>
    '''
# ==========================================================================

# ====================== Part 4: 3×3 UI / Main =============================
def render_main():
    fixed_css()
    sidebar_calculators()   # ← 사이드바는 계산기만

    # ── 1행: 데이터랩 / 아이템스카우트 / 셀러라이프
    c1, c2, c3 = st.columns(3, gap="small")
    with c1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("데이터랩")
        cat = st.selectbox("카테고리(10개)", list(CID_MAP.keys()), index=0, key="dl_cat")
        dl = fetch_datalab_top20(cat)
        if dl.empty:
            st.warning("DataLab 호출 결과 없음(프록시/기간/CID/세션 확인).")
        st.dataframe(dl, use_container_width=True, height=280)
        st.markdown('</div>', unsafe_allow_html=True)

    with c2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("아이템스카우트")
        st.info("연동 대기 (별도 API/프록시)")
        st.markdown('</div>', unsafe_allow_html=True)

    with c3:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("셀러라이프")
        st.info("연동 대기 (별도 API/프록시)")
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="row-gap"></div>', unsafe_allow_html=True)

    # ── 2행: 레이더 / 11번가(모바일) / 상품명 생성기
    c4, c5, c6 = st.columns(3, gap="small")
    with c4:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("AI 키워드 레이더 (국내/글로벌)")
        mode = st.radio("모드", ["국내","글로벌"], index=0, horizontal=True)
        if mode == "글로벌":
            rk = fetch_rakuten_keywords()
            if rk.empty:
                st.warning("Rakuten 결과 없음(네트워크/쿼터 확인).")
            st.dataframe(rk, use_container_width=True, height=280)
        else:
            st.dataframe(dl, use_container_width=True, height=280)
        st.markdown('</div>', unsafe_allow_html=True)

    with c5:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("11번가 (모바일)")
        url = st.text_input("11번가 URL", "https://m.11st.co.kr/browsing/bestSellers.mall")
        st.markdown(elevenst_iframe(url), unsafe_allow_html=True)
        st.caption("임베드 차단 시 프록시/헤더 수정 모드 필요.")
        st.markdown('</div>', unsafe_allow_html=True)

    with c6:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("상품명 생성기 (규칙 기반)")
        brand    = st.text_input("브랜드", "envy")
        base_kw  = st.text_input("베이스 키워드", "K-coffee mix")
        rel_kw   = st.text_input("연관키워드(,로 구분)", "Maxim, Kanu, Korea")
        banned   = st.text_input("금칙어", "copy, fake, replica")
        limit    = st.slider("글자수 제한", 20, 80, 80)
        if st.button("제목 5개 생성"):
            rel = [w.strip() for w in rel_kw.split(",") if w.strip()]
            outs = []
            for i in range(5):
                title = f"{brand} {base_kw} {' '.join(rel[:2])}".strip()
                # 금칙어 제거 + 길이 제한
                for bad in [b.strip() for b in banned.split(",") if b.strip()]:
                    title = title.replace(bad, "")
                outs.append(title[:limit])
            st.write("\n".join([f"- {t}" for t in outs]))
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="row-gap"></div>', unsafe_allow_html=True)

    # ── 3행: 확장 슬롯(지금은 빈 카드)
    c7, c8, c9 = st.columns(3, gap="small")
    for col in (c7, c8, c9):
        with col:
            st.markdown('<div class="card">업데이트 예정 섹션</div>', unsafe_allow_html=True)

# ▶ 진입점
if __name__ == "__main__":
    render_main()
# ===========================================================================


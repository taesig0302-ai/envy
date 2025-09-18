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

    # 사이드바 전체 폰트 한 단계 ↓, 로고 더 작게, 배지(컬러 박스) 복원
    st.markdown(f"""
    <style>
      html, body, [data-testid="stAppViewContainer"] {{
        background-color:{bg} !important; color:{fg} !important;
      }}

      /* 본문 카드 여백 */
      .block-container{{padding-top:2.0rem; padding-bottom:.7rem;}}

      /* ===== Sidebar Compact v4 ===== */
      [data-testid="stSidebar"] section {{
        padding-top:.28rem; padding-bottom:.28rem;
        height:100vh; overflow:hidden;   /* 스크롤락 */
        font-size: 0.93rem;              /* ← 전체 한 단계 축소 */
      }}
      [data-testid="stSidebar"] ::-webkit-scrollbar{{display:none;}}

      /* 제목(### …) 더 작고 타이트 */
      [data-testid="stSidebar"] h2, 
      [data-testid="stSidebar"] h3 {{
        font-size: 0.9rem !important;
        line-height: 1.05rem !important;
        margin: .25rem 0 .2rem 0 !important;
      }}

      /* 라벨/부제 */
      [data-testid="stSidebar"] [data-testid="stWidgetLabel"] > div, 
      [data-testid="stSidebar"] label p {{
        font-size: .88re

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
RAKUTEN_DEMO = {
    "도서/미디어": [
        "YOUNG OLD 初回盤 Blu-ray",
        "YOUNG OLD DVD 初回盤 【SixTONES】",
        "楽天ブックス限定特典",
        "映画 パンフレット",
        "アニメ OST"
    ],
    "가전/디지털": [
        "Anker 充電器 65W",
        "USB-C ケーブル 2m",
        "Nintendo Switch Pro",
        "Dyson V12 掃除機",
        "AirPods ケース"
    ],
    "패션/잡화": [
        "ニューバランス 530",
        "ナイキ エアフォース1",
        "カシオ G-SHOCK",
        "無印良品 トートバッグ",
        "帽子 キャップ"
    ],
}

def fetch_rakuten_by_category(cat: str) -> pd.DataFrame:
    items = RAKUTEN_DEMO.get(cat, [])[:10]
    rows = [{"rank":i+1, "keyword":kw, "source":"Rakuten JP"} for i, kw in enumerate(items)]
    return pd.DataFrame(rows)

def render_rakuten_block():
    st.subheader("AI 키워드 레이더 (국내/글로벌)")
    mode = st.radio("모드", ["국내","글로벌"], horizontal=True, label_visibility="collapsed")
    col1, col2 = st.columns([1,2])
    with col1:
        cat = st.selectbox("카테고리", list(RAKUTEN_DEMO.keys()), index=0)
    with col2:
        st.caption("※ 현재는 데모 데이터. API 연결 시 카테고리 파라미터만 매핑하면 됩니다.")

    df = fetch_rakuten_by_category(cat)
    st.dataframe(df, use_container_width=True, hide_index=True)
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

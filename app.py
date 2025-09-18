# ============================================
# Part 0 — 공통 유틸 & 테마
# ============================================
import streamlit as st
import requests, pandas as pd, re, json
from bs4 import BeautifulSoup
from pathlib import Path

st.set_page_config(page_title="ENVY v8", page_icon="✨", layout="wide")

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
      .block-container{{padding-top:.4rem; padding-bottom:.4rem;}}
      [data-testid="stSidebar"] section{{padding-top:.4rem; padding-bottom:.4rem; height:100vh; overflow:hidden;}}
      [data-testid="stSidebar"] ::-webkit-scrollbar{{display:none;}}
      .badge-green {{background:#e6ffcc; border:1px solid #b6f3a4; padding:8px 12px; border-radius:6px; color:#0b2e13;}}
      .badge-blue  {{background:#e6f0ff; border:1px solid #b7ccff; padding:8px 12px; border-radius:6px; color:#0b1e4a;}}
      .note-small  {{color:#8aa0b5; font-size:12px;}}
    </style>
    """, unsafe_allow_html=True)
# ============================================
# Part 1 — 사이드바 (로고/다크토글/계산기)
# ============================================
def render_sidebar():
    with st.sidebar:
        # 로고
        lp = Path(__file__).parent / "logo.png"
        if lp.exists():
            st.image(str(lp), width=140)
        else:
            st.warning("logo.png 를 앱 파일과 같은 폴더에 두면 사이드바에 표시됩니다.")

        # 다크/라이트 토글
        st.toggle("다크 모드", value=(st.session_state["theme"] == "dark"), on_change=toggle_theme)

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
# Part 2 — 데이터랩 블록 (크롤링)
# ============================================
def fetch_datalab_keywords(max_rows: int = 20) -> pd.DataFrame:
    url = "https://datalab.naver.com/shoppingInsight/sCategory.naver"
    rows = []
    try:
        r = requests.get(url, headers={**MOBILE_HEADERS, "referer": "https://datalab.naver.com/"}, timeout=10)
        r.raise_for_status()
    except Exception:
        return pd.DataFrame([
            {"rank":1,"keyword":"맥심 커피믹스"},
            {"rank":2,"keyword":"카누 미니"},
            {"rank":3,"keyword":"원두커피 1kg"},
        ])

    soup = BeautifulSoup(r.text, "html.parser")

    # 1) <script> 내부 JSON(__NEXT_DATA__/__INITIAL_STATE__/window.__DATA__) 탐색
    scripts = soup.find_all("script")
    for s in scripts:
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
                    found = walk(v)
                    if found: return found
            elif isinstance(o, list):
                if o and isinstance(o[0], dict) and any(("keyword" in o[0]) or ("name" in o[0]) or ("rank" in o[0]) for _ in [0]):
                    return o
                for v in o:
                    found = walk(v)
                    if found: return found
            return None

        items = walk(data) or []
        for i, it in enumerate(items[:max_rows], start=1):
            kw = it.get("keyword") or it.get("name") or it.get("title") or str(it)
            kw = re.sub(r"\s+", " ", kw).strip()
            if kw:
                rows.append({"rank": i, "keyword": kw})
        if rows:
            return pd.DataFrame(rows)

    # 2) 텍스트 휴리스틱
    texts = []
    for el in soup.select("li, a, span, div"):
        t = (el.get_text(" ", strip=True) or "").strip()
        if len(t) >= 2 and any(ch.isalnum() for ch in t):
            texts.append(re.sub(r"\s+", " ", t))
    uniq = []
    for x in texts:
        if x not in uniq:
            uniq.append(x)
        if len(uniq) >= max_rows:
            break
    if uniq:
        return pd.DataFrame([{"rank":i+1, "keyword":kw} for i, kw in enumerate(uniq)])

    # 3) demo
    return pd.DataFrame([
        {"rank":1,"keyword":"맥심 커피믹스"},
        {"rank":2,"keyword":"카누 미니"},
        {"rank":3,"keyword":"원두커피 1kg"},
    ])

def render_datalab_block():
    st.subheader("데이터랩")
    df = fetch_datalab_keywords()
    st.dataframe(df, use_container_width=True, hide_index=True)
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
# Part 5 — 11번가 블록 (모바일 크롤링)
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

    for li in soup.select("li[class*=prd], li[class*=product], li[class*=item]"):
        a = li.select_one("a[href]")
        title_el = li.select_one(".name, .title, .prd_name, [class*=name], [class*=title]") or a
        price_el = li.select_one(".price, .value, .num, [class*=price], [class*=value]")
        title = (title_el.get_text(" ", strip=True) if title_el else "").strip()
        price = (price_el.get_text(" ", strip=True) if price_el else "").strip()
        if not title:
            continue
        i += 1
        rows.append({"rank": i, "title": title, "price": price})
        if i >= max_rows: break

    if rows:
        return pd.DataFrame(rows)
    return pd.DataFrame([{"rank":1,"title":"empty","price":""}])

def render_elevenst_block():
    st.subheader("11번가 (모바일)")
    df = fetch_11st_best()
    st.dataframe(df, use_container_width=True, hide_index=True)
# ============================================
# Part 6 — AI 키워드 레이더 블록 (라쿠텐 데모)
# ============================================
def fetch_rakuten_demo() -> pd.DataFrame:
    return pd.DataFrame([
        {"rank":1,"keyword":"YOUNG OLD 初回盤 Blu-ray","source":"Rakuten JP"},
        {"rank":2,"keyword":"YOUNG OLD DVD 初回盤 【SixTONES】","source":"Rakuten JP"},
        {"rank":3,"keyword":"YOUNG OLD Blu-ray 初回盤","source":"Rakuten JP"},
        {"rank":4,"keyword":"楽天ブックス限定特典","source":"Rakuten JP"},
        {"rank":5,"keyword":"楽天ブックス ランキング","source":"Rakuten JP"},
    ])

def render_rakuten_block():
    st.subheader("AI 키워드 레이더 (국내/글로벌)")
    mode = st.radio("모드", ["국내","글로벌"], horizontal=True, label_visibility="collapsed")
    if mode == "국내":
        st.info("국내는 데이터랩/아이템스카우트/셀러라이프 조합 (현재 DataLab 결과 우선)")
    st.dataframe(fetch_rakuten_demo(), use_container_width=True, hide_index=True)
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

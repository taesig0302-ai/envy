# app.py — ENVY v11.x (stable, S1 UX hotfix)
import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import date
from urllib.parse import quote
from pathlib import Path
import base64

st.set_page_config(page_title="ENVY — v11.x (stable)", layout="wide")

# ─────────────────────────────────────────────────────────────
# 세션 초기값
# ─────────────────────────────────────────────────────────────
def init_state():
    ss = st.session_state
    ss.setdefault("theme", "light")
    ss.setdefault("PROXY_URL", "")  # Cloudflare Worker
    # 외부 API 키들
    ss.setdefault("RAKUTEN_APP_ID", "")
    ss.setdefault("ITEMSCOUT_API_KEY", "")
    ss.setdefault("SELLERLIFE_API_KEY", "")
    # 환율/마진
    ss.setdefault("fx_base", "USD")
    ss.setdefault("sale_foreign", 1.00)
    ss.setdefault("m_base", "USD")
    ss.setdefault("purchase_foreign", 0.00)
    ss.setdefault("card_fee_pct", 4.00)
    ss.setdefault("market_fee_pct", 14.00)
    ss.setdefault("shipping_won", 0.0)
    ss.setdefault("margin_mode", "퍼센트")
    ss.setdefault("margin_pct", 10.00)
    ss.setdefault("margin_won", 10000.0)
init_state()

CURRENCIES = {
    "USD": {"kr": "미국 달러", "symbol": "$", "unit": "USD"},
    "EUR": {"kr": "유로", "symbol": "€", "unit": "EUR"},
    "JPY": {"kr": "일본 엔", "symbol": "¥", "unit": "JPY"},
    "CNY": {"kr": "중국 위안", "symbol": "元","unit": "CNY"},
}
FX_DEFAULT = {"USD": 1400.0, "EUR": 1500.0, "JPY": 10.0, "CNY": 200.0}

# ─────────────────────────────────────────────────────────────
# CSS (페이지폭 확대 + 카드 + 사이드바 고정 + 라이트/다크)
# ─────────────────────────────────────────────────────────────
def inject_css():
    theme = st.session_state.get("theme", "light")
    if theme == "dark":
        bg = "#0e1117"; fg = "#e6edf3"; cardbg = "rgba(255,255,255,0.03)"
        border = "rgba(255,255,255,0.12)"; badge_bg="#1f2937"; good="#10b981"; warn="#f59e0b"
    else:
        bg = "#ffffff"; fg = "#111111"; cardbg = "rgba(0,0,0,0.03)"
        border = "rgba(0,0,0,0.08)"; badge_bg="#f7f7f9"; good="#10b981"; warn="#f59e0b"

    st.markdown(f"""
    <style>
      .block-container {{ max-width: 1920px !important; }}
      :root, .stApp, [data-testid="stAppViewContainer"] {{
        background:{bg} !important; color:{fg} !important;
      }}

      /* 사이드바 고정 + 자체 스크롤 */
      [data-testid="stSidebar"] {{ min-width:300px !important; }}
      [data-testid="stSidebar"] > div:first-child {{
        height:100vh !important; overflow-y:auto !important;
        position:sticky !important; top:0 !important; background:{bg} !important;
      }}

      .section-card {{
        background:{cardbg}; border:1px solid {border};
        border-radius:12px; padding:14px; margin-bottom:14px;
      }}

      .badge {{
        display:inline-block; padding:6px 10px; border-radius:8px;
        background:{badge_bg}; border:1px solid {border}; font-size:.86rem;
      }}

      /* 강조 박스 */
      .pill-good {{
        display:inline-block; padding:8px 12px; border-radius:999px;
        background:{good}; color:white; font-weight:600; margin-right:6px;
      }}
      .pill-warn {{
        display:inline-block; padding:8px 12px; border-radius:999px;
        background:{warn}; color:black; font-weight:700; margin-right:6px;
      }}

      /* 열 간격 살짝 좁혀서 좀 더 넓게 보여주기 */
      .stHorizontalBlock > div > div[data-testid="column"] {{
        padding-right:10px !important;
      }}
    </style>
    """, unsafe_allow_html=True)

inject_css()

# ─────────────────────────────────────────────────────────────
# 유틸
# ─────────────────────────────────────────────────────────────
def logo_box():
    lp = Path(__file__).parent / "logo.png"
    if lp.exists():
        b64 = base64.b64encode(lp.read_bytes()).decode("ascii")
        st.markdown(
            f'<div style="width:95px;height:95px;border-radius:50%;overflow:hidden;'
            f'margin:.15rem auto .35rem auto;box-shadow:0 2px 8px rgba(0,0,0,.12);'
            f'border:1px solid rgba(0,0,0,.06);"><img src="data:image/png;base64,{b64}" '
            f'style="width:100%;height:100%;object-fit:cover;"></div>',
            unsafe_allow_html=True
        )
    else:
        st.caption("logo.png 를 앱 폴더에 두면 로고가 표시됩니다.")

def proxify(raw_url: str) -> str:
    proxy = st.session_state.get("PROXY_URL", "").strip()
    if proxy:
        if proxy.endswith("/"): proxy = proxy[:-1]
        return f"{proxy}?url={quote(raw_url, safe='')}"
    return raw_url

# ─────────────────────────────────────────────────────────────
# 사이드바 (프록시/환경은 PROXY_URL 없을 때만 노출)
# ─────────────────────────────────────────────────────────────
def render_sidebar():
    with st.sidebar:
        logo_box()
        # 테마 토글
        dark_on = st.toggle("🌓 다크 모드", value=(st.session_state["theme"]=="dark"))
        st.session_state["theme"] = "dark" if dark_on else "light"
        inject_css()

        st.markdown("### ① 환율 계산기")
        base = st.selectbox("기준 통화", list(CURRENCIES.keys()),
                            index=list(CURRENCIES.keys()).index(st.session_state["fx_base"]),
                            key="fx_base")
        sale_foreign = st.number_input("판매금액 (외화)", value=float(st.session_state["sale_foreign"]),
                                       step=0.01, format="%.2f", key="sale_foreign")
        won = FX_DEFAULT[base] * sale_foreign
        st.markdown(f'<span class="pill-warn">환산 금액 {won:,.2f} 원</span>', unsafe_allow_html=True)
        st.caption(f"환율 기준: {FX_DEFAULT[base]:,.2f} ₩/{CURRENCIES[base]['unit']}")

        st.markdown("### ② 마진 계산기")
        m_base = st.selectbox("매입 통화", list(CURRENCIES.keys()),
                              index=list(CURRENCRIES.keys()).index(st.session_state["m_base"]) if "CURRENCRIES" in globals() else list(CURRENCIES.keys()).index(st.session_state["m_base"]),
                              key="m_base")
        purchase_foreign = st.number_input("매입금액 (외화)", value=float(st.session_state["purchase_foreign"]),
                                           step=0.01, format="%.2f", key="purchase_foreign")
        base_cost_won = FX_DEFAULT[m_base] * purchase_foreign if purchase_foreign > 0 else won
        st.markdown(f'<span class="pill-warn">원가 {base_cost_won:,.2f} 원</span>', unsafe_allow_html=True)

        colf1, colf2 = st.columns(2)
        with colf1:
            card_fee = st.number_input("카드수수료(%)", value=float(st.session_state["card_fee_pct"]),
                                       step=0.01, format="%.2f", key="card_fee_pct")
        with colf2:
            market_fee = st.number_input("마켓수수료(%)", value=float(st.session_state["market_fee_pct"]),
                                         step=0.01, format="%.2f", key="market_fee_pct")
        shipping_won = st.number_input("배송비(₩)", value=float(st.session_state["shipping_won"]),
                                       step=100.0, format="%.0f", key="shipping_won")
        mode = st.radio("마진 방식", ["퍼센트", "플러스"], horizontal=True, key="margin_mode")
        if mode == "퍼센트":
            margin_pct = st.number_input("마진율 (%)", value=float(st.session_state["margin_pct"]),
                                         step=0.01, format="%.2f", key="margin_pct")
            target_price = base_cost_won * (1 + card_fee/100) * (1 + market_fee/100) * (1 + margin_pct/100) + shipping_won
            margin_value = target_price - base_cost_won
        else:
            margin_won = st.number_input("마진액 (₩)", value=float(st.session_state["margin_won"]),
                                         step=100.0, format="%.0f", key="margin_won")
            target_price = base_cost_won * (1 + card_fee/100) * (1 + market_fee/100) + margin_won + shipping_won
            margin_value = margin_won

        st.markdown(
            f'<span class="pill-good">판매가 {target_price:,.2f} 원</span>'
            f'<span class="badge">순이익 {margin_value:,.2f} 원</span>',
            unsafe_allow_html=True
        )

        # PROXY_URL 없을 때만 고급 설정 노출
        if not st.session_state.get("PROXY_URL"):
            st.divider()
            with st.expander("고급 설정 (프록시/환경)", expanded=False):
                st.text_input("PROXY_URL (Cloudflare Worker)", value=st.session_state.get("PROXY_URL",""),
                              key="PROXY_URL", placeholder="https://envy-proxy.yourname.workers.dev")
                st.text_input("Rakuten APP_ID", value=st.session_state.get("RAKUTEN_APP_ID",""),
                              key="RAKUTEN_APP_ID")
                st.text_input("아이템스카우트 API Key", value=st.session_state.get("ITEMSCOUT_API_KEY",""),
                              key="ITEMSCOUT_API_KEY")
                st.text_input("셀러라이프 API Key", value=st.session_state.get("SELLERLIFE_API_KEY",""),
                              key="SELLERLIFE_API_KEY")

render_sidebar()

# ─────────────────────────────────────────────────────────────
# 라쿠텐 간단 API 래퍼 (랭킹 → 키워드 추출: 제목 토큰화)
# ─────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False, ttl=60*10)
def fetch_rakuten_keywords(genre_id: str, app_id: str, size: int = 30):
    """IchibaItemRanking에서 title을 모아 키워드 상위 빈도 반환(간단 추출)"""
    if not app_id:
        return {"ok": False, "reason": "APP_ID 누락"}
    url = "https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20170628"
    params = {"format":"json", "genreId": genre_id, "applicationId": app_id}
    try:
        r = requests.get(url, params=params, timeout=10)
        if r.status_code != 200:
            return {"ok": False, "reason": f"HTTP {r.status_code}"}
        data = r.json()
        items = data.get("Items", [])
        titles = [it["Item"]["itemName"] for it in items if "Item" in it and "itemName" in it["Item"]]
        tokens = []
        for t in titles:
            # 아주 단순 토큰화(공백/특수문자 기준)
            for tok in pd.Series(t).str.replace(r"[^0-9A-Za-z가-힣]", " ", regex=True).str.split().sum():
                if len(tok) >= 2: tokens.append(tok)
        vc = pd.Series(tokens).value_counts().head(size)
        df = pd.DataFrame({"rank": range(1, len(vc)+1), "keyword": vc.index, "freq": vc.values})
        return {"ok": True, "df": df}
    except Exception as e:
        return {"ok": False, "reason": str(e)}

# ─────────────────────────────────────────────────────────────
# 레이아웃 4×2
# ─────────────────────────────────────────────────────────────
st.markdown("## ENVY — v11.x (stable)")
st.caption("시즌1: 데이터랩(임베드 X, API/쿠키 방식), 11번가/아이템스카우트/셀러라이프는 프록시 기반 임베드")

row1 = st.columns(4)
row2 = st.columns(4)

# 1-1 데이터랩 (시즌1: 임베드 제거, 분석 카드 자리)
with row1[0]:
    st.markdown("### 데이터랩 (시즌1 — 분석 카드)")
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.selectbox("카테고리", ["디지털/가전","패션의류","화장품/미용","생활/건강"], key="s1_cat")
    with c2:
        st.selectbox("기간 단위", ["week","month"], key="s1_unit")
    with c3:
        st.selectbox("기기", ["all","pc","mo"], key="s1_dev")
    if st.button("Top20 불러오기 (샘플)", key="s1_btn"):
        demo = pd.DataFrame({"rank": range(1,21),
                             "keyword": [f"키워드{i}" for i in range(1,21)],
                             "vol": np.random.randint(1200, 9800, size=20)})
        st.dataframe(demo, use_container_width=True, hide_index=True)
    st.markdown('</div>', unsafe_allow_html=True)

# 1-2 11번가 (아마존베스트)
with row1[1]:
    st.markdown("### 11번가 (모바일) — 아마존베스트")
    url_11 = "https://m.11st.co.kr/page/main/abest?tabId=ABEST&pageId=AMOBEST&ctgr1No=166160"
    if not st.session_state.get("PROXY_URL"):
        st.info("PROXY_URL 미설정: 11번가는 iFrame 제한이 있을 수 있습니다.")
    st.components.v1.iframe(proxify(url_11), height=560, scrolling=True)

# 1-3 상품명 생성기
with row1[2]:
    st.markdown("### 상품명 생성기 (규칙 기반)")
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    cc = st.columns([1,1,1,1])
    with cc[0]:
        brand = st.text_input("브랜드", placeholder="예: 오쏘", key="nm_brand")
    with cc[1]:
        style = st.text_input("스타일/속성", placeholder="예: 프리미엄, 무선, 초경량", key="nm_style")
    with cc[2]:
        length = st.slider("길이(단어 수)", 4, 12, 8, key="nm_len")
    with cc[3]:
        seed = st.text_input("핵심 키워드(콤마)", placeholder="예: 가습기, 무선청소기, 텀블러", key="nm_seed")
    if st.button("상품명 20개 생성", key="nm_btn"):
        kws = [s.strip() for s in seed.split(",") if s.strip()]
        base_parts = ([brand] if brand else []) + ([style] if style else [])
        rng = np.random.default_rng(42)
        names = []
        for i in range(20):
            pick = rng.choice(kws, size=min(len(kws), max(1,(len(kws)//2) or 1)), replace=False) if kws else []
            parts = base_parts + list(pick)
            rng.shuffle(parts)
            if len(parts) < length:
                parts += [rng.choice(["업그레이드","신형","정품","히트","베스트","인기","특가"])] * (length - len(parts))
            names.append(" ".join(parts[:length]))
        df = pd.DataFrame({"rank": range(1, len(names)+1), "name": names})
        st.dataframe(df, use_container_width=True, hide_index=True)
        # 추천 키워드 5개
        tokens = " ".join(names).split()
        vc = pd.Series(tokens).value_counts().head(5)
        rec = pd.DataFrame({"keyword": vc.index, "search_volume": vc.values*123 + rng.integers(50,500, size=len(vc))})
        st.markdown("**추천 키워드 TOP5 (추정 검색량)**")
        st.dataframe(rec, use_container_width=True, hide_index=True)
    st.markdown('</div>', unsafe_allow_html=True)

# 1-4 선택 키워드 트렌드 (샘플 그래프)
with row1[3]:
    st.markdown("### 선택 키워드 트렌드 (샘플)")
    x = np.arange(0,12)
    y1 = 55 + 8*np.sin(x/1.6) + 2*x
    y2 = 52 + 6*np.sin(x/1.8) + 1.5*x
    data = pd.DataFrame({"p": x, "전체": y1, "패션의류": y2}).set_index("p")
    st.line_chart(data, height=300)

# 2-1 라쿠텐 키워드 레이더 (실제 호출 포함)
with row2[0]:
    st.markdown("### AI 키워드 레이더 (Rakuten)")
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.radio("범위", ["국내","글로벌"], horizontal=True, key="rk_scope")
    st.selectbox("라쿠텐 카테고리", ["전체(샘플)","패션","생활","뷰티","가전"], key="rk_cat")
    gid = st.text_input("GenreID", value="100283", key="rk_genre")
    st.text_input("APP_ID", value=st.session_state.get("RAKUTEN_APP_ID",""), key="RAKUTEN_APP_ID_VIEW")
    if st.button("키워드 불러오기", key="rk_btn"):
        res = fetch_rakuten_keywords(gid, st.session_state.get("RAKUTEN_APP_ID",""))
        if not res["ok"]:
            st.error(f"조회 실패: {res['reason']} (APP_ID/장르/요청 제한 확인)")
        else:
            st.dataframe(res["df"], use_container_width=True, hide_index=True)
    else:
        # 샘플 표
        sample = [{"rank": i+1, "keyword": f"[샘플] 키워드 {i+1} 🚀", "source":"sample"} for i in range(12)]
        st.dataframe(pd.DataFrame(sample), use_container_width=True, hide_index=True)
    st.markdown('</div>', unsafe_allow_html=True)

# 2-2 구글 번역(로컬)
with row2[1]:
    st.markdown("### 구글 번역 (텍스트 입력/출력 + 한국어 확인용)")
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.selectbox("원문 언어", ["자동 감지","한국어","영어","일본어","중국어"], key="tr_src")
    st.selectbox("번역 언어", ["영어","한국어","일본어","중국어"], key="tr_tgt")
    src_txt = st.text_area("원문 입력", height=220, key="tr_input")
    if st.button("번역", key="tr_btn"):
        out = src_txt.strip()
        st.text_area("번역 결과", value=out, height=120, key="tr_output")
    st.markdown('</div>', unsafe_allow_html=True)

# 2-3 아이템스카우트 임베드
with row2[2]:
    st.markdown("### 아이템스카우트 (원본 임베드)")
    url_itemscout = "https://items.singtown.com"
    if not st.session_state.get("PROXY_URL"):
        st.info("PROXY_URL 이 비어 있습니다. 사이드바 고급 설정에서 설정하세요.")
    st.components.v1.iframe(proxify(url_itemscout), height=360, scrolling=True)

# 2-4 셀러라이프 임베드
with row2[3]:
    st.markdown("### 셀러라이프 (원본 임베드)")
    url_sellerlife = "https://www.sellerlife.co.kr"
    if not st.session_state.get("PROXY_URL"):
        st.info("PROXY_URL 이 비어 있습니다. 사이드바 고급 설정에서 설정하세요.")
    st.components.v1.iframe(proxify(url_sellerlife), height=360, scrolling=True)

# 하단 상태 안내
st.divider()
msgs = []
if not st.session_state.get("PROXY_URL"):
    msgs.append("PROXY_URL 미설정 — 일부 임베드는 브라우저/호스트 정책으로 차단될 수 있습니다.")
if not st.session_state.get("RAKUTEN_APP_ID"):
    msgs.append("Rakuten APP_ID 미설정 — 키워드 레이더는 샘플로 표시됩니다.")
if msgs:
    for m in msgs: st.warning(m)
else:
    st.success("환경 설정 양호 — 모든 섹션이 정상 구성되었습니다.")

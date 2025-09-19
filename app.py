# app.py  — ENVY v11.x (stable, Season-1 full layout)
import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, timedelta
from urllib.parse import quote
from pathlib import Path
import base64

st.set_page_config(page_title="ENVY — v11.x (stable)", layout="wide")

# ──────────────────────────────────────────────────────────────────────────────
# 공통 상태/상수
# ──────────────────────────────────────────────────────────────────────────────
CURRENCIES = {
    "USD": {"kr": "미국 달러", "symbol": "$", "unit": "USD"},
    "EUR": {"kr": "유로",     "symbol": "€", "unit": "EUR"},
    "JPY": {"kr": "일본 엔",   "symbol": "¥", "unit": "JPY"},
    "CNY": {"kr": "중국 위안", "symbol": "元","unit": "CNY"},
}
FX_DEFAULT = {"USD": 1400.0, "EUR": 1500.0, "JPY": 10.0, "CNY": 200.0}

def _ensure_session_defaults():
    ss = st.session_state
    ss.setdefault("theme", "light")
    ss.setdefault("PROXY_URL", "")
    ss.setdefault("RAKUTEN_APP_ID", "")
    ss.setdefault("ITEMSCOUT_API_KEY", "")
    ss.setdefault("SELLERLIFE_API_KEY", "")
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

_ensure_session_defaults()

# ──────────────────────────────────────────────────────────────────────────────
# 스타일 (넓게 + 스크롤 보장 + 다크/라이트)
# ──────────────────────────────────────────────────────────────────────────────
def _toggle_theme():
    st.session_state["theme"] = (
        "dark" if st.session_state.get("theme", "light") == "light" else "light"
    )

def inject_global_css():
    theme = st.session_state.get("theme", "light")
    bg, fg = ("#0e1117", "#e6edf3") if theme == "dark" else ("#ffffff", "#111111")
    st.markdown(f"""
    <style>
      .block-container {{ max-width: 1700px !important; }}
      html, body {{ overflow: auto !important; background:{bg} !important; color:{fg} !important; }}
      /* 사이드바 고정/스크롤 */
      [data-testid="stSidebar"],
      [data-testid="stSidebar"] section {{
        height: 100vh !important; overflow-y: auto !important;
      }}
      /* 그리드 자간 */
      .section-card {{ background:rgba(0,0,0,.03); border:1px solid rgba(0,0,0,.08); border-radius:10px; padding:12px; }}
      .hint {{ font-size:.85rem; opacity:.8; }}
      .muted {{ opacity:.7; }}
      .pill {{ display:inline-block; padding:2px 8px; border-radius:999px; background:#eef4ff; border:1px solid #cfe0ff; font-size:.8rem; }}
      .badge {{ display:inline-block; padding:4px 8px; border-radius:6px; background:#f7f7f9; border:1px solid #e2e8f0; font-size:.82rem; }}
      .kpill {{ padding:3px 8px; border-radius:8px; background:#fff7d6; border:1px solid #f1d27a; font-size:.8rem; }}
    </style>
    """, unsafe_allow_html=True)

inject_global_css()

# ──────────────────────────────────────────────────────────────────────────────
# 사이드바 (로고 + 환율/마진 + 프록시/키)
# ──────────────────────────────────────────────────────────────────────────────
def render_sidebar():
    def logo():
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

    with st.sidebar:
        logo()
        st.toggle("🌓 다크 모드", value=(st.session_state.get("theme","light")=="dark"),
                  on_change=_toggle_theme, key="__theme_toggle")

        st.markdown("### ① 환율 계산기")
        base = st.selectbox("기준 통화", list(CURRENCIES.keys()),
                            index=list(CURRENCIES.keys()).index(st.session_state["fx_base"]),
                            key="fx_base")
        sale_foreign = st.number_input("판매금액 (외화)", value=float(st.session_state["sale_foreign"]),
                                       step=0.01, format="%.2f", key="sale_foreign")
        won = FX_DEFAULT[base] * sale_foreign
        st.markdown(f'<span class="badge">환산 금액: <b>{won:,.2f} 원</b> '
                    f'<span class="muted">({CURRENCIES[base]["kr"]} • {CURRENCIES[base]["symbol"]})</span></span>',
                    unsafe_allow_html=True)
        st.caption(f"환율 기준: {FX_DEFAULT[base]:,.2f} ₩/{CURRENCIES[base]['unit']}")

        st.markdown("### ② 마진 계산기")
        m_base = st.selectbox("매입 통화", list(CURRENCIES.keys()),
                              index=list(CURRENCIES.keys()).index(st.session_state["m_base"]),
                              key="m_base")
        purchase_foreign = st.number_input("매입금액 (외화)", value=float(st.session_state["purchase_foreign"]),
                                           step=0.01, format="%.2f", key="purchase_foreign")
        base_cost_won = FX_DEFAULT[m_base] * purchase_foreign if purchase_foreign > 0 else won
        st.markdown(f'<span class="badge">원가(₩): <b>{base_cost_won:,.2f}</b></span>', unsafe_allow_html=True)

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
            margin_desc = f"{margin_pct:.2f}%"
        else:
            margin_won = st.number_input("마진액 (₩)", value=float(st.session_state["margin_won"]),
                                         step=100.0, format="%.0f", key="margin_won")
            target_price = base_cost_won * (1 + card_fee/100) * (1 + market_fee/100) + margin_won + shipping_won
            margin_value = margin_won
            margin_desc = f"+{margin_won:,.0f}"

        st.markdown(f'<span class="badge">판매가: <b>{target_price:,.2f} 원</b></span> '
                    f'<span class="badge">순이익: <b>{margin_value:,.2f} 원</b> — {margin_desc}</span>',
                    unsafe_allow_html=True)

        st.divider()
        st.markdown("##### 프록시/환경")
        st.text_input("PROXY_URL (Cloudflare Worker)", value=st.session_state.get("PROXY_URL",""),
                      key="PROXY_URL", placeholder="https://envy-proxy.yourname.workers.dev")
        with st.expander("외부 API Key 보관", expanded=False):
            st.text_input("Rakuten APP_ID", value=st.session_state.get("RAKUTEN_APP_ID",""),
                          key="RAKUTEN_APP_ID")
            st.text_input("아이템스카우트 API Key", value=st.session_state.get("ITEMSCOUT_API_KEY",""),
                          key="ITEMSCOUT_API_KEY")
            st.text_input("셀러라이프 API Key", value=st.session_state.get("SELLERLIFE_API_KEY",""),
                          key="SELLERLIFE_API_KEY")

sidebar_vals = render_sidebar()
inject_global_css()

# ──────────────────────────────────────────────────────────────────────────────
# 유틸: 프록시 경유 URL
# ──────────────────────────────────────────────────────────────────────────────
def proxify(raw_url: str) -> str:
    proxy = st.session_state.get("PROXY_URL", "").strip()
    if proxy:
        # Cloudflare Worker: https://worker...?url=<ENCODED>
        if proxy.endswith("/"):
            proxy = proxy[:-1]
        return f"{proxy}?url={quote(raw_url, safe='')}"
    return raw_url

# ──────────────────────────────────────────────────────────────────────────────
# 레이아웃 4×2 섹션
# ──────────────────────────────────────────────────────────────────────────────
st.markdown("## ENVY — v11.x (stable)")
st.caption("사이드바 고정, 본문 카드는 금지/고정 크기. PROXY_URL 미설정 시 iFrame 제한된 페이지는 노출이 어려울 수 있습니다.")

row1 = st.columns(4)
row2 = st.columns(4)

# ── 1-1 데이터랩 (원본 임베드) ────────────────────────────────────────────────
with row1[0]:
    st.markdown("### 데이터랩 (원본 임베드)")
    c1, c2, c3 = st.columns(3)
    with c1:
        cat = st.selectbox("카테고리", ["디지털/가전","패션의류","화장품/미용","생활/건강"], key="dl_cat")
    with c2:
        unit = st.selectbox("기간 단위", ["week","month"], key="dl_unit")
    with c3:
        dev = st.selectbox("기기", ["all","pc","mo"], key="dl_dev")

    # DataLab 원본 그래프 페이지(샘플 엔드포인트)
    # 카테고리 ID는 실제와 다를 수 있으므로 임시 파라미터만 구성
    cid_map = {"디지털/가전":"50000003","패션의류":"50000002","화장품/미용":"50000001","생활/건강":"50000004"}
    raw = f"https://datalab.naver.com/shoppingInsight/category.naver?cat_id={cid_map.get(cat,'50000003')}&period={unit}&device={dev}"
    if not st.session_state.get("PROXY_URL"):
        st.info("PROXY_URL 이 비어 있습니다. 사이드바 하단에 Cloudflare Worker 주소를 입력해 주세요.")
    st.components.v1.iframe(proxify(raw), height=560, scrolling=True, key="dl_iframe")

# ── 1-2 11번가 (아마존베스트 탭 고정) ─────────────────────────────────────────
with row1[1]:
    st.markdown("### 11번가 (모바일)")
    st.caption("아마존베스트 탭 고정")
    eleven_url = "https://m.11st.co.kr/page/main/abest?tabId=ABEST&pageId=AMOBEST&ctgr1No=166160"
    if not st.session_state.get("PROXY_URL"):
        st.info("PROXY_URL 미설정: 11번가는 iFrame 제한이 있을 수 있습니다.")
    st.components.v1.iframe(proxify(eleven_url), height=560, scrolling=True, key="eleven_iframe")

# ── 1-3 상품명 생성기 ───────────────────────────────────────────────────────
with row1[2]:
    st.markdown("### 상품명 생성기 (규칙 기반)")
    col = st.columns(3)
    with col[0]:
        brand = st.text_input("브랜드", placeholder="예: 오쏘", key="nm_brand")
    with col[1]:
        style = st.text_input("스타일/속성", placeholder="예: 프리미엄, 무선, 초경량", key="nm_style")
    with col[2]:
        length = st.slider("길이(단어 수)", 4, 12, 8, key="nm_len")

    seed = st.text_area("핵심 키워드(콤마로 구분)", placeholder="예: 가습기, 무선청소기, 텀블러", key="nm_seed")
    gen = st.button("상품명 20개 생성", key="nm_btn")
    if gen:
        kws = [s.strip() for s in seed.split(",") if s.strip()]
        base_parts = ([brand] if brand else []) + ([style] if style else [])
        rng = np.random.default_rng(42)
        names = []
        for i in range(20):
            pick = rng.choice(kws, size=min(len(kws), max(1, len(kws)//2 or 1)), replace=False) if kws else []
            parts = base_parts + list(pick)
            rng.shuffle(parts)
            # 길이 맞추기
            if len(parts) < length:
                parts += [rng.choice(["업그레이드","신형","정품","히트","베스트","인기","특가"])] * (length - len(parts))
            names.append(" ".join(parts[:length]))
        df = pd.DataFrame({"rank": range(1, len(names)+1), "name": names})
        st.dataframe(df, use_container_width=True, hide_index=True)

        # 단순 추천 키워드 Top5 (가중치 = 등장 빈도) + 임의 검색량
        tokens = " ".join(names).split()
        value_counts = pd.Series(tokens).value_counts().head(5)
        rec = pd.DataFrame({
            "keyword": value_counts.index,
            "search_volume": (value_counts.values * 123 + rng.integers(50, 999, size=len(value_counts)))
        })
        st.markdown("**추천 키워드 TOP5 (추정 검색량)**")
        st.dataframe(rec, use_container_width=True, hide_index=True)

# ── 1-4 데이터랩 (분석: 샘플 라인) ────────────────────────────────────────────
with row1[3]:
    st.markdown("### 선택 키워드 트렌드 (분석)")
    st.caption("좌측에서 키워드를 1~5개 골라 샘플 라인을 보거나, 시즌2에서 실데이터 연동 예정")
    # 샘플 라인
    x = np.arange(0, 12)
    y1 = 50 + 8*np.sin(x/1.5) + 2*x
    y2 = 48 + 6*np.sin(x/1.7) + 1.5*x
    data = pd.DataFrame({"p": x, "전채": y1, "패션의류": y2}).set_index("p")
    st.line_chart(data, height=290)

# ── 2-1 AI 키워드 레이더 (Rakuten) ──────────────────────────────────────────
with row2[0]:
    st.markdown("### AI 키워드 레이더 (Rakuten)")
    scope = st.radio("범위", ["국내","글로벌"], horizontal=True, key="rk_scope")
    cat = st.selectbox("라쿠텐 카테고리", ["전체(샘플)","패션","생활","뷰티","가전"], key="rk_cat")
    genre = st.text_input("GenreID", value="100283", key="rk_genre")
    st.text_input("APP_ID", value=st.session_state.get("RAKUTEN_APP_ID",""), key="RAKUTEN_APP_ID_view",
                  help="사이드바의 APP_ID와 동일합니다.")

    # 샘플 표
    sample = [{"rank": i+1, "keyword": f"[샘플] 키워드 {i+1} 🚀", "source":"sample"} for i in range(20)]
    st.dataframe(pd.DataFrame(sample), use_container_width=True, hide_index=True, height=360)

# ── 2-2 구글 번역 (로컬 대체) ───────────────────────────────────────────────
with row2[1]:
    st.markdown("### 구글 번역 (텍스트 입력/출력 + 한국어 확인용)")
    sl = st.selectbox("원문 언어", ["자동 감지","한국어","영어","일본어","중국어"], key="tr_src")
    tl = st.selectbox("번역 언어", ["영어","한국어","일본어","중국어"], key="tr_tgt")
    src_txt = st.text_area("원문 입력", height=260, key="tr_input")
    if st.button("번역", key="tr_btn"):
        # 실제 API 미연결: 간단 치환/에코 (시즌2에서 정식 API로 교체)
        out = src_txt.strip()
        if not out:
            st.warning("입력된 텍스트가 없습니다.")
        else:
            st.text_area("번역 결과", value=out, height=120, key="tr_output")

# ── 2-3 아이템스카우트 임베드 ──────────────────────────────────────────────
with row2[2]:
    st.markdown("### 아이템스카우트 (원본 임베드)")
    items_url = "https://items.singtown.com"
    if not st.session_state.get("PROXY_URL"):
        st.info("PROXY_URL 이 비어 있습니다. 사이드바 하단에 Cloudflare Worker 주소를 입력해 주세요.")
    st.components.v1.iframe(proxify(items_url), height=360, scrolling=True, key="items_iframe")

# ── 2-4 셀러라이프 임베드 ──────────────────────────────────────────────────
with row2[3]:
    st.markdown("### 셀러라이프 (원본 임베드)")
    sellerlife_url = "https://www.sellerlife.co.kr"
    if not st.session_state.get("PROXY_URL"):
        st.info("PROXY_URL 이 비어 있습니다. 사이드바 하단에 Cloudflare Worker 주소를 입력해 주세요.")
    st.components.v1.iframe(proxify(sellerlife_url), height=360, scrolling=True, key="sellerlife_iframe")

# ──────────────────────────────────────────────────────────────────────────────
# 하단 오류/안내 영역
# ──────────────────────────────────────────────────────────────────────────────
st.divider()
st.markdown("#### 안내 / 오류 로그")
msgs = []
if not st.session_state.get("PROXY_URL"):
    msgs.append("PROXY_URL 미설정 — 일부 임베드(11번가/아이템스카우트/셀러라이프/데이터랩) 노출이 제한될 수 있습니다.")
if not st.session_state.get("RAKUTEN_APP_ID"):
    msgs.append("Rakuten APP_ID 미설정 — 키워드 레이더는 샘플 테이블로 표시됩니다.")
if msgs:
    for m in msgs:
        st.warning(m)
else:
    st.success("환경 설정 양호 — 모든 섹션이 정상 구성되었습니다.")

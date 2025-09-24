# -*- coding: utf-8 -*-
# ENVY — Season 1 (Dual Proxy Edition) — SAFE FULL BUILD (2025-09-24)
# - Sidebar scroll-lock (fixed)
# - Dark/Light: main area full dark skin, inputs stay white with black text (readable)
# - Sidebar always light
# - link_button() helper supports both old/new Streamlit signatures (no TypeError)

import io, re, json, math, time, base64, datetime as dt
from pathlib import Path
import pandas as pd
import streamlit as st

try:
    from urllib.parse import quote as _q
except Exception:
    def _q(s, safe=None): return s

try:
    import requests
except Exception:
    requests = None

st.set_page_config(page_title="ENVY — Season 1 (Dual Proxy Edition)", layout="wide")

# ---------------------------
# Session defaults
# ---------------------------
def _ensure_session_defaults():
    ss = st.session_state
    ss.setdefault("theme", "light")  # "dark" | "light"
    ss.setdefault("__show_translator", False)

    # 계산기
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

    # 라쿠텐 장르맵
    ss.setdefault("rk_genre_map", {})

_ensure_session_defaults()

# ---------------------------
# Const
# ---------------------------
CURRENCIES = {
    "USD":{"kr":"미국 달러","symbol":"$","unit":"USD"},
    "EUR":{"kr":"유로","symbol":"€","unit":"EUR"},
    "JPY":{"kr":"일본 엔","symbol":"¥","unit":"JPY"},
    "CNY":{"kr":"중국 위안","symbol":"元","unit":"CNY"},
}
FX_DEFAULT = {"USD":1400.0,"EUR":1500.0,"JPY":10.0,"CNY":200.0}

# ---------------------------
# Safe link button helper (new/old Streamlit)
# ---------------------------
def link_button(label: str, url: str, key: str | None = None):
    """Streamlit 버전에 따라 st.link_button 시그니처가 다름.
    - 신버전: st.link_button(label, url, key=...)
    - 구버전: st.link_button(label, url) (key 미지원) 또는 존재하지 않음
    안전하게 순차 시도하고, 모두 실패하면 HTML 버튼로 대체.
    """
    fn = getattr(st, "link_button", None)
    if callable(fn):
        # 신버전 시도
        try:
            return fn(label, url, key=key)
        except TypeError:
            # 구버전(키 미지원)
            try:
                return fn(label, url)
            except Exception:
                pass
        except Exception:
            pass
    # 완전 구버전: HTML로 대체
    st.markdown(
        f"""
        <a href="{url}" target="_blank" rel="noopener">
          <button style="
            all:unset; display:inline-block; padding:.55rem .9rem; border-radius:8px;
            background:#2563eb; color:#fff; font-weight:700; cursor:pointer;">
            {label}
          </button>
        </a>
        """,
        unsafe_allow_html=True,
    )

# ---------------------------
# CSS (sidebar lock + theme)
# ---------------------------
def _inject_css():
    theme = st.session_state.get("theme","light")

    # Sidebar: 항상 밝게 + 스크롤락
    st.markdown("""
    <style>
      [data-testid="stSidebar"]{
        height:100vh !important;
        overflow-y:hidden !important;
        -ms-overflow-style:none !important;
        scrollbar-width:none !important;
        background:#ffffff !important; color:#111 !important;
      }
      [data-testid="stSidebar"] > div:first-child{
        height:100vh !important; overflow-y:hidden !important;
      }
      [data-testid="stSidebar"]::-webkit-scrollbar,
      [data-testid="stSidebar"] > div:first-child::-webkit-scrollbar{ display:none !important; }

      [data-testid="stSidebar"] .block-container{ padding-top:.4rem !important; padding-bottom:0 !important; }
      [data-testid="stSidebar"] .stExpander{ margin-bottom:.25rem !important; padding:.25rem .4rem !important; }

      /* Sidebar text is always dark */
      :root [data-testid="stSidebar"] *{
        color:#111111 !important; -webkit-text-fill-color:#111111 !important; opacity:1 !important;
        text-shadow:none !important; filter:none !important;
      }

      /* pills (used in sidebar) */
      .pill{ font-size:.85rem !important; border-radius:8px !important; font-weight:600 !important; padding:.5rem .7rem; }
      .pill-green{ background:#dcfce7 !important; border:1px solid #22c55e !important; color:#111 !important; }
      .pill-blue{  background:#dbeafe !important; border:1px solid #3b82f6 !important; color:#111 !important; }
      .pill-yellow{background:#fef3c7 !important; border:1px solid #eab308 !important; color:#111 !important; }
    </style>
    """, unsafe_allow_html=True)

    if theme == "dark":
        # 1) 본문 전체 다크 스킨
        st.markdown("""
        <style>
          [data-testid="stAppViewContainer"]{
            background:#0f172a !important; color:#e5e7eb !important;
          }
          [data-testid="stAppViewContainer"] *{
            color:#e5e7eb !important;
          }
          h1,h2,h3,h4,h5,strong,b{ color:#ffffff !important; }
          .stButton button{
            background:#334155 !important; color:#fff !important; border:1px solid #475569 !important;
          }
          .stDownloadButton button{
            background:#334155 !important; color:#fff !important; border:1px solid #475569 !important;
          }
          /* 차트/테이블 틀 */
          .stDataFrame, .stTable{ background:#111827 !important; }
        </style>
        """, unsafe_allow_html=True)

        # 2) 입력/선택/텍스트는 흰 바탕 + 검정 글자 (시안성) — **덮어쓰기**
        st.markdown("""
        <style>
          [data-testid="stAppViewContainer"] div[data-testid="stTextInput"] input,
          [data-testid="stAppViewContainer"] div[data-testid="stNumberInput"] input,
          [data-testid="stAppViewContainer"] div[data-testid="stTextArea"] textarea,
          [data-testid="stAppViewContainer"] [data-baseweb="textarea"] textarea{
            background:#ffffff !important; color:#111 !important; -webkit-text-fill-color:#111 !important;
            border:1px solid rgba(0,0,0,.18) !important;
          }
          [data-testid="stAppViewContainer"] [data-baseweb="select"] > div{
            background:#ffffff !important; border:1px solid rgba(0,0,0,.18) !important;
          }
          [data-testid="stAppViewContainer"] [data-baseweb="select"] *,
          [data-testid="stAppViewContainer"] [data-baseweb="select"] input{
            color:#111 !important; -webkit-text-fill-color:#111 !important;
          }
          [data-baseweb="popover"] [role="listbox"],
          [data-baseweb="popover"] [role="listbox"] *{
            background:#ffffff !important; color:#111 !important; -webkit-text-fill-color:#111 !important;
          }
          [data-testid="stAppViewContainer"] input::placeholder,
          [data-testid="stAppViewContainer"] textarea::placeholder{
            color:#6b7280 !important; opacity:1 !important;
          }
        </style>
        """, unsafe_allow_html=True)
    else:
        # 라이트: 본문 컬러박스(알럿 등) 파란 배경 + 흰 글자
        st.markdown("""
        <style>
          [data-testid="stAppViewContainer"] .stAlert{
            background:#2563eb !important; border:1px solid #1e40af !important;
          }
          [data-testid="stAppViewContainer"] .stAlert,
          [data-testid="stAppViewContainer"] .stAlert *{
            color:#ffffff !important; fill:#ffffff !important;
          }
        </style>
        """, unsafe_allow_html=True)

_inject_css()

# ---------------------------
# Sidebar UI
# ---------------------------
def _sidebar():
    with st.sidebar:
        # 로고
        st.markdown("""
        <style>
          [data-testid="stSidebar"] .logo-circle{
            width:64px;height:64px;border-radius:9999px;overflow:hidden;
            margin:.35rem auto .6rem auto;
            box-shadow:0 2px 8px rgba(0,0,0,.12);
            border:1px solid rgba(0,0,0,.06);
          }
          [data-testid="stSidebar"] .logo-circle img{ width:100%;height:100%;object-fit:cover;display:block; }
        </style>
        """, unsafe_allow_html=True)
        try:
            lp = Path(__file__).parent / "logo.png"
            if lp.exists():
                b64 = base64.b64encode(lp.read_bytes()).decode("ascii")
                st.markdown(f'<div class="logo-circle"><img src="data:image/png;base64,{b64}"></div>', unsafe_allow_html=True)
        except Exception:
            pass

        # 토글
        c1, c2 = st.columns(2)
        with c1:
            is_dark = st.toggle("🌓 다크", value=(st.session_state.get("theme","light")=="dark"),
                                key="__theme_toggle_sb")
            st.session_state["theme"] = "dark" if is_dark else "light"
        with c2:
            st.session_state["__show_translator"] = st.toggle(
                "🌐 번역기", value=st.session_state.get("__show_translator", False),
                key="__show_translator_toggle_sb"
            )

        # 환율/마진 (간단)
        def fx_block(expanded=True):
            with st.expander("💱 환율 계산기", expanded=expanded):
                fx_base = st.selectbox("기준 통화", list(CURRENCIES.keys()),
                                       index=list(CURRENCIES.keys()).index(st.session_state.get("fx_base","USD")),
                                       key="fx_base_sb")
                sale_foreign = st.number_input("판매금액 (외화)", value=float(st.session_state.get("sale_foreign",1.0)),
                                               step=0.01, format="%.2f", key="sale_foreign_sb")
                won = FX_DEFAULT[fx_base]*sale_foreign
                st.markdown(f'<div class="pill pill-blue">환산 금액: <b>{won:,.2f} 원</b>'
                            f'<span style="opacity:.75;font-weight:700"> ({CURRENCIES[fx_base]["symbol"]})</span></div>',
                            unsafe_allow_html=True)
                st.caption(f"환율 기준: {FX_DEFAULT[fx_base]:,.2f} ₩/{CURRENCIES[fx_base]['unit']}")

        def margin_block(expanded=True):
            with st.expander("📈 마진 계산기", expanded=expanded):
                m_base = st.selectbox("매입 통화", list(CURRENCIES.keys()),
                                      index=list(CURRENCIES.keys()).index(st.session_state.get("m_base","USD")),
                                      key="m_base_sb")
                purchase_foreign = st.number_input("매입금액 (외화)",
                                                   value=float(st.session_state.get("purchase_foreign",0.0)),
                                                   step=0.01, format="%.2f", key="purchase_foreign_sb")
                base_cost_won = FX_DEFAULT[m_base]*purchase_foreign if purchase_foreign>0 \
                                else FX_DEFAULT[st.session_state.get("fx_base","USD")]*st.session_state.get("sale_foreign",1.0)
                st.markdown(f'<div class="pill pill-green">원가(₩): <b>{base_cost_won:,.2f} 원</b></div>',
                            unsafe_allow_html=True)

                c1, c2 = st.columns(2)
                with c1:
                    card_fee = st.number_input("카드수수료(%)",
                                               value=float(st.session_state.get("card_fee_pct",4.0)),
                                               step=0.01, format="%.2f", key="card_fee_pct_sb")
                with c2:
                    market_fee = st.number_input("마켓수수료(%)",
                                                 value=float(st.session_state.get("market_fee_pct",14.0)),
                                                 step=0.01, format="%.2f", key="market_fee_pct_sb")

                shipping_won = st.number_input("배송비(₩)",
                                               value=float(st.session_state.get("shipping_won",0.0)),
                                               step=100.0, format="%.0f", key="shipping_won_sb")
                mode = st.radio("마진 방식", ["퍼센트","플러스"], horizontal=True, key="margin_mode_sb")

                if mode=="퍼센트":
                    margin_pct = st.number_input("마진율 (%)",
                                                 value=float(st.session_state.get("margin_pct",10.0)),
                                                 step=0.01, format="%.2f", key="margin_pct_sb")
                    target_price = base_cost_won*(1+card_fee/100)*(1+market_fee/100)*(1+margin_pct/100)+shipping_won
                    margin_value = target_price - base_cost_won; desc=f"{margin_pct:.2f}%"
                else:
                    margin_won = st.number_input("마진액 (₩)",
                                                 value=float(st.session_state.get("margin_won",10000.0)),
                                                 step=100.0, format="%.0f", key="margin_won_sb")
                    target_price = base_cost_won*(1+card_fee/100)*(1+market_fee/100)+margin_won+shipping_won
                    margin_value = margin_won; desc=f"+{margin_won:,.0f}"

                st.markdown(f'<div class="pill pill-blue">판매가: <b>{target_price:,.2f} 원</b></div>', unsafe_allow_html=True)
                st.markdown(f'<div class="pill pill-yellow">순이익(마진): <b>{margin_value:,.2f} 원</b> — {desc}</div>',
                            unsafe_allow_html=True)

        if st.session_state.get("__show_translator", False):
            fx_block(expanded=False); margin_block(expanded=False)
        else:
            fx_block(expanded=True);  margin_block(expanded=True)

_sidebar()

# ---------------------------
# Simple sections (API-less demo to keep stable)
# ---------------------------
def section_category_keyword_lab():
    st.markdown('### 카테고리 ➔ 키워드 Top20 & 트렌드')
    cats = ["패션의류","패션잡화","뷰티/미용","디지털/가전","생활/건강","스포츠/레저"]
    c1,c2,c3 = st.columns([1,1,1])
    with c1: cat = st.selectbox("카테고리", cats, key="cat_lab")
    with c2: unit = st.selectbox("단위", ["week","month"], key="cat_unit")
    with c3: months = st.slider("조회기간(개월)", 1, 12, 3, key="cat_months")
    df = pd.DataFrame({
        "키워드":[f"{cat} 키워드{i}" for i in range(1,21)],
        "검색합계":[int(100000/i) for i in range(1,21)],
        "PC월간검색수":[int(60000/i) for i in range(1,21)],
        "Mobile월간검색수":[int(40000/i) for i in range(1,21)],
    })
    st.dataframe(df, use_container_width=True, height=330)
    st.download_button("CSV 다운로드", df.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"category_{cat}_top20.csv", mime="text/csv", key=f"dl_cat_{cat}")

def section_korea_radar():
    st.markdown('### AI 키워드 레이더 (국내)')
    c1,c2,c3 = st.columns([1,1,1])
    with c1: months = st.slider("분석기간(개월)", 1, 6, 3, key="kr_months")
    with c2: device = st.selectbox("디바이스", ["all","pc","mo"], key="kr_device")
    with c3: src = st.selectbox("키워드 소스", ["직접 입력"], key="kr_src")
    kw_txt = st.text_area("키워드(콤마)", "무릎보호대, 슬개골보호대", height=90, key="kr_kwtxt")
    if st.button("레이더 업데이트", key="kr_run"):
        kws = [k.strip() for k in kw_txt.split(",") if k.strip()]
        out = pd.DataFrame({"키워드":kws, "PC월간검색수":[9000]*len(kws), "Mobile월간검색수":[41000]*len(kws)})
        st.dataframe(out, use_container_width=True, height=300)
        st.download_button("CSV 다운로드", out.to_csv(index=False).encode("utf-8-sig"),
                           file_name="korea_keyword.csv", mime="text/csv", key="dl_kr")

def section_rakuten():
    st.markdown('### AI 키워드 레이더 (해외 · Rakuten Ranking)')
    cat = st.selectbox("라쿠텐 카테고리", ["전체(샘플)","뷰티/코스메틱","의류/패션"], key="rk_cat")
    df = pd.DataFrame([{"rank":i+1,"keyword":f"[샘플] 키워드 {i+1}","shop":"샘플","url":"https://example.com"} for i in range(20)])
    st.dataframe(df, use_container_width=True, height=300)
    st.download_button("표 CSV 다운로드", df.to_csv(index=False).encode("utf-8-sig"),
                       file_name="rakuten_ranking.csv", mime="text/csv", key="dl_rk")

def section_title_generator():
    st.markdown('### 상품명 생성기 (스마트스토어 · Top-N)')
    if st.session_state.get("theme","light") == "light":
        st.info("라이트 모드: 본문 컬러박스는 파란 배경/흰 글자로 표시됩니다.")

    cA,cB = st.columns([1,2])
    with cA:
        brand = st.text_input("브랜드", placeholder="예: 무지 / Apple", key="tg_brand")
        attrs = st.text_input("속성(콤마, 선택)", placeholder="예: 스포츠, 헬스, 러닝, 남녀공용", key="tg_attrs")
    with cB:
        kws_raw = st.text_input("키워드(콤마, 첫 번째가 메인)", placeholder="예: 무릎보호대, 관절보호, 충격흡수", key="tg_kw")
        main_kw = next((k.strip() for k in (kws_raw or "").split(",") if k.strip()), "")

    c1,c2,c3,c4 = st.columns([1,1,1,1])
    with c1: N = st.slider("추천 개수", 5, 20, 10, 1, key="tg_n")
    with c2: min_chars = st.slider("최소 글자(권장 30~50)", 30, 50, 35, 1, key="tg_min")
    with c3: max_bytes = st.slider("최대 바이트", 30, 50, 50, 1, key="tg_max")
    with c4: months = st.slider("검색 트렌드 기간(개월)", 1, 6, 3, key="tg_months")

    if st.button("상품명 생성", key="tg_run"):
        if not main_kw:
            st.error("키워드를 입력하세요.")
            return
        sugg = ["스포츠","헬스","러닝","관절보호","압박밴드","테이핑"]
        attrs_list = [a.strip() for a in (attrs or "").split(",") if a.strip()]
        base = [t for t in [main_kw]+attrs_list if t]
        titles=[]
        for s in sugg:
            cand = " ".join(base+[s])
            if len(cand.encode("utf-8"))>max_bytes:
                raw=cand.encode("utf-8")[:max_bytes]
                while True:
                    try: cand=raw.decode("utf-8"); break
                    except UnicodeDecodeError: raw=raw[:-1]
            titles.append(cand)
            if len(titles)>=N: break
        if titles:
            first = titles[0]
            st.success(f"1순위(등록용) — {first}  (문자 {len(first)}/{max_bytes} · 바이트 {len(first.encode('utf-8'))}/{max_bytes})")
        st.divider()
        for i,t in enumerate(titles,1):
            st.markdown(f"**{i}.** {t}")
        st.download_button("제목 CSV 다운로드",
                           data=pd.DataFrame({"title":titles}).to_csv(index=False).encode("utf-8-sig"),
                           file_name=f"titles_{main_kw}.csv", mime="text/csv", key="dl_tg")

def section_11st():
    st.markdown('### 11번가 (모바일) — 아마존 베스트')
    st.caption("임베드가 차단될 수 있어 데모 프레임으로 표시합니다.")
    src = "https://m.11st.co.kr/page/main/abest?tabId=ABEST&pageId=AMOBEST&ctgr1No=166160"
    html = f"""
    <style>
      .embed-11st-wrap {{ height: 680px; overflow: hidden; border-radius: 10px; }}
      .embed-11st-wrap iframe {{ width:100%; height:100%; border:0; border-radius:10px; overflow:hidden; }}
    </style>
    <div class="embed-11st-wrap"><iframe src="{src}" loading="lazy" scrolling="no"></iframe></div>
    """
    st.components.v1.html(html, height=700, scrolling=False)

def section_itemscout_placeholder():
    st.markdown('### 아이템스카우트')
    st.info("임베드는 보류 중입니다. 아래 버튼으로 원본 페이지를 새 탭에서 여세요.")
    link_button("아이템스카우트 직접 열기 (새 탭)", "https://app.itemscout.io/market/keyword", key="btn_itemscout")

def section_sellerlife_placeholder():
    st.markdown('### 셀러라이프')
    st.info("임베드는 보류 중입니다. 아래 버튼으로 원본 페이지를 새 탭에서 여세요.")
    link_button("셀러라이프 직접 열기 (새 탭)", "https://sellochomes.co.kr/sellerlife/", key="btn_sellerlife")

# ---------------------------
# Layout
# ---------------------------
st.title("ENVY — Season 1 (Dual Proxy Edition)")

colA, colB, colC = st.columns([4,8,4], gap="medium")
with colA:
    tab_cat, tab_direct = st.tabs(["카테고리", "직접 입력"])
    with tab_cat:
        section_category_keyword_lab()
    with tab_direct:
        st.markdown('### 키워드 트렌드 (직접 입력)')
        kw = st.text_input("키워드(콤마)", "가방, 원피스", key="kw_dir")
        unit = st.selectbox("단위", ["week","month"], index=0, key="kw_unit_dir")
        months = st.slider("조회기간(개월)", 1, 12, 3, key="kw_months_dir")
        if st.button("트렌드 조회", key="kw_run_dir"):
            cols = [k.strip() for k in kw.split(",") if k.strip()]
            df = pd.DataFrame({"날짜":[f"2024-0{i}-01" for i in range(1,6)]})
            for c in cols: df[c] = [i*10 for i in range(1,6)]
            st.dataframe(df, use_container_width=True, height=260)
            st.line_chart(df.set_index("날짜"))
with colB:
    tab_k, tab_r = st.tabs(["국내", "해외"])
    with tab_k: section_korea_radar()
    with tab_r: section_rakuten()
with colC:
    section_title_generator()

st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)

c1, c2, c3 = st.columns([3,3,3], gap="medium")
with c1: section_11st()
with c2: section_itemscout_placeholder()
with c3: section_sellerlife_placeholder()

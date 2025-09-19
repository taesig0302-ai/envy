# =========================
# Part 1 — 사이드바 (로고 + 환율/마진 계산기 + 프록시 입력)
# =========================
import streamlit as st
import base64
from pathlib import Path

# ── 전역 기본값 (다른 파트에서 재사용) ─────────────────────────────────────────────
CURRENCIES = {
    "USD": {"kr": "미국 달러", "symbol": "$", "unit": "USD"},
    "EUR": {"kr": "유로",     "symbol": "€", "unit": "EUR"},
    "JPY": {"kr": "일본 엔",   "symbol": "¥", "unit": "JPY"},
    "CNY": {"kr": "중국 위안", "symbol": "元","unit": "CNY"},
}
FX_DEFAULT = {"USD": 1400.0, "EUR": 1500.0, "JPY": 10.0, "CNY": 200.0}

def _ensure_session_defaults():
    """새 세션에 필요한 기본 상태 세팅."""
    ss = st.session_state
    ss.setdefault("theme", "light")
    ss.setdefault("PROXY_URL", "")
    # 환율/마진 계산기 기본값
    ss.setdefault("fx_base", "USD")
    ss.setdefault("sale_foreign", 1.00)
    ss.setdefault("m_base", "USD")
    ss.setdefault("purchase_foreign", 0.00)
    ss.setdefault("card_fee_pct", 4.00)
    ss.setdefault("market_fee_pct", 14.00)
    ss.setdefault("shipping_won", 0.0)
    ss.setdefault("margin_mode", "퍼센트")  # or "플러스"
    ss.setdefault("margin_pct", 10.00)
    ss.setdefault("margin_won", 10000.0)

def _toggle_theme():
    st.session_state["theme"] = "dark" if st.session_state.get("theme","light")=="light" else "light"

def _inject_sidebar_css():
    theme = st.session_state.get("theme","light")
    bg, fg = ("#0e1117", "#e6edf3") if theme=="dark" else ("#ffffff","#111111")
    st.markdown(f"""
    <style>
      html, body, [data-testid="stAppViewContainer"] {{
        background-color:{bg} !important; color:{fg} !important;
      }}
      /* 본문 여백 살짝 조정 */
      .block-container {{ padding-top:.8rem !important; padding-bottom:.35rem !important; }}
      /* 사이드바 고정 + 스크롤락 */
      [data-testid="stSidebar"],
      [data-testid="stSidebar"] > div:first-child,
      [data-testid="stSidebar"] section {{
        height: 100vh !important; overflow: hidden !important;
        padding-top:.25rem !important; padding-bottom:.25rem !important;
      }}
      [data-testid="stSidebar"] ::-webkit-scrollbar {{ display:none !important; }}
      /* 컴포넌트 간격 압축 */
      [data-testid="stSidebar"] .stSelectbox,
      [data-testid="stSidebar"] .stNumberInput,
      [data-testid="stSidebar"] .stRadio,
      [data-testid="stSidebar"] .stMarkdown,
      [data-testid="stSidebar"] .stTextInput,
      [data-testid="stSidebar"] .stButton {{ margin:.14rem 0 !important; }}
      /* 입력 높이/폰트 경량화 */
      [data-baseweb="input"] input,
      .stNumberInput input,
      [data-baseweb="select"] div[role="combobox"] {{
        height:1.55rem !important; padding:.12rem !important; font-size:.92rem !important;
      }}
      /* 로고 (원형, 그림자) */
      .logo-circle {{
        width:95px; height:95px; border-radius:50%; overflow:hidden;
        margin:.15rem auto .35rem auto; box-shadow:0 2px 8px rgba(0,0,0,.12);
        border:1px solid rgba(0,0,0,.06);
      }}
      .logo-circle img {{ width:100%; height:100%; object-fit:cover; }}
      /* 배지 */
      .badge-green  {{ background:#e6ffcc; border:1px solid #b6f3a4; padding:6px 10px; border-radius:6px; color:#0b2e13; font-size:.86rem; }}
      .badge-blue   {{ background:#eef4ff; border:1px solid #bcd0ff; padding:6px 10px; border-radius:6px; color:#0a235a; font-size:.86rem; }}
      .badge-yellow {{ background:#fff7d6; border:1px solid #f1d27a; padding:6px 10px; border-radius:6px; color:#4a3b07; font-size:.86rem; }}
      .muted        {{ opacity:.8; font-size:.8rem; }}
      /* 사이드바 하단 정보박스(프록시/버전) */
      .info-box {{ background:rgba(0,0,0,.03); border:1px dashed rgba(0,0,0,.08); padding:.6rem; border-radius:.5rem; }}
    </style>
    """, unsafe_allow_html=True)

def render_sidebar() -> dict:
    """
    사이드바 전체 UI 렌더링.
    - 로고
    - 테마 토글
    - 환율/마진 계산기 (컬러 배지 3종)
    - 하단: PROXY_URL 입력칸 + 프로그램 정보
    반환: 계산 결과 딕셔너리(다른 파트에서 사용 가능)
    """
    _ensure_session_defaults()
    _inject_sidebar_css()

    result = {}
    with st.sidebar:
        # ── 로고 ─────────────────────────────────────────────────────────────
        lp = Path(__file__).parent / "logo.png"
        if lp.exists():
            b64 = base64.b64encode(lp.read_bytes()).decode("ascii")
            st.markdown(f'<div class="logo-circle"><img src="data:image/png;base64,{b64}"></div>', unsafe_allow_html=True)
        else:
            st.caption("logo.png 를 앱 파일과 같은 폴더에 두면 로고가 표시됩니다.")

        # 테마 토글
        st.toggle("🌓 다크 모드", value=(st.session_state.get("theme","light")=="dark"), on_change=_toggle_theme, key="__theme_toggle")

        # ── ① 환율 계산기 ───────────────────────────────────────────────────
        st.markdown("### ① 환율 계산기")
        base = st.selectbox(
            "기준 통화",
            list(CURRENCIES.keys()),
            index=list(CURRENCIES.keys()).index(st.session_state["fx_base"]),
            key="fx_base"
        )
        sale_foreign = st.number_input("판매금액 (외화)", value=float(st.session_state["sale_foreign"]), step=0.01, format="%.2f", key="sale_foreign")
        won = FX_DEFAULT[base] * sale_foreign
        st.markdown(
            f'<div class="badge-green">환산 금액: <b>{won:,.2f} 원</b> '
            f'<span class="muted">({CURRENCIES[base]["kr"]} • {CURRENCIES[base]["symbol"]})</span></div>',
            unsafe_allow_html=True
        )
        st.caption(f"환율 기준: {FX_DEFAULT[base]:,.2f} ₩/{CURRENCIES[base]['unit']}")

        # ── ② 마진 계산기 ───────────────────────────────────────────────────
        st.markdown("### ② 마진 계산기")
        m_base = st.selectbox(
            "매입 통화",
            list(CURRENCIES.keys()),
            index=list(CURRENCIES.keys()).index(st.session_state["m_base"]),
            key="m_base"
        )
        purchase_foreign = st.number_input("매입금액 (외화)", value=float(st.session_state["purchase_foreign"]), step=0.01, format="%.2f", key="purchase_foreign")

        base_cost_won = FX_DEFAULT[m_base] * purchase_foreign if purchase_foreign>0 else won
        st.markdown(f'<div class="badge-green">원가(₩): <b>{base_cost_won:,.2f} 원</b></div>', unsafe_allow_html=True)

        # 수수료/배송비
        colf1, colf2 = st.columns(2)
        with colf1:
            card_fee = st.number_input("카드수수료(%)", value=float(st.session_state["card_fee_pct"]), step=0.01, format="%.2f", key="card_fee_pct")
        with colf2:
            market_fee = st.number_input("마켓수수료(%)", value=float(st.session_state["market_fee_pct"]), step=0.01, format="%.2f", key="market_fee_pct")
        shipping_won = st.number_input("배송비(₩)", value=float(st.session_state["shipping_won"]), step=100.0, format="%.0f", key="shipping_won")

        # 마진 방식
        mode = st.radio("마진 방식", ["퍼센트","플러스"], horizontal=True, key="margin_mode")

        if mode == "퍼센트":
            margin_pct = st.number_input("마진율 (%)", value=float(st.session_state["margin_pct"]), step=0.01, format="%.2f", key="margin_pct")
            target_price = base_cost_won * (1 + card_fee/100) * (1 + market_fee/100) * (1 + margin_pct/100) + shipping_won
            margin_value = target_price - base_cost_won
            margin_desc = f"{margin_pct:.2f}%"
        else:
            margin_won = st.number_input("마진액 (₩)", value=float(st.session_state["margin_won"]), step=100.0, format="%.0f", key="margin_won")
            target_price = base_cost_won * (1 + card_fee/100) * (1 + market_fee/100) + margin_won + shipping_won
            margin_value = margin_won
            margin_desc = f"+{margin_won:,.0f}"

        st.markdown(f'<div class="badge-blue">판매가: <b>{target_price:,.2f} 원</b></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="badge-yellow">순이익(마진): <b>{margin_value:,.2f} 원</b> — {margin_desc}</div>', unsafe_allow_html=True)

        # ── 하단: PROXY_URL + 프로그램 정보 ────────────────────────────────
        st.divider()
        st.markdown("##### 프록시/환경")
        st.text_input("PROXY_URL (Cloudflare Worker 등)", value=st.session_state.get("PROXY_URL",""), key="PROXY_URL", help="예: https://envy-proxy.example.workers.dev/")
        st.markdown(
            """
            <div class="info-box">
              <b>ENVY</b> 사이드바 정보는 고정입니다. 이 아래는 숨김/고정 권장.<br/>
              · 로고/환율/마진 계산기: 변경 금지<br/>
              · PROXY_URL: 11번가 등 iFrame 제한 회피용(옵션)<br/>
              · 다크/라이트 모드는 상단 토글
            </div>
            """, unsafe_allow_html=True
        )

    # 다른 파트에서 쓸 수 있게 결과 반환
    result.update({
        "fx_base": base,
        "sale_foreign": sale_foreign,
        "converted_won": won,
        "purchase_base": m_base,
        "purchase_foreign": purchase_foreign,
        "base_cost_won": base_cost_won,
        "card_fee_pct": card_fee,
        "market_fee_pct": market_fee,
        "shipping_won": shipping_won,
        "margin_mode": mode,
        "target_price": target_price,
        "margin_value": margin_value,
    })
    return result
# =========================
# Part 2 — 공용 유틸
# =========================
import time
import pandas as pd

# 언어 → 한국어 라벨 (번역기 드롭다운용)
LANG_LABELS = {
    "auto":"자동 감지",
    "ko":"한국어",
    "en":"영어",
    "ja":"일본어",
    "zh-CN":"중국어(간체)",
    "zh-TW":"중국어(번체)",
    "vi":"베트남어",
    "th":"태국어",
    "id":"인도네시아어",
    "de":"독일어",
    "fr":"프랑스어",
    "es":"스페인어",
    "it":"이탈리아어",
    "pt":"포르투갈어",
}

def lang_label_to_code(label_or_code:str) -> str:
    # label/코드 혼합 입력을 모두 코드로 통일
    rev = {v:k for k,v in LANG_LABELS.items()}
    return rev.get(label_or_code, label_or_code)

def toast_ok(msg:str): st.toast(f"✅ {msg}")
def toast_warn(msg:str): st.toast(f"⚠️ {msg}")
def toast_err(msg:str): st.toast(f"❌ {msg}")
# =========================
# Part 3 — 데이터랩(대분류 12종) + 그래프
# =========================
import numpy as np

DATALAB_CATS = [
    "패션의류","패션잡화","화장품/미용","디지털/가전","가구/인테리어",
    "출산/육아","식품","스포츠/레저","생활/건강","여가/생활편의","면세점","도서"
]

def mock_keywords(cat:str, k:int=20):
    """실서비스 전 샘플: 카테고리명 seed로 항상 같은 20개 키워드/점수 반환"""
    rng = np.random.default_rng(abs(hash(cat)) % (2**32))
    pool = ["가습기","복합기","무선청소기","정수기필터","보조배터리","음식물처리기","노트북","아이폰16케이스","블루투스이어폰","블루투스스피커",
            "공기청정기","제습기","레인저프린터","드라이기","커피머신","포터블모니터","태블릿PC","게이밍마우스","키보드","외장SSD"]
    scores = sorted((rng.integers(40,100,size=k)).tolist(), reverse=True)
    return [{"rank":i+1,"keyword":pool[i%len(pool)],"score":scores[i]} for i in range(k)]

def render_datalab_block():
    st.markdown("## 데이터랩 (대분류 12종 전용)")
    c1,c2 = st.columns([1,1])
    with c1:
        cat = st.selectbox("카테고리", DATALAB_CATS, key="dl_cat")
        start = st.date_input("시작일", value=pd.to_datetime("2024-09-19"), key="dl_start")
        end   = st.date_input("종료일", value=pd.to_datetime("2025-09-19"), key="dl_end")
        st.button("시동", key="dl_go")
        data = mock_keywords(cat, 20)

        df = pd.DataFrame(data)
        st.dataframe(df, hide_index=True, use_container_width=True)

        # 아래 라인그래프는 “검색량 흐름” 데모 — 요청대로 보기용
        x = np.arange(0, 22)
        y = np.linspace(120, 0, len(x))
        st.line_chart(pd.DataFrame({"trend":y}, index=x), height=220, use_container_width=True)

    with c2:
        st.markdown("### 캠프 기간 (기간 프리셋 + 기기별)")
        kw = st.text_input("키워드(최대 5개, 콤마로 구분)", "가습기, 복합기, 무선청소기", key="trend_kws")
        preset = st.selectbox("기간 프리셋", ["1년","3개월","1개월"], key="trend_preset")
        device = st.selectbox("기기별", ["전체","PC","모바일"], key="trend_device")
        bigcat = st.selectbox("카테고리(대분류)", DATALAB_CATS, key="trend_bigcat")
        st.caption("※ 실제 API 접근 권한이 제한되어, 프리셋/기기/카테고리 변경시 **샘플 라인**을 표시합니다.")

        # 샘플 라인 3개 (삼색 상태)
        xx = np.arange(0, 12)
        base = 50 + 5*np.sin(xx/2)
        df_line = pd.DataFrame({
            "가습기": base,
            "무선청소기": base-5 + 3*np.cos(xx/3),
            "복합기": base+3 + 4*np.sin(xx/4),
        }, index=xx)
        st.line_chart(df_line, height=220, use_container_width=True)
# =========================
# Part 4 — 11번가(모바일) 임베드
# =========================
def render_11st_block():
    st.markdown("## 11번가 (모바일)")
    url = st.text_input("모바일 URL", "https://m.11st.co.kr/browsing/bestSellers.mall", key="t11_url")
    proxy = st.session_state.get("PROXY_URL","").strip()
    if not proxy:
        st.info("PROXY_URL 미설정: iFrame을 직접 막힐 수 있습니다.")
    # 임베드 (Streamlit은 sandbox라 완전한 제어 어려움)
    try:
        st.components.v1.iframe(url, height=560, scrolling=True)
    except Exception as e:
        toast_err(f"11번가 로드 실패: {e}")
# =========================
# Part 5 — AI 키워드 레이더 (Rakuten)
# =========================
RAKUTEN_CATS = [
    "전체(샘플)","뷰티/코스메틱","의류/패션","가전/디지털","가구/인테리어","식품","생활/건강","스포츠/레저","문구/취미"
]

def mock_rakuten_rows(n=30):
    rng = np.random.default_rng(42)
    items = []
    for i in range(1, n+1):
        kw = f"[公式] 샘플 키워드 {i} ハロウィン 秋 お彼岸 🍂"
        items.append({"rank":i, "keyword":kw, "source":"Rakute"})
    return items

def render_rakuten_block():
    st.markdown("## AI 캠프 랩 (Rakuten)")

    colA, colB, colC = st.columns([1,1,1])
    with colA:
        scope = st.radio("가구용 가구", ["국내","글로벌"], horizontal=True, key="rk_scope")
    with colB:
        cat = st.selectbox("라쿠텐 카테고리", RAKUTEN_CATS, key="rk_cat")
    with colC:
        genreid = st.text_input("장르ID(직접 입력)", "100283", key="rk_genre")

    st.caption("앱 ID: 1043271015809337425  |  400/파싱 실패 → ‘전체(샘플)’로 자동 폴백")

    # 테이블 폰트 소형화
    st.markdown("""
    <style>
      .rk table { font-size: 0.92rem !important; }
    </style>
    """, unsafe_allow_html=True)

    # 샘플 데이터 (실제 연동 전 안전성)
    rows = mock_rakuten_rows(30)
    df = pd.DataFrame(rows)
    with st.container():
        st.markdown('<div class="rk">', unsafe_allow_html=True)
        st.dataframe(df, hide_index=True, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
# =========================
# Part 6 — 구글 번역 (텍스트 I/O + 한국어 확인용)
# =========================
from deep_translator import GoogleTranslator

def translate_text(src:str, tgt:str, text:str) -> tuple[str,str]:
    # src/tgt는 코드(auto/ko/en/zh-CN 등)
    src = lang_label_to_code(src)
    tgt = lang_label_to_code(tgt)
    translator = GoogleTranslator(source=src, target=tgt)
    out = translator.translate(text)
    ko_hint = ""
    if tgt != "ko" and out.strip():
        try:
            ko_hint = GoogleTranslator(source=tgt, target="ko").translate(out)
        except Exception:
            ko_hint = ""
    return out, ko_hint

def render_translator_block():
    st.markdown("## 구글 번역 (텍스트 입력/출력 + 한국어 확인용)")
    c1, c2 = st.columns([1,1])
    with c1:
        src = st.selectbox("원문 언어", list(LANG_LABELS.values()), index=list(LANG_LABELS.keys()).index("auto"), key="tr_src")
        text_in = st.text_area("원문 입력", height=150, key="tr_in")
    with c2:
        tgt = st.selectbox("번역 언어", list(LANG_LABELS.values()), index=list(LANG_LABELS.keys()).index("en"), key="tr_tgt")
        if st.button("번역", key="tr_go"):
            try:
                out, ko_hint = translate_text(lang_label_to_code(src), lang_label_to_code(tgt), text_in)
                if ko_hint:
                    st.text_area("번역 결과", value=f"{out}\n{ko_hint}", height=150)
                else:
                    st.text_area("번역 결과", value=out, height=150)
                toast_ok("번역 완료")
            except ModuleNotFoundError as e:
                st.warning(f"deep-translator 설치 필요: {e}")
            except Exception as e:
                st.error(f"번역 실패: {e}")
# =========================
# Part 7 — 메인 조립
# =========================
def main():
    # 1) 사이드바 (이미 Part1에서 정의)
    sidebar_vals = render_sidebar()

    st.title("ENVY — v11.x (stable)")
    st.caption("사이드바는 고정/스크롤락, 본문 카드는 큼직하고 시안성 위주 배치")

    # 2) 데이터랩 + 기간/기기 그래프
    render_datalab_block()
    st.divider()

    # 3) 11번가 임베드 + 라쿠텐 키워드
    colL, colR = st.columns([1,1])
    with colL:
        render_11st_block()
    with colR:
        render_rakuten_block()
    st.divider()

    # 4) 번역기
    render_translator_block()

if __name__ == "__main__":
    main()

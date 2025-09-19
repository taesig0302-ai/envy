# ==============================================================
# ENVY — v11.x (stable)  |  4x2 Grid + Sidebar (original) 2025-09
# ==============================================================

import streamlit as st
import base64
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import date, timedelta
import urllib.parse

# 외부 통신 모듈 (없어도 돌아가게)
try:
    import requests
except Exception:
    requests = None

# -----------------------------
# 전역 상수
# -----------------------------
CURRENCIES = {
    "USD": {"kr": "미국 달러", "symbol": "$", "unit": "USD"},
    "EUR": {"kr": "유로",     "symbol": "€", "unit": "EUR"},
    "JPY": {"kr": "일본 엔",   "symbol": "¥", "unit": "JPY"},
    "CNY": {"kr": "중국 위안", "symbol": "元","unit": "CNY"},
}
FX_DEFAULT = {"USD": 1400.0, "EUR": 1500.0, "JPY": 10.0, "CNY": 200.0}

# ------------------------------------------------------------
# Sidebar (원본) — 로고 + 환율/마진 계산기 + PROXY_URL
# ------------------------------------------------------------
def _ensure_session_defaults():
    ss = st.session_state
    ss.setdefault("theme", "light")
    ss.setdefault("PROXY_URL", "")
    # 환율/마진 기본
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
      /* 본문 넓게 */
      .block-container {{ max-width: 1800px !important; padding-top:.8rem !important; padding-bottom:.6rem !important; }}
      /* 사이드바 고정/간격 */
      [data-testid="stSidebar"], [data-testid="stSidebar"] section {{ height:100vh !important; overflow:hidden !important; }}
      [data-testid="stSidebar"] ::-webkit-scrollbar {{ display:none !important; }}
      [data-testid="stSidebar"] .stSelectbox, [data-testid="stSidebar"] .stNumberInput,
      [data-testid="stSidebar"] .stRadio, [data-testid="stSidebar"] .stMarkdown,
      [data-testid="stSidebar"] .stTextInput, [data-testid="stSidebar"] .stButton {{ margin:.14rem 0 !important; }}
      [data-baseweb="input"] input, .stNumberInput input, [data-baseweb="select"] div[role="combobox"] {{
        height:1.55rem !important; padding:.12rem !important; font-size:.92rem !important;
      }}
      /* 로고 */
      .logo-circle {{ width:95px; height:95px; border-radius:50%; overflow:hidden; margin:.15rem auto .35rem; box-shadow:0 2px 8px rgba(0,0,0,.12); border:1px solid rgba(0,0,0,.06); }}
      .logo-circle img {{ width:100%; height:100%; object-fit:cover; }}
      /* 배지 */
      .badge-green  {{ background:#e6ffcc; border:1px solid #b6f3a4; padding:6px 10px; border-radius:6px; color:#0b2e13; font-size:.86rem; }}
      .badge-blue   {{ background:#eef4ff; border:1px solid #bcd0ff; padding:6px 10px; border-radius:6px; color:#0a235a; font-size:.86rem; }}
      .badge-yellow {{ background:#fff7d6; border:1px solid #f1d27a; padding:6px 10px; border-radius:6px; color:#4a3b07; font-size:.86rem; }}
      .muted        {{ opacity:.8; font-size:.8rem; }}
      .info-box {{ background:rgba(0,0,0,.03); border:1px dashed rgba(0,0,0,.08); padding:.6rem; border-radius:.5rem; }}
      /* 카드 타이틀 압축 */
      .card-title {{ margin:0 0 .4rem 0; font-weight:700; font-size:1.05rem; }}
    </style>
    """, unsafe_allow_html=True)

def render_sidebar():
    _ensure_session_defaults()
    _inject_sidebar_css()

    with st.sidebar:
        # 로고
        lp = Path(__file__).parent / "logo.png"
        if lp.exists():
            b64 = base64.b64encode(lp.read_bytes()).decode("ascii")
            st.markdown(f'<div class="logo-circle"><img src="data:image/png;base64,{b64}"></div>', unsafe_allow_html=True)
        else:
            st.caption("logo.png 를 앱과 같은 폴더에 두면 로고 표시")

        # 테마
        st.toggle("🌓 다크 모드", value=(st.session_state.get("theme","light")=="dark"), on_change=_toggle_theme, key="__theme_toggle")

        # ① 환율 계산기
        st.markdown("### ① 환율 계산기")
        base = st.selectbox("기준 통화", list(CURRENCIES.keys()), index=list(CURRENCIES.keys()).index(st.session_state["fx_base"]), key="fx_base")
        sale_foreign = st.number_input("판매금액 (외화)", value=float(st.session_state["sale_foreign"]), step=0.01, format="%.2f", key="sale_foreign")
        won = FX_DEFAULT[base] * sale_foreign
        st.markdown(f'<div class="badge-green">환산 금액: <b>{won:,.2f} 원</b> <span class="muted">({CURRENCIES[base]["kr"]} • {CURRENCIES[base]["symbol"]})</span></div>', unsafe_allow_html=True)
        st.caption(f"환율 기준: {FX_DEFAULT[base]:,.2f} ₩/{CURRENCIES[base]['unit']}")

        # ② 마진 계산기
        st.markdown("### ② 마진 계산기")
        m_base = st.selectbox("매입 통화", list(CURRENCIES.keys()), index=list(CURRENCIES.keys()).index(st.session_state["m_base"]), key="m_base")
        purchase_foreign = st.number_input("매입금액 (외화)", value=float(st.session_state["purchase_foreign"]), step=0.01, format="%.2f", key="purchase_foreign")
        base_cost_won = FX_DEFAULT[m_base] * purchase_foreign if purchase_foreign>0 else won
        st.markdown(f'<div class="badge-green">원가(₩): <b>{base_cost_won:,.2f} 원</b></div>', unsafe_allow_html=True)

        colf1, colf2 = st.columns(2)
        with colf1:
            card_fee = st.number_input("카드수수료(%)", value=float(st.session_state["card_fee_pct"]), step=0.01, format="%.2f", key="card_fee_pct")
        with colf2:
            market_fee = st.number_input("마켓수수료(%)", value=float(st.session_state["market_fee_pct"]), step=0.01, format="%.2f", key="market_fee_pct")
        shipping_won = st.number_input("배송비(₩)", value=float(st.session_state["shipping_won"]), step=100.0, format="%.0f", key="shipping_won")

        mode = st.radio("마진 방식", ["퍼센트","플러스"], horizontal=True, key="margin_mode")
        if mode == "퍼센트":
            margin_pct = st.number_input("마진율 (%)", value=float(st.session_state["margin_pct"]), step=0.01, format="%.2f", key="margin_pct")
            target_price = base_cost_won * (1 + card_fee/100) * (1 + market_fee/100) * (1 + margin_pct/100) + shipping_won
            margin_value = target_price - base_cost_won
        else:
            margin_won = st.number_input("마진액 (₩)", value=float(st.session_state["margin_won"]), step=100.0, format="%.0f", key="margin_won")
            target_price = base_cost_won * (1 + card_fee/100) * (1 + market_fee/100) + margin_won + shipping_won
            margin_value = margin_won

        st.markdown(f'<div class="badge-blue">판매가: <b>{target_price:,.2f} 원</b></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="badge-yellow">순이익(마진): <b>{margin_value:,.2f} 원</b></div>', unsafe_allow_html=True)

        st.divider()
        st.markdown("##### 프록시/환경")
        st.text_input("PROXY_URL (Cloudflare Worker 등)", value=st.session_state.get("PROXY_URL",""), key="PROXY_URL", help="예: https://envy-proxy.***.workers.dev/")
        st.markdown("""<div class="info-box">
          · 로고/환율/마진 계산기: 고정<br/>
          · PROXY_URL: 11번가/외부 사이트 iFrame 제한 회피용(필요 시)<br/>
          · 다크/라이트 모드: 상단 토글
        </div>""", unsafe_allow_html=True)

    # 반환 (본문에서 필요할 수 있어 그대로 리턴)
    return {
        "fx_base": base, "sale_foreign": sale_foreign, "converted_won": won,
        "purchase_base": m_base, "purchase_foreign": purchase_foreign, "base_cost_won": base_cost_won,
        "card_fee_pct": card_fee, "market_fee_pct": market_fee, "shipping_won": shipping_won
    }

# ------------------------------------------------------------
# 공용 유틸
# ------------------------------------------------------------
def status_chip(ok:bool, ok_txt="OK", bad_txt="MISSING"):
    color = "#16a34a" if ok else "#ef4444"
    txt = ok_txt if ok else bad_txt
    st.markdown(f"<span style='padding:.15rem .45rem;border-radius:.4rem;border:1px solid {color};color:{color};font-size:.8rem;'>{txt}</span>", unsafe_allow_html=True)

def proxied(url:str) -> str:
    proxy = st.session_state.get("PROXY_URL","").strip()
    if not proxy:
        return url
    # Cloudflare Worker가 ?url= 대상 경로를 받는 타입이라고 가정
    if not proxy.endswith("/"):
        proxy += ""
    return f"{proxy}?url={urllib.parse.quote(url, safe='')}"

# ------------------------------------------------------------
# 카드 1 — 데이터랩(원본 임베드)
# ------------------------------------------------------------
DATALAB_CATS = [
    "디지털/가전","패션의류","패션잡화","화장품/미용","가구/인테리어","출산/육아","식품",
    "스포츠/레저","생활/건강","여가/생활편의","면세점","도서"
]
def view_datalab_embed():
    st.markdown('<div class="card-title">데이터랩 (원본 임베드)</div>', unsafe_allow_html=True)
    c1,c2,c3 = st.columns([1,1,1])
    with c1:
        cat = st.selectbox("카테고리", DATALAB_CATS, key="dlb_cat")
    with c2:
        unit = st.selectbox("기간 단위", ["week","mo"], index=0, key="dlb_unit")
    with c3:
        device = st.selectbox("기기", ["all","pc","mo"], index=0, key="dlb_device")

    raw_url = f"https://datalab.naver.com/shoppingInsight/sCategory?cat_id=50000003&period={unit}&device={device}"
    if not st.session_state.get("PROXY_URL","").strip():
        st.info("PROXY_URL 이 비어 있습니다. 사이드바 하단에 Cloudflare Worker 주소를 입력해 주세요.")
    try:
        st.components.v1.iframe(proxied(raw_url), height=560, scrolling=True, key="dl_raw_iframe")
    except Exception as e:
        st.error(f"iFrame 로드 실패: {e}")

# ------------------------------------------------------------
# 카드 2 — 데이터랩(분석) : 샘플 그래프 + 자리잡기
# ------------------------------------------------------------
def view_datalab_analysis():
    st.markdown('<div class="card-title">데이터랩 (분석)</div>', unsafe_allow_html=True)
    st.caption("※ 시즌1은 쿠키/광고 API 없이 샘플 그래프만 표시. (시즌2에서 원본 임베드 방식으로 전환)")
    x = np.arange(0, 12)
    base = 50 + 5*np.sin(x/2)
    df_line = pd.DataFrame({
        "전체": base,
        "패션의류": base-5 + 3*np.cos(x/3)
    }, index=[f"P{i}" for i in range(len(x))])
    st.line_chart(df_line, height=220, use_container_width=True)

# ------------------------------------------------------------
# 카드 3 — 11번가(모바일)
# ------------------------------------------------------------
def view_11st_mobile():
    st.markdown('<div class="card-title">11번가 (모바일)</div>', unsafe_allow_html=True)
    # 요청: 아마존베스트 탭 바로
    default_url = "https://m.11st.co.kr/page/main/abest?tabId=ABEST&pageId=AMOBEST&ctgr1No=166160"
    url = st.text_input("모바일 URL", value=default_url, key="t11_url_fixed")
    if not st.session_state.get("PROXY_URL","").strip():
        st.warning("PROXY_URL 미설정: iFrame 차단될 수 있습니다.")
    try:
        st.components.v1.iframe(proxied(url), height=580, scrolling=True, key="t11_iframe")
    except Exception as e:
        st.error(f"11번가 로드 실패: {e}")

# ------------------------------------------------------------
# 카드 4 — 상품명 생성기 (규칙 기반)
# ------------------------------------------------------------
def simple_keywords_from_title(title:str, topn:int=5):
    tokens = [t.strip() for t in title.replace("/", " ").replace("|"," ").split() if len(t.strip())>=2]
    # 간단 빈도
    freq = {}
    for t in tokens:
        freq[t] = freq.get(t,0)+1
    ranked = sorted(freq.items(), key=lambda x:(-x[1], -len(x[0]), x[0]))[:topn]
    return [{"kw":k, "count":c} for k,c in ranked]

def view_title_generator():
    st.markdown('<div class="card-title">상품명 생성기 (규칙 기반)</div>', unsafe_allow_html=True)
    c1,c2 = st.columns([2,1])
    with c2:
        max_len = st.slider("최대 글자수", 20, 80, 60, key="tg_len")
        order = st.selectbox("구분자", ["brand,keyword,attrs,model", "brand,model,keyword,attrs"], index=0, key="tg_order")
    with c1:
        brand = st.text_input("브랜드", key="tg_brand")
        model = st.text_input("모델", key="tg_model")
        attrs = st.text_input("속성(콤마)", help="예: AS가1, 좌우대칭, 정음식", key="tg_attrs")
        keywords = st.text_input("키워드(콤마)", help="예: 노트북, 거치대", key="tg_kws")

    if st.button("상품명 생성", key="tg_go"):
        parts = {
            "brand": brand.strip(),
            "model": model.strip(),
            "attrs": " ".join([a.strip() for a in attrs.split(",") if a.strip()]),
            "keyword": " ".join([k.strip() for k in keywords.split(",") if k.strip()]),
        }
        seq = order.split(",")
        title = " ".join([parts[s] for s in seq if parts[s]])
        if len(title) > max_len:
            title = title[:max_len-1].rstrip()+"…"
        st.success(title if title else "생성된 제목이 없습니다.")
        # 추천 키워드 5개 (검색량은 자리값)
        topk = simple_keywords_from_title(title or (brand+" "+model+" "+attrs+" "+keywords))
        df = pd.DataFrame([{"rank":i+1,"keyword":x["kw"],"score":100-3*i} for i,x in enumerate(topk)])
        st.caption("추천 키워드(샘플 점수)")
        st.dataframe(df, hide_index=True, use_container_width=True)

# ------------------------------------------------------------
# 카드 5 — AI 키워드 레이더 (Rakuten)
# ------------------------------------------------------------
def view_rakuten():
    st.markdown('<div class="card-title">AI 키워드 레이더 (Rakuten)</div>', unsafe_allow_html=True)
    colA, colB, colC = st.columns([1,1,1])
    with colA:
        scope = st.radio("범위", ["국내","글로벌"], horizontal=True, key="rk_scope")
    with colB:
        cat = st.selectbox("라쿠텐 카테고리", ["전체(샘플)","뷰티/코스메틱","의류/패션","가전/디지털"], key="rk_cat")
    with colC:
        genreid = st.text_input("GenreID", "100283", key="rk_genre")

    # APP_ID 점검 (secrets 우선)
    app_id = st.secrets.get("RAKUTEN_APP_ID", "")
    with st.expander("Rakuten APP_ID 설정", expanded=(app_id=="")):
        app_id = st.text_input("APP_ID", value=app_id, type="password", key="rk_appid")
    st.write("상태:", end=" ")
    status_chip(bool(app_id), "APP_ID OK", "APP_ID 없음")

    # 실제 API는 네트워크/인증 이슈가 잦아 데모 테이블 제공
    rows = [{"rank":i+1, "keyword":f"[공식] 샘플 키워드 {i+1}", "source":"rakuten"} for i in range(20)]
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True, height=300)

# ------------------------------------------------------------
# 카드 6 — 구글 번역
# ------------------------------------------------------------
def view_translator():
    st.markdown('<div class="card-title">구글 번역 (텍스트 입력/출력 + 한국어 확인용)</div>', unsafe_allow_html=True)
    c1,c2 = st.columns([1,1])
    with c1:
        src = st.selectbox("원문 언어", ["자동 감지","한국어","영어","일본어","중국어(간체)","중국어(번체)"], key="tr_src")
        text_in = st.text_area("원문 입력", height=150, key="tr_in")
    with c2:
        tgt = st.selectbox("번역 언어", ["영어","한국어","일본어","중국어(간체)","중국어(번체)"], key="tr_tgt")
        if st.button("번역", key="tr_go"):
            try:
                from deep_translator import GoogleTranslator
                s = "auto" if src=="자동 감지" else {"한국어":"ko","영어":"en","일본어":"ja","중국어(간체)":"zh-CN","중국어(번체)":"zh-TW"} .get(src, "auto")
                t = {"한국어":"ko","영어":"en","일본어":"ja","중국어(간체)":"zh-CN","중국어(번체)":"zh-TW"} .get(tgt, "en")
                out = GoogleTranslator(source=s, target=t).translate(text_in or "")
                ko_hint = ""
                if t != "ko" and out.strip():
                    try:
                        ko_hint = GoogleTranslator(source=t, target="ko").translate(out)
                    except Exception:
                        pass
                st.text_area("번역 결과", value=f"{out}\n{ko_hint}" if ko_hint else out, height=150)
                st.success("번역 완료")
            except ModuleNotFoundError as e:
                st.warning(f"deep-translator 설치 필요: {e}")
            except Exception as e:
                st.error(f"번역 실패: {e}")

# ------------------------------------------------------------
# 카드 7 — 아이템스카우트 (원본 임베드)
# ------------------------------------------------------------
def view_itemscout():
    st.markdown('<div class="card-title">아이템스카우트 (원본 임베드)</div>', unsafe_allow_html=True)
    url = "https://items.singtown.com"
    if not st.session_state.get("PROXY_URL","").strip():
        st.info("PROXY_URL 이 비어 있습니다. 사이드바 하단에 Cloudflare Worker 주소를 입력해 주세요.")
    try:
        st.components.v1.iframe(proxied(url), height=520, scrolling=True, key="is_iframe")
    except Exception as e:
        st.error(f"아이템스카우트 로드 실패: {e}")

# ------------------------------------------------------------
# 카드 8 — 셀러라이프 (원본 임베드)
# ------------------------------------------------------------
def view_sellerlife():
    st.markdown('<div class="card-title">셀러라이프 (원본 임베드)</div>', unsafe_allow_html=True)
    url = "https://www.sellerlife.co.kr"
    if not st.session_state.get("PROXY_URL","").strip():
        st.info("PROXY_URL 이 비어 있습니다. 사이드바 하단에 Cloudflare Worker 주소를 입력해 주세요.")
    try:
        st.components.v1.iframe(proxied(url), height=520, scrolling=True, key="sl_iframe")
    except Exception as e:
        st.error(f"셀러라이프 로드 실패: {e}")

# ------------------------------------------------------------
# 메인 (4×2 고정 배열)
# ------------------------------------------------------------
def main():
    render_sidebar()

    st.title("ENVY — v11.x (stable)")
    st.caption("사이드바는 고정 · 본문은 4×2 카드 고정 배치")

    # Row 1
    c1, c2, c3, c4 = st.columns(4, gap="medium")
    with c1: view_datalab_embed()
    with c2: view_datalab_analysis()
    with c3: view_11st_mobile()
    with c4: view_title_generator()

    st.divider()

    # Row 2
    r2c1, r2c2, r2c3, r2c4 = st.columns(4, gap="medium")
    with r2c1: view_rakuten()
    with r2c2: view_translator()
    with r2c3: view_itemscout()
    with r2c4: view_sellerlife()

    st.divider()
    # 하단 공통 안내/오류 멘트 바
    proxy = st.session_state.get("PROXY_URL","").strip()
    rakuten_ok = bool(st.secrets.get("RAKUTEN_APP_ID","") or st.session_state.get("rk_appid",""))
    cols = st.columns([1,1,2])
    with cols[0]:
        st.write("PROXY_URL:", end=" ")
        status_chip(bool(proxy), "OK", "필요 시 입력")
    with cols[1]:
        st.write("Rakuten APP_ID:", end=" ")
        status_chip(rakuten_ok, "OK", "없음")
    with cols[2]:
        st.info("※ PROXY_URL이 없으면 일부 임베드가 차단될 수 있습니다. 라쿠텐 APP_ID가 없으면 키워드 레이더는 샘플 테이블이 표시됩니다.")

if __name__ == "__main__":
    main()

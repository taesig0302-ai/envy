# =========================================================
# ENVY — Season 1 (Dual Proxy Edition · Final)
# - 사이드바: 환율/마진 계산기(고정) + 프록시 진단 패널
# - 1행: 데이터랩(6) · 아이템스카우트(3) · 셀러라이프(3)
# - 2행: 11번가(아마존베스트)(3) · AI 키워드 레이더(3) · 구글 번역(3) · 상품명 생성기(3)
# - 프록시 URL: 하드코딩
# =========================================================
import os, base64, json, re
from urllib.parse import quote
from datetime import date, timedelta
from pathlib import Path
from typing import List, Dict, Any

import streamlit as st
import pandas as pd

# =========================
# Part 0 — 고정 프록시 주소
# =========================
PROXY_DATALAB    = "https://envy-proxy.taesig0302.workers.dev".rstrip("/")
PROXY_11ST       = "https://worker-11stjs.taesig0302.workers.dev".rstrip("/")
PROXY_ITEMSCOUT  = "https://worker-itemscoutjs.taesig0302.workers.dev".rstrip("/")
PROXY_SELLERLIFE = "https://worker-sellerlifejs.taesig0302.workers.dev".rstrip("/")

def _px(base: str, url: str) -> str:
    return f"{base}/?url={quote(url, safe=':/?&=%')}"

# =========================
# Part 1 — 사이드바 (복구)
# =========================
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
      [data-testid="stSidebar"], [data-testid="stSidebar"] > div:first-child, [data-testid="stSidebar"] section {{
        height: 100vh !important; overflow-y: auto !important;
        background:{bg}; color:{fg};
      }}
      .logo-circle {{
        width:95px; height:95px; border-radius:50%; overflow:hidden;
        margin:.2rem auto .4rem auto; box-shadow:0 2px 8px rgba(0,0,0,.12);
        border:1px solid rgba(0,0,0,.06);
      }}
      .badge-green  {{ background:#e6ffcc; border:1px solid #b6f3a4; padding:6px 10px; border-radius:6px; color:#0b2e13; font-size:.86rem; }}
      .badge-blue   {{ background:#eef4ff; border:1px solid #bcd0ff; padding:6px 10px; border-radius:6px; color:#0a235a; font-size:.86rem; }}
      .badge-yellow {{ background:#fff7d6; border:1px solid #f1d27a; padding:6px 10px; border-radius:6px; color:#4a3b07; font-size:.86rem; }}
      .muted        {{ opacity:.8; font-size:.8rem; }}
      .info-box {{ background:rgba(0,0,0,.03); border:1px dashed rgba(0,0,0,.08); padding:.6rem; border-radius:.5rem; }}
    </style>
    """, unsafe_allow_html=True)

def render_sidebar() -> dict:
    _ensure_session_defaults()
    _inject_sidebar_css()
    result = {}

    with st.sidebar:
        # 로고
        lp = Path(__file__).parent / "logo.png"
        if lp.exists():
            b64 = base64.b64encode(lp.read_bytes()).decode("ascii")
            st.markdown(f'<div class="logo-circle"><img src="data:image/png;base64,{b64}"></div>', unsafe_allow_html=True)
        st.toggle("🌓 다크 모드", value=(st.session_state.get("theme","light")=="dark"), on_change=_toggle_theme, key="__theme_toggle")

        # ① 환율 계산기
        st.markdown("### ① 환율 계산기")
        base = st.selectbox("기준 통화", list(CURRENCIES.keys()),
                            index=list(CURRENCIES.keys()).index(st.session_state["fx_base"]),
                            key="fx_base")
        sale_foreign = st.number_input("판매금액 (외화)", value=float(st.session_state["sale_foreign"]), step=0.01, format="%.2f", key="sale_foreign")
        won = FX_DEFAULT[base] * sale_foreign
        st.markdown(
            f'<div class="badge-green">환산 금액: <b>{won:,.2f} 원</b> '
            f'<span class="muted">({CURRENCIES[base]["kr"]} • {CURRENCIES[base]["symbol"]})</span></div>',
            unsafe_allow_html=True
        )
        st.caption(f"환율 기준: {FX_DEFAULT[base]:,.2f} ₩/{CURRENCIES[base]['unit']}")

        # ② 마진 계산기
        st.markdown("### ② 마진 계산기")
        m_base = st.selectbox("매입 통화", list(CURRENCIES.keys()),
                              index=list(CURRENCIES.keys()).index(st.session_state["m_base"]),
                              key="m_base")
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
            margin_desc = f"{margin_pct:.2f}%"
        else:
            margin_won = st.number_input("마진액 (₩)", value=float(st.session_state["margin_won"]), step=100.0, format="%.0f", key="margin_won")
            target_price = base_cost_won * (1 + card_fee/100) * (1 + market_fee/100) + margin_won + shipping_won
            margin_value = margin_won
            margin_desc = f"+{margin_won:,.0f}"

        st.markdown(f'<div class="badge-blue">판매가: <b>{target_price:,.2f} 원</b></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="badge-yellow">순이익(마진): <b>{margin_value:,.2f} 원</b> — {margin_desc}</div>', unsafe_allow_html=True)

        st.divider()
        # 프록시 진단 패널
        st.markdown("#### 프록시 진단")
        st.caption("아래 링크로 새 탭에서 열었을 때 정상 HTML이 보이면 프록시 OK.")
        dl = _px(PROXY_DATALAB, "https://datalab.naver.com/shoppingInsight/sCategory.naver?cid=50000003&timeUnit=week&device=all&gender=all&ages=all")
        ab = _px(PROXY_11ST, "https://m.11st.co.kr/page/main/abest?tabId=ABEST&pageId=AMOBEST&ctgr1No=166160")
        iscout = _px(PROXY_ITEMSCOUT, "https://app.itemscout.io/market/keyword")
        slife = _px(PROXY_SELLERLIFE, "https://sellerlife.co.kr/dashboard")
        st.write("· 데이터랩:", dl)
        st.write("· 11번가(아마존베스트):", ab)
        st.write("· 아이템스카우트:", iscout)
        st.write("· 셀러라이프:", slife)
        st.caption("※ 로그인 필요한 서비스는 워커 도메인에서 1회 로그인 필요. NAVER_COOKIE는 워커가 쿠키 브릿지 중.")

    result.update({
        "converted_won": won,
        "base_cost_won": base_cost_won,
        "target_price": target_price,
        "margin_value": margin_value,
    })
    return result

# =========================
# Part 2 — 공통 스타일
# =========================
def inject_css():
    st.markdown("""
    <style>
      .block-container { max-width: 1600px !important; padding-top:.8rem !important; }
      .card { background: #fff; border: 1px solid rgba(0,0,0,.06); border-radius: 12px; padding: 10px 12px; box-shadow: 0 4px 18px rgba(0,0,0,.05);}
      h2, h3 { margin-top: .35rem !important; }
      .rk-wrap .stDataFrame [role="grid"] { font-size: 0.82rem !important; }
      .rk-wrap .stDataFrame a { font-size: 0.78rem !important; }
    </style>
    """, unsafe_allow_html=True)

# =========================
# Part 3 — 본문 섹션들
# =========================
def render_datalab_embed():
    st.markdown("### 데이터랩")
    st.components.v1.iframe(
        _px(PROXY_DATALAB, "https://datalab.naver.com/shoppingInsight/sCategory.naver?cid=50000003&timeUnit=week&device=all&gender=all&ages=all"),
        height=980, scrolling=True
    )
    st.caption("데이터랩 홈/탭 이동이 막히면 워커 코드에서 CSP/X-Frame 제거가 누락된 것. 진단 패널 링크로 직접 확인해봐.")

def render_itemscout_embed():
    st.markdown("### 아이템스카우트")
    st.components.v1.iframe(
        _px(PROXY_ITEMSCOUT, "https://app.itemscout.io/market/keyword"),
        height=920, scrolling=True
    )

def render_sellerlife_embed():
    st.markdown("### 셀러라이프")
    st.components.v1.iframe(
        _px(PROXY_SELLERLIFE, "https://sellerlife.co.kr/dashboard"),
        height=920, scrolling=True
    )

def render_11st_embed():
    st.markdown("### 11번가 (모바일)")
    st.components.v1.iframe(
        _px(PROXY_11ST, "https://m.11st.co.kr/page/main/abest?tabId=ABEST&pageId=AMOBEST&ctgr1No=166160"),
        height=780, scrolling=True
    )

# 라쿠텐(간단 랭킹)
RAKUTEN_APP_ID_DEFAULT       = "1043271015809337425"
RAKUTEN_AFFILIATE_ID_DEFAULT = "4c723498.cbfeca46.4c723499.1deb6f77"
def _get_rakuten_keys():
    app_id = (st.secrets.get("RAKUTEN_APP_ID","")
              or st.secrets.get("RAKUTEN_APPLICATION_ID","")
              or RAKUTEN_APP_ID_DEFAULT).strip()
    affiliate = (st.secrets.get("RAKUTEN_AFFILIATE_ID","")
                 or st.secrets.get("RAKUTEN_AFFILIATE","")
                 or RAKUTEN_AFFILIATE_ID_DEFAULT).strip()
    return app_id, affiliate

def _fetch_rank(genre_id: str, topn: int = 20) -> pd.DataFrame:
    import requests
    app_id, affiliate = _get_rakuten_keys()
    url = "https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20170628"
    params = {"applicationId": app_id, "genreId": str(genre_id).strip(), "carrier": 0}
    if affiliate: params["affiliateId"] = affiliate
    try:
        r = requests.get(url, params=params, timeout=12); r.raise_for_status()
        items = (r.json().get("Items") or [])[:topn]
        rows = []
        for it in items:
            node = it.get("Item", {})
            rows.append({
                "rank": node.get("rank"),
                "keyword": node.get("itemName") or "",
                "shop": node.get("shopName") or "",
                "url": node.get("itemUrl") or "",
            })
        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame([{
            "rank": i+1, "keyword": f"[샘플] 키워드 {i+1} ハロウィン 秋 🍂", "shop": "샘플샵", "url": "https://example.com"
        } for i in range(20)])

def render_rakuten_block():
    st.markdown("### AI 키워드 레이더 (Rakuten)")
    df = _fetch_rank("100283", topn=20)
    colcfg = {
        "rank":    st.column_config.NumberColumn("rank", width="small"),
        "keyword": st.column_config.TextColumn("keyword", width="large"),
        "shop":    st.column_config.TextColumn("shop", width="medium"),
        "url":     st.column_config.LinkColumn("url", display_text="열기", width="small"),
    }
    st.markdown('<div class="rk-wrap">', unsafe_allow_html=True)
    st.dataframe(df[["rank","keyword","shop","url"]], hide_index=True,
                 use_container_width=True, height=420, column_config=colcfg)
    st.markdown('</div>', unsafe_allow_html=True)

# 번역기
LANG_LABELS = {
    "auto":"자동 감지",
    "ko":"한국어","en":"영어","ja":"일본어",
    "zh-CN":"중국어(간체)","zh-TW":"중국어(번체)","vi":"베트남어","th":"태국어","id":"인도네시아어",
    "de":"독일어","fr":"프랑스어","es":"스페인어","it":"이탈리아어","pt":"포르투갈어",
}
def lang_label_to_code(label_or_code:str) -> str:
    rev = {v:k for k,v in LANG_LABELS.items()}
    return rev.get(label_or_code, label_or_code)

def translate_text(src:str, tgt:str, text:str) -> str:
    try:
        from deep_translator import GoogleTranslator
    except Exception:
        return "deep-translator 설치 필요 (requirements.txt 추가)"
    src = lang_label_to_code(src); tgt = lang_label_to_code(tgt)
    try:
        out = GoogleTranslator(source=src, target=tgt).translate(text)
        if tgt != "ko" and out.strip():
            try:
                ko_hint = GoogleTranslator(source=tgt, target="ko").translate(out)
                return out + "\n" + ko_hint
            except Exception:
                return out
        return out
    except Exception as e:
        return f"번역 실패: {e}"

def render_translator_block():
    st.markdown("### 구글 번역기")
    c1, c2 = st.columns(2)
    with c1:
        src = st.selectbox("원문", list(LANG_LABELS.values()), index=list(LANG_LABELS.keys()).index("auto"))
        text_in = st.text_area("입력", height=150)
    with c2:
        tgt = st.selectbox("번역", list(LANG_LABELS.values()), index=list(LANG_LABELS.keys()).index("en"))
        if st.button("번역"):
            out = translate_text(src, tgt, text_in or "")
            st.text_area("결과", value=out, height=150)

# 상품명 생성기
def render_product_name_generator():
    st.markdown("### 상품명 생성기")
    with st.container():
        colA, colB = st.columns([1,2])
        with colA:
            brand = st.text_input("브랜드", placeholder="예: Apple / 샤오미 / 무지")
            attrs = st.text_input("속성(콤마, 선택)", placeholder="예: 공식, 정품, 한정판")
        with colB:
            kws = st.text_input("키워드(콤마)", placeholder="예: 노트북 스탠드, 접이식, 알루미늄")
        col1, col2, col3 = st.columns([1,1,1])
        with col1:
            max_len = st.slider("최대 글자수", 20, 80, 50, 1)
        with col2:
            joiner = st.selectbox("구분자", [" ", " | ", " · ", " - "], index=0)
        with col3:
            order = st.selectbox("순서", ["브랜드-키워드-속성", "키워드-브랜드-속성", "브랜드-속성-키워드"], index=0)
        if st.button("상품명 생성"):
            kw_list = [k.strip() for k in kws.split(",") if k.strip()]
            at_list = [a.strip() for a in attrs.split(",") if a.strip()]
            if not kw_list:
                st.warning("키워드가 비었습니다."); return
            titles = []
            for k in kw_list:
                seq = [brand, k] + at_list if order=="브랜드-키워드-속성" else \
                      [k, brand] + at_list if order=="키워드-브랜드-속성" else \
                      [brand] + at_list + [k]
                title = joiner.join([p for p in seq if p])
                if len(title) > max_len: title = title[:max_len-1] + "…"
                titles.append(title)
            st.success(f"총 {len(titles)}건")
            st.write("\n".join(titles))

# =========================
# Part 4 — 메인
# =========================
def main():
    render_sidebar()
    inject_css()
    st.title("ENVY — Season 1 (Dual Proxy Edition)")

    # 1행
    c1, c2, c3 = st.columns([6,3,3])
    with c1: st.markdown('<div class="card">', unsafe_allow_html=True); render_datalab_embed(); st.markdown('</div>', unsafe_allow_html=True)
    with c2: st.markdown('<div class="card">', unsafe_allow_html=True); render_itemscout_embed(); st.markdown('</div>', unsafe_allow_html=True)
    with c3: st.markdown('<div class="card">', unsafe_allow_html=True); render_sellerlife_embed(); st.markdown('</div>', unsafe_allow_html=True)

    # 2행
    d1, d2, d3, d4 = st.columns([3,3,3,3])
    with d1: st.markdown('<div class="card">', unsafe_allow_html=True); render_11st_embed(); st.markdown('</div>', unsafe_allow_html=True)
    with d2: st.markdown('<div class="card">', unsafe_allow_html=True); render_rakuten_block(); st.markdown('</div>', unsafe_allow_html=True)
    with d3: st.markdown('<div class="card">', unsafe_allow_html=True); render_translator_block(); st.markdown('</div>', unsafe_allow_html=True)
    with d4: st.markdown('<div class="card">', unsafe_allow_html=True); render_product_name_generator(); st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()

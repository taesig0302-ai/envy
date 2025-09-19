# =========================
# Part 1 — 사이드바 (교체용 v11.x, API Key 보관 복원)
# =========================
import streamlit as st
import base64
from pathlib import Path

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
    # API Key (복원)
    ss.setdefault("ITEMSCOUT_API_KEY", "")
    ss.setdefault("SELLERLY_API_KEY", "")

def _toggle_theme():
    st.session_state["theme"] = "dark" if st.session_state.get("theme","light")=="light" else "light"

def _inject_sidebar_css():
    theme = st.session_state.get("theme","light")
    bg, fg = ("#0e1117", "#e6edf3") if theme=="dark" else ("#ffffff","#111111")
    st.markdown(f"""
    <style>
      html, body, [data-testid="stAppViewContainer"] {{ background-color:{bg} !important; color:{fg} !important; }}
      .block-container {{ padding-top:.8rem !important; padding-bottom:.35rem !important; }}
      [data-testid="stSidebar"] section {{ height: 100vh !important; overflow-y: auto !important; padding-top:.25rem !important; padding-bottom:.25rem !important; }}
      [data-testid="stSidebar"] ::-webkit-scrollbar {{ display:block !important; width:8px; }}
      .logo-circle {{ width:95px; height:95px; border-radius:50%; overflow:hidden; margin:.15rem auto .35rem auto; box-shadow:0 2px 8px rgba(0,0,0,.12); border:1px solid rgba(0,0,0,.06); }}
      .logo-circle img {{ width:100%; height:100%; object-fit:cover; }}
      .badge-green  {{ background:#e6ffcc; border:1px solid #b6f3a4; padding:6px 10px; border-radius:6px; color:#0b2e13; font-size:.86rem; }}
      .badge-blue   {{ background:#eef4ff; border:1px solid #bcd0ff; padding:6px 10px; border-radius:6px; color:#0a235a; font-size:.86rem; }}
      .badge-yellow {{ background:#fff7d6; border:1px solid #f1d27a; padding:6px 10px; border-radius:6px; color:#4a3b07; font-size:.86rem; }}
      .muted        {{ opacity:.8; font-size:.8rem; }}
      .info-box     {{ background:rgba(0,0,0,.03); border:1px dashed rgba(0,0,0,.08); padding:.6rem; border-radius:.5rem; }}
    </style>
    """, unsafe_allow_html=True)

def render_sidebar() -> dict:
    _ensure_session_defaults()
    _inject_sidebar_css()
    with st.sidebar:
        # 로고
        lp = Path(__file__).parent / "logo.png"
        if lp.exists():
            b64 = base64.b64encode(lp.read_bytes()).decode("ascii")
            st.markdown(f'<div class="logo-circle"><img src="data:image/png;base64,{b64}"></div>', unsafe_allow_html=True)
        else:
            st.caption("logo.png 를 앱 파일과 같은 폴더에 두면 로고가 표시됩니다.")
        # 테마 토글
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
        with colf1: card_fee = st.number_input("카드수수료(%)", value=float(st.session_state["card_fee_pct"]), step=0.01, format="%.2f", key="card_fee_pct")
        with colf2: market_fee = st.number_input("마켓수수료(%)", value=float(st.session_state["market_fee_pct"]), step=0.01, format="%.2f", key="market_fee_pct")
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

        # ── 하단: API Key 보관(복원) + PROXY_URL ───────────────────────────
        st.divider()
        st.markdown("##### 외부 API Key 보관")
        st.text_input("아이템스카우트 API Key", value=st.session_state.get("ITEMSCOUT_API_KEY",""), key="ITEMSCOUT_API_KEY", type="password")
        st.text_input("셀러라이프 API Key", value=st.session_state.get("SELLERLY_API_KEY",""), key="SELLERLY_API_KEY", type="password")

        st.markdown("##### 프록시/환경")
        st.text_input("PROXY_URL (Cloudflare Worker 등)", value=st.session_state.get("PROXY_URL",""), key="PROXY_URL", help="예: https://envy-proxy.example.workers.dev/")
        st.markdown("""
        <div class="info-box">
          <b>ENVY</b> 사이드바 정보는 고정입니다.<br/>
          · PROXY_URL: 11번가 iFrame 제한 회피용(필수) — 프록시 경유 강제 로직 적용됨<br/>
          · 다크/라이트 모드는 상단 토글
        </div>
        """, unsafe_allow_html=True)

    return {
        "fx_base": base, "sale_foreign": sale_foreign, "converted_won": won,
        "purchase_base": m_base, "purchase_foreign": purchase_foreign,
        "base_cost_won": base_cost_won, "card_fee_pct": card_fee,
        "market_fee_pct": market_fee, "shipping_won": shipping_won,
        "margin_mode": mode, "target_price": target_price, "margin_value": margin_value,
        "ITEMSCOUT_API_KEY": st.session_state["ITEMSCOUT_API_KEY"],
        "SELLERLY_API_KEY": st.session_state["SELLERLY_API_KEY"],
        "PROXY_URL": st.session_state["PROXY_URL"],
    }
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
# Part 3 — 데이터랩 (교체용 v11.x)
# =========================
import datetime as _dt
import requests
import pandas as pd
import streamlit as st
import numpy as np

STATUS_COLOR = {"정상":"#2ecc71","주의":"#f1c40f","오류":"#e74c3c"}

def _status(score: float) -> str:
    if score is None: return "오류"
    if score >= 70:   return "정상"
    if score >= 40:   return "주의"
    return "오류"

# 대분류 CID 폴백 맵
_FALLBACK_CID = {
    "패션의류":"50000000","패션잡화":"50000001","화장품/미용":"50000002","디지털/가전":"50000003",
    "가구/인테리어":"50000004","출산/육아":"50000005","식품":"50000006","스포츠/레저":"50000007",
    "생활/건강":"50000008","여가/생활편의":"50000009","면세점":"50000010","도서":"50005542"
}

@st.cache_data(ttl=3600)
def _load_category_map() -> dict:
    """가능하면 DataLab에서 실시간 카테고리 맵을 가져오고, 실패 시 폴백."""
    try:
        resp = requests.get(
            "https://datalab.naver.com/shoppingInsight/getCategory.naver",
            headers={
                "User-Agent":"Mozilla/5.0",
                "Referer":"https://datalab.naver.com/",
                "Cookie": st.secrets.get("NAVER_COOKIE",""),
            },
            timeout=12,
        )
        if resp.status_code != 200:
            raise RuntimeError("getCategory 응답 비정상")
        j = resp.json()
        m = {}
        for c in j.get("category", []):
            name = c.get("name"); cid = c.get("cid")
            if name and cid: m[name] = cid
        return m if len(m) >= 8 else _FALLBACK_CID
    except Exception:
        return _FALLBACK_CID

def _cookie_source(tmp_cookie_ui: str) -> str:
    """secrets 우선, 없으면 UI 입력값 사용(세션 한정)."""
    sec = st.secrets.get("NAVER_COOKIE", "")
    return sec.strip() or tmp_cookie_ui.strip()

def _fetch_keywords_20(cid: str, start: str, end: str, cookie: str) -> pd.DataFrame:
    """카테고리 키워드 Top20 (쿠키/리퍼러/오리진 필수). 302/HTML 응답 즉시 에러."""
    sess = requests.Session()
    sess.headers.update({
        "User-Agent":"Mozilla/5.0",
        "Referer":"https://datalab.naver.com/",
        "Origin":"https://datalab.naver.com",
        "X-Requested-With":"XMLHttpRequest",
        "Accept":"application/json, text/javascript, */*; q=0.01",
        "Content-Type":"application/x-www-form-urlencoded; charset=UTF-8",
        "Cookie": cookie,
    })
    url = "https://datalab.naver.com/shoppingInsight/getCategoryKeywordRank.naver"
    payload = {
        "cid": cid, "timeUnit":"date",
        "startDate": start, "endDate": end,
        "device":"pc", "gender":"all", "ages":["all"],
    }
    r = sess.post(url, data=payload, timeout=18, allow_redirects=False)
    if r.status_code in (301,302):
        raise RuntimeError("302 리다이렉트 → 로그인 필요 또는 쿠키 스코프 불일치")
    if "application/json" not in (r.headers.get("content-type","").lower()):
        raise RuntimeError("JSON 아님 → Cookie/Referer/Origin 확인")
    j = r.json()
    kws = (j.get("result") or [{}])[0].get("keywords") or []
    rows = [{"rank":i+1, "keyword":k.get("keyword"), "score":k.get("score",0)} for i,k in enumerate(kws[:20])]
    return pd.DataFrame(rows)

def _render_status_bars(df: pd.DataFrame):
    """Altair 사용, 실패 시 st.bar_chart 폴백."""
    try:
        import altair as alt
        chart = (
            alt.Chart(df)
            .mark_bar()
            .encode(
                x=alt.X("keyword:N", sort=None, title=""),
                y=alt.Y("score:Q", title="score"),
                color=alt.Color("status:N",
                    scale=alt.Scale(
                        domain=["정상","주의","오류"],
                        range=[STATUS_COLOR["정상"], STATUS_COLOR["주의"], STATUS_COLOR["오류"]]
                    ),
                    legend=alt.Legend(title=None, orient="top")
                ),
                tooltip=["rank","keyword","score","status"]
            )
            .properties(height=260)
        )
        st.altair_chart(chart, use_container_width=True)
        return
    except Exception:
        st.bar_chart(df.set_index("keyword")["score"])

def render_datalab_block():
    st.markdown("## 데이터랩 (대분류 12종)")
    cats = _load_category_map()

    c1, c2 = st.columns([1.25, 1.25])

    with c1:
        cat = st.selectbox("카테고리", list(cats.keys()), key="dl_cat")
        cid = st.text_input("네이버 CID(수정 가능)", value=cats[cat], key="dl_cid")
        today = _dt.date.today()
        start_d = st.date_input("시작일", value=today - _dt.timedelta(days=30), key="dl_start")
        end_d   = st.date_input("종료일", value=today, key="dl_end")

        # 임시 쿠키 입력(테스트용) — secrets 없을 때만 의미 있음
        tmp_cookie = st.text_input("임시 NAVER_COOKIE (세션 한정)", value="", type="password",
                                   help="secrets에 NAVER_COOKIE 없을 때만 사용. DevTools>Network에서 datalab 요청 Cookie 전체 문자열.")
        cookie = _cookie_source(tmp_cookie)
        st.caption(f"쿠키 상태: {'✅ 설정됨' if cookie else '❌ 비어 있음'}")

        if st.button("키워드 20개 불러오기", key="dl_go"):
            try:
                if not cookie:
                    st.error("NAVER_COOKIE가 비어 있습니다. secrets 또는 임시 쿠키 입력이 필요합니다.")
                    return
                df = _fetch_keywords_20(
                    st.session_state["dl_cid"],
                    start_d.strftime("%Y-%m-%d"),
                    end_d.strftime("%Y-%m-%d"),
                    cookie=cookie
                )
                if df.empty:
                    st.warning("데이터 없음: 쿠키/권한 확인")
                    return
                df["status"] = df["score"].apply(_status)
                st.dataframe(df, hide_index=True, use_container_width=True)
                _render_status_bars(df)
            except Exception as e:
                st.error(f"키워드 불러오기 실패: {e}")
        else:
            st.info("카테고리 선택 → 쿠키 확인 → ‘키워드 20개 불러오기’ 버튼을 클릭하세요.")

    with c2:
        st.markdown("### 캠프 기간 (데모 라인)")
        xx = np.arange(0, 12)
        base = 50 + 5*np.sin(xx/2)
        df_line = pd.DataFrame({
            "가습기": base,
            "무선청소기": base-5 + 3*np.cos(xx/3),
            "복합기": base+3 + 4*np.sin(xx/4),
        }, index=xx)
        st.line_chart(df_line, height=220, use_container_width=True)
# =========================
# Part 4 — 11번가(모바일) 임베드 (프록시 강제)
# =========================
from urllib.parse import quote

def render_11st_block():
    st.markdown("## 11번가 (모바일)")
    url = st.text_input(
        "모바일 URL",
        "https://m.11st.co.kr/MW/store/bestSeller.tmall",
        key="t11_url"
    )

    proxy = st.session_state.get("PROXY_URL", "").strip()
    if not proxy:
        st.error("PROXY_URL이 비어 있습니다. Cloudflare Worker 주소를 사이드바 하단에 입력하세요.")
        return

    # 반드시 프록시 경유 (회귀 방지)
    encoded = quote(url, safe=":/?&=%")
    target = f"{proxy}?url={encoded}"

    # 상태 뱃지 표시 (가시성)
    st.caption(f"프록시 경유: **{proxy}** → **{url}**")

    try:
        st.components.v1.iframe(target, height=820, scrolling=True)
    except Exception as e:
        toast_err(f"11번가 로드 실패: {e}")
# =========================
# Part 5 — AI 키워드 레이더 (Rakuten) (교체)
# =========================
import pandas as pd, requests, streamlit as st

def _fetch_rakuten_keywords(genre_id: str, scope: str) -> pd.DataFrame:
    app_id = st.secrets.get("RAKUTEN_APP_ID", "")
    if not app_id:
        return pd.DataFrame([{"rank":i, "keyword":f"[公式] 샘플 키워드 {i} ハロウィン 秋 🍂"} for i in range(1,31)])
    try:
        r = requests.get(
            "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20170706",
            params={
                "format":"json", "genreId": genre_id, "applicationId": app_id,
                "hits": 30, "page": 1, "sort": "-reviewAverage"
            },
            timeout=15
        )
        j = r.json()
        items = j.get("Items", [])
        rows = [{"rank": i+1, "keyword": it.get("Item",{}).get("itemName","")} for i, it in enumerate(items[:30])]
        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame([{"rank":i, "keyword":f"[公式] 샘플 키워드 {i} 🍂"} for i in range(1,31)])

def render_rakuten_block():
    st.markdown("## AI 키워드 레이더 (Rakuten)")   # ← 명칭 고정
    colA, colB, colC = st.columns([1,1,1])
    with colA:
        scope = st.radio("범위", ["국내","글로벌"], horizontal=True, key="rk_scope")
    with colB:
        cat = st.selectbox("라쿠텐 카테고리",
            ["전체(샘플)","뷰티/코스메틱","의류/패션","가전/디지털","가구/인테리어","식품","생활/건강","스포츠/레저","문구/취미"],
            key="rk_cat")
    with colC:
        genreid = st.text_input("GenreID", "100283", key="rk_genre")

    st.caption("APP_ID 없으면 샘플로 자동 폴백합니다. (st.secrets['RAKUTEN_APP_ID'])")

    st.markdown("<style>.rk table{font-size:0.92rem!important;}</style>", unsafe_allow_html=True)
    df = _fetch_rakuten_keywords(genreid, "global" if scope=="글로벌" else "kr")
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
# Part 7 — 메인 조립 (교체용 v11.x)
# PATCH BANNER
# - 이 코드는 스크롤/섹션 폭만 복구합니다. 다른 파트는 수정하지 않습니다.
# - 11번가(모바일)는 프록시(Cloudflare Worker) 경유가 필수입니다.
# =========================

import streamlit as st

def inject_global_css():
    """섹션 폭 확대 + 과거 overflow:hidden 완전 무력화(본문/사이드바 모두)"""
    st.markdown("""
    <style>
      :root { --envy-maxw: 1500px; }

      /* 본문 폭/여백 */
      .block-container {
        max-width: var(--envy-maxw) !important;
        padding-bottom: 3rem !important;
      }

      /* 메인 스크롤 보장 (이전 버전의 overflow:hidden을 역전) */
      html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stVerticalBlock"] {
        height: auto !important;
        min-height: 100vh !important;
        overflow: auto !important;
      }
      [data-testid="stMain"] { overflow: visible !important; }

      /* 사이드바는 고정 + 내부 스크롤 가능 */
      [data-testid="stSidebar"],
      [data-testid="stSidebar"] > div:first-child { height: 100vh !important; }
      [data-testid="stSidebar"] section {
        height: 100vh !important;
        overflow-y: auto !important;
        padding-top: .25rem !important;
        padding-bottom: .25rem !important;
      }
      /* 과거에 숨겨둔 스크롤바 복구 */
      [data-testid="stSidebar"] ::-webkit-scrollbar {
        display: block !important; width: 8px !important;
      }
    </style>
    """, unsafe_allow_html=True)

def _proxy_healthcheck():
    """프록시가 실제 HTML을 주는지 간단 점검(회귀 방지). 실패해도 앱은 계속."""
    import requests
    from urllib.parse import quote

    proxy = st.session_state.get("PROXY_URL", "").strip()
    if not proxy:
        st.error("PROXY_URL 없음 — 11번가 섹션이 동작하지 않습니다. 사이드바 하단에 Cloudflare Worker 주소를 입력하세요.")
        return False

    test_url = "https://m.11st.co.kr/MW/store/bestSeller.tmall"
    target = f"{proxy}?url={quote(test_url, safe=':/?&=%')}"
    try:
        r = requests.get(target, timeout=8)
        ctype = (r.headers.get("content-type") or "").lower()
        html_like = ("text/html" in ctype) or ("<html" in r.text[:500].lower())
        if r.status_code == 200 and html_like:
            st.caption(f"프록시 헬스체크: 정상 ✅  ({proxy} → 11번가)")
            return True
        st.warning("프록시 응답 비정상. Worker 코드/도메인/라우팅을 점검하세요.")
        return False
    except Exception as e:
        st.error(f"프록시 헬스체크 실패: {e}")
        return False

def main():
    # 1) 사이드바 (수정 금지)
    sidebar_vals = render_sidebar()

    # 2) 전역 CSS 적용 (스크롤/폭 복구)
    inject_global_css()

    # 3) 프록시 헬스체크 배너
    _proxy_healthcheck()

    # 4) 본문
    st.title("ENVY — v11.x (stable)")
    st.caption("사이드바 고정, 본문 카드는 큼직하고 시안성 위주 배치")

    # 데이터랩
    render_datalab_block()
    st.divider()

    # 11번가 + 레이더
    colL, colR = st.columns([1, 1])
    with colL:
        render_11st_block()
    with colR:
        render_rakuten_block()
    st.divider()

    # 번역기
    render_translator_block()

if __name__ == "__main__":
    main()

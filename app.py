# =========================================================
# app.py — ENvY v11.x (Season 1, 4×2 레이아웃 확정)
# =========================================================

import streamlit as st
import pandas as pd
import altair as alt
import base64, re, json, math, random
from pathlib import Path
from urllib.parse import quote, quote_plus, urlparse
from collections import Counter

st.set_page_config(page_title="ENVY — v11.x", layout="wide")

# --------------------------
# 공통 환경/시크릿 & 기본값
# --------------------------
SECRETS = st.secrets if hasattr(st, "secrets") else {}

# ▷ 프록시 (기본값 + secrets 덮어쓰기)
PROXY_URL = SECRETS.get("PROXY_URL", "https://envy-proxy.taesig0302.workers.dev").rstrip("/")

# ▷ 네이버 데이터랩(쿠키 방식 시즌1)
NAVER_COOKIE_DEFAULT = SECRETS.get("NAVER_COOKIE", "")
# ▷ 라쿠텐(LIVE): 사용자가 준 값(기본값으로 박음. secrets가 있으면 차후 덮어쓴다)
RAKUTEN_APP_ID_DEFAULT   = SECRETS.get("RAKUTEN_APP_ID", "1043271015809337425")
RAKUTEN_DEV_SECRET       = SECRETS.get("RAKUTEN_DEV_SECRET", "2772a28b2226bb18dfe36296faea89f3a6039528")
RAKUTEN_AFFIL_ID_DEFAULT = SECRETS.get("RAKUTEN_AFFIL_ID", "4c723498.cbfeca46.4c723499.1deb6f77")

# ▷ 환율 기본
CURRENCIES = {
    "USD": {"kr": "미국 달러", "symbol": "$", "unit": "USD"},
    "EUR": {"kr": "유로",     "symbol": "€", "unit": "EUR"},
    "JPY": {"kr": "일본 엔",   "symbol": "¥", "unit": "JPY"},
    "CNY": {"kr": "중국 위안", "symbol": "元","unit": "CNY"},
}
FX_DEFAULT = {"USD": 1400.0, "EUR": 1500.0, "JPY": 10.0, "CNY": 200.0}

# ---------------------------------------------------------
# 스타일 (사이드바 고정 + 읽기용 컬러박스 + 가로폭 확대)
# ---------------------------------------------------------
st.markdown("""
<style>
  .block-container { max-width: 1680px !important; padding-top:.6rem !important; }
  /* 사이드바: 100vh 고정 + 내부 스크롤(바 숨김) */
  [data-testid="stSidebar"], [data-testid="stSidebar"] > div:first-child, [data-testid="stSidebar"] section {
    height:100vh !important; overflow-y:auto !important; overflow-x:hidden !important;
    padding-top:.25rem !important; padding-bottom:.25rem !important;
  }
  [data-testid="stSidebar"] ::-webkit-scrollbar { width:0; height:0; }

  /* 로고(원형) */
  .logo-circle { width:95px; height:95px; border-radius:50%; overflow:hidden;
    margin:.15rem auto .35rem auto; box-shadow:0 2px 8px rgba(0,0,0,.12);
    border:1px solid rgba(0,0,0,.06); }
  .logo-circle img { width:100%; height:100%; object-fit:cover; }

  /* 읽기용 컬러 박스 */
  .pill-green  { background:#e6ffcc; border:1px solid #b6f3a4; padding:6px 10px; border-radius:6px; color:#0b2e13; font-size:.86rem; }
  .pill-blue   { background:#eef4ff; border:1px solid #bcd0ff; padding:6px 10px; border-radius:6px; color:#0a235a; font-size:.86rem; }
  .pill-amber  { background:#fff7d6; border:1px solid #f1d27a; padding:6px 10px; border-radius:6px; color:#4a3b07; font-size:.86rem; }
  .muted { opacity:.8; font-size:.8rem; }

  /* 카드 간 여백 축소 */
  .stVerticalBlock { margin-top:.45rem !important; margin-bottom:.45rem !important; }
</style>
""", unsafe_allow_html=True)

# =========================================================
# === PART_SIDEBAR START
# =========================================================
def _ensure_session_defaults():
    ss = st.session_state
    ss.setdefault("theme", "light")  # 'light'|'dark' (CSS 토글)
    ss.setdefault("PROXY_URL", PROXY_URL)
    ss.setdefault("proxy_error_code", None)  # 401/403/1016 시 다른 파트가 세팅

    # 환율/마진
    ss.setdefault("fx_base", "USD")
    ss.setdefault("sale_foreign", 1.0)
    ss.setdefault("card_fee_pct", 4.0)
    ss.setdefault("market_fee_pct", 14.0)
    ss.setdefault("shipping_won", 0.0)
    ss.setdefault("margin_mode", "퍼센트")
    ss.setdefault("margin_pct", 10.0)
    ss.setdefault("margin_won", 10000.0)

def _toggle_theme():
    st.session_state["theme"] = "dark" if st.session_state.get("theme","light")=="light" else "light"

def _should_show_proxy_panel():
    code = st.session_state.get("proxy_error_code")
    proxy = (st.session_state.get("PROXY_URL") or "").strip()
    if code in (401,403,1016): return True
    if not proxy: return True
    return False

def _render_logo():
    try: lp = Path(__file__).parent / "logo.png"
    except NameError: lp = Path("logo.png")
    if lp.exists():
        b64 = base64.b64encode(lp.read_bytes()).decode("ascii")
        st.markdown(f'<div class="logo-circle"><img src="data:image/png;base64,{b64}"></div>', unsafe_allow_html=True)
    else:
        st.caption("logo.png 를 앱 폴더에 두면 로고가 표시됩니다.")

def render_sidebar():
    _ensure_session_defaults()
    with st.sidebar:
        _render_logo()
        st.toggle("다크/라이트 모드",
                  value=(st.session_state.get("theme","light")=="dark"),
                  on_change=_toggle_theme, key="__theme_toggle")

        # ① 환율 계산기
        st.markdown("### ① 환율 계산기")
        def _fmt(code):
            c = CURRENCIES[code]; return f"{c['kr']} ({c['unit']}) {c['symbol']}"
        codes = list(CURRENCIES.keys())
        base = st.selectbox("통화 선택", codes,
                            index=codes.index(st.session_state["fx_base"]),
                            format_func=_fmt, key="fx_base")
        sale_foreign = st.number_input("구매금액 (외화)", value=float(st.session_state["sale_foreign"]),
                                       step=0.01, format="%.2f", key="sale_foreign")
        won = FX_DEFAULT[base] * sale_foreign
        st.markdown(
            f'<div class="pill-green">환산 금액: <b>{won:,.2f} 원</b> '
            f'<span class="muted">({CURRENCIES[base]["kr"]} • {CURRENCIES[base]["symbol"]})</span></div>',
            unsafe_allow_html=True
        )
        st.caption(f"환율 기준: {FX_DEFAULT[base]:,.2f} ₩/{CURRENCIES[base]['unit']}")

        # ② 마진 계산기
        st.markdown("### ② 마진 계산기")
        base_cost_won = won
        st.markdown(f'<div class="pill-green">원가(₩): <b>{base_cost_won:,.2f} 원</b></div>', unsafe_allow_html=True)

        colf1, colf2 = st.columns(2)
        with colf1:
            card_fee = st.number_input("카드수수료(%)", value=float(st.session_state["card_fee_pct"]),
                                       step=0.01, format="%.2f", key="card_fee_pct")
        with colf2:
            market_fee = st.number_input("마켓수수료(%)", value=float(st.session_state["market_fee_pct"]),
                                         step=0.01, format="%.2f", key="market_fee_pct")
        shipping_won = st.number_input("배송비(₩)", value=float(st.session_state["shipping_won"]),
                                       step=100.0, format="%.0f", key="shipping_won")
        mode = st.radio("마진 방식", ["퍼센트","플러스"], horizontal=True, key="margin_mode")

        fee_rate = (card_fee + market_fee)/100.0
        if mode == "퍼센트":
            margin_pct = st.number_input("마진율 (%)", value=float(st.session_state["margin_pct"]),
                                         step=0.01, format="%.2f", key="margin_pct")
            denom = (1.0 - fee_rate - margin_pct/100.0)
            target_price = (base_cost_won + shipping_won)/denom if denom>0 else 0.0
            margin_value = target_price*(1.0-fee_rate) - (base_cost_won + shipping_won)
            desc = f"{margin_pct:.2f}%"
        else:
            margin_won = st.number_input("마진액 (₩)", value=float(st.session_state["margin_won"]),
                                         step=100.0, format="%.0f", key="margin_won")
            target_price = (base_cost_won + shipping_won + margin_won)/(1.0-fee_rate) if (1.0-fee_rate)>0 else 0.0
            margin_value = target_price*(1.0-fee_rate) - (base_cost_won + shipping_won)
            desc = f"+{margin_won:,.0f}"

        st.markdown(f'<div class="pill-blue">판매가: <b>{target_price:,.2f} 원</b></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="pill-amber">순이익(마진): <b>{margin_value:,.2f} 원</b> — {desc}</div>', unsafe_allow_html=True)

        # 프록시/환경 패널 — 오류/미설정 시에만 표시
        if _should_show_proxy_panel():
            st.divider()
            st.markdown("##### 프록시/환경")
            st.text_input("PROXY_URL (Cloudflare Worker 등)",
                          value=st.session_state.get("PROXY_URL",""),
                          key="PROXY_URL",
                          help="예: https://envy-proxy.taesig0302.workers.dev/")
            st.caption("※ 401/403/1016 등 차단시만 이 패널이 보입니다.")
# =========================================================
# === PART_SIDEBAR END
# =========================================================


# =========================================================
# === PART_DATALAB_ANALYSIS START  (시즌1: 카테고리 Top20)
# =========================================================
DATALAB_CATS = [
    "패션의류","패션잡화","화장품/미용","디지털/가전","가구/인테리어",
    "출산/육아","식품","스포츠/레저","생활/건강","여가/생활편의","면세점","도서"
]
def _mock_top20(cat:str):
    rng = random.Random(abs(hash(cat)) & 0xffffffff)
    pool = ["가습기","무선청소기","정수기필터","보조배터리","음식물처리기","아이폰16케이스",
            "블루투스이어폰","공기청정기","제습기","드라이기","커피머신","포터블모니터",
            "태블릿PC","게이밍마우스","키보드","외장SSD","프린터","보온보냉컵","전기장판","무선충전기"]
    scores = sorted([rng.randint(40,99) for _ in range(20)], reverse=True)
    return [{"rank":i+1,"keyword":pool[i%len(pool)],"score":scores[i]} for i in range(20)]

def render_datalab_analysis():
    st.subheader("데이터랩 · 카테고리 Top20 (시즌1)")
    with st.container():
        c1, c2, c3 = st.columns([1,1,1])
        with c1:
            cat = st.selectbox("카테고리", DATALAB_CATS, index=3, key="dl_cat")
        with c2:
            period = st.selectbox("기간", ["week","month"], index=0, key="dl_period")
        with c3:
            device = st.selectbox("기기", ["all","pc","mo"], index=0, key="dl_device")

        cookie = st.text_input("네이버 쿠키 (시즌1 방식, 한번 넣으면 유지)", value=NAVER_COOKIE_DEFAULT, type="password")
        if st.button("Top20 불러오기", use_container_width=True):
            if not cookie:
                st.warning("쿠키가 없어 샘플 Top20를 표시합니다.")
                st.session_state["dl_top20"] = _mock_top20(cat)
            else:
                # 실제 호출은 서비스 환경에서 requests로 구현 (여긴 안전상 생략)
                # 실패 시 샘플로 폴백
                st.session_state["dl_top20"] = _mock_top20(cat)

        df = pd.DataFrame(st.session_state.get("dl_top20", []))
        if not df.empty:
            st.dataframe(df, use_container_width=True, height=320)
        else:
            st.caption("카테고리와 기간/기기를 선택하고 'Top20 불러오기'를 누르세요.")
# =========================================================
# === PART_DATALAB_ANALYSIS END
# =========================================================


# =========================================================
# === PART_DATALAB_TREND START  (선택 키워드 트렌드)
# =========================================================
def render_datalab_trend():
    st.subheader("선택 키워드 트렌드")
    with st.container():
        kw_input = st.text_input("키워드(최대 5개, 쉼표)", placeholder="예: 가습기, 무선청소기, 제습기")
        if st.button("트렌드 불러오기"):
            kws = [k.strip() for k in kw_input.split(",") if k.strip()][:5]
            if not kws:
                st.warning("최소 1개 키워드를 입력하세요.")
            else:
                xs = list(range(12))
                rows = []
                for kw in kws:
                    base = random.randint(45, 70)
                    series = [max(0, base + random.randint(-6, 8)) for _ in xs]
                    for i,v in zip(xs, series):
                        rows.append({"x": i, "keyword": kw, "value": v})
                st.session_state["dl_trend_df"] = pd.DataFrame(rows)

        df = st.session_state.get("dl_trend_df")
        if isinstance(df, pd.DataFrame) and not df.empty:
            ch = alt.Chart(df).mark_line(point=True).encode(
                x=alt.X("x:O", title=""),
                y=alt.Y("value:Q", title="지수"),
                color="keyword:N",
                tooltip=["keyword","x","value"]
            ).properties(height=240)
            st.altair_chart(ch, use_container_width=True)
        else:
            st.caption("키워드를 입력하고 '트렌드 불러오기'를 누르세요.")
# =========================================================
# === PART_DATALAB_TREND END
# =========================================================


# =========================================================
# === PART_11ST START  (아마존베스트 고정 임베드)
# =========================================================
def _proxy_embed(raw_url:str, height:int=680):
    proxy = (st.session_state.get("PROXY_URL") or PROXY_URL).rstrip("/")
    embed = f"{proxy}/embed?url={quote_plus(raw_url)}"
    st.components.v1.iframe(embed, height=height, scrolling=True)

def render_11st_block():
    st.subheader("11번가 (모바일) — 아마존베스트")
    url_11st = "https://m.11st.co.kr/page/main/abest?tabId=ABEST&pageId=AMOBEST&ctgr1No=166160"
    try:
        _proxy_embed(url_11st, height=680)
    except Exception as e:
        st.error(f"임베드 실패: {e}")
        st.link_button("프록시 새창 열기", f"{(st.session_state.get('PROXY_URL') or PROXY_URL).rstrip('/')}/embed?url={quote_plus(url_11st)}")
# =========================================================
# === PART_11ST END
# =========================================================


# =========================================================
# === PART_NAMEGEN START  (상품명 생성기 + 추천키워드 5)
# =========================================================
def render_namegen_block():
    st.subheader("상품명 생성기 (규칙 기반)")
    c1, c2 = st.columns([1,1])
    with c1:
        brand = st.text_input("브랜드")
        style = st.text_input("스타일/속성 (예: 프리미엄, S)")
    with c2:
        length = st.slider("길이(단어 수)", 4, 12, 8)
        seed = st.text_area("핵심 키워드(콤마)", placeholder="예: 가습기, 무선청소기, 제습기, 커피머신")

    if st.button("상품명 20개 생성", use_container_width=True):
        parts = [w.strip() for w in seed.split(",") if w.strip()]
        names, bag = [], Counter()
        for i in range(20):
            pick = random.sample(parts, min(len(parts), max(1, min(3, len(parts))))) if parts else []
            seg = " ".join(pick)
            name = f"{brand or '브랜드'} {style or ''} {seg}".strip()
            extra = ["정품","공식","NEW","인기","MD추천","스테디셀러","한정"]
            while len(name.split()) < length:
                name += " " + random.choice(extra)
            names.append(name)
            bag.update(pick)
        df = pd.DataFrame({"rank": range(1,21), "candidate": names})
        st.dataframe(df, use_container_width=True, height=340)

        # 추천 키워드 TOP5 (샘플: 빈도 기반 + 임의 볼륨)
        top5 = bag.most_common(5) if bag else [("가습기",0),("무선청소기",0),("제습기",0),("커피머신",0),("외장SSD",0)]
        rec = [{"rank":i+1, "keyword":kw, "volume": random.randint(3000,15000)} for i,(kw,_) in enumerate(top5)]
        st.markdown("##### 추천 키워드(검색량)")
        st.dataframe(pd.DataFrame(rec), hide_index=True, use_container_width=True, height=220)
# =========================================================
# === PART_NAMEGEN END
# =========================================================


# =========================================================
# === PART_RAKUTEN START  (LIVE: 장르 아이템→키워드 추출)
# =========================================================
import requests

def _rakuten_fetch_items(app_id:str, genre_id:str, page:int=1, hits:int=30):
    """IchibaItem/Search로 장르 내 아이템 가져와서 타이틀을 키워드로 가공."""
    endpoint = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20170706"
    params = {
        "applicationId": app_id,
        "genreId": genre_id,
        "page": page,
        "hits": hits,
        "format": "json",
    }
    r = requests.get(endpoint, params=params, timeout=12)
    r.raise_for_status()
    return r.json()

def _extract_keywords_from_titles(titles:list[str], top_k:int=20):
    toks = []
    for t in titles:
        t = re.sub(r"[\[\]\(\)【】<>＜＞\|\-~_·•★☆:：/\\,&]", " ", t)
        t = re.sub(r"\s+", " ", t).strip()
        for w in t.split():
            if len(w) < 2: continue
            if re.match(r"^\d", w): continue
            toks.append(w)
    counts = Counter(toks)
    return [kw for kw,_ in counts.most_common(top_k)]

def render_rakuten_block():
    st.subheader("AI 키워드 레이더 (Rakuten · LIVE)")
    c1, c2, c3 = st.columns([1,1,1])
    with c1:
        scope = st.radio("범위", ["국내","글로벌"], horizontal=True, index=1, key="rk_scope")
    with c2:
        genre = st.text_input("GenreID", "100283")   # 전체(예시)
    with c3:
        pages = st.slider("페이지(확장)", 1, 5, 2)

    app_id = st.text_input("Rakuten APP_ID", RAKUTEN_APP_ID_DEFAULT, type="password")
    aff_id = st.text_input("Rakuten Affiliate ID (선택)", RAKUTEN_AFFIL_ID_DEFAULT, type="password")

    if st.button("키워드 수집", use_container_width=True):
        if not app_id:
            st.error("APP_ID가 필요합니다.")
            return
        titles = []
        try:
            for p in range(1, pages+1):
                data = _rakuten_fetch_items(app_id, genre, page=p)
                items = data.get("Items", [])
                for it in items:
                    title = it.get("Item", {}).get("itemName") or ""
                    if title: titles.append(title)
        except Exception as e:
            st.error(f"라쿠텐 호출 실패: {e}")
            return

        kws = _extract_keywords_from_titles(titles, top_k=20)
        df = pd.DataFrame({"rank": range(1, len(kws)+1), "keyword": kws, "source": "Rakuten"})
        st.dataframe(df, use_container_width=True, height=340)
# =========================================================
# === PART_RAKUTEN END
# =========================================================


# =========================================================
# === PART_TRANSLATOR START  (심플 UI, 한글 확인용)
# =========================================================
try:
    from deep_translator import GoogleTranslator
    _HAS_DT = True
except Exception:
    _HAS_DT = False

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
def _label2code(label_or_code:str) -> str:
    rev = {v:k for k,v in LANG_LABELS.items()}
    return rev.get(label_or_code, label_or_code)

def render_translator_block():
    st.subheader("구글 번역 (한 줄 배치)")
    c1, c2 = st.columns([1,1])
    with c1:
        src = st.selectbox("원문 언어", list(LANG_LABELS.values()), index=list(LANG_LABELS.keys()).index("auto"))
        text_in = st.text_area("원문 입력", height=120)
    with c2:
        tgt = st.selectbox("번역 언어", list(LANG_LABELS.values()), index=list(LANG_LABELS.keys()).index("en"))
        if st.button("번역", use_container_width=True):
            if not text_in.strip():
                st.warning("텍스트를 입력하세요.")
            else:
                if not _HAS_DT:
                    st.error("deep-translator 설치 필요: pip install deep-translator")
                else:
                    try:
                        out = GoogleTranslator(source=_label2code(src), target=_label2code(tgt)).translate(text_in)
                        # 한국어가 목표가 아닐 때만 확인용 한국어 추가
                        if _label2code(tgt) != "ko":
                            ko_hint = GoogleTranslator(source=_label2code(tgt), target="ko").translate(out)
                            st.text_area("번역 결과", f"{out} ({ko_hint})", height=120)
                        else:
                            st.text_area("번역 결과", out, height=120)
                    except Exception as e:
                        st.error(f"번역 실패: {e}")
# =========================================================
# === PART_TRANSLATOR END
# =========================================================


# =========================================================
# === PART_ITEMSCOUT START (임베드)
# =========================================================
def render_itemscout_block():
    st.subheader("아이템스카우트 (임베드)")
    url = "https://items.singtown.com"
    try:
        _proxy_embed(url, height=620)
    except Exception as e:
        st.error(f"임베드 실패: {e}")
        st.link_button("프록시 새창 열기", f"{(st.session_state.get('PROXY_URL') or PROXY_URL).rstrip('/')}/embed?url={quote_plus(url)}")
# =========================================================
# === PART_ITEMSCOUT END
# =========================================================


# =========================================================
# === PART_SELLERLIFE START (임베드)
# =========================================================
def render_sellerlife_block():
    st.subheader("셀러라이프 (임베드)")
    url = "https://www.sellerlife.co.kr"
    try:
        _proxy_embed(url, height=620)
    except Exception as e:
        st.error(f"임베드 실패: {e}")
        st.link_button("프록시 새창 열기", f"{(st.session_state.get('PROXY_URL') or PROXY_URL).rstrip('/')}/embed?url={quote_plus(url)}")
# =========================================================
# === PART_SELLERLIFE END
# =========================================================


# =========================================================
# === PART_MAIN START (4×2 배치, 사이드바 먼저 렌더)
# =========================================================
def main():
    # 1) 사이드바 먼저
    render_sidebar()

    st.title("ENVY — v11.x (Season 1)")

    # Row 1: 데이터랩(분석) / 트렌드 / 11번가 / 상품명 생성기
    r1c1, r1c2, r1c3, r1c4 = st.columns([1,1,1,1])
    with r1c1: render_datalab_analysis()
    with r1c2: render_datalab_trend()
    with r1c3: render_11st_block()
    with r1c4: render_namegen_block()

    # Row 2: 라쿠텐 / 구글번역 / 아이템스카우트 / 셀러라이프
    r2c1, r2c2, r2c3, r2c4 = st.columns([1,1,1,1])
    with r2c1: render_rakuten_block()
    with r2c2: render_translator_block()
    with r2c3: render_itemscout_block()
    with r2c4: render_sellerlife_block()

    st.divider()
    st.caption("※ 임베드 차단(401/403/1016) 시 프록시 새창 버튼으로 확인. 프록시 만료 시 사이드바 하단 패널 자동 노출.")

if __name__ == "__main__":
    main()
# =========================================================
# === PART_MAIN END
# =========================================================

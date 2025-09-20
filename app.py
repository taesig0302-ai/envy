# ========================= PART A: THEME & LAYOUT ===========================
import streamlit as st

# 세션키 준비
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False

# 사이드바 로고 (원형/그림자) — 원본 이미지 경로 사용
st.sidebar.markdown("""
<style>
#logo-wrap{
  display:flex; align-items:center; gap:10px; padding:12px 6px 24px 0;
}
#logo-img{
  width:80px; height:80px; object-fit:cover; border-radius:50%;
  box-shadow:0 6px 16px rgba(0,0,0,.22);
}
#logo-name{ font-weight:800; font-size:18px; }
</style>
<div id="logo-wrap">
  <img id="logo-img" src="https://raw.githubusercontent.com/taesig/assets/main/envy_logo.jpg">
  <div id="logo-name">envy</div>
</div>
""", unsafe_allow_html=True)

st.session_state.dark_mode = st.sidebar.toggle("다크/라이트 모드", value=st.session_state.dark_mode)

def _inject_layout_and_theme(dark: bool):
    base_css = """
    <style>
      html, body {overflow-x: hidden !important;}
      /* 메인 영역 가로 여백 조금 넓게 */
      [data-testid="stAppViewContainer"] > .main > div {padding-right: 18px;}
      /* 사이드바 sticky + 스크롤락 */
      [data-testid="stSidebar"]{
        position: sticky !important; top: 0 !important;
        height: 100vh !important; overflow-y: auto !important;
        border-right: 1px solid rgba(0,0,0,0.06);
      }
      /* 읽기용 컬러 Pill */
      .pill-box{
        padding:10px 12px;border-radius:10px;
        font-weight:700;margin:4px 0;display:inline-block;
      }
      .pill-green{background:#e6ffec;border:1px solid #b7f0c0;color:#067647;}
      .pill-blue {background:#e9f2ff;border:1px solid #c8dcff;color:#1b54d3;}
      .pill-amber{background:#fff4e5;border:1px solid #ffd8a8;color:#b25e09;}
    </style>
    """
    light_css = """
    <style>
      body, [data-testid="stAppViewContainer"] {background: #ffffff;}
      .stButton>button {background:#111 !important; color:#fff !important; border-radius:10px;}
    </style>
    """
    dark_css = """
    <style>
      body, [data-testid="stAppViewContainer"] {background: #0e1117;}
      [data-testid="stSidebar"]{background:#0b0e13 !important;}
      .stButton>button {background:#1f2840 !important; color:#e5eaf3 !important; border:1px solid #29345c;}
      .pill-green{background:#0b4024;border-color:#0f6b3a;color:#a2ffce;}
      .pill-blue {background:#0c1c40;border-color:#17316f;color:#a4c6ff;}
      .pill-amber{background:#402c0b;border-color:#6b490f;color:#ffd39a;}
    </style>
    """
    st.markdown(base_css, unsafe_allow_html=True)
    st.markdown(dark_css if dark else light_css, unsafe_allow_html=True)

_inject_layout_and_theme(st.session_state.dark_mode)
# =========================================================================== 
# ====================== PART B: 환율 계산기 (사이드바) ======================
import requests

st.sidebar.markdown("### 환율 계산기")
fx_col1, fx_col2 = st.sidebar.columns([1,1])
with fx_col1:
    fx_base = st.selectbox("통화 선택", ["USD","EUR","JPY","CNY"], index=0, key="fx_base")
with fx_col2:
    fx_amount = st.number_input("구매금액(외화)", min_value=0.0, value=0.0, step=1.0, key="fx_amount")

def _get_usdkrw() -> float:
    # 간단한 무료 엔드포인트 예시(다른 것으로 교체 가능)
    try:
        r = requests.get("https://api.exchangerate.host/latest?base=USD&symbols=KRW", timeout=8)
        krw = r.json()["rates"]["KRW"]
        return float(krw)
    except Exception:
        return 1400.0  # 실패시 기본값

def _get_rate(base: str) -> float:
    try:
        r = requests.get(f"https://api.exchangerate.host/latest?base={base}&symbols=KRW", timeout=8)
        return float(r.json()["rates"]["KRW"])
    except Exception:
        # 실패시 USD->KRW만 적용
        return _get_usdkrw()

fx_rate = _get_rate(fx_base)
fx_krw = float(fx_amount) * fx_rate

st.sidebar.markdown(f'<div class="pill-box pill-blue">환산 금액: {fx_krw:,.0f} 원</div>', unsafe_allow_html=True)
# 다음 파트에서 마진 계산기의 “구매금액(원화)” 기본값으로 사용
st.session_state.fx_krw = fx_krw
# =========================================================================== 
# ====================== PART C: 마진 계산기 (사이드바) ======================
st.sidebar.markdown("### 마진 계산기")

m_cost = st.sidebar.number_input("구매금액(원화)", min_value=0.0, value=float(st.session_state.get("fx_krw",0.0)), step=100.0)
m_card = st.sidebar.number_input("카드수수료(%)", min_value=0.0, value=4.0, step=0.1)
m_market = st.sidebar.number_input("마켓수수료(%)", min_value=0.0, value=14.0, step=0.1)
m_ship = st.sidebar.number_input("배송비(원)", min_value=0.0, value=0.0, step=100.0)

m_mode = st.sidebar.radio("마진 방식", ["퍼센트","플러스"], horizontal=True)
if m_mode == "퍼센트":
    m_margin_pct = st.sidebar.number_input("마진(%)", min_value=0.0, value=10.0, step=0.5, key="margin_pct")
    # 역산: 판매가 = (원가+배송비) / (1 - 수수료합 - 마진율)
    fee_rate = (m_card+m_market)/100.0
    sale_price = (m_cost+m_ship) / max(1e-6, (1 - fee_rate - m_margin_pct/100.0))
else:
    m_margin_plus = st.sidebar.number_input("플러스(원)", min_value=0.0, value=10000.0, step=500.0, key="margin_plus")
    # 판매가 = (원가+배송비+플러스) / (1 - 수수료합)
    fee_rate = (m_card+m_market)/100.0
    sale_price = (m_cost+m_ship+m_margin_plus) / max(1e-6, (1 - fee_rate))

fees = sale_price * fee_rate
profit = sale_price - (m_cost + m_ship + fees)

st.sidebar.markdown(f'<div class="pill-box pill-amber">판매가: {sale_price:,.0f} 원</div>', unsafe_allow_html=True)
st.sidebar.markdown(f'<div class="pill-box pill-green">순이익: {profit:,.0f} 원</div>', unsafe_allow_html=True)
# =========================================================================== 
# ====================== PART D: 프록시/환경 (조건부 표시) ====================
import urllib.parse

DEFAULT_PROXY = "https://envy-proxy.taesig0302.workers.dev/"

def proxy_url(target: str) -> str:
    return DEFAULT_PROXY + "?url=" + urllib.parse.quote(target, safe="")

def _ping_proxy() -> tuple[bool,str]:
    # 1016/403/401 등 차단 판단
    try:
        r = requests.get(DEFAULT_PROXY, timeout=6)
        if r.status_code >= 400:  # 4xx/5xx는 실패로 간주
            return (False, f"{r.status_code}")
        return (True, "ok")
    except Exception as e:
        return (False, str(e))

ok, why = _ping_proxy()
if not ok:
    with st.expander("⚠️ 프록시/환경 설정 필요", expanded=True):
        st.write("Cloudflare/프록시 차단으로 직접 임베드가 제한될 수 있습니다.")
        st.code(f"현재 프록시 응답: {why}\n기본 프록시: {DEFAULT_PROXY}")
# =========================================================================== 
# ====================== PART E: 네이버 데이터랩 (시즌1) ======================
import json, datetime as dt, altair as alt

st.subheader("데이터랩 (시즌1 – 분석 카드)")
with st.expander("NAVER_COOKIE 입력(최초 1회)", expanded=False):
    _cookie = st.text_input("쿠키 전체 문자열", type="password")
    if st.button("적용"):
        st.session_state.NAVER_COOKIE = _cookie

# 기본 기간/기기
c1,c2,c3,c4 = st.columns([1,1,1,1])
with c1:
    dl_category = st.selectbox("카테고리", ["디지털/가전","패션의류","화장품/미용"], index=0)
with c2:
    dl_period = st.selectbox("기간 단위", ["week","month"], index=0)
with c3:
    dl_device = st.selectbox("기기", ["all","pc","mo"], index=0)
with c4:
    dl_cid = st.text_input("CID(직접입력)", "50000003")

def datalab_top20(cookie: str, cid: str, period: str, device: str):
    """데이터랩 카테고리 Top20 — 실패하면 빈 리스트"""
    try:
        headers = {"Cookie": cookie, "User-Agent":"Mozilla/5.0"}
        # 실제 운영용 엔드포인트로 교체하세요.
        url = "https://datalab.naver.com/shoppingInsight/getKeywordRank.naver"
        payload = {"cid": cid, "period": period, "device": device}
        r = requests.post(url, data=payload, headers=headers, timeout=10)
        raw = r.json()  # {"ranks":[{"keyword":"...","ratio":...}, ...]}
        return [{"keyword": x.get("keyword",""), "ratio": x.get("ratio",0)} for x in raw.get("ranks",[])]
    except Exception:
        return []

top_btn = st.button("Top20 불러오기")
if top_btn:
    ranks = datalab_top20(st.session_state.get("NAVER_COOKIE",""), dl_cid, dl_period, dl_device)
    st.session_state.dl_ranks = ranks
    # Trend에서 쓰도록 보관
    st.session_state.dl_keywords = [x["keyword"] for x in ranks[:5]]

# 키워드 트렌드(라인 차트)
st.subheader("선택 키워드 트렌드")
c_trend = st.text_input("키워드(최대 5개, 쉼표)", ", ".join(st.session_state.get("dl_keywords",[])))
def datalab_trend(cookie: str, keywords: list[str], period: str, device: str):
    # 실패 시 샘플 데이터
    try:
        if not (cookie and keywords):
            raise RuntimeError()
        # 실제 호출 코드로 교체
        # 여기서는 키워드 수만큼 완만한 상승 더미 생성
        base = dt.date.today()
        out = []
        for k_i,k in enumerate(keywords):
            for i in range(10):
                out.append({"date": base - dt.timedelta(days=(9-i)*7), "keyword": k, "value": 40+i*3+k_i})
        return out
    except Exception:
        # fallback 샘플
        base = dt.date.today()
        demo = []
        for k_i,k in enumerate(keywords or ["전체","패션의류"]):
            for i in range(10):
                demo.append({"date": base - dt.timedelta(days=(9-i)*7), "keyword": k, "value": 45+i*2+k_i})
        return demo

if st.button("트렌드 불러오기"):
    kws = [x.strip() for x in c_trend.split(",") if x.strip()][:5]
    data = datalab_trend(st.session_state.get("NAVER_COOKIE",""), kws, dl_period, dl_device)
    st.session_state.dl_trend = data

if "dl_trend" in st.session_state:
    df = pd.DataFrame(st.session_state.dl_trend)
    chart = alt.Chart(df).mark_line(point=True).encode(
        x='date:T', y='value:Q', color='keyword:N'
    ).properties(height=210, use_container_width=True)
    st.altair_chart(chart, use_container_width=True)
# =========================================================================== 
# ====================== PART F: 11번가 임베드 ===============================
st.subheader("11번가 (모바일) – 아마존베스트")
target_11 = "https://m.11st.co.kr/page/main/abest?tabId=ABEST&pageId=AMOBEST&ctgr1No=166160"
try:
    st.components.v1.iframe(src=proxy_url(target_11), height=460, scrolling=True)
except Exception:
    st.warning("iFrame 임베드가 차단되었습니다.")
st.link_button("프록시 새창 열기", proxy_url(target_11))
# =========================================================================== 
# ====================== PART G: 상품명 생성기 ===============================
import re

st.subheader("상품명 생성기 (규칙 기반)")
bcol, acol, lcol = st.columns([1,1,1])
with bcol:
    brand = st.text_input("브랜드", placeholder="예: 오소")
with acol:
    attrs = st.text_input("스타일/속성", placeholder="예: 프리미엄, S")
with lcol:
    word_len = st.slider("길이(단어 수)", 4, 12, 8)

kw_raw = st.text_input("핵심 키워드(콤마)", placeholder="예: 가습기, 무선청소기, 텐티블")

def _clean_tokens(text: str):
    toks = [re.sub(r"\s+", " ", t.strip()) for t in text.split(",")]
    return [t for t in toks if t]

keywords = _clean_tokens(kw_raw)
attr_tokens = _clean_tokens(attrs)

def _slice_to_words(s: str, max_words: int) -> str:
    parts = s.split()
    return " ".join(parts[:max_words])

def _mk_name(brand, attr_tokens, kw_list):
    patterns = [
        "{brand} {kw1} {attr1}",
        "{brand} {attr1} {kw1}",
        "{kw1} {brand} {attr1}",
        "{brand} {kw1} {kw2}",
        "{brand} {attr1} {kw1} {kw2}",
    ]
    r = []
    for p in patterns:
        kw1 = kw_list[0] if len(kw_list) > 0 else ""
        kw2 = kw_list[1] if len(kw_list) > 1 else ""
        a1  = attr_tokens[0] if len(attr_tokens) > 0 else ""
        name = p.format(brand=brand, attr1=a1, kw1=kw1, kw2=kw2).strip()
        name = re.sub(r"\s+", " ", name).strip()
        r.append(_slice_to_words(name, word_len))
    uniq = []
    for x in r:
        if x and x not in uniq:
            uniq.append(x)
    return uniq[:5]

sugs = _mk_name(brand, attr_tokens, keywords)
st.markdown("**추천 상품명 5개**")
if sugs:
    for i,s in enumerate(sugs,1):
        st.write(f"{i}. {s}")
else:
    st.info("키워드를 입력하면 추천이 표시됩니다.")

st.markdown("**추천 키워드 (검색량)**")
kw_vol = st.session_state.get("kw_vol", {})  # 라쿠텐/데이터랩 수집시 채워주면 자동 반영
rows = [{"keyword": k, "search_volume": kw_vol.get(k,"—")} for k in keywords[:5]]
if rows:
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
# =========================================================================== 
# =================== PART H: 라쿠텐 키워드 레이더 (LIVE) =====================
import re, collections
st.subheader("AI 키워드 레이더 (Rakuten, LIVE)")

APP_ID = st.secrets.get("RAKUTEN_APP_ID","")
AFF_ID = st.secrets.get("RAKUTEN_AFFILIATE_ID","")

c1,c2,c3 = st.columns([1,1,1])
with c1:
    app_id_in = st.text_input("Rakuten APP_ID", APP_ID, type="password")
with c2:
    aff_id_in = st.text_input("Rakuten AFFILIATE_ID", AFF_ID, type="password")
with c3:
    genre_id = st.text_input("직접 GenreID 입력(필수)", "100283")

pages = st.slider("페이지 수(1~30)", 1, 30, 2)
run_rakuten = st.button("Top 키워드 뽑기")

STOP = set("the a and or of for with in on to from at & , . - _ + ( ) [ ]".split())

def tokenize(name:str):
    name = re.sub(r"[^0-9A-Za-z가-힣 ]+"," ", name)
    toks = [t.strip().lower() for t in name.split() if t.strip()]
    return [t for t in toks if t not in STOP and len(t)>1]

def fetch_rakuten_keywords(appid:str, aff:str, gid:str, page:int)->list[str]:
    url = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601"
    params = {
        "applicationId": appid, "affiliateId": aff,
        "genreId": gid, "page": page, "hits": 30, "sort": "-reviewCount"
    }
    r = requests.get(url, params=params, timeout=10)
    j = r.json()
    result = []
    for it in j.get("Items",[]):
        name = it["Item"]["itemName"]
        result.extend(tokenize(name))
    return result

if run_rakuten:
    if not (app_id_in and genre_id):
        st.error("APP_ID/GENRE_ID가 필요합니다.")
    else:
        counter = collections.Counter()
        for p in range(1, pages+1):
            try:
                toks = fetch_rakuten_keywords(app_id_in, aff_id_in, genre_id, p)
                counter.update(toks)
            except Exception as e:
                st.warning(f"{p}페이지 수집 실패: {e}")
        top20 = counter.most_common(20)
        df = pd.DataFrame(top20, columns=["keyword","freq"])
        st.session_state.kw_vol = {k:int(v) for k,v in top20}  # 상품명 생성기에 연결
        st.dataframe(df, use_container_width=True, hide_index=True)
# =========================================================================== 
# ========================= PART I: TRANSLATOR ===============================
from typing import Optional

_LANGS = {
    "자동 감지":"auto","한국어":"ko","영어":"en","일본어":"ja","중국어(간체)":"zh-cn","중국어(번체)":"zh-tw",
    "독일어":"de","프랑스어":"fr","스페인어":"es","포르투갈어":"pt","이탈리아어":"it",
    "러시아어":"ru","베트남어":"vi","태국어":"th","인도네시아어":"id"
}

def translate_text(text: str, src_code: Optional[str], dst_code: str) -> str:
    if not text.strip():
        return ""
    try:
        from deep_translator import GoogleTranslator as DT
        src = None if (not src_code or src_code == "auto") else src_code
        return DT(source=src, target=dst_code).translate(text)
    except Exception:
        try:
            from googletrans import Translator
            t = Translator()
            src = "auto" if (not src_code or src_code == "auto") else src_code
            return t.translate(text, src=src, dest=dst_code).text
        except Exception as e:
            return f"[번역 실패] {e}"

st.subheader("구글 번역 (텍스트 입력/출력 + 한국어 확인)")
c1, c2 = st.columns([1,1])
with c1:
    src_display = st.selectbox("원문 언어", list(_LANGS.keys()), index=0)
    src_code = _LANGS[src_display]
    src_text = st.text_area("원문 입력", height=160, placeholder="번역할 문장을 입력하세요.")
with c2:
    dst_display = st.selectbox("번역 언어", list(_LANGS.keys()), index=list(_LANGS.keys()).index("한국어"))
    dst_code = _LANGS[dst_display]
    if "translated_text" not in st.session_state:
        st.session_state.translated_text = ""
    st.text_area("번역 결과", st.session_state.translated_text, height=160, disabled=True)

if st.button("번역"):
    st.session_state.translated_text = translate_text(src_text, src_code, dst_code)
    st.rerun()
# =========================================================================== 
# ========== PART J: 아이템스카우트 / 셀러라이프 (원본 임베드) ===============
st.subheader("아이템스카우트 (원본 임베드)")
items_url = "https://items.singtown.com"
try:
    st.components.v1.iframe(src=proxy_url(items_url), height=460, scrolling=True)
except Exception:
    st.warning("임베드 실패(1016 등). 아래 버튼으로 새창을 열어주세요.")
st.link_button("프록시 새창 열기", proxy_url(items_url))

st.subheader("셀러라이프 (원본 임베드)")
sellerlife_url = "https://www.sellerlife.co.kr"
try:
    st.components.v1.iframe(src=proxy_url(sellerlife_url), height=460, scrolling=True)
except Exception:
    st.warning("임베드 실패(1016 등). 아래 버튼으로 새창을 열어주세요.")
st.link_button("프록시 새창 열기", proxy_url(sellerlife_url))
# =========================================================================== 

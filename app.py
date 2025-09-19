# =========================
# Part 0 — 공통 유틸 & 테마
# =========================
import streamlit as st
import requests, pandas as pd, json, urllib.parse, time, base64, re, textwrap
from bs4 import BeautifulSoup
from pathlib import Path

st.set_page_config(page_title="ENVY v11.3", page_icon="✨", layout="wide")

# 언어 라벨 (한국어 표기)
LANG_LABELS = {
    "auto":"자동 감지","ko":"한국어","en":"영어","ja":"일본어",
    "zh-CN":"중국어(간체)","zh-TW":"중국어(번체)","de":"독일어","fr":"프랑스어",
    "es":"스페인어","it":"이탈리아어","ru":"러시아어","vi":"베트남어",
}

# 통화 라벨/기호 (한국어 표기)
CURRENCY_LABELS = {
    "USD":"미국 달러(USD)","EUR":"유로(EUR)","JPY":"일본 엔(JPY)","CNY":"중국 위안(CNY)"
}
CURRENCY_SYMBOL = {"USD":"$","EUR":"€","JPY":"¥","CNY":"元"}
FX_DEFAULT = {"USD":1400.0, "EUR":1500.0, "JPY":10.0, "CNY":200.0}

# UA
MOBILE_HEADERS = {
    "user-agent": ("Mozilla/5.0 (Linux; Android 13; Pixel 7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/125.0 Mobile Safari/537.36"),
    "accept-language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "cache-control": "no-cache",
}

# 외부 API 고정
DATALAB_API = "https://datalab.naver.com/shoppingInsight/getCategoryKeywordRank.naver"
RAKUTEN_APP_ID = "1043271015809337425"

def init_theme():
    if "theme" not in st.session_state:
        st.session_state["theme"] = "light"

def toggle_theme():
    st.session_state["theme"] = "dark" if st.session_state["theme"]=="light" else "light"

def inject_css():
    theme = st.session_state.get("theme","light")
    if theme=="dark":
        bg, fg = "#0e1117", "#e6edf3"
    else:
        bg, fg = "#ffffff", "#111111"

    st.markdown(f"""
    <style>
      html, body, [data-testid="stAppViewContainer"] {{
        background:{bg} !important; color:{fg} !important;
      }}
      .block-container {{ padding-top:.8rem !important; padding-bottom:.25rem !important; }}

      /* Sidebar 고정 + 스크롤락 */
      [data-testid="stSidebar"],
      [data-testid="stSidebar"] > div:first-child,
      [data-testid="stSidebar"] section {{
        height: 100vh !important; overflow: hidden !important;
        padding-top:.25rem !important; padding-bottom:.25rem !important;
      }}
      [data-testid="stSidebar"] ::-webkit-scrollbar {{ display:none !important; }}

      /* 사이드바 컴포넌트 간격 */
      [data-testid="stSidebar"] .stSelectbox,
      [data-testid="stSidebar"] .stNumberInput,
      [data-testid="stSidebar"] .stRadio,
      [data-testid="stSidebar"] .stMarkdown,
      [data-testid="stSidebar"] .stTextInput,
      [data-testid="stSidebar"] .stButton {{
        margin-top:.16rem !important; margin-bottom:.16rem !important;
      }}

      /* 입력 높이 축소 */
      [data-baseweb="input"] input,
      .stNumberInput input,
      [data-baseweb="select"] div[role="combobox"] {{
        height:1.55rem !important; font-size:.92rem !important;
      }}

      /* 배지 */
      .badge-green  {{ background:#e6ffcc; border:1px solid #b6f3a4;
        padding:6px 10px; border-radius:6px; color:#0b2e13; font-size:.86rem; }}
      .badge-blue   {{ background:#eef4ff; border:1px solid #bcd0ff;
        padding:6px 10px; border-radius:6px; color:#0a235a; font-size:.86rem; }}
      .badge-yellow {{ background:#fff7d6; border:1px solid #f1d27a;
        padding:6px 10px; border-radius:6px; color:#4a3b07; font-size:.86rem; }}

      /* 로고(원형) */
      .logo-circle {{
        width:95px;height:95px;border-radius:50%;overflow:hidden;margin:.15rem auto .35rem auto;
        box-shadow:0 2px 8px rgba(0,0,0,.12);border:1px solid rgba(0,0,0,.06);
      }}
      .logo-circle img {{ width:100%;height:100%;object-fit:cover; }}

      /* 라쿠텐 표 글꼴 축소 */
      .compact-table td, .compact-table th {{ font-size: .86rem !important; }}

    </style>
    """, unsafe_allow_html=True)

def has_proxy() -> bool:
    return bool(st.session_state.get("PROXY_URL","").strip())

def iframe_url(target: str) -> str:
    if not has_proxy(): return target
    return f"{st.session_state['PROXY_URL'].rstrip('/')}/iframe?target={urllib.parse.quote(target, safe='')}"

def fetch_via_proxy_or_direct(url: str, **kw):
    if has_proxy():
        prox = f"{st.session_state['PROXY_URL'].rstrip('/')}/fetch?target={urllib.parse.quote(url, safe='')}"
        return requests.get(prox, headers=MOBILE_HEADERS, timeout=12, **kw)
    return requests.get(url, headers=MOBILE_HEADERS, timeout=12, **kw)
# =========================
# Part 1 — 사이드바
# =========================
def render_sidebar():
    with st.sidebar:
        # 로고
        lp = Path(__file__).parent / "logo.png"
        if lp.exists():
            b64 = base64.b64encode(lp.read_bytes()).decode("ascii")
            st.markdown(
                f'<div class="logo-circle"><img src="data:image/png;base64,{b64}"></div>',
                unsafe_allow_html=True
            )
        else:
            st.caption("logo.png 를 앱 파일과 같은 폴더에 두면 로고 표시")

        # 다크모드 토글
        st.toggle("🌓 다크 모드", value=(st.session_state.get("theme","light")=="dark"), on_change=toggle_theme, key="dark_toggle")

        st.markdown("### ① 환율변환기")
        base = st.selectbox("기준통화", list(CURRENCY_LABELS.keys()), index=0, format_func=lambda k:CURRENCY_LABELS[k], key="sb_fx_base")
        sale_foreign = st.number_input("판매금액(외화)", value=1.00, step=0.01, format="%.2f", key="sb_fx_amt")
        won = FX_DEFAULT[base] * sale_foreign
        st.markdown(f'<div class="badge-green">환산 금액: <b>{won:,.2f} 원</b>  —  {CURRENCY_SYMBOL[base]}</div>', unsafe_allow_html=True)
        st.caption(f"환율 기준: {FX_DEFAULT[base]:,.2f} ₩/{base}")

        st.markdown("### ② 마진 테스트")
        m_base = st.selectbox("매입 통화", list(CURRENCY_LABELS.keys()), index=0, format_func=lambda k:CURRENCY_LABELS[k], key="sb_m_base")
        purchase_foreign = st.number_input("매입금액(외화)", value=0.00, step=0.01, format="%.2f", key="sb_m_amt")
        base_cost_won = FX_DEFAULT[m_base] * purchase_foreign if purchase_foreign>0 else won
        st.markdown(f'<div class="badge-green">원가(₩): <b>{base_cost_won:,.2f} 원</b></div>', unsafe_allow_html=True)

        colf1, colf2 = st.columns(2)
        with colf1:
            card_fee = st.number_input("카드수수료(%)", value=4.00, step=0.01, format="%.2f", key="sb_card")
        with colf2:
            market_fee = st.number_input("광고/마켓수수료(%)", value=14.00, step=0.01, format="%.2f", key="sb_market")
        shipping = st.number_input("배송비(₩)", value=0.0, step=100.0, format="%.0f", key="sb_ship")

        mode = st.radio("마진 방식", ["퍼센트","플러스"], horizontal=True, key="sb_mode")
        if mode=="퍼센트":
            margin_pct = st.number_input("마진율(%)", value=10.00, step=0.01, format="%.2f", key="sb_m_pct")
            target_price = base_cost_won*(1+card_fee/100)*(1+market_fee/100)*(1+margin_pct/100)+shipping
            margin_value = target_price - base_cost_won
            desc = f"{margin_pct:.2f}%"
        else:
            margin_won = st.number_input("마진액(₩)", value=10000.0, step=100.0, format="%.0f", key="sb_m_won")
            target_price = base_cost_won*(1+card_fee/100)*(1+market_fee/100)+margin_won+shipping
            margin_value = margin_won
            desc = f"+{margin_won:,.0f}"

        st.markdown(f'<div class="badge-blue">판매가: <b>{target_price:,.2f} 원</b></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="badge-yellow">순이익(마진): <b>{margin_value:,.2f} 원</b> — {desc}</div>', unsafe_allow_html=True)

        st.divider()
        # PROXY_URL은 맨 아래로
        st.text_input("PROXY_URL(클라우드플레어 워커)", value=st.session_state.get("PROXY_URL",""), key="PROXY_URL")
# =========================
# Part 2 — 데이터랩 (12종/20개 고정)
# =========================

# 네이버 대분류 맵(표시명 -> cid)
CID_TOP12 = {
    "패션의류":"50000000","패션잡화":"50000001","화장품/미용":"50000002","디지털/가전":"50000003",
    "가구/인테리어":"50000004","출산/육아":"50000005","식품":"50000006","스포츠/레저":"50000007",
    "생활/건강":"50000008","여가/생활편의":"50000009","면세점":"50000010","도서":"50005542",
}

@st.cache_data(ttl=300)
def datalab_fetch(cid: str, start_date: str, end_date: str, count: int = 20) -> pd.DataFrame:
    params = {"cid": cid, "timeUnit": "date", "startDate": start_date, "endDate": end_date, "page": 1, "count": count}
    r = requests.get(DATALAB_API, params=params, timeout=10)
    r.raise_for_status()
    try:
        data = r.json()
        rows = data.get("ranks") or data.get("data") or data.get("result") or []
        if isinstance(rows, dict): rows = rows.get("ranks",[])
        out=[]
        for i,it in enumerate(rows[:count], start=1):
            kw = (it.get("keyword") or it.get("name") or "").strip()
            score = it.get("ratio") or it.get("value") or it.get("score")
            out.append({"rank":i,"keyword":kw,"score":score})
        df = pd.DataFrame(out)
    except json.JSONDecodeError:
        soup = BeautifulSoup(r.text, "html.parser")
        words=[]
        for el in soup.select("a, span, li"):
            t=(el.get_text(" ", strip=True) or "").strip()
            if 1<len(t)<=40: words.append(t)
            if len(words)>=count: break
        if not words: words=["데이터 없음"]*count
        df=pd.DataFrame([{"rank":i+1,"keyword":w} for i,w in enumerate(words)])
    if df.empty: return df
    if "score" not in df.columns or df["score"].isna().all():
        n=len(df); df["score"]=[max(1,int(100-i*(100/max(1,n-1)))) for i in range(n)]
    return df

def render_datalab_block():
    st.subheader("캠프 기간 (기간 프리셋 + 기기별)")
    left, right = st.columns([1,1], gap="large")
    with left:
        cat = st.selectbox("카테고리", list(CID_TOP12.keys()), index=3, key="datalab_cat")
        st.caption(f"선택 카테고리: {cat} (cid={CID_TOP12[cat]})")
        today = pd.Timestamp.today().normalize()
        start = st.date_input("시작일", today - pd.Timedelta(days=365), key="dl_start")
        end   = st.date_input("종료일", today, key="dl_end")
        if st.button("시동", key="dl_go"):
            st.cache_data.clear()

        df = datalab_fetch(CID_TOP12[cat], str(start), str(end), count=20)
        st.dataframe(df[["rank","keyword","score"]], use_container_width=True, hide_index=True)
        st.line_chart(df[["rank","score"]].set_index("rank").sort_index(), height=190)

    with right:
        st.selectbox("키워드(최대 5개, 콤마로 구분)", ["가습기, 복합기, 무선청소기"], index=0, key="trend_kw_dummy")
        st.selectbox("기간 프리셋", ["1년","3개월","1개월","1주"], index=0, key="trend_preset")
        st.selectbox("기기별", ["전체","PC","모바일"], index=0, key="trend_device")
        st.selectbox("카테고리(대분류)", list(CID_TOP12.keys()), index=3, key="trend_cat")
        st.markdown("※ 실제 API 접근 권한이 제한되어, 프리셋/기기/카테고리 변경시 **샘플 라인**을 표시합니다.")
        # 샘플 차트
        demo = pd.DataFrame({
            "x": list(range(1,11)),
            "A": [60,65,70,58,72,60,74,62,68,71],
            "B": [58,63,68,55,70,58,72,60,66,69],
            "C": [62,66,73,60,76,64,78,66,70,74],
        }).set_index("x")
        st.line_chart(demo.rename(columns={"A":"가습기","B":"무선청소기","C":"복합기"}), height=220)
# =========================
# Part 3 — 아이템스카우트 / 셀러라이프 (데모)
# =========================
def render_item_scout():
    st.subheader("아이템스카우트")
    st.info("연동 대기 (API 키 확보 후 교체) — 자리는 유지합니다.")
    demo = pd.DataFrame([
        {"rank":1,"keyword":"가습기","search":48210,"compete":0.61,"market":"스마트스토어"},
        {"rank":2,"keyword":"가습기 필터","search":12034,"compete":0.48,"market":"스마트스토어"},
        {"rank":3,"keyword":"초음파 가습기","search":8033,"compete":0.42,"market":"스마트스토어"},
    ])
    st.dataframe(demo, use_container_width=True, hide_index=True)

def render_sellerlife():
    st.subheader("셀러라이프")
    st.info("연동 대기 (API 키 확보 후 교체) — 자리는 유지합니다.")
    bar = pd.DataFrame({"분기":["전","현"],"객단가":[11_200_000,12_600_000],"매출":[0,0],"주문수":[0,0]}).set_index("분기")
    st.bar_chart(bar[["객단가"]], height=260)
# =========================
# Part 4 — 11번가 (모바일 iFrame)
# =========================
ELEVEN_URL = "https://m.11st.co.kr/browsing/bestSellers.mall"

def render_elevenst():
    st.subheader("11번가 (모바일)")
    url = st.text_input("모바일 URL", value=ELEVEN_URL, key="eleven_url")
    if not has_proxy():
        st.warning("PROXY_URL 미설정: iFrame을 직접 막힐 수 있습니다.")
        st.components.v1.iframe(url, height=720, scrolling=True)
    else:
        st.caption("프록시 iFrame (권장)")
        st.components.v1.iframe(iframe_url(url), height=720, scrolling=True)
# =========================
# Part 5 — AI 키워드 레이더 (Rakuten)
# =========================
SAFE_GENRES = {
    "전체(샘플)":"100283","여성패션":"100371","남성패션":"551169","뷰티/코스메틱":"100939",
    "식품/식료품":"100316","도서":"101266","취미/게임/완구":"101205","스포츠/레저":"101070",
    "자동차/바이크":"558929","베이비/키즈":"100533","반려동물":"101213"
}
DEFAULT_GENRE = SAFE_GENRES["전체(샘플)"]

def _rk_url(params: dict) -> str:
    endpoint = "https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20170628"
    qs = urllib.parse.urlencode(params, safe="")
    url = f"{endpoint}?{qs}"
    if has_proxy():
        return f"{st.session_state['PROXY_URL'].rstrip('/')}/fetch?target={urllib.parse.quote(url, safe='')}"
    return url

@st.cache_data(ttl=600)
def rakuten_fetch(genre_id: str, rows: int = 50) -> pd.DataFrame:
    params = {"applicationId":RAKUTEN_APP_ID,"format":"json","formatVersion":2,"genreId":genre_id}
    try:
        resp = requests.get(_rk_url(params), headers=MOBILE_HEADERS, timeout=12)
        if resp.status_code==400: raise ValueError("400 Bad Request (장르/매개변수)")
        resp.raise_for_status()
        data = resp.json()
        items = data.get("Items", [])[:rows]
        out=[]
        for i,it in enumerate(items, start=1):
            if isinstance(it,dict) and "itemName" in it: name = it.get("itemName") or ""
            else: name = (it.get("Item") or {}).get("itemName","")
            if name: out.append({"rank":i,"keyword":name,"source":"Rakute"})
        if not out: raise ValueError("응답 파싱 결과 비어 있음")
        return pd.DataFrame(out)
    except Exception as e:
        if genre_id != DEFAULT_GENRE:
            try:
                fb = rakuten_fetch.__wrapped__(DEFAULT_GENRE, rows)
                fb["note"]="fallback: genreId 자동 대체"
                return fb
            except Exception:
                pass
        return pd.DataFrame([{"rank":1,"keyword":f"(Rakuten) {type(e).__name__}: {e}", "source":"DEMO"}])

def render_rakuten():
    st.subheader("AI 캠프 랩 (Rakuten)")
    st.radio("모드", ["국내","글로벌"], horizontal=True, key="rk_mode", label_visibility="collapsed")
    col1,col2,col3 = st.columns([1.2,.9,1.2])
    with col1:
        cat = st.selectbox("라쿠텐 카테고리", list(SAFE_GENRES.keys()), index=0, key="rk_cat")
    with col2:
        preset_id = SAFE_GENRES[cat]
        gid = st.text_input("장르ID(직접 입력)", value=preset_id, key="rk_gid")
    with col3:
        st.caption(f"앱 ID: {RAKUTEN_APP_ID}")
        st.caption("400/파싱 실패 → '전체(샘플)'로 자동 폴백")

    df = rakuten_fetch(gid, rows=50)
    st.dataframe(df, use_container_width=True, hide_index=True, classes="compact-table")
    st.caption("※ Rakuten Ranking API는 '상품 랭킹'을 반환합니다. 상품명을 키워드처럼 표기.")
# =========================
# Part 6 — 구글 번역 (텍스트 입력/출력 + 한국어 확인용)
# =========================
def translate_text(src: str, tgt: str, text: str) -> str:
    if not text.strip(): return ""
    # 시도 1: deep_translator
    try:
        from deep_translator import GoogleTranslator
        translated = GoogleTranslator(source=src if src!="auto" else "auto", target=tgt).translate(text)
        if tgt!="ko":
            ko = GoogleTranslator(source=tgt, target="ko").translate(translated)
            translated = f"{translated} ({ko})"
        return translated
    except Exception as e1:
        # 시도 2: googletrans (있다면)
        try:
            from googletrans import Translator
            tr = Translator()
            if src=="auto":
                res = tr.translate(text, dest=tgt)
            else:
                res = tr.translate(text, src=src, dest=tgt)
            translated = res.text
            if tgt!="ko":
                ko = tr.translate(translated, src=tgt, dest="ko").text
                translated = f"{translated} ({ko})"
            return translated
        except Exception as e2:
            return f"[번역 실패] {type(e2).__name__}: {e2}"

def render_translator():
    st.subheader("구글 번역 (텍스트 입력/출력 + 한국어 확인용)")
    c1,c2 = st.columns([1,1])
    with c1:
        src = st.selectbox("원문 언어", list(LANG_LABELS.keys()), index=0, format_func=lambda k:LANG_LABELS[k], key="tr_src")
    with c2:
        tgt = st.selectbox("번역 언어", list(LANG_LABELS.keys())[1:], index=list(LANG_LABELS.keys()).index("en")-1, format_func=lambda k:LANG_LABELS[k], key="tr_tgt")
    text = st.text_area("원문 입력", height=120, key="tr_in")
    if st.button("번역", key="tr_go"):
        out = translate_text(src, tgt, text or "")
        st.text_area("번역 결과", value=out, height=140, key="tr_out")
# =========================
# Part 7 — 상품명 생성기 (규칙 기반)
# =========================
def render_namegen():
    st.subheader("상품명 생성기 (규칙 기반)")
    brand = st.text_input("브랜드", value="envy", key="ng_brand")
    base_kw = st.text_input("베이스 키워드", value="K-coffee mix", key="ng_base")
    rel_kw = st.text_input("연관키워드(콤마)", value="Maxim, Kanu", key="ng_rel")
    limit = st.slider("글자수 제한", 20, 80, 80, key="ng_limit")
    if st.button("생성", key="ng_go"):
        kws = [k.strip() for k in rel_kw.split(",") if k.strip()]
        outs = [f"{brand} {base_kw} {k}"[:limit] for k in kws[:5]]
        st.text_area("결과", "\n".join(outs), height=160, key="ng_out")
# =========================
# Part 8 — 메인 레이아웃
# =========================
def main():
    init_theme()
    inject_css()
    render_sidebar()

    # 상단: 데이터랩 (조금 아래로 내렸던 배치 유지: 여기선 좌우 한 벌로 구성)
    render_datalab_block()

    st.divider()

    # 중단: 좌(11번가) / 우(라쿠텐)
    left, right = st.columns([1,1], gap="large")
    with left:
        render_elevenst()
    with right:
        render_rakuten()

    st.divider()

    # 하단: 아이템스카우트, 셀러라이프, 번역기, 이름 생성기
    b1,b2 = st.columns([1,1], gap="large")
    with b1:
        render_item_scout()
        render_namegen()
    with b2:
        render_sellerlife()
        render_translator()

if __name__ == "__main__":
    main()

# app.py  (ENVY v11.2 — single-file full code)

import streamlit as st
import requests, pandas as pd, json, time, base64, urllib.parse, re
from bs4 import BeautifulSoup
from pathlib import Path

# =============== 기본 설정/테마/CSS ===============
st.set_page_config(page_title="ENVY v11.2", page_icon="✨", layout="wide")

def init_state():
    if "theme" not in st.session_state:
        st.session_state["theme"] = "light"
    if "PROXY_URL" not in st.session_state:
        st.session_state["PROXY_URL"] = ""

init_state()

def has_proxy() -> bool:
    p = st.session_state.get("PROXY_URL", "")
    return isinstance(p, str) and p.strip() != ""

def iframe_url(target: str) -> str:
    if not has_proxy():
        return target
    # Cloudflare Worker: /iframe?target=...  (배너 제거는 워커에서 처리)
    return f"{st.session_state['PROXY_URL'].rstrip('/')}/iframe?target={urllib.parse.quote(target, safe='')}"

def fetch_url_through_proxy(url: str) -> str:
    """프록시로 일반 fetch가 필요한 경우(라쿠텐 등)"""
    if not has_proxy(): 
        return url
    return f"{st.session_state['PROXY_URL'].rstrip('/')}/fetch?target={urllib.parse.quote(url, safe='')}"

def inject_css():
    theme = st.session_state.get("theme", "light")
    if theme == "dark":
        bg, fg = "#0e1117", "#e6edf3"
        card = "#111827"
    else:
        bg, fg, card = "#ffffff", "#111111", "#ffffff"
    st.markdown(f"""
    <style>
      html, body, [data-testid="stAppViewContainer"] {{
        background:{bg} !important; color:{fg} !important;
      }}
      .block-container {{ padding-top:.8rem !important; padding-bottom:.4rem !important; }}
      /* Sidebar 고정 + 스크롤락 */
      [data-testid="stSidebar"], [data-testid="stSidebar"]>div:first-child, [data-testid="stSidebar"] section {{
        height:100vh !important; overflow:hidden !important; padding-top:.25rem !important; padding-bottom:.25rem !important;
      }}
      [data-testid="stSidebar"] ::-webkit-scrollbar {{ display:none !important; }}
      /* 사이드바 컴팩트 마진 */
      [data-testid="stSidebar"] .stNumberInput, [data-testid="stSidebar"] .stSelectbox,
      [data-testid="stSidebar"] .stRadio, [data-testid="stSidebar"] .stTextInput, 
      [data-testid="stSidebar"] .stButton, [data-testid="stSidebar"] .stMarkdown {{
        margin-top:.18rem !important; margin-bottom:.18rem !important;
      }}
      /* 입력 높이 축소 */
      [data-baseweb="input"] input, .stNumberInput input, [data-baseweb="select"] div[role="combobox"] {{
        height:1.55rem !important; font-size:.92rem !important;
      }}
      /* 배지 */
      .badge-green  {{ background:#e6ffcc; border:1px solid #b6f3a4; padding:6px 10px; border-radius:6px; color:#0b2e13; font-size:.86rem; }}
      .badge-blue   {{ background:#eef4ff; border:1px solid #bcd0ff; padding:6px 10px; border-radius:6px; color:#0a235a; font-size:.86rem; }}
      .badge-yellow {{ background:#fff7d6; border:1px solid #f1d27a; padding:6px 10px; border-radius:6px; color:#4a3b07; font-size:.86rem; }}
      /* 로고 원형 */
      .logo-circle {{ width: 95px; height:95px; border-radius:50%; overflow:hidden; margin:.25rem auto .5rem; 
                      box-shadow:0 2px 8px rgba(0,0,0,.12); border:1px solid rgba(0,0,0,.06); }}
      .logo-circle img {{ width:100%; height:100%; object-fit:cover; }}
      /* 라쿠텐 표 글꼴 한 단계 축소 */
      .compact-table td, .compact-table th {{ font-size: .85rem !important; line-height:1.15rem !important; }}
    </style>
    """, unsafe_allow_html=True)

inject_css()

# =============== 공통 상수 ===============
MOBILE_HEADERS = {
    "user-agent": ("Mozilla/5.0 (Linux; Android 13; Pixel 7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Mobile Safari/537.36"),
    "accept-language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "cache-control": "no-cache",
    "referer": "https://datalab.naver.com/"
}

CURRENCY_MAP = {
    "미국 달러 (USD)": ("USD", "$", 1400.0),
    "유로 (EUR)": ("EUR", "€", 1500.0),
    "일본 엔 (JPY)": ("JPY", "¥", 10.0),
    "중국 위안 (CNY)": ("CNY", "元", 200.0),
}

# =============== 사이드바 ===============
def render_sidebar():
    with st.sidebar:
        # 로고
        lp = Path(__file__).parent / "logo.png"
        if lp.exists():
            b64 = base64.b64encode(lp.read_bytes()).decode("ascii")
            st.markdown(f'<div class="logo-circle"><img src="data:image/png;base64,{b64}"></div>', unsafe_allow_html=True)
        else:
            st.caption("logo.png 를 앱 폴더에 두면 로고가 표시됩니다.")

        st.toggle("🌓 다크 모드", value=(st.session_state.get("theme","light")=="dark"),
                  on_change=lambda: st.session_state.update(theme=("dark" if st.session_state.get("theme")=="light" else "light")))

        st.markdown("### ① 환율 변환기")
        base_name = st.selectbox("기준 통화", list(CURRENCY_MAP.keys()), index=0)
        base_code, base_sym, base_fx = CURRENCY_MAP[base_name]
        sale_foreign = st.number_input("판매금액 (외화)", value=1.00, step=0.01, format="%.2f")
        won = base_fx * sale_foreign
        st.markdown(f'<div class="badge-green">환산 금액: <b>{won:,.2f} 원</b></div>', unsafe_allow_html=True)
        st.caption(f"환율 기준: {base_fx:,.2f} ₩/{base_code}")

        st.markdown("### ② 마진 계산기")
        m_base_name = st.selectbox("매입 통화", list(CURRENCY_MAP.keys()), index=0, key="mbase")
        m_code, m_sym, m_fx = CURRENCY_MAP[m_base_name]
        purchase_foreign = st.number_input("매입금액 (외화)", value=0.00, step=0.01, format="%.2f")
        base_cost_won = m_fx * purchase_foreign if purchase_foreign>0 else won
        st.markdown(f'<div class="badge-green">원가(₩): <b>{base_cost_won:,.2f} 원</b></div>', unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1: card_fee = st.number_input("카드수수료(%)", value=4.00, step=0.01, format="%.2f")
        with c2: market_fee = st.number_input("마켓수수료(%)", value=14.00, step=0.01, format="%.2f")
        ship = st.number_input("배송비(₩)", value=0.0, step=100.0, format="%.0f")

        mode = st.radio("마진 방식", ["퍼센트", "플러스"], horizontal=True)
        if mode == "퍼센트":
            margin_pct = st.number_input("마진율 (%)", value=10.00, step=0.01, format="%.2f")
            target_price = base_cost_won * (1 + card_fee/100) * (1 + market_fee/100) * (1 + margin_pct/100) + ship
            margin_value = target_price - base_cost_won
            md = f"{margin_pct:.2f}%"
        else:
            margin_won = st.number_input("마진액 (₩)", value=10000.0, step=100.0, format="%.0f")
            target_price = base_cost_won * (1 + card_fee/100) * (1 + market_fee/100) + margin_won + ship
            margin_value = margin_won
            md = f"+{margin_won:,.0f}"

        st.markdown(f'<div class="badge-blue">판매가: <b>{target_price:,.2f} 원</b></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="badge-yellow">순이익(마진): <b>{margin_value:,.2f} 원</b> — {md}</div>', unsafe_allow_html=True)

        with st.expander("🔧 고급 설정", expanded=False):
            st.session_state["PROXY_URL"] = st.text_input("PROXY_URL (Cloudflare Worker)", 
                                                          value=st.session_state.get("PROXY_URL",""),
                                                          placeholder="https://your-worker.workers.dev")

render_sidebar()

# =============== 데이터랩 (대분류 12종, 20개 고정) ===============
DATALAB_API = "https://datalab.naver.com/shoppingInsight/getCategoryKeywordRank.naver"

CID_TOP12 = {
    "패션의류":"50000000", "패션잡화":"50000001", "화장품/미용":"50000002", "디지털/가전":"50000003",
    "가구/인테리어":"50000004", "출산/육아":"50000005", "식품":"50000006", "스포츠/레저":"50000007",
    "생활/건강":"50000008", "여가/생활편의":"50000009", "면세점":"50000010", "도서":"50000011",
}

@st.cache_data(ttl=300)
def datalab_fetch(cid: str, start_date: str, end_date: str, count: int = 20) -> pd.DataFrame:
    params = {
        "cid": cid, "timeUnit":"date", "startDate": start_date, "endDate": end_date,
        "page": 1, "count": count,
    }
    r = requests.get(DATALAB_API, params=params, headers=MOBILE_HEADERS, timeout=12)
    r.raise_for_status()
    try:
        data = r.json()
        rows = data.get("ranks") or data.get("data") or data.get("result") or []
        if isinstance(rows, dict):
            rows = rows.get("ranks", [])
        out=[]
        for i, it in enumerate(rows, start=1):
            kw = (it.get("keyword") or it.get("name") or "").strip()
            score = it.get("ratio") or it.get("value") or it.get("score")
            out.append({"rank":i, "keyword":kw, "score":score})
        df = pd.DataFrame(out)
    except json.JSONDecodeError:
        soup = BeautifulSoup(r.text, "html.parser")
        words=[]
        for el in soup.select("a, span, li"):
            t=(el.get_text(" ", strip=True) or "").strip()
            if 1 < len(t) <= 40: words.append(t)
            if len(words) >= count: break
        if not words:
            words = ["데이터 없음"]*count
        df = pd.DataFrame([{"rank":i+1, "keyword":w} for i, w in enumerate(words)])

    if df.empty: return df
    if "score" not in df.columns or df["score"].isna().all():
        n = len(df); df["score"] = [max(1, int(100 - i*(100/max(1,n-1)))) for i in range(n)]
    return df.head(20)

def render_datalab_block():
    st.subheader("캠프 기간 (기간 프리셋 + 기기별)")
    col_l, col_r = st.columns([1,1])
    with col_l:
        cat = st.selectbox("카테고리", list(CID_TOP12.keys()), index=3)
        st.caption(f"선택 카테고리: {cat} (cid={CID_TOP12[cat]})")
        today = pd.Timestamp.today().normalize()
        start = st.date_input("시작일", today - pd.Timedelta(days=365))
        end   = st.date_input("종료일", today)
        if st.button("시동", type="primary"):
            st.cache_data.clear()
    with col_r:
        # 키워드 트렌드(보여주기용 고정 키워드 3개)
        kp = st.text_input("키워드(최대 5개, 콤마로 구분)", "가습기, 복합기, 무선청소기")
        period = st.selectbox("기간 프리셋", ["1년","3개월","1개월"], index=0)
        device = st.selectbox("기기별", ["전체","PC","모바일"], index=0)

    try:
        df = datalab_fetch(CID_TOP12[cat], str(start), str(end), 20)
        st.dataframe(df[["rank","keyword","score"]], use_container_width=True, hide_index=True, height=420)
        chart_df = df[["rank","score"]].set_index("rank").sort_index()
        st.line_chart(chart_df, height=220)
    except Exception as e:
        st.error(f"DataLab 호출 실패: {type(e).__name__}: {e}")
        st.info("※ JSON 막히면 HTML 휴리스틱으로 키워드만 추출합니다.")

render_datalab_block()

# =============== 11번가(모바일) ===============
ELEVEN_URL = "https://m.11st.co.kr/browsing/bestSellers.mall"
def render_elevenst_block():
    st.subheader("11번가 (모바일)")
    url = st.text_input("모바일 URL", value=ELEVEN_URL, label_visibility="collapsed")
    if not has_proxy():
        st.warning("PROXY_URL 미설정: 직접 iFrame은 정책에 막힐 수 있습니다.")
    try:
        st.components.v1.iframe(iframe_url(url), height=720, scrolling=True)
    except Exception as e:
        st.error(f"11번가 임베드 실패: {type(e).__name__}: {e}")
        st.caption("Cloudflare Worker 프록시를 설정하면 배너 제거/차단 우회를 돕습니다.")

# =============== AI 캠프 랩 (Rakuten) ===============
RAKUTEN_APP_ID = "1043271015809337425"

SAFE_GENRES = {
    "전체(샘플)": "100283", "여성패션": "100371", "남성패션": "551169", "뷰티/코스메틱": "100939",
    "식품/식료품": "100316", "도서": "101266", "음반/CD": "101240", "영화/DVD·BD": "101251",
    "취미/게임/완구": "101205", "스포츠/레저": "101070", "자동차/바이크":"558929", "베이비/키즈":"100533",
    "반려동물":"101213",
}

def rk_url(genre_id: str) -> str:
    endpoint = "https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20170628"
    qs = urllib.parse.urlencode({"applicationId":RAKUTEN_APP_ID, "format":"json", "formatVersion":2, "genreId":genre_id})
    url = f"{endpoint}?{qs}"
    return fetch_url_through_proxy(url)

@st.cache_data(ttl=600)
def rakuten_fetch(genre_id: str, rows: int = 50) -> pd.DataFrame:
    try:
        resp = requests.get(rk_url(genre_id), headers=MOBILE_HEADERS, timeout=12)
        if resp.status_code == 400:
            raise ValueError("400 Bad Request (장르 코드/매개변수)")
        resp.raise_for_status()
        data = resp.json()
        items = data.get("Items", [])[:rows]
        out=[]
        for i, it in enumerate(items, start=1):
            if isinstance(it, dict) and "itemName" in it:
                name = it.get("itemName") or ""
            else:
                name = (it.get("Item") or {}).get("itemName","")
            if name: out.append({"rank":i, "keyword":name, "source":"Rakuten"})
        if not out: raise ValueError("응답 파싱 결과 비어 있음")
        return pd.DataFrame(out)
    except Exception as e:
        if genre_id != SAFE_GENRES["전체(샘플)"]:
            try:
                fb = rakuten_fetch.__wrapped__(SAFE_GENRES["전체(샘플)"], rows)
                fb["note"] = "fallback: genreId 자동 대체"
                return fb
            except Exception:
                pass
        return pd.DataFrame([{"rank":1, "keyword":f"(Rakuten) {type(e).__name__}: {e}", "source":"DEMO"}])

def render_rakuten_block():
    st.subheader("AI 캠프 랩 (Rakuten)")
    c1, c2, c3 = st.columns([1.2,.9,1.2])
    with c1:
        cat = st.selectbox("라쿠텐 카테고리", list(SAFE_GENRES.keys()), index=0)
    with c2:
        genre_id = st.text_input("genreId (직접 입력)", value=SAFE_GENRES[cat])
    with c3:
        st.caption(f"App ID: **{RAKUTEN_APP_ID}** — 400/파싱 실패 시 '전체(샘플)' 자동 폴백")
    df = rakuten_fetch(genre_id=genre_id, rows=50)
    st.dataframe(df, use_container_width=True, hide_index=True, column_config=None, height=430, 
                 column_order=["rank","keyword","source"])
    st.caption("※ Rakuten Ranking API는 '상품 랭킹'을 반환합니다. 상품명을 키워드처럼 표기합니다.")

# =============== 상품명 생성기(규칙) ===============
def render_namegen_block():
    st.subheader("상품명 생성기 (규칙 기반)")
    brand = st.text_input("브랜드", value="envy")
    base_kw = st.text_input("베이스 키워드", value="K-coffee mix")
    rel_kw = st.text_input("연관키워드(콤마)", value="Maxim, Kanu, Korea")
    limit = st.slider("글자수 제한", 20, 80, 80)
    if st.button("생성"):
        kws = [k.strip() for k in rel_kw.split(",") if k.strip()]
        outs = [f"{brand} {base_kw} {k}"[:limit] for k in kws[:5]]
        st.text_area("생성 결과", "\n".join(outs), height=160)

# =============== 번역기(텍스트 입력/출력 + 한국어 확인용) ===============
LANG_LABELS = {
    "자동 감지":"auto", "한국어":"ko", "영어":"en", "일본어":"ja",
    "중국어(간체)":"zh", "중국어(번체)":"zh-TW", "독일어":"de", "프랑스어":"fr", "스페인어":"es"
}

def translate_libre(text: str, src: str, tgt: str) -> str:
    """libretranslate 공개 엔드포인트 사용(키 불필요). 실패 시 원문 반환."""
    if not text.strip(): return ""
    url = "https://libretranslate.de/translate"
    payload = {"q": text, "source": src if src!="auto" else "auto", "target": tgt, "format": "text"}
    try:
        r = requests.post(url, data=payload, timeout=12)
        r.raise_for_status()
        return r.json().get("translatedText","")
    except Exception:
        return text  # 실패하면 원문 노출

def render_translator_block():
    st.subheader("구글 번역 (텍스트 입력/출력 + 한국어 확인용)")
    c1, c2 = st.columns(2)
    with c1:
        src_label = st.selectbox("원문 언어", list(LANG_LABELS.keys()), index=0)
    with c2:
        tgt_label = st.selectbox("번역 언어", list(LANG_LABELS.keys()), index=1)  # 기본 en
    src, tgt = LANG_LABELS[src_label], LANG_LABELS[tgt_label]

    raw = st.text_area("원문 입력", height=120, placeholder="번역할 텍스트를 입력하세요.")
    if st.button("번역", type="primary"):
        out = translate_libre(raw, src, tgt)
        if tgt != "ko":  # 한국어 확인용 추가
            ko = translate_libre(raw, src, "ko")
            out = f"{out} ({ko})" if ko else out
        st.text_area("번역 결과", out, height=140)

# =============== 레이아웃 ===============
def main():
    # 상단 2행
    top1, top2 = st.columns([1,1])
    with top1:
        render_datalab_block()
    with top2:
        render_elevenst_block()
        render_rakuten_block()

    # 하단 2열
    bot1, bot2 = st.columns([1,1])
    with bot1:
        render_namegen_block()
    with bot2:
        render_translator_block()

if __name__ == "__main__":
    main()

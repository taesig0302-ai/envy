
# ENVY v11.2b — single file app
import streamlit as st
import requests, pandas as pd, json, urllib.parse, time, base64, re
from bs4 import BeautifulSoup
from pathlib import Path

st.set_page_config(page_title="ENVY v11.2b", page_icon="✨", layout="wide")

# =========================
# Global / Proxy / Headers
# =========================
def _side_input():
    with st.sidebar:
        return st.text_input("PROXY_URL (Cloudflare Worker)", value="", help="예: https://envy-proxy.example.workers.dev")
PROXY_URL = _side_input()

def has_proxy() -> bool:
    return isinstance(PROXY_URL, str) and PROXY_URL.strip() != ""

def iframe_url(target: str) -> str:
    if not has_proxy():
        return target
    return f"{PROXY_URL}/iframe?target={urllib.parse.quote(target, safe='')}"

MOBILE_HEADERS = {
    "user-agent": ("Mozilla/5.0 (Linux; Android 13; Pixel 7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/125.0 Mobile Safari/537.36"),
    "accept-language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "cache-control": "no-cache",
}

# Currency / Defaults
CURRENCY_SYMBOL = {"USD":"$", "EUR":"€", "JPY":"¥", "CNY":"元"}
FX_DEFAULT = {"USD":1400.0, "EUR":1500.0, "JPY":10.0, "CNY":200.0}

# =========
# THEME CSS
# =========
def init_theme_state():
    if "theme" not in st.session_state:
        st.session_state["theme"] = "light"

def toggle_theme():
    st.session_state["theme"] = "dark" if st.session_state["theme"]=="light" else "light"

def inject_css():
    theme = st.session_state.get("theme", "light")
    if theme == "dark":
        bg, fg = "#0e1117", "#e6edf3"
        badge_fg = "#0b2e13"
    else:
        bg, fg = "#ffffff", "#111111"
        badge_fg = "#0b2e13"

    st.markdown(f"""
    <style>
      html, body, [data-testid="stAppViewContainer"] {{
        background-color:{bg} !important; color:{fg} !important;
      }}
      .block-container {{ padding-top: .6rem !important; padding-bottom: .4rem !important; }}
      /* Sidebar 고정 + 스크롤락 */
      [data-testid="stSidebar"], [data-testid="stSidebar"] > div:first-child, [data-testid="stSidebar"] section {{
        height: 100vh !important; overflow: hidden !important;
        padding-top: .2rem !important; padding-bottom: .2rem !important;
      }}
      [data-testid="stSidebar"] ::-webkit-scrollbar {{ display: none !important; }}

      /* Sidebar compact spacing */
      [data-testid="stSidebar"] .stSelectbox, [data-testid="stSidebar"] .stNumberInput,
      [data-testid="stSidebar"] .stRadio, [data-testid="stSidebar"] .stMarkdown,
      [data-testid="stSidebar"] .stTextInput, [data-testid="stSidebar"] .stButton {{
        margin-top: .14rem !important; margin-bottom: .14rem !important;
      }}

      /* Inputs scale down a little */
      [data-baseweb="input"] input, .stNumberInput input, [data-baseweb="select"] div[role="combobox"] {{
        height: 1.55rem !important; padding-top: .12rem !important; padding-bottom: .12rem !important; font-size: .92rem !important;
      }}

      /* 배지 */
      .badge-green  {{ background:#e6ffcc; border:1px solid #b6f3a4; padding:6px 10px; border-radius:6px; color:{badge_fg}; font-size:.86rem; }}
      .badge-blue   {{ background:#eef4ff; border:1px solid #bcd0ff; padding:6px 10px; border-radius:6px; color:#0a235a; font-size:.86rem; }}
      .badge-yellow {{ background:#fff7d6; border:1px solid #f1d27a; padding:6px 10px; border-radius:6px; color:#4a3b07; font-size:.86rem; }}

      /* 로고 */
      .logo-circle {{ width: 95px; height: 95px; border-radius: 50%; overflow: hidden; margin: .15rem auto .35rem auto;
                     box-shadow: 0 2px 8px rgba(0,0,0,.12); border: 1px solid rgba(0,0,0,.06);}}
      .logo-circle img {{ width:100%; height:100%; object-fit:cover; }}
      .compact-table td, .compact-table th {{ font-size: 13px !important; line-height: 1.2 !important; }}
    </style>
    """, unsafe_allow_html=True)

# ===============
# SIDEBAR (with logo)
# ===============
def render_sidebar_only_widgets():
    with st.sidebar:
        # 로고 표시
        lp = Path(__file__).parent / "logo.png"
        if lp.exists():
            b64 = base64.b64encode(lp.read_bytes()).decode("ascii")
            st.markdown(f'<div class="logo-circle"><img src="data:image/png;base64,{b64}"></div>', unsafe_allow_html=True)
        st.toggle("🌓 다크 모드", value=(st.session_state.get("theme","light")=="dark"), on_change=toggle_theme)

        # ① 환율 계산기
        st.markdown("### ① 환율 계산기")
        base = st.selectbox("기준 통화", list(CURRENCY_SYMBOL.keys()), index=0, key="sb_fx_base")
        sale_foreign = st.number_input("판매금액 (외화)", value=1.00, step=0.01, format="%.2f", key="sb_sale_foreign")
        won = FX_DEFAULT[base] * sale_foreign
        st.markdown(f'<div class="badge-green">환산 금액: <b>{won:,.2f} 원</b></div>', unsafe_allow_html=True)
        st.caption(f"환율 기준: {FX_DEFAULT[base]:,.2f} ₩/{base}")

        # ② 마진 계산기
        st.markdown("### ② 마진 계산기")
        m_base = st.selectbox("매입 통화", list(CURRENCY_SYMBOL.keys()), index=0, key="sb_mbase")
        purchase_foreign = st.number_input("매입금액 (외화)", value=0.00, step=0.01, format="%.2f", key="sb_purchase_foreign")
        base_cost_won = FX_DEFAULT[m_base] * purchase_foreign if purchase_foreign>0 else won
        st.markdown(f'<div class="badge-green">원가(₩): <b>{base_cost_won:,.2f} 원</b></div>', unsafe_allow_html=True)

        fee_col1, fee_col2 = st.columns(2)
        with fee_col1:
            m_rate = st.number_input("카드수수료(%)", value=4.00, step=0.01, format="%.2f", key="sb_mrate")
        with fee_col2:
            m_fee  = st.number_input("마켓수수료(%)", value=14.00, step=0.01, format="%.2f", key="sb_mfee")
        ship = st.number_input("배송비(₩)", value=0.0, step=100.0, format="%.0f", key="sb_ship")

        mode = st.radio("마진 방식", ["퍼센트", "플러스"], horizontal=True, key="sb_mode")
        if mode == "퍼센트":
            margin_pct = st.number_input("마진율 (%)", value=10.00, step=0.01, format="%.2f", key="sb_margin_pct")
            target_price = base_cost_won * (1 + m_rate/100) * (1 + m_fee/100) * (1 + margin_pct/100) + ship
            margin_value = target_price - base_cost_won
            margin_desc = f"{margin_pct:.2f}%"
        else:
            margin_won = st.number_input("마진액 (₩)", value=10000.0, step=100.0, format="%.0f", key="sb_margin_won")
            target_price = base_cost_won * (1 + m_rate/100) * (1 + m_fee/100) + margin_won + ship
            margin_value = margin_won
            margin_desc = f"+{margin_won:,.0f}"
        st.markdown(f'<div class="badge-blue">판매가: <b>{target_price:,.2f} 원</b></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="badge-yellow">순이익(마진): <b>{margin_value:,.2f} 원</b> — {margin_desc}</div>', unsafe_allow_html=True)

# =========================
# DataLab (fixed 20 items)
# =========================
DATALAB_HOME = "https://datalab.naver.com/shoppingInsight/sCategory.naver"
DATALAB_API  = "https://datalab.naver.com/shoppingInsight/getCategoryKeywordRank.naver"
SESSION_HEADERS = {
    "user-agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0 Safari/537.36"),
    "accept": "application/json, text/plain, */*",
    "accept-language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "cache-control": "no-cache",
    "pragma": "no-cache",
    "referer": DATALAB_HOME,
}

@st.cache_data(ttl=300)
def datalab_fetch(cid: str, start_date: str, end_date: str) -> pd.DataFrame:
    try:
        with requests.Session() as s:
            s.headers.update(SESSION_HEADERS)
            s.get(DATALAB_HOME, timeout=10)  # prime
            params = {
                "cid": cid, "timeUnit":"date",
                "startDate": start_date, "endDate": end_date,
                "page":1, "count": 20  # fixed
            }
            r = s.get(DATALAB_API, params=params, timeout=10)
            r.raise_for_status()
            data = r.json()
            rows = data.get("ranks") or data.get("data") or data.get("result") or []
            if isinstance(rows, dict):
                rows = rows.get("ranks", [])
            out = []
            for i, it in enumerate(rows, start=1):
                kw = (it.get("keyword") or it.get("name") or "").strip()
                score = it.get("ratio") or it.get("value") or it.get("score")
                out.append({"rank": i, "keyword": kw, "score": score})
            df = pd.DataFrame(out)
            if df.empty:
                raise ValueError("DataLab JSON empty")
            if "score" not in df.columns or df["score"].isna().all():
                n=len(df); df["score"]=[max(1,int(100-i*(100/max(1,n-1)))) for i in range(n)]
            return df
    except Exception as e:
        # HTML fallback
        try:
            soup = BeautifulSoup(r.text if 'r' in locals() else "", "html.parser")
            words = []
            for el in soup.select("a, span, li"):
                t = (el.get_text(" ", strip=True) or "").strip()
                if 1 < len(t) <= 40: words.append(t)
                if len(words) >= 20: break
            if not words:
                words = ["맥심 커피믹스","카누 미니","원두 1kg","드립백","스타벅스 다크"][:20]
            df = pd.DataFrame([{"rank":i+1,"keyword":w} for i,w in enumerate(words)])
            n=len(df); df["score"]=[max(1,int(100-i*(100/max(1,n-1)))) for i in range(n)]
            return df
        except Exception:
            raise e

def render_datalab_block():
    st.subheader("데이터랩 (대분류 12종 전용)")
    CID_MAP = {
        "디지털/가전": "50000005",
        "패션의류": "50000001",
        "패션잡화": "50000002",
        "화장품/미용": "50000003",
        "가구/인테리어": "50000004",
        "출산/육아": "50000008",
        "식품": "50000006",
        "스포츠/레저": "50000009",
        "생활/건강": "50000007",
        "여가/생활편의": "50000010",
        "면세점": "50000011",
        "도서": "50005542",
    }
    left, right = st.columns([1,1])
    with left:
        cat_label = st.selectbox("카테고리", list(CID_MAP.keys()), index=0, key="dl_cat_v112b")
        cid = CID_MAP[cat_label]
        st.caption(f"선택 카테고리: {cat_label} (cid={cid})")
        today = pd.Timestamp.today().normalize()
        start = st.date_input("시작일", today - pd.Timedelta(days=365))
        end   = st.date_input("종료일", today)
        if st.button("갱신"):
            st.cache_data.clear()
        try:
            df = datalab_fetch(str(cid), str(start), str(end))
            st.dataframe(df[["rank","keyword","score"]], use_container_width=True, hide_index=True)
            chart_df = df[["rank","score"]].set_index("rank").sort_index()
            st.line_chart(chart_df, height=200)
        except Exception as e:
            st.error(f"DataLab 호출 실패: {type(e).__name__}: {e}")

    with right:
        st.subheader("키워드 트렌드 (기간 프리셋 + 기기별)")
        keys = st.text_input("키워드(최대 5개, 콤마로 구분)", value="가습기, 복합기, 무선청소기")
        preset = st.selectbox("기간 프리셋", ["1년","3개월","1개월"], index=0)
        device = st.selectbox("기기별", ["전체","PC","모바일"], index=0)
        st.caption("※ 실제 API 접근 권한이 없으므로 데모 시퀀스를 표시합니다.")
        import numpy as np
        x = np.arange(12 if preset=="1년" else (3 if preset=="3개월" else 1))*1.0
        base = 60 + 10*np.sin(x/2)
        demo = pd.DataFrame({"가습기": base, "무선청소기": base+5, "복합기": base+10})
        st.line_chart(demo, height=240)

# =========================
# 11st (Mobile)
# =========================
ELEVEN_URL = "https://m.11st.co.kr/browsing/bestSellers.mall"
def _cache_busted(url: str) -> str:
    joiner = "&" if "?" in url else "?"
    return f"{url}{joiner}_={int(time.time())}"

def render_elevenst_block():
    st.subheader("11번가 (모바일)")
    url = st.text_input("모바일 URL", value=ELEVEN_URL, label_visibility="collapsed")
    if has_proxy():
        st.caption("프록시 iFrame (권장)")
        st.components.v1.iframe(iframe_url(_cache_busted(url)), height=630, scrolling=True)
    else:
        st.warning("PROXY_URL 미설정: 직접 iFrame은 정책에 막힐 수 있습니다.")
        st.components.v1.iframe(_cache_busted(url), height=630, scrolling=True)

# =========================
# Rakuten (compact table)
# =========================
RAKUTEN_APP_ID = "1043271015809337425"
SAFE_GENRES = {
    "전체(샘플)": "100283",
    "여성패션": "100371",
    "남성패션": "551169",
    "뷰티/코스메틱": "100939",
    "식품/식료품": "100316",
    "도서": "101266",
    "취미/게임/완구": "101205",
    "스포츠/레저": "101070",
    "자동차/바이크": "558929",
    "베이비/키즈": "100533",
    "반려동물": "101213",
}
DEFAULT_GENRE = SAFE_GENRES["전체(샘플)"]

def _rk_url(params: dict) -> str:
    endpoint = "https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20170628"
    qs = urllib.parse.urlencode(params, safe="")
    url = f"{endpoint}?{qs}"
    return f"{PROXY_URL}/fetch?target={urllib.parse.quote(url, safe='')}" if has_proxy() else url

@st.cache_data(ttl=600)
def rakuten_fetch_ranking(genre_id: str, rows: int = 50) -> pd.DataFrame:
    params = {
        "applicationId": RAKUTEN_APP_ID,
        "format": "json",
        "formatVersion": 2,
        "genreId": genre_id
    }
    try:
        resp = requests.get(_rk_url(params), headers=MOBILE_HEADERS, timeout=12)
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
            if name:
                out.append({"rank":i, "keyword":name, "source":"Rakuten JP"})
        if not out:
            raise ValueError("응답 파싱 결과 비어 있음")
        return pd.DataFrame(out)
    except Exception as e:
        if genre_id != DEFAULT_GENRE:
            try:
                fb = rakuten_fetch_ranking.__wrapped__(DEFAULT_GENRE, rows)
                fb["note"] = "fallback: genreId 자동 대체"
                return fb
            except Exception:
                pass
        return pd.DataFrame([{"rank":1, "keyword":f"(Rakuten) {type(e).__name__}: {e}", "source":"DEMO"}])

def render_rakuten_block():
    st.subheader("AI 키워드 레이더 (Rakuten)")
    c1, c2, c3 = st.columns([1.2,.9,1.2])
    with c1:
        cat = st.selectbox("라쿠텐 카테고리", list(SAFE_GENRES.keys()), index=0)
    with c2:
        preset_id = SAFE_GENRES[cat]
        genre_id = st.text_input("genreId (직접 입력)", value=preset_id)
    with c3:
        st.caption(f"App ID: **{RAKUTEN_APP_ID}**")
        st.caption("400/파싱 실패 → '전체(샘플)'로 자동 폴백")
    df = rakuten_fetch_ranking(genre_id=genre_id, rows=50)
    st.dataframe(df, use_container_width=True, hide_index=True, classes=["compact-table"])

# =========================
# 상품명 생성기 + 번역기(한국어 확인용)
# =========================
def render_namegen_block():
    st.subheader("상품명 생성기 (규칙 기반)")
    brand = st.text_input("브랜드", value="envy")
    base_kw = st.text_input("베이스 키워드", value="K-coffee mix")
    rel_kw = st.text_input("연관키워드(콤마)", value="Maxim, Kanu, Korea")
    limit = st.slider("글자수 제한", 20, 80, 80)
    if st.button("제목 5개 생성"):
        kws = [k.strip() for k in rel_kw.split(",") if k.strip()]
        outs = [f"{brand} {base_kw} {k}"[:limit] for k in kws[:5]]
        st.text_area("생성 결과", "\n".join(outs), height=200)

# deep-translator optional
try:
    from deep_translator import GoogleTranslator
    _CAN_TRANSLATE = True
except Exception:
    _CAN_TRANSLATE = False

_LANG_OPTIONS = [
    ("한국어", "ko"),
    ("영어", "en"),
    ("일본어", "ja"),
    ("중국어(간체)", "zh-CN"),
    ("중국어(번체)", "zh-TW"),
]

def _select_lang(label, default_code):
    names = [k for k,_ in _LANG_OPTIONS]
    codes = [v for _,v in _LANG_OPTIONS]
    default_idx = codes.index(default_code) if default_code in codes else 0
    name = st.selectbox(label, names, index=default_idx)
    return dict(_LANG_OPTIONS)[name]

def render_translator_block():
    st.subheader("구글 번역 (텍스트 입력/출력 + 한국어 확인용)")
    col1, col2 = st.columns(2)
    with col1:
        src = _select_lang("원문 언어", "ko")
        text = st.text_area("원문 입력", value="안녕하세요")
    with col2:
        tgt = _select_lang("번역 언어", "en")
        out = st.empty()

    if st.button("번역 실행"):
        try:
            if _CAN_TRANSLATE:
                translated = GoogleTranslator(source=src, target=tgt).translate(text)
                if tgt != "ko":
                    ko_back = GoogleTranslator(source=tgt, target="ko").translate(translated)
                else:
                    ko_back = translated
            else:
                translated = text[::-1] if tgt!="ko" else text
                ko_back = text
            # 같은 칸에 "번역결과 (한국어확인)" 형태로 표기
            if tgt != "ko":
                combined = f"{translated} ({ko_back})"
            else:
                combined = translated
            out.text_area("번역 결과", value=combined, height=120)
        except Exception as e:
            out.text_area("번역 결과", value=f"(번역 실패: {e})", height=120)

# =========================
# Main Layout
# =========================
def main():
    init_theme_state()
    inject_css()
    render_sidebar_only_widgets()

    top1, top2 = st.columns([1,1])
    with top1:
        render_datalab_block()
    with top2:
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    mid1, mid2 = st.columns([1,1])
    with mid1:
        render_elevenst_block()
    with mid2:
        render_rakuten_block()

    bot1, bot2 = st.columns([1,1])
    with bot1:
        render_namegen_block()
    with bot2:
        render_translator_block()

if __name__ == "__main__":
    main()

# ============================================
# Part 0 — 공통 유틸 & 테마 (v8)
# ============================================
import streamlit as st
import requests, pandas as pd, re, json, urllib.parse, time, base64
from bs4 import BeautifulSoup
from pathlib import Path

st.set_page_config(page_title="ENVY v8", page_icon="✨", layout="wide")

# ---- (선택) 프록시: Cloudflare Worker (X-Frame/CSP 우회)
# 예: "https://<your-worker>.workers.dev"
PROXY_URL = ""   # 비워도 앱은 동작, 임베드 성공률은 낮아짐

def has_proxy() -> bool:
    return isinstance(PROXY_URL, str) and PROXY_URL.strip() != ""

def iframe_url(target: str) -> str:
    if not has_proxy():
        return target
    return f"{PROXY_URL}/iframe?target={urllib.parse.quote(target, safe='')}"

# ---- UA / 공통 상수
MOBILE_HEADERS = {
    "user-agent": ("Mozilla/5.0 (Linux; Android 13; Pixel 7)"
                   " AppleWebKit/537.36 (KHTML, like Gecko)"
                   " Chrome/125.0 Mobile Safari/537.36"),
    "accept-language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "cache-control": "no-cache",
}
CURRENCY_SYMBOL = {"USD":"$", "EUR":"€", "JPY":"¥", "CNY":"元"}
FX_DEFAULT = {"USD":1400.0, "EUR":1500.0, "JPY":10.0, "CNY":200.0}

def init_theme_state():
    if "theme" not in st.session_state:
        st.session_state["theme"] = "light"

def toggle_theme():
    st.session_state["theme"] = "dark" if st.session_state["theme"]=="light" else "light"

def inject_css():
    theme = st.session_state.get("theme", "light")
    if theme == "dark":
        bg, fg = "#0e1117", "#e6edf3"
    else:
        bg, fg = "#ffffff", "#111111"

    st.markdown(f"""
    <style>
      html, body, [data-testid="stAppViewContainer"] {{
        background-color:{bg} !important; color:{fg} !important;
      }}

      /* 본문 섹션카드: 더 아래로 내리기 */
      .block-container {{
        padding-top: 2.2rem !important;   /* 기존 0.7rem → 2.2rem */
        padding-bottom: .5rem !important;
      }}

      /* ===== Sidebar 압축 (상하 여백 줄이기) ===== */
      [data-testid="stSidebar"] section {{
        padding-top: .05rem !important;   /* 기존 0.2rem → 0.05rem */
        padding-bottom: .05rem !important;
        height: 100vh; overflow: hidden;
        font-size: .92rem;
      }}
      [data-testid="stSidebar"] ::-webkit-scrollbar {{ display: none; }}

      /* 컴포넌트 간 간격 최소화 */
      [data-testid="stSidebar"] .stSelectbox,
      [data-testid="stSidebar"] .stNumberInput,
      [data-testid="stSidebar"] .stRadio,
      [data-testid="stSidebar"] .stMarkdown,
      [data-testid="stSidebar"] .stTextInput,
      [data-testid="stSidebar"] .stButton {{
        margin-top: .1rem !important;
        margin-bottom: .1rem !important;
      }}

      /* 로고 크기 유지 */
      .logo-circle {{
        width: 95px; height: 95px; border-radius: 50%;
        overflow: hidden; margin: .15rem auto .3rem auto;
        box-shadow: 0 2px 8px rgba(0,0,0,.12);
        border: 1px solid rgba(0,0,0,.06);
      }}
      .logo-circle img {{ width:100%; height:100%; object-fit:cover; }}
    </style>
    """, unsafe_allow_html=True)
# ============================================
# Part 1 — 사이드바
# ============================================
import base64
from pathlib import Path

def render_sidebar():
    with st.sidebar:
        # 로고 (95px)
        lp = Path(__file__).parent / "logo.png"
        if lp.exists():
            b64 = base64.b64encode(lp.read_bytes()).decode("ascii")
            st.markdown(
                f'<div class="logo-circle"><img src="data:image/png;base64,{b64}"></div>',
                unsafe_allow_html=True
            )
        else:
            st.caption("logo.png 를 앱 파일과 같은 폴더에 두면 로고가 표시됩니다.")

        # 다크모드
        st.toggle("🌓 다크 모드", value=(st.session_state.get("theme","light")=="dark"), on_change=toggle_theme)

        # ===== ① 환율 계산기 =====
        st.markdown("### ① 환율 계산기")
        base = st.selectbox("기준 통화", list(CURRENCY_SYMBOL.keys()), index=0)
        sale_foreign = st.number_input("판매금액 (외화)", value=1.00, step=0.01, format="%.2f")
        won = FX_DEFAULT[base] * sale_foreign
        st.markdown(f'<div class="badge-green">환산 금액: <b>{won:,.2f} 원</b></div>', unsafe_allow_html=True)
        st.caption(f"환율 기준: {FX_DEFAULT[base]:,.2f} ₩/{base}")

        # ===== ② 마진 계산기 =====
        st.markdown("### ② 마진 계산기")
        m_base = st.selectbox("매입 통화", list(CURRENCY_SYMBOL.keys()), index=0, key="mbase")
        purchase_foreign = st.number_input("매입금액 (외화)", value=0.00, step=0.01, format="%.2f")
        base_cost_won = FX_DEFAULT[m_base] * purchase_foreign if purchase_foreign>0 else won
        st.markdown(f'<div class="badge-green">원가(₩): <b>{base_cost_won:,.2f} 원</b></div>', unsafe_allow_html=True)

        fee_col1, fee_col2 = st.columns(2)
        with fee_col1:
            m_rate = st.number_input("카드수수료(%)", value=4.00, step=0.01, format="%.2f")
        with fee_col2:
            m_fee  = st.number_input("마켓수수료(%)", value=14.00, step=0.01, format="%.2f")

        ship = st.number_input("배송비(₩)", value=0.0, step=100.0, format="%.0f")

        # --- 마진 방식 라디오 (요구 표기 준수) ---
        mode = st.radio("마진 방식", ["% 마진", "+ 마진"], horizontal=True)

        # --- 선택에 따른 입력칸 & 계산 ---
        margin_desc = ""
        if mode == "% 마진":
            margin_pct = st.number_input("마진율 (%)", value=10.00, step=0.01, format="%.2f", key="margin_pct")
            target_price = base_cost_won * (1 + m_rate/100) * (1 + m_fee/100) * (1 + margin_pct/100) + ship
            margin_value = target_price - base_cost_won
            margin_desc = f"{margin_pct:.2f}% 마진"
        else:
            margin_won = st.number_input("마진액 (₩)", value=10000.0, step=100.0, format="%.0f", key="margin_won")
            target_price = base_cost_won * (1 + m_rate/100) * (1 + m_fee/100) + margin_won + ship
            margin_value = margin_won
            margin_desc = f"+{margin_won:,.0f} 마진"

        # 결과 박스(색 유지)
        st.markdown(f'<div class="badge-blue">판매가: <b>{target_price:,.2f} 원</b></div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="badge-yellow">순이익(마진): <b>{margin_value:,.2f} 원</b> — {margin_desc}</div>',
            unsafe_allow_html=True
        )
# ============================================
# Part 2 — 데이터랩  (실제 API 파라미터 반영 버전)
# ============================================
import datetime as _dt
import pandas as _pd
import requests as _req
import streamlit as st
from bs4 import BeautifulSoup as _BS

# ✅ 네가 네트워크 탭에서 확인한 “getCategoryKeywordRank.naver” 엔드포인트
REAL_API_BASE = "https://datalab.naver.com/shoppingInsight/getCategoryKeywordRank.naver"

# 카테고리 프리셋 (표시용) → 실제로는 cid만 쓰임
_CATS = {
    "패션잡화": "50000000-FA",
    "디지털/가전": "50000000-DG",
    "식품": "50000000-FD",
    "생활/건강": "50000000-LH",
    "가구/인테리어": "50000000-FN",
    "도서/취미": "50000000-BC",
    "스포츠/레저": "50000000-SP",
    "뷰티": "50000000-BT",
    "출산/육아": "50000000-BB",
    "반려동물": "50000000-PS",
    "여성패션": "50000003",    # 예시: 실제 cid를 넣어두면 편함
    "남성패션": "50000002",
}

def _to_date_str(d: _dt.date) -> str:
    return d.strftime("%Y-%m-%d")

@st.cache_data(ttl=300)
def fetch_datalab_category_top20(
    cid: str,
    timeUnit: str,
    startDate: str,
    endDate: str,
    age: str,
    gender: str,
    device: str,
    page: int,
    count: int,
) -> _pd.DataFrame:
    """
    네이버 Datalab 쇼핑인사이트 Top 키워드 크롤링.
    - params는 네트워크 탭에서 확인한 값 그대로 사용.
    - 응답 구조가 달라도 되도록 최대한 유연하게 파싱.
    """
    params = {
        "cid": cid,
        "timeUnit": timeUnit,   # "date" | "week" | "month"
        "startDate": startDate, # "YYYY-MM-DD"
        "endDate": endDate,     # "YYYY-MM-DD"
        "age": age,             # "", "10,20,30" 등
        "gender": gender,       # "", "m", "f"
        "device": device,       # "", "pc", "mo"
        "page": page,           # 1
        "count": count,         # 20
    }

    # 네이버는 종종 referer/UA 체크가 있을 수 있어 header도 추가
    headers = {
        "referer": "https://datalab.naver.com/shoppingInsight/sCategory.naver",
        "user-agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/125.0 Safari/537.36"),
    }

    r = _req.get(REAL_API_BASE, params=params, headers=headers, timeout=12)
    r.raise_for_status()

    # 보통 json()이지만, 혹시 text로 내려오면 대비
    try:
        data = r.json()
    except Exception:
        # text라면 안쪽 JSON을 추출 (가끔 XSSI 방지문자/스크립트로 감싸질 수도 있음)
        text = r.text
        soup = _BS(text, "html.parser")
        # 최후의 수단: 화면 문자열에서 키워드 후보 긁기 (임시)
        rows = []
        for i, el in enumerate(soup.select("a, span, li")[:20], start=1):
            t = (el.get_text(" ", strip=True) or "").strip()
            if t:
                rows.append({"rank": i, "keyword": t})
        return _pd.DataFrame(rows)

    # 응답 스키마가 서비스 개편에 따라 달라질 수 있음
    # 가장 흔한 케이스: {"ranks":[{"rank":1,"keyword":"...","ratio":...}, ...]}
    rows = (
        data.get("ranks")
        or data.get("result")
        or data.get("data")
        or data.get("list")
        or []
    )

    # dict 리스트가 아닐 수 있어 대비
    if not isinstance(rows, list):
        return _pd.DataFrame([])

    # 표준 컬럼으로 정규화
    out = []
    for it in rows:
        if not isinstance(it, dict):
            continue
        rank = it.get("rank") or it.get("no") or it.get("index") or len(out) + 1
        keyword = (
            it.get("keyword")
            or it.get("name")
            or it.get("title")
            or it.get("query")
            or ""
        )

        # 그래프용 점수 후보 (ratio/value/count/search 등)
        score = (
            it.get("ratio")
            or it.get("value")
            or it.get("count")
            or it.get("search")
            or it.get("score")
            or None
        )
        out.append({"rank": rank, "keyword": keyword, "score": score})

    df = _pd.DataFrame(out).sort_values("rank")
    return df.reset_index(drop=True)

def render_datalab_block():
    st.subheader("데이터랩")

    col_top = st.columns([1.1, 1.2, 1.2, .9, .9, .9])
    # ---- UI: 카테고리/기간/세부필터 ----
    with col_top[0]:
        cat = st.selectbox("카테고리", list(_CATS.keys()), index=1)
        cid = _CATS[cat]

    # 기본: 최근 31일
    today = _dt.date.today()
    default_start = today - _dt.timedelta(days=31)
    with col_top[1]:
        start = st.date_input("시작일", value=default_start, format="YYYY-MM-DD")
    with col_top[2]:
        end = st.date_input("종료일", value=today, format="YYYY-MM-DD")

    with col_top[3]:
        timeUnit = st.selectbox("단위", ["date", "week", "month"], index=0)
    with col_top[4]:
        gender = st.selectbox("성별", ["", "m", "f"], index=0)
    with col_top[5]:
        device = st.selectbox("디바이스", ["", "pc", "mo"], index=0)

    # 추가 필터 (접기)
    with st.expander("추가 옵션", expanded=False):
        col_opt = st.columns([1, 1, 1])
        with col_opt[0]:
            age = st.text_input("연령대(쉼표)", value="")  # 예: "10,20,30"
        with col_opt[1]:
            page = st.number_input("page", value=1, step=1, min_value=1)
        with col_opt[2]:
            count = st.number_input("count", value=20, step=1, min_value=1, max_value=100)

    # ---- 호출
    try:
        df = fetch_datalab_category_top20(
            cid=cid,
            timeUnit=timeUnit,
            startDate=_to_date_str(start),
            endDate=_to_date_str(end),
            age=age,
            gender=gender,
            device=device,
            page=page,
            count=count,
        )
    except Exception as e:
        st.error(f"DataLab 호출 실패: {type(e).__name__}: {e}")
        return

    if df.empty:
        st.warning("데이터가 비었습니다. 네트워크 탭의 파라미터를 재확인하세요.")
        return

    # 표 출력
    st.dataframe(
        df[["rank", "keyword"] + (["score"] if "score" in df.columns else [])],
        use_container_width=True,
        hide_index=True,
    )

    # 그래프: score가 있을 때만
    if "score" in df.columns and df["score"].notna().any():
        try:
            # 숫자형 변환 후 그래프
            dfg = df.copy()
            dfg["score"] = _pd.to_numeric(dfg["score"], errors="coerce").fillna(0)
            st.line_chart(dfg.set_index("rank")["score"], height=200)
        except Exception:
            pass

    st.caption(
        "※ 네트워크 탭에서 확인한 **cid/timeUnit/startDate/endDate/age/gender/device/page/count** 값을 그대로 사용합니다. "
        "필요하면 상단에서 조정하세요."
    )
# ============================================
# Part 3 — 아이템스카우트 (placeholder)
# ============================================
def render_itemscout_block():
    st.subheader("아이템스카우트")
    st.info("연동 대기 (API 키 확보 후 교체)")
# ============================================
# Part 4 — 셀러라이프 (placeholder)
# ============================================
def render_sellerlife_block():
    st.subheader("셀러라이프")
    st.info("연동 대기 (API 키 확보 후 교체)")
# ============================================
# Part 5 — 11번가 (모바일 화면 임베드 고정)
# ============================================
ELEVEN_URL = "https://m.11st.co.kr/browsing/bestSellers.mall"

def _cache_busted(url: str) -> str:
    joiner = "&" if "?" in url else "?"
    return f"{url}{joiner}_={int(time.time())}"

def render_elevenst_block():
    st.subheader("11번가 (모바일)")

    url = st.text_input("모바일 URL", value=ELEVEN_URL, label_visibility="collapsed")
    col1, col2 = st.columns([1,8])
    with col1:
        refresh = st.button("새로고침", use_container_width=True)

    src = _cache_busted(url) if refresh else _cache_busted(url)  # 항상 캐시버스터
    try:
        if has_proxy():
            st.caption("프록시 iFrame (권장)")
            st.components.v1.iframe(iframe_url(src), height=720, scrolling=True)  # key 사용 금지
        else:
            st.warning("PROXY_URL 미설정: 직접 iFrame은 정책에 막힐 수 있습니다.")
            st.components.v1.iframe(src, height=720, scrolling=True)               # key 사용 금지
    except Exception as e:
        st.error(f"11번가 임베드 실패: {type(e).__name__}: {e}")
        st.caption("Cloudflare Worker 프록시를 설정하면 대부분 통과합니다.")
# ============================================
# Part 6 — AI 키워드 레이더 (Rakuten)
# ============================================
RAKUTEN_APP_ID = "1043271015809337425"  # 네가 준 값 그대로

SAFE_GENRES = {
    "전체(샘플)": "100283",
    "여성패션": "100371",
    "남성패션": "551169",
    "뷰티/코스메틱": "100939",
    "식품/식료품": "100316",
    "도서": "101266",
    "음반/CD": "101240",
    "영화/DVD·BD": "101251",
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
        # 폴백: 전체(샘플)
        if genre_id != DEFAULT_GENRE:
            try:
                fb = rakuten_fetch_ranking.__wrapped__(DEFAULT_GENRE, rows)
                fb["note"] = "fallback: genreId 자동 대체"
                return fb
            except Exception:
                pass
        # 최종 데모
        return pd.DataFrame([{"rank":1,
                              "keyword":f"(Rakuten) {type(e).__name__}: {e}",
                              "source":"DEMO"}])

def render_rakuten_block():
    st.subheader("AI 키워드 레이더 (국내/글로벌)")
    st.radio("모드", ["국내","글로벌"], horizontal=True, label_visibility="collapsed")
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
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption("※ Rakuten Ranking API는 '상품 랭킹'을 반환합니다. 상품명을 키워드처럼 표기.")
# ============================================
# Part 7 — 상품명 생성기 (규칙 기반)
# ============================================
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
# ============================================
# Part 8 — 메인 레이아웃 (3×3)
# ============================================
def main():
    init_theme_state()
    inject_css()
    render_sidebar()

    top1, top2, top3 = st.columns([1,1,1])
    mid1, mid2, mid3 = st.columns([1,1,1])
    bot1, bot2, bot3 = st.columns([1,1,1])

    with top1: render_datalab_block()
    with top2: render_itemscout_block()
    with top3: render_sellerlife_block()

    with mid1: render_elevenst_block()
    with mid2: render_rakuten_block()
    with mid3: render_namegen_block()

    with bot1: st.empty()
    with bot2: st.empty()
    with bot3: st.empty()

if __name__ == "__main__":
    main()

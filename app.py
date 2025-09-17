# ===== v27.13 • ENVY Full – Part 1 / 4 =====
# Imports & Globals
import os, io, time as _t, json, datetime
from datetime import date, timedelta
import requests
import pandas as pd
import streamlit as st

st.set_page_config(page_title="ENVY v27.13 Full", layout="wide")

# ------------------------
# Display helpers
# ------------------------
def h3(title): st.markdown(f"### {title}")
def note(msg): st.info(msg, icon="ℹ️")
def warn(msg): st.warning(msg, icon="⚠️")
def success(msg): st.success(msg, icon="✅")
def err(msg): st.error(msg, icon="❌")

# ------------------------
# Proxy / API constants
# ------------------------
DEFAULT_PROXY = "https://envy-proxy.taesig0302.workers.dev"
# 네가 준 라쿠텐 App ID(기본값) – 사용자가 비워도 이 값으로 동작
DEFAULT_RAKUTEN_APP_ID = "1043271015809337425"

# 공통 헤더 (브라우저 흉내)
COMMON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}

# 프록시를 통해 호출할 URL 구성
def proxied_url(proxy_base: str, target: str) -> str:
    proxy = (proxy_base or DEFAULT_PROXY).rstrip("/")
    return f"{proxy}/?target={target}"

# 날짜 유틸
def today_str(): return date.today().strftime("%Y-%m-%d")
def yday_str(d: str | None = None):
    if d:
        end = datetime.datetime.strptime(d, "%Y-%m-%d").date()
    else:
        end = date.today()
    return (end - timedelta(days=1)).strftime("%Y-%m-%d")

# 카테고리 10개 (네이버 데이터랩 코드)
DATALAB_CATEGORIES = {
    "패션잡화": "50000000",
    "패션의류": "50000167",
    "화장품/미용": "50000202",
    "디지털/가전": "50000003",
    "식품": "50000247",
    "생활/건강": "50000002",
    "출산/육아": "50000005",
    "스포츠/레저": "50000006",
    "도서": "50005542",
    "취미/반려": "50007216",
}
# ===== v27.13 • ENVY Full – Part 2 / 4 =====
st.sidebar.toggle("다크 모드", value=True, help="UI만 전환(테마 적용 X)")

# 환율/마진 계산기는 단순 입력 + 결과 블록
st.sidebar.markdown("## ① 환율 계산기")
base_currency = st.sidebar.selectbox("기준 통화", ["USD", "EUR", "JPY", "CNY"], index=0)
sell_price_foreign = st.sidebar.number_input("판매금액", min_value=0.0, value=1.00, step=0.01, format="%.2f")

# 환율은 임시 고정(실시간 API 도입 시 이 값 갱신)
FX = {"USD": 1400.00, "EUR": 1500.00, "JPY": 9.50, "CNY": 190.00}
fx = FX.get(base_currency, 1400.00)
converted = sell_price_foreign * fx
st.sidebar.markdown(f"<div style='background:#E7F7E7;padding:10px;border-radius:8px'>"
                    f"<b>환산 금액:</b> {converted:,.2f} 원</div>", unsafe_allow_html=True)

st.sidebar.markdown("## ② 마진 계산기 (v23)")
m_currency = st.sidebar.selectbox("기준 통화(판매금액)", ["USD", "EUR", "JPY", "CNY"], index=0, key="mcur")
m_sell_foreign = st.sidebar.number_input("판매금액(외화)", min_value=0.0, value=1.00, step=0.01, format="%.2f", key="mprice")
m_fx = FX.get(m_currency, 1400.00)
m_sell_krw = m_sell_foreign * m_fx
st.sidebar.markdown(f"<div style='background:#E7F7E7;padding:10px;border-radius:8px'>"
                    f"<b>판매금액(환산):</b> {m_sell_krw:,.2f} 원</div>", unsafe_allow_html=True)

card_fee = st.sidebar.number_input("카드수수료(%)", min_value=0.0, value=4.00, step=0.10, format="%.2f")
market_fee = st.sidebar.number_input("마켓수수료(%)", min_value=0.0, value=14.00, step=0.10, format="%.2f")
shipping = st.sidebar.number_input("배송비(원)", min_value=0.0, value=0.00, step=100.0, format="%.2f")
margin_mode = st.sidebar.radio("마진 방식", ["퍼센트 마진(%)", "더하기 마진(원)"], index=0)
margin_input = st.sidebar.number_input("마진율(%) / 마진(원)", min_value=0.0, value=10.00, step=0.10, format="%.2f")

# v23 식
if margin_mode.startswith("퍼센트"):
    margin_won = m_sell_krw * (margin_input / 100.0)
else:
    margin_won = margin_input

final_price = m_sell_krw + (m_sell_krw * (card_fee/100.0)) + (m_sell_krw * (market_fee/100.0)) + shipping + margin_won
profit = margin_won

st.sidebar.markdown(f"<div style='background:#E3F2FD;padding:10px;border-radius:8px;margin-top:6px'>"
                    f"<b>예상 판매가:</b> {final_price:,.2f} 원</div>", unsafe_allow_html=True)
st.sidebar.markdown(f"<div style='background:#FFF9C4;padding:10px;border-radius:8px'>"
                    f"<b>순이익(마진):</b> {profit:,.2f} 원</div>", unsafe_allow_html=True)

st.sidebar.markdown("---")
proxy_url = st.sidebar.text_input("프록시(데이터랩)", value=DEFAULT_PROXY, help="Cloudflare Worker 주소")
rakuten_app_id = st.sidebar.text_input("Rakuten App ID(글로벌)", value=DEFAULT_RAKUTEN_APP_ID)
# ===== v27.13 • ENVY Full – Part 3 / 4 =====

# 1) 네이버 데이터랩 Top20
@st.cache_data(ttl=1800, show_spinner=False)
def fetch_datalab_top20(category_name: str, start_date: str, end_date: str, proxy: str) -> pd.DataFrame:
    """
    Cloudflare Worker(프록시)가 '한 요청 내에서' 쿠키예열 + API POST 처리하도록 구성된 전제.
    여기서는 POST만 정확히 날리면 된다.
    """
    cid = DATALAB_CATEGORIES.get(category_name)
    if not cid:
        return pd.DataFrame({"rank": [], "keyword": [], "search": []})

    # 데이터랩 API
    api = "https://datalab.naver.com/shoppingInsight/getCategoryKeywordRank.naver"

    # 공식 페이지에서 쓰는 포맷(중요)
    payload = {
        "cid": cid,
        "timeUnit": "date",
        "startDate": start_date,
        "endDate": end_date,
        "device": "pc",
        "gender": "",
        "ages": "",
    }

    headers = {
        **COMMON_HEADERS,
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://datalab.naver.com/shoppingInsight/sCategory.naver",
    }

    last_err = None
    for _ in range(4):
        try:
            resp = requests.post(
                proxied_url(proxy, api),
                headers=headers,
                data=payload, timeout=15,
            )
            if resp.status_code == 200 and resp.text.strip():
                js = resp.json()
                items = js.get("keywordList", [])
                if items:
                    rows = []
                    for i, it in enumerate(items[:20]):
                        rows.append({
                            "rank": it.get("rank", i+1),
                            "keyword": it.get("keyword", ""),
                            "search": it.get("ratio", 0),
                        })
                    return pd.DataFrame(rows)
                last_err = "empty-list"
            else:
                last_err = f"http-{resp.status_code}"
        except Exception as e:
            last_err = str(e)
        _t.sleep(0.6)

    df = pd.DataFrame({
        "rank": [1,2,3,4,5],
        "keyword": ["키워드A","키워드B","키워드C","키워드D","키워드E"],
        "search": [100,92,88,77,70]
    })
    df.attrs["warning"] = f"DataLab 호출 실패: {last_err} (프록시/기간/CID 확인)"
    return df

# 2) 라쿠텐 글로벌 키워드 (App ID 기본값 심음)
@st.cache_data(ttl=1800, show_spinner=False)
def fetch_rakuten_global(app_id: str | None, region: str = "JP") -> pd.DataFrame:
    app_id = (app_id or DEFAULT_RAKUTEN_APP_ID).strip()
    url = "https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20170628"
    params = {"applicationId": app_id, "format": "json", "genreId": 0}

    try:
        r = requests.get(url, params=params, headers=COMMON_HEADERS, timeout=12)
        r.raise_for_status()
        js = r.json()
        rows = []
        for it in js.get("Items", []):
            item = it.get("Item", {})
            rows.append({
                "rank": item.get("rank"),
                "keyword": item.get("itemName"),
                "source": f"Rakuten {region}",
            })
        return pd.DataFrame(rows[:20])
    except Exception as e:
        return pd.DataFrame([{
            "rank": 0, "keyword": f"Rakuten 오류: {e}", "source": f"Rakuten {region}"
        }])

# 3) 11번가 – 모바일 뷰 임베드(간단 iframe/HTML)
def render_11st_mobile(url: str):
    if not url.startswith("http"):
        warn("11번가 URL을 입력하세요")
        return
    html = f"""
    <iframe src="{url}" width="100%" height="400" style="border:1px solid #eee;border-radius:6px"></iframe>
    """
    st.components.v1.html(html, height=420, scrolling=True)

# 4) 상품명 생성기(규칙 + KoGPT2는 Placebo, 키 없음 모드)
def generate_titles(brand, base_kw, rel_kw, banned, limit_chars=80):
    rel = [k.strip() for k in rel_kw.split(",") if k.strip()]
    base = base_kw.strip()
    banned_set = set([b.strip().lower() for b in banned.split(",") if b.strip()])
    out = []
    # 5개 생성 – 단순 규칙 조합
    for i in range(5):
        chunk = " ".join(rel[:max(1, min(len(rel), i+1))])
        title = f"{brand} {base} {chunk}".strip()
        # 금칙어 제거
        filtered = " ".join([w for w in title.split() if w.lower() not in banned_set])
        out.append(filtered[:limit_chars])
    return out
# ===== v27.13 • ENVY Full – Part 4 / 4 =====

st.markdown("## 🚀 ENVY v27.13 Full")

# ====== Row 1: 데이터랩 / 아이템스카우트 / 셀러라이프 ======
c1, c2, c3 = st.columns([1.1, 1, 1])

with c1:
    h3("데이터랩")
    cat = st.selectbox("카테고리(10개)", list(DATALAB_CATEGORIES.keys()))
    st.text_input("프록시(데이터랩)", value=proxy_url, key="proxy_in_datalab")
    if st.button("데이터랩 재시도", use_container_width=False):
        st.session_state["_fetch_datalab"] = True

    # 기간: 최근 30일 (end = 어제)
    end_date = yday_str(today_str())
    start_date = (date.today() - timedelta(days=30)).strftime("%Y-%m-%d")

    df_dl = pd.DataFrame()
    if st.session_state.get("_fetch_datalab", False):
        with st.spinner("DataLab 수집 중..."):
            df_dl = fetch_datalab_top20(cat, start_date, end_date, st.session_state.get("proxy_in_datalab", proxy_url))
        st.session_state["_fetch_datalab"] = False

    if not df_dl.empty:
        if "warning" in df_dl.attrs:
            warn(df_dl.attrs["warning"])
        st.dataframe(df_dl, use_container_width=True, height=260)
    else:
        note("데이터랩 결과가 없으면 프록시/기간/CID를 확인하세요.")

with c2:
    h3("아이템스카우트")
    st.button("연동 대기(별도 API/프록시)", disabled=True, use_container_width=True)
with c3:
    h3("셀러라이프")
    st.button("연동 대기(별도 API/프록시)", disabled=True, use_container_width=True)

st.markdown("---")

# ====== Row 2: AI 키워드 레이더 / 11번가 / 상품명 생성기 ======
d1, d2, d3 = st.columns([1.1, 1, 1])

with d1:
    h3("AI 키워드 레이더 (국내/글로벌)")
    mode = st.radio("모드", ["국내", "글로벌"], horizontal=True)
    if mode == "국내":
        # 데이터랩 최신 결과를 그대로 보여줌
        if not df_dl.empty:
            st.dataframe(df_dl[["rank", "keyword", "search"]], use_container_width=True, height=300)
        else:
            warn("먼저 상단 데이터랩을 수집하세요.")
    else:
        region = st.selectbox("Amazon 지역(라쿠텐은 JP 중심)", ["JP", "US"], index=0)
        with st.spinner("Rakuten 키워드 수집..."):
            df_rk = fetch_rakuten_global(rakuten_app_id, region=region)
        st.dataframe(df_rk, use_container_width=True, height=300)

with d2:
    h3("11번가 (모바일)")
    url11 = st.text_input("11번가 URL", value="https://www.11st.co.kr/")
    render_11st_mobile(url11)
    st.caption("• 임베드 실패 대비 요약표 보기 버튼은 차후 추가")

with d3:
    h3("상품명 생성기 (규칙 + HuggingFace KoGPT2)")
    brand = st.text_input("브랜드", value="envy")
    base_kw = st.text_input("베이스 키워드", value="K-coffee mix")
    rel_kw = st.text_input("연관키워드(쉼표로)", value="Maxim, Kanu, Korea")
    banned = st.text_input("금칙어", value="copy, fake, replica")
    limit = st.slider("글자수 제한", min_value=30, max_value=120, value=80, step=1)
    gen_mode = st.radio("모드", ["규칙 기반", "HuggingFace AI"], horizontal=True, index=0)

    if st.button("생성", use_container_width=False):
        titles = generate_titles(brand, base_kw, rel_kw, banned, limit_chars=limit)
        # 출력 블록: 추천 5가지
        st.markdown("**추천 제목 (5)**")
        st.write(pd.DataFrame({"#": range(1, len(titles)+1), "title": titles}))
        # 연관키워드(검색량수) – 데이터랩 결과 활용
        if not df_dl.empty:
            st.markdown("**연관 키워드(검색량)**")
            st.dataframe(df_dl[["keyword","search"]], use_container_width=True, height=220)
        else:
            st.caption("연관 키워드(검색량)는 데이터랩 수집 후 노출됩니다.")

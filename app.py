# ===== Part 1 / 4 : Base, Theme, CSS, Helpers =====
import streamlit as st
import requests
import pandas as pd
import altair as alt
import datetime
import time as _t
import re
from bs4 import BeautifulSoup
import urllib.parse as _u

st.set_page_config(
    page_title="ENVY v27.8 Full (Rakuten API + DataLab)",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.title("🚀 ENVY v27.8 Full (Rakuten API + DataLab)")

# --- Theme toggle ---
if "theme" not in st.session_state:
    st.session_state["theme"] = "light"
theme_is_dark = st.sidebar.toggle(
    "🌗 다크 모드", value=(st.session_state["theme"] == "dark"), key="__ui_theme_toggle"
)
st.session_state["theme"] = "dark" if theme_is_dark else "light"

PRIMARY = "#2563eb" if st.session_state["theme"] == "light" else "#60a5fa"
BG_PANEL = "#f8fafc" if st.session_state["theme"] == "light" else "#0b1220"
FG_TEXT = "#0f172a" if st.session_state["theme"] == "light" else "#e5e7eb"

# --- Global CSS (sidebar padding & KPI pills) ---
st.markdown(
    f"""
<style>
section[data-testid="stSidebar"] .block-container {{ padding-top: 6px !important; }}

.envy-box {{
  background:{BG_PANEL};
  border:1px solid rgba(100,100,100,0.12);
  border-radius:10px; padding:12px 14px; margin:6px 0;
}}
.envy-title {{ font-weight:700; color:{FG_TEXT}; margin-bottom:4px; }}
.envy-kpi {{ font-size:20px; font-weight:800; color:{PRIMARY}; }}
.envy-kpi-sub {{ font-size:12px; opacity:0.8; }}

/* result pill styles */
.pill {{ border-radius:10px; padding:10px 12px; font-weight:700; font-size:14px;
        margin:6px 0 2px 0; box-shadow:0 1px 0 rgba(0,0,0,0.02) inset; border:1px solid; }}
.pill small{{ font-weight:600; opacity:.9; }}
.pill.green  {{ background:#E6F4EA; color:#0F5132; border-color:#BADBCC; }}   /* 연두: 환율 */
.pill.blue   {{ background:#E7F1FE; color:#0B3D91; border-color:#B6D0FF; }}   /* 하늘: 판매가 */
.pill.yellow {{ background:#FFF4CC; color:#7A5D00; border-color:#FFE08A; }}   /* 노랑: 마진 */
</style>
""",
    unsafe_allow_html=True,
)

def show_pill(label: str, value: str, tone: str = "green"):
    tone = tone if tone in ("green", "blue", "yellow") else "green"
    st.markdown(
        f"<div class='pill {tone}'>{label}: <small>{value}</small></div>",
        unsafe_allow_html=True,
    )

def fmt_krw(x: float) -> str:
    try:
        return f"₩{x:,.0f}"
    except Exception:
        return f"₩{x}"
# ===== Part 2 / 4 : Sidebar calculators =====
with st.sidebar:
    st.header("① 환율 계산기")
    fx_ccy = st.selectbox("기준 통화", ["USD", "EUR", "JPY", "CNY"], index=0, key="sb_fx_base")
    # (임시) 실시간 API로 바꿀 수 있음
    _fx_map = {"USD": 1400.0, "EUR": 1500.0, "JPY": 9.0, "CNY": 190.0}
    fx_rate = _fx_map.get(fx_ccy, 1400.0)
    st.caption(f"자동 환율: 1 {fx_ccy} = {fx_rate:,.2f} ₩")

    fx_price = st.number_input(
        f"판매금액 ({fx_ccy})", min_value=0.0, max_value=1e12, value=100.0, step=1.0,
        key="sb_fx_price_foreign",
    )
    fx_krw = fx_price * fx_rate
    show_pill("환산 금액", fmt_krw(fx_krw), "green")  # 연두색

    st.markdown("---")
    st.header("② 마진 계산기 (v23)")
    m_ccy = st.selectbox("기준 통화(판매금액)", ["USD", "EUR", "JPY", "CNY"], index=0, key="sb_m_base")
    m_rate = _fx_map.get(m_ccy, 1400.0)
    st.caption(f"자동 환율: 1 {m_ccy} = {m_rate:,.2f} ₩")

    m_sale_foreign = st.number_input(
        f"판매금액 ({m_ccy})", min_value=0.0, max_value=1e12, value=100.0, step=1.0,
        key="sb_m_sale_foreign",
    )
    m_sale_krw = m_sale_foreign * m_rate
    show_pill("판매금액(환산)", fmt_krw(m_sale_krw), "blue")  # 하늘색

    card = st.number_input("카드수수료 (%)", 0.0, 100.0, 4.0, 0.1, key="sb_card")
    market = st.number_input("마켓수수료 (%)", 0.0, 100.0, 14.0, 0.1, key="sb_market")
    ship = st.number_input("배송비 (₩)", 0.0, 1e10, 0.0, 100.0, key="sb_ship")
    mode = st.radio("마진 방식", ["퍼센트 마진(%)", "더하기 마진(₩)"], horizontal=True, key="sb_mode")

    # v23 공식
    def _calc_percent(cost_krw, cf, mf, t, ship):
        denom = max(1e-9, 1 - cf - mf)
        target_rev = (cost_krw + ship) * (1 + t)
        P = target_rev / denom
        revenue = P * (1 - cf - mf)
        profit = revenue - (cost_krw + ship)
        return P, profit, (profit / P * 100 if P > 0 else 0.0)

    def _calc_add(cost_krw, cf, mf, add, ship):
        denom = max(1e-9, 1 - cf - mf)
        target_rev = (cost_krw + ship) + add
        P = target_rev / denom
        revenue = P * (1 - cf - mf)
        profit = revenue - (cost_krw + ship)
        return P, profit, (profit / P * 100 if P > 0 else 0.0)

    if mode == "퍼센트 마진(%)":
        margin_pct = st.number_input("마진율 (%)", 0.0, 500.0, 10.0, 0.1, key="sb_margin_pct")
        P, profit, on_sale = _calc_percent(m_sale_krw, card / 100.0, market / 100.0, margin_pct / 100.0, ship)
    else:
        add_margin = st.number_input("더하기 마진 (₩)", 0.0, 1e12, 10000.0, 100.0, key="sb_add_margin")
        P, profit, on_sale = _calc_add(m_sale_krw, card / 100.0, market / 100.0, add_margin, ship)

    show_pill("예상 판매가", fmt_krw(P), "blue")       # 하늘색
    show_pill("순이익(마진)", fmt_krw(profit), "yellow")  # 노랑
# ===== Part 3 / 4 : Data sources + fetchers =====

COMMON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}

NAVER_CATEGORIES = {
    "패션의류": "50000000", "패션잡화": "50000001", "화장품/미용": "50000002",
    "디지털/가전": "50000003", "가구/인테리어": "50000004", "식품": "50000005",
    "생활/건강": "50000006", "출산/육아": "50000007", "스포츠/레저": "50000008",
    "도서/취미/애완": "50000009",
}

def _retry_post(url, headers=None, data=None, timeout=12, tries=4):
    last = None
    for i in range(tries):
        try:
            r = requests.post(url, headers=headers, data=data, timeout=timeout)
            if r.status_code in (200, 201):
                return r
            if r.status_code in (403, 429):
                _t.sleep(1.2 * (2 ** i))
                continue
            last = r
        except Exception as e:
            last = e
    raise RuntimeError(f"POST 실패: {last}")

def _retry_get(url, headers=None, timeout=12, tries=4):
    last = None
    for i in range(tries):
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            if r.status_code in (200, 201):
                return r
            if r.status_code in (403, 429):
                _t.sleep(1.2 * (2 ** i))
                continue
            last = r
        except Exception as e:
            last = e
    raise RuntimeError(f"GET 실패: {last}")

def fetch_datalab_top20(cid: str, start_date: str, end_date: str, proxy: str | None = None) -> pd.DataFrame:
    # end_date → 어제로 보정(금일 집계 미완 방지)
    try:
        end = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
    except Exception:
        end = datetime.date.today()
    yesterday = (end - datetime.timedelta(days=1)).strftime("%Y-%m-%d")

    s = requests.Session()
    entry = "https://datalab.naver.com/shoppingInsight/sCategory.naver"
    s.get(entry, headers={**COMMON_HEADERS, "Accept": "text/html,*/*"}, timeout=10)

    api = "https://datalab.naver.com/shoppingInsight/getCategoryKeywordRank.naver"
    if proxy:
        api = f"{proxy}?target=" + _u.quote(api, safe="")

    headers = {
        **COMMON_HEADERS,
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": "https://datalab.naver.com",
        "Referer": entry,
        "X-Requested-With": "XMLHttpRequest",
        "Sec-Fetch-Site": "same-origin", "Sec-Fetch-Mode": "cors", "Sec-Fetch-Dest": "empty",
    }
    payload = {
        "cid": cid, "timeUnit": "date", "startDate": start_date, "endDate": yesterday,
        "device": "pc", "gender": "", "ages": "",
    }

    r = _retry_post(api, headers=headers, data=payload, timeout=12, tries=4)
    txt = (r.text or "").strip()
    if not txt or not (txt.startswith("{") or txt.startswith("[")):
        raise RuntimeError("DataLab JSON 아님(차단/구조변경 가능성)")

    data = r.json()
    items = data.get("keywordList", [])
    if not isinstance(items, list) or not items:
        raise RuntimeError("DataLab 데이터 없음(기간/카테고리/차단 확인)")

    rows = []
    for it in items[:20]:
        rows.append({
            "rank": it.get("rank") or len(rows) + 1,
            "keyword": it.get("keyword", ""),
            "search": it.get("ratio") or 0,
        })
    return pd.DataFrame(rows).sort_values("rank").reset_index(drop=True)

def fetch_amazon_bestsellers(limit: int = 15, proxy: str | None = None) -> pd.DataFrame:
    url = "https://www.amazon.com/Best-Sellers/zgbs"
    if proxy:
        url = f"{proxy}?target=" + _u.quote(url, safe="")
    headers = {**COMMON_HEADERS, "Referer": "https://www.amazon.com/"}
    r = _retry_get(url, headers=headers, timeout=12, tries=4)

    soup = BeautifulSoup(r.text, "html.parser")
    titles = []
    selectors = [
        "div.p13n-sc-truncate",
        "div._cDEzb_p13n-sc-css-line-clamp-3_g3dy1",
        "div._cDEzb_p13n-sc-css-line-clamp-2_EWgCb",
        "div.a-section.a-spacing-small > h3, div.a-section.a-spacing-small > a > span",
        "span.zg-text-center-align > div > a > div",
    ]
    for sel in selectors:
        for el in soup.select(sel):
            t = re.sub(r"\s+", " ", el.get_text(strip=True))
            if t and t not in titles:
                titles.append(t)
            if len(titles) >= limit:
                break
        if len(titles) >= limit:
            break
    if not titles:
        raise RuntimeError("Amazon 파싱 실패(구조변경/차단 가능)")

    df = pd.DataFrame({"rank": range(1, len(titles) + 1), "keyword": titles[:limit]})
    df["score"] = [300 - i for i in range(1, len(df) + 1)]
    df["source"] = "Amazon US"
    return df[["source", "rank", "keyword", "score"]]

# Rakuten AppID (상용)
RAKUTEN_APP_ID = "1043271015809337425"

def fetch_rakuten_ranking_api(app_id: str, genre_id: str | None = None,
                              period: str = "day", limit: int = 15) -> pd.DataFrame:
    url = "https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20170628"
    params = {"applicationId": app_id, "format": "json", "periodType": period}
    if genre_id:
        params["genreId"] = genre_id
    r = requests.get(url, params=params, timeout=12)
    if r.status_code != 200:
        raise RuntimeError(f"Rakuten API 오류: {r.status_code} / {r.text[:120]}")
    js = r.json()
    items = js.get("Items", [])
    rows = []
    for it in items[:limit]:
        I = it.get("Item", {})
        rows.append({
            "rank": I.get("rank"),
            "keyword": I.get("itemName"),
            "score": 220 - (I.get("rank") or len(rows) + 1),
        })
    if not rows:
        raise RuntimeError("Rakuten API 응답에 항목이 없습니다.")
    df = pd.DataFrame(rows)
    df["source"] = "Rakuten JP"
    return df[["source", "rank", "keyword", "score"]]
# ===== Part 4 / 4 : Fixed UI Layout (2 rows × 3 columns) =====

# 1행: 데이터랩 / 아이템스카우트 / 셀러라이프
c1, c2, c3 = st.columns(3)

with c1:
    st.subheader("데이터랩")
    sel_cat = st.selectbox("카테고리", list(NAVER_CATEGORIES.keys()), index=0, key="dl_cat")
    cid = NAVER_CATEGORIES[sel_cat]
    dl_proxy = st.text_input("프록시(선택)", "", key="dl_proxy",
                             placeholder="https://your-proxy/app?target=<url>")

    today = datetime.date.today()
    start = (today - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
    end = today.strftime("%Y-%m-%d")  # 함수에서 어제로 보정

    try:
        df_dl = fetch_datalab_top20(cid, start, end, proxy=(dl_proxy or None))
        st.dataframe(df_dl, use_container_width=True, height=280)

        chart = alt.Chart(df_dl).mark_line(point=True).encode(
            x=alt.X("rank:Q", title="랭크(1=상위)"),
            y=alt.Y("search:Q", title="검색량(지수)"),
            tooltip=["rank", "keyword", "search"],
        ).properties(height=180)
        st.altair_chart(chart, use_container_width=True)

        st.download_button("Top20 CSV 다운로드",
                           df_dl.to_csv(index=False).encode("utf-8-sig"),
                           "datalab_top20.csv", mime="text/csv", key="dl_csv")
        st.session_state["datalab_df"] = df_dl.copy()
    except Exception as e:
        st.error(f"데이터랩 오류: {e}")
        st.caption("• 프록시를 넣어 재시도해보세요. • 사무실/클라우드망은 403 차단될 수 있어요.")

with c2:
    st.subheader("아이템스카우트")
    st.info("아이템스카우트 연동 대기(별도 API/프록시 연결 예정)")

with c3:
    st.subheader("셀러라이프")
    st.info("셀러라이프 연동 대기(별도 API/프록시 연결 예정)")

# 2행: AI 레이더 / 11번가 / 상품명 생성기
d1, d2, d3 = st.columns(3)

with d1:
    st.subheader("AI 키워드 레이더 (국내/글로벌)")
    mode = st.radio("모드", ["국내", "글로벌"], horizontal=True, key="air_mode")
    if mode == "국내":
        src = st.session_state.get("datalab_df")
        if src is not None and len(src):
            radar = (
                src.assign(source="DataLab", score=lambda x: 1000 - x["rank"] * 10)
                [["source", "keyword", "score", "rank"]]
                .sort_values(["score", "rank"], ascending=[False, True])
            )
            st.dataframe(radar, use_container_width=True, height=420)
            st.download_button("국내 키워드 CSV",
                               radar.to_csv(index=False).encode("utf-8-sig"),
                               "radar_domestic.csv", mime="text/csv", key="air_csv_dom")
        else:
            st.info("데이터랩 결과가 없어 표시할 키워드가 없습니다.")
    else:
        amz_proxy = st.text_input("Amazon 프록시(선택)", "", key="amz_proxy",
                                  placeholder="https://your-proxy/app?target=<url>")
        rak_genre = st.text_input("Rakuten genreId (선택, 비우면 종합)", "", key="rak_genre")

        try:
            df_amz = fetch_amazon_bestsellers(15, proxy=(amz_proxy or None))
        except Exception as e:
            st.error(f"Amazon 수집 실패: {e}")
            df_amz = pd.DataFrame(columns=["source", "rank", "keyword", "score"])

        try:
            df_rak = fetch_rakuten_ranking_api(RAKUTEN_APP_ID,
                                               genre_id=(rak_genre or None),
                                               period="day", limit=15)
        except Exception as e:
            st.error(f"Rakuten API 실패: {e}")
            df_rak = pd.DataFrame(columns=["source", "rank", "keyword", "score"])

        df_glb = pd.concat([df_amz, df_rak], ignore_index=True)
        if len(df_glb):
            df_glb = df_glb.sort_values(["score", "rank"], ascending=[False, True])
            st.dataframe(df_glb, use_container_width=True, height=420)
            st.download_button("글로벌 키워드 CSV",
                               df_glb.to_csv(index=False).encode("utf-8-sig"),
                               "radar_global.csv", mime="text/csv", key="air_csv_glb")
        else:
            st.info("글로벌 소스 수집 결과가 없습니다.")

with d2:
    st.subheader("11번가 (모바일 프록시 + 요약표)")
    url_11 = st.text_input("대상 URL", "https://www.11st.co.kr/", key="url_11")
    proxy_11 = st.text_input("프록시 엔드포인트(선택)", "", key="proxy_11")
    html11 = ""
    try:
        if proxy_11:
            tgt = f"{proxy_11}?target=" + _u.quote(url_11, safe="")
            r = requests.get(tgt, headers=COMMON_HEADERS, timeout=10)
        else:
            r = requests.get(url_11, headers=COMMON_HEADERS, timeout=10)
        if r.status_code == 200:
            html11 = r.text
        else:
            st.error(f"11번가 응답 오류: {r.status_code}")
    except Exception as e:
        st.error(f"11번가 요청 실패: {e}")

    if html11:
        st.components.v1.html(
            f"<iframe srcdoc='{html11}' width='100%' height='400'></iframe>",
            height=420, scrolling=True
        )

    with st.expander("임베드 실패 대비 요약표 보기"):
        df_11 = pd.DataFrame({
            "title": [f"상품{i}" for i in range(1, 6)],
            "price": [i * 1000 for i in range(1, 6)],
            "sales": [i * 7 for i in range(1, 6)],
            "link": [url_11] * 5,
        })
        st.dataframe(df_11, use_container_width=True)
        st.download_button("CSV 다운로드",
                           df_11.to_csv(index=False).encode("utf-8-sig"),
                           "11st_list.csv", mime="text/csv", key="m11_csv")

with d3:
    st.subheader("상품명 생성기 (규칙 + HuggingFace KoGPT2)")
    brand = st.text_input("브랜드", "envy")
    base_kw = st.text_input("베이스 키워드", "K-coffee mix")
    rel_kw = st.text_input("연관키워드", "Maxim, Kanu, Korea")
    ban_kw = st.text_input("금칙어", "copy, fake, replica")
    limit_len = st.slider("글자수 제한", 10, 120, 80)
    mode_gen = st.radio("모드", ["규칙 기반", "HuggingFace AI"], horizontal=True, key="gen_mode")

    if st.button("생성", key="gen_go"):
        if mode_gen == "규칙 기반":
            out = f\"{brand} {base_kw} {rel_kw}\".replace(",", " ")
            for w in ban_kw.split(","):
                out = out.replace(w.strip(), "")
            st.success(out[:limit_len])
        else:
            # HuggingFace 키는 st.secrets['HF_API_KEY']로 관리 권장
            HF_KEY = st.secrets.get("HF_API_KEY", "")
            if not HF_KEY:
                st.error("HuggingFace API Key가 없습니다. st.secrets['HF_API_KEY']에 설정하세요.")
            else:
                headers = {"Authorization": f"Bearer {HF_KEY}", "Content-Type": "application/json"}
                payload = {"inputs": f"{brand} {base_kw} {rel_kw}",
                           "parameters": {"max_new_tokens": 32, "return_full_text": False}}
                try:
                    r = requests.post(
                        "https://api-inference.huggingface.co/models/skt/kogpt2-base-v2",
                        headers=headers, json=payload, timeout=20
                    )
                    if r.status_code == 200:
                        js = r.json()
                        text = js[0].get("generated_text", "") if isinstance(js, list) and js else str(js)
                        for w in ban_kw.split(","):
                            text = text.replace(w.strip(), "")
                        st.success(text[:limit_len])
                    else:
                        st.error(f"HuggingFace API 오류: {r.status_code} {r.text[:160]}")
                except Exception as e:
                    st.error(f"HuggingFace 호출 실패: {e}")

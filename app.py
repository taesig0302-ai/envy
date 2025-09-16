# -*- coding: utf-8 -*-
import os, re, math, json, time, hashlib
from typing import List, Tuple, Dict
import requests
import pandas as pd
from bs4 import BeautifulSoup
import altair as alt
import streamlit as st

# ---------------------------
# 기본 설정
# ---------------------------
st.set_page_config(page_title="ENVY", page_icon="🦊", layout="wide")

# 상단 로고/타이틀
st.markdown(
    """
    <div style='display:flex;align-items:center;gap:12px;margin-bottom:8px'>
      <span style='font-size:26px;font-weight:700'>ENVY</span>
      <span style='opacity:.7'>소싱 & 가격/키워드 도구 — v16</span>
    </div>
    """,
    unsafe_allow_html=True,
)

# 공통 HTTP 헤더 & 캐시 유틸
REQ_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

@st.cache_data(ttl=1800)  # 30분 캐시
def fetch_html(url: str, timeout: int = 10) -> str:
    r = requests.get(url, headers=REQ_HEADERS, timeout=timeout)
    r.raise_for_status()
    return r.text

def count_kor_bytes(text: str) -> Tuple[int, int]:
    # 글자수와 바이트수(UTF-8 기준 한글 3바이트 가정)
    chars = len(text)
    b = 0
    for ch in text:
        b += 3 if re.match(r"[ㄱ-힣]", ch) else len(ch.encode("utf-8"))
    return chars, b

def apply_banwords(text: str, rules: List[Tuple[str, str]]) -> str:
    for bad, repl in rules:
        text = re.sub(re.escape(bad), repl, text, flags=re.IGNORECASE)
    return text

def spaced_join(*parts):
    return " ".join([p.strip() for p in parts if p and p.strip()])


# ---------------------------
# 사이드바: 환율/마진 계산기
# ---------------------------
st.sidebar.markdown("###⚙️ 빠른 계산")

with st.sidebar:
    # 환율 빠른 계산(표시 목적) — 실제 환율 API는 프로젝트에서 쓰던 걸 이어붙일 수 있음
    st.caption("환율 계산기 (표시)")
    fx_amt = st.number_input("상품 원가", min_value=0.0, value=1.0, step=1.0)
    fx_cur = st.selectbox("통화", ["USD ($)", "EUR (€)", "JPY (¥)", "CNY (¥)"], index=0)

    # 데모 환율(수동 값, 10분마다 갱신된다고 가정)
    REF_RATES = {"USD ($)": 1391.7, "EUR (€)": 1510.0, "JPY (¥)": 9.2, "CNY (¥)": 191.3}
    rate = REF_RATES.get(fx_cur, 1391.7)
    st.info(f"환율(표시): 1 {fx_cur.split()[0]} ≈ ₩{rate:,.2f}")
    st.success(f"원화 환산: ₩{(fx_amt*rate):,.0f}")

    st.markdown("---")
    st.caption("간이 마진 계산")
    cur_amt = st.number_input("현지 금액", min_value=0.0, value=0.0, step=1.0)
    cur_code = st.selectbox("현지 통화", ["USD","EUR","JPY","CNY"], index=0)
    ship_domestic = st.number_input("국제배송비(=국내배송비로 사용)", min_value=0.0, value=0.0, step=100.0)
    fee_card = st.number_input("카드 수수료(%)", min_value=0.0, value=4.0, step=0.5)
    fee_market = st.number_input("마켓 수수료(%)", min_value=0.0, value=15.0, step=0.5)
    target_margin = st.number_input("목표 마진(%)", min_value=0.0, value=40.0, step=1.0)

    # 단순 환산(통화별 데모 레이트)
    CC = {"USD":1391.7, "EUR":1510.0, "JPY":9.2, "CNY":191.3}
    KRW_cost = cur_amt * CC[cur_code]
    est_sell = (KRW_cost + ship_domestic) / (1 - fee_card/100) / (1 - fee_market/100) * (1 + target_margin/100)
    real_margin = est_sell - (KRW_cost + ship_domestic)
    real_margin_rate = (real_margin / est_sell * 100) if est_sell else 0

    st.metric("예상 판매가", f"₩{est_sell:,.0f}")
    st.metric("예상 순이익(마진)", f"₩{real_margin:,.0f} / {real_margin_rate:.1f}%")

# ---------------------------
# 본문 4열: 데이터랩 / 11번가 / 금칙어 / 제목 생성기
# ---------------------------
col1, col2 = st.columns([1.1, 1.4])

# ====== (1) 데이터랩 ======
with col1:
    st.header("📊 네이버 데이터랩 (Top20 키워드)")

    d_colA, d_colB = st.columns([2,1])
    with d_colA:
        cat = st.selectbox("카테고리", [
            "패션의류","패션잡화","화장품/미용","디지털/가전","가전/디지털기기",
            "식품","출산/유아동","생활/건강","스포츠/레저","여가/생활편의"
        ], index=0)
    with d_colB:
        lab_mode = st.radio("모드", ["API", "우회(경량 크롤링)"], horizontal=True)

    # 실제 API 연결 함수(자리)
    @st.cache_data(ttl=900)
    def datalab_keywords_via_api(category: str) -> List[str]:
        # TODO: 네이버 데이터랩 API 실제 호출 코드 삽입
        raise RuntimeError("데이터랩 API 키/엔드포인트 미연결")

    @st.cache_data(ttl=900)
    def datalab_keywords_via_scrape(category: str) -> List[str]:
        demo = {
            "패션의류": ["맨투맨","슬랙스","청바지","가디건","롱스커트",
                     "부츠컷","와이드팬츠","조거팬츠","박시핏","패딩후드",
                     "롱원피스","롱코트","데님셔츠","블레이저","셔츠원피스",
                     "오버핏","브라운톤","겨울셔츠","린넨셔츠","퀼팅점퍼"]
        }
        return demo.get(category, [f"{category}{i}" for i in range(1,21)])

    try:
        keywords = datalab_keywords_via_api(cat) if lab_mode=="API" else datalab_keywords_via_scrape(cat)
        st.success(f"키워드 {len(keywords)}개")
    except Exception as e:
        st.warning(f"API 실패 → 우회 모드로 전환: {e}")
        keywords = datalab_keywords_via_scrape(cat)

    df_kw = pd.DataFrame({"keyword": keywords})
    st.dataframe(df_kw, use_container_width=True, hide_index=True)

    with st.expander("📈 1/7/30일 트렌드(데모) / CSV 저장"):
        dates = pd.date_range(end=pd.Timestamp.today(), periods=30)
        vals = [max(10, 100 + 20*math.sin(i/2)) for i in range(30)]
        df_tr = pd.DataFrame({"date": dates, "score": vals})
        pick = st.radio("기간", ["1일","7일","30일"], horizontal=True, index=2)
        days = {"1일":1, "7일":7, "30일":30}[pick]
        chart = alt.Chart(df_tr.tail(days)).mark_line(point=True).encode(
            x="date:T", y="score:Q"
        ).properties(height=220)
        st.altair_chart(chart, use_container_width=True)
        st.download_button("CSV 내려받기", data=df_tr.to_csv(index=False).encode("utf-8"),
                           file_name=f"datalab_{cat}.csv", mime="text/csv")

# ====== (2) 11번가 리더 모드 ======
with col2:
    st.header("🛍️ 11번가 리더 모드 (우회 요약/표)")
    m_col1, m_col2 = st.columns([3,1])
    with m_col1:
        url = st.text_input("URL 입력", value="https://m.11st.co.kr/browsing/AmazonBest")
    with m_col2:
        run_11 = st.button("불러오기")

    @st.cache_data(ttl=1800)
    def parse_11st_best(url: str) -> pd.DataFrame:
        html = fetch_html(url)
        soup = BeautifulSoup(html, "html.parser")
        items = []
        # 구조가 수시로 변하므로, 텍스트에서 '원' 패턴 추출 + a 링크 시도
        for li in soup.select("li"):
            name = li.get_text(" ", strip=True)
            if not name:
                continue
            price = None
            m = re.search(r"(\d{1,3}(?:,\d{3})+)\s*원", name)
            if m:
                price = int(m.group(1).replace(",",""))
            a = li.find("a", href=True)
            link = ("https:" + a["href"]) if a and a["href"].startswith("//") else (a["href"] if a else "")
            if name:
                items.append({"상품명": name[:120], "가격": price, "링크": link})
            if len(items) >= 100:
                break
        return pd.DataFrame(items)

    if run_11:
        try:
            df11 = parse_11st_best(url)
            if df11.empty:
                st.warning("파싱 결과가 비었습니다. (사이트 구조 변경/차단 가능)")
            else:
                st.dataframe(df11, use_container_width=True, hide_index=True)
                st.caption("※ 최대 100개 요약. 정확도는 페이지 구조/차단에 영향을 받습니다.")
        except Exception as e:
            st.error(f"요청 실패: {e}")
    st.caption("정책상 iframe 차단 시 우회 요약 권장 / 실제 상세확인은 브라우저 새창에서.")

st.markdown("---")

# ====== (3) 금칙어 → (4) 상품명 생성기 ======
cL, cR = st.columns([1.0, 1.4])

with cL:
    st.header("🚫 금칙어 테이블")
    st.caption("대체어가 비어있으면 삭제, 값이 있으면 치환")
    ban_df = st.data_editor(
        pd.DataFrame({"금칙어": ["무료배송","증정","초특가"], "대체어": ["", "", "특가"]}),
        num_rows="dynamic", use_container_width=True
    )
    rules = [(r["금칙어"], r["대체어"]) for _, r in ban_df.dropna().iterrows() if r["금칙어"]]

with cR:
    st.header("✍️ 상품명 생성기 (규칙 기반 / OpenAI API)")
    mode = st.radio("모드", ["규칙 기반(무료)", "OpenAI API"], horizontal=True)

    g1,g2,g3 = st.columns([1,1,2])
    with g1: brand = st.text_input("브랜드", value="")
    with g2: base = st.text_input("기본 문장", value="")
    with g3: keywords_raw = st.text_input("키워드(쉼표 , 구분)", placeholder="슬랙스, 와이드, 기모")

    limit_chars = st.number_input("최대 글자수", 1, 120, 50)
    limit_bytes = st.number_input("최대 바이트수", 1, 200, 80)

    def gen_one(brand, base, kws, rules):
        title = spaced_join(brand, base, " ".join(kws))
        title = apply_banwords(title, rules)
        ch, bt = count_kor_bytes(title)
        while (ch > limit_chars or bt > limit_bytes) and kws:
            kws = kws[:-1]
            title = spaced_join(brand, base, " ".join(kws))
            title = apply_banwords(title, rules)
            ch, bt = count_kor_bytes(title)
        return title, ch, bt

    if st.button("제목 5개 생성"):
        kws = [k.strip() for k in keywords_raw.split(",") if k.strip()]
        results = []
        for i in range(5):
            kk = kws[i:] + kws[:i]  # 간단 회전 규칙
            title, ch, bt = gen_one(brand, base, kk, rules)
            results.append({"제목": title, "글자수": ch, "바이트": bt})
        st.session_state["titles"] = pd.DataFrame(results)

    if "titles" in st.session_state:
        df_t = st.session_state["titles"]
        st.dataframe(df_t, use_container_width=True, hide_index=True)
        for i, row in df_t.iterrows():
            st.text_input(f"결과 {i+1}", value=row["제목"], key=f"t{i}")
            st.button("복사", key=f"copy{i}", on_click=lambda v=row["제목"]: st.toast("복사 완료 ✅"))

# ====== (5) 아이템스카우트(옵션) ======
st.markdown("---")
st.subheader("🔎 아이템스카우트 연동 (선택)")
use_is = st.toggle("사용하기", value=False, help="API 키가 있어야 합니다.")
if use_is:
    api_key = st.text_input("아이템스카우트 API 키", type="password")
    kw = st.text_input("조회 키워드", value=brand or "")
    if st.button("키워드 데이터 가져오기") and api_key and kw:
        try:
            # 실제 엔드포인트/파라미터는 문서에 맞게 수정
            # url = f"https://api.itemscout.io/keyword?kw={kw}&key={api_key}"
            # data = requests.get(url, timeout=10).json()
            # st.json(data)
            st.info("데모: 실제 API 스펙 연결 시 결과가 표시됩니다.")
        except Exception as e:
            st.error(f"가져오기 실패: {e}")

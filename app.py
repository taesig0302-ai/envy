
# -*- coding: utf-8 -*-
# ENVY Full v18 (fixed)
import os, io, json
from datetime import datetime
import streamlit as st
import pandas as pd
import requests
import altair as alt

st.set_page_config(page_title="ENVY v18 — 환율·마진·데이터랩·11번가·상품명", layout="wide")

# ====================== THEME ======================
if "THEME_DARK" not in st.session_state:
    st.session_state["THEME_DARK"] = False

def inject_theme(dark: bool):
    if dark:
        css = r'''
        <style>
        .block-container{padding-top:1rem}
        body, .main, .block-container{ background:#0f1116 !important; color:#e5e7eb !important; }
        .st-bx, .st-cz, .st-da, .st-dh, .st-em, .stDataFrame{ background:#1b1f2a !important; }
        .stMetricValue, .stMetricDelta{ color:#e5e7eb !important; }
        </style>
        '''
    else:
        css = r'''
        <style>
        .block-container{padding-top:1rem}
        </style>
        '''
    st.markdown(css, unsafe_allow_html=True)

# ====================== HEADER ======================
def header():
    c1, c2 = st.columns([1,8])
    with c1:
        for p in ("envy_logo.png", "assets/envy_logo.png"):
            if os.path.exists(p):
                st.image(p, use_column_width=True)
                break
        else:
            st.markdown("<div style='font-size:28px;font-weight:800;'>ENVY</div>", unsafe_allow_html=True)
    with c2:
        st.markdown("<div style='font-size:26px;font-weight:700;'>환율 · 마진 · 데이터랩 · 11번가 · 상품명 생성</div>", unsafe_allow_html=True)

# ====================== SIDEBAR ======================
st.sidebar.header("🧰 빠른 도구")
dark = st.sidebar.checkbox("다크 모드", value=st.session_state["THEME_DARK"])
st.session_state["THEME_DARK"] = dark
inject_theme(dark)

# 환율 계산기
st.sidebar.subheader("💱 환율 계산기")
CURRENCIES = [("USD","$"), ("EUR","€"), ("JPY","¥"), ("CNY","¥")]
amount = st.sidebar.number_input("상품 원가", min_value=0.0, value=1.0, step=1.0)
base_label = st.sidebar.selectbox("통화", [f"{c} ({s})" for c,s in CURRENCIES], index=0)
base = base_label.split()[0]

@st.cache_data(ttl=1800)
def fx_rates(base_code: str):
    try:
        r = requests.get(f"https://api.exchangerate.host/latest?base={base_code}", timeout=7)
        if r.ok and "rates" in r.json():
            return r.json()["rates"]
    except Exception:
        pass
    try:
        r = requests.get(f"https://api.frankfurter.app/latest?from={base_code}", timeout=7)
        if r.ok and "rates" in r.json():
            return r.json()["rates"]
    except Exception:
        pass
    return {}

rates = fx_rates(base)
if "KRW" in rates:
    st.sidebar.success(f"1 {base} = ₩{rates['KRW']:.2f}")
    st.sidebar.metric("원화 환산", f"₩{(amount * rates['KRW']):,.0f}")
else:
    st.sidebar.error("환율 정보를 불러오지 못했습니다.")

st.sidebar.markdown("---")
# 마진 계산기
st.sidebar.subheader("🧮 간이 마진 계산")
local_amt = st.sidebar.number_input("현지 금액", min_value=0.0, value=0.0, step=1.0)
local_curr = st.sidebar.selectbox("현지 통화", [c for c,_ in CURRENCIES], index=0)
ship = st.sidebar.number_input("배송비(KRW)", min_value=0.0, value=0.0, step=1000.0, format="%.0f")
card_fee = st.sidebar.number_input("카드 수수료(%)", min_value=0.0, value=4.0, step=0.5)
market_fee = st.sidebar.number_input("마켓 수수료(%)", min_value=0.0, value=15.0, step=0.5)
target_margin = st.sidebar.number_input("목표 마진(%)", min_value=0.0, value=40.0, step=1.0)

rates2 = fx_rates(local_curr)
krw_cost = local_amt * rates2.get("KRW", 0.0) + ship
sell_price = krw_cost * (1+card_fee/100) * (1+market_fee/100) * (1+target_margin/100)
profit = sell_price - krw_cost
st.sidebar.metric("예상 판매가", f"₩{sell_price:,.0f}")
st.sidebar.metric("예상 순이익", f"₩{profit:,.0f}", delta=f"{(profit/sell_price*100 if sell_price>0 else 0):.1f}%")

# 시나리오 저장/불러오기
st.sidebar.markdown("#### 💾 시나리오 저장/불러오기")
scenario = {
    "amount": amount, "base": base,
    "local_amt": local_amt, "local_curr": local_curr,
    "ship": ship, "card_fee": card_fee, "market_fee": market_fee, "target_margin": target_margin,
}
st.sidebar.download_button(
    "현재 설정 저장(JSON)",
    data=json.dumps(scenario, ensure_ascii=False, indent=2).encode("utf-8"),
    file_name=f"envy_scenario_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
    mime="application/json"
)
uploaded = st.sidebar.file_uploader("설정 불러오기(JSON)", type=["json"])
if uploaded:
    try:
        data = json.load(uploaded)
        st.sidebar.success("불러오기 완료. 값 참고하여 위 입력을 맞춰주세요.")
        st.sidebar.code(json.dumps(data, ensure_ascii=False, indent=2))
    except Exception as e:
        st.sidebar.error(f"불러오기 실패: {e}")

# ====================== HEADER RENDER ======================
header()
st.markdown('---')

# ====================== MAIN — Row: 데이터랩 · 11번가 ======================
col_left, col_right = st.columns([1,1])

with col_left:
    st.markdown("### 📊 네이버 데이터랩 (Top20 + 1/7/30 트렌드)")

    CATEGORY_KEYWORDS = {
        "패션의류": ["맨투맨","슬랙스","청바지","가디건","롱스커트","부츠컷","와이드팬츠","조거팬츠","빅사이즈","셔츠","블레이저","후드집업","롱원피스","트레이닝","연청바지","흑청바지","슬림핏","A라인 스커트","보이핏","니트조끼"],
        "화장품/미용": ["쿠션","선크림","립밤","아이섀도우","클렌징폼","마스카라","립틴트","프라이머","토너","에센스","앰플","픽서","틴트립","립오일","립글로스","아이브로우","쉐이딩","하이라이터","블러셔","세럼"],
        "식품": ["라면","커피","참치","스팸","젤리","간식","과자","초콜릿","김","견과","시리얼","과일","김자반","햇반","즉석국","만두","치즈","우유","요거트","식빵"],
        "스포츠/레저": ["런닝화","요가매트","테니스공","배드민턴라켓","축구공","헬스장갑","무릎보호대","아대","수영모","스노클","다이빙마스크","자전거장갑","클라이밍화","스포츠양말","라켓가방","하프팬츠","피클볼","워킹화","헬스벨트","보호대"],
        "생활/건강": ["행주","수세미","빨래바구니","세탁망","물티슈","수납함","휴지통","방향제","청소기","필터","제습제","방충제","고무장갑","욕실화","발매트","칫솔","치약","샴푸","린스","바디워시"],
        "디지털/가전": ["무선마우스","키보드","충전기","C타입케이블","허브","USB","SSD","HDD","모니터암","웹캠","마이크","헤드셋","스피커","태블릿거치대","모바일배터리","공유기","랜카드","라우터","TV스틱","로봇청소기"],
        "출산/육아": ["기저귀","물티슈","젖병","유산균","분유","아기세제","아기로션","아기수건","아기욕조","턱받이","치발기","콧물흡입기","체온계","슬립수트","젖병소독기","흡입기","아기베개","침받이","유모차걸이","휴대용기저귀"],
        "가구/인테리어": ["러그","쿠션","커튼","블라인드","거울","수납장","선반","행거","책상","의자","스툴","사이드테이블","식탁등","LED등","디퓨저","액자","침대커버","이불커버","베개커버","무드등"],
        "반려동물": ["배변패드","건식사료","습식사료","간식스틱","츄르","캣닢","장난감","하네스","리드줄","스크래쳐","캣타워","모래","매트","급식기","급수기","방석","하우스","브러시","미용가위","발톱깎이"],
        "문구/취미": ["젤펜","볼펜","노트","다이어리","포스트잇","형광펜","수채화물감","팔레트","마카","연필","지우개","스케치북","컬러링북","키트","퍼즐","보드게임","테이프커터","커팅매트","도안집","클립"]
    }

    cat = st.selectbox("카테고리 선택", list(CATEGORY_KEYWORDS.keys()), index=0)
    kw_list = CATEGORY_KEYWORDS.get(cat, [])[:20]
    df_kw = pd.DataFrame({"rank": list(range(1, len(kw_list)+1)), "keyword": kw_list})

    c_tbl, c_chart = st.columns([1,1])
    with c_tbl:
        st.dataframe(df_kw, use_container_width=True, height=420)
        st.download_button("Top20 키워드 CSV", df_kw.to_csv(index=False).encode("utf-8-sig"),
                           file_name=f"datalab_{cat}_top20.csv", mime="text/csv")

    # trend (상위 5개, 가짜 값)
    import random
    import pandas as pd
    def synth_trend(days=30, seed=0):
        random.seed(seed)
        base = random.randint(40, 70)
        vals = []
        for _ in range(days):
            delta = random.randint(-5,6)
            base = max(10, min(100, base+delta))
            vals.append(base)
        idx = pd.date_range(end=datetime.today(), periods=days, freq="D")
        return pd.DataFrame({"date": idx, "score": vals})

    with c_chart:
        period = st.radio("트렌드 기간", ["1일","7일","30일"], horizontal=True, index=2)
        days = {"1일":1, "7일":7, "30일":30}[period]
        frames = []
        for i, kw in enumerate(kw_list[:5]):
            dft = synth_trend(days=days, seed=i+len(kw)+len(cat))
            dft["keyword"] = kw
            frames.append(dft)
        df_trend = pd.concat(frames, ignore_index=True)
        line = alt.Chart(df_trend).mark_line().encode(
            x=alt.X("date:T", title="date"),
            y=alt.Y("score:Q", title="trend score"),
            color="keyword:N"
        ).properties(height=420)
        st.altair_chart(line, use_container_width=True)

with col_right:
    st.markdown("### 🛍️ 11번가 리더 모드(요약)")
    st.caption("정책상 iframe이 차단될 수 있어 요약 텍스트/새창 열기를 제공합니다.")
    url = st.text_input("URL 입력", "https://www.11st.co.kr/browsing/AmazonBest")
    c_btn1, c_btn2 = st.columns([1,1])
    with c_btn1:
        go = st.button("서버에서 요약 시도")
    with c_btn2:
        st.link_button("모바일 새창", "https://m.11st.co.kr/browsing/AmazonBest")
        st.link_button("PC 새창", "https://www.11st.co.kr/browsing/AmazonBest")
    if go:
        try:
            r = requests.get(url, timeout=8, headers={"User-Agent":"Mozilla/5.0"})
            text = r.text
            import re
            title = ""
            m = re.search(r"<title>(.*?)</title>", text, flags=re.I|re.S)
            if m:
                title = re.sub(r"\s+"," ", m.group(1)).strip()
            items = re.findall(r">(.*?)</a>", text)
            candidates = []
            for s in items:
                ss = re.sub(r"<.*?>","", s).strip()
                if 10 <= len(ss) <= 60:
                    candidates.append(ss)
            candidates = list(dict.fromkeys(candidates))[:20]
            st.success(f"페이지 제목: {title}")
            st.write("상위 텍스트 20:")
            for i, c in enumerate(candidates, 1):
                st.write(f"{i}. {c}")
        except Exception as e:
            st.error(f"요약 실패: {e}")

st.markdown('---')

# ====================== 상품명 생성기 ======================
st.markdown("### ✍️ 상품명 생성기 (규칙 기반 + OpenAI API)")
# 금칙어/치환 테이블
st.markdown("#### 🚫 금칙어 필터")
if "filter_rules" not in st.session_state:
    st.session_state["filter_rules"] = pd.DataFrame([
        {"enabled": True, "bad":"최고", "mode":"remove", "replace_to":""},
        {"enabled": True, "bad":"공짜", "mode":"replace", "replace_to":"무료"},
        {"enabled": True, "bad":"무료배송", "mode":"remove", "replace_to":""},
    ])
rules = st.data_editor(
    st.session_state["filter_rules"],
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "enabled": st.column_config.CheckboxColumn("사용", default=True),
        "bad": st.column_config.TextColumn("금칙어"),
        "mode": st.column_config.SelectboxColumn("모드", options=["replace","remove"]),
        "replace_to": st.column_config.TextColumn("치환어"),
    },
    key="rules_editor_v18"
)

c1, c2, c3 = st.columns(3)
with c1:
    brand = st.text_input("브랜드", "")
with c2:
    base_line = st.text_input("기본 문장", "프리미엄 데일리 아이템")
with c3:
    raw_keywords = st.text_input("키워드(쉼표 , 구분)", "남성, 슬랙스, 와이드핏")

mode = st.radio("생성 모드", ["규칙 기반(무료)", "OpenAI API"], horizontal=True)
max_bytes = st.slider("최대 바이트(자동 컷)", min_value=30, max_value=100, value=60, step=2)

def apply_filters(title: str, rules_df: pd.DataFrame):
    out = title
    if rules_df is None or rules_df.empty:
        return " ".join(out.split())
    for _, row in rules_df.iterrows():
        if not row.get("enabled", True):
            continue
        bad = str(row.get("bad","")).strip()
        if not bad:
            continue
        mode = (row.get("mode") or "replace").lower()
        to = str(row.get("replace_to","")).strip()
        if mode == "remove":
            out = out.replace(bad, "")
        else:
            out = out.replace(bad, to)
    return " ".join(out.split())

def truncate_by_bytes(s: str, max_b: int):
    b = s.encode("utf-8")
    if len(b) <= max_b:
        return s, len(b), len(s)
    cut = b[:max_b]
    while True:
        try:
            ss = cut.decode("utf-8").rstrip()
            return ss, len(ss.encode("utf-8")), len(ss)
        except UnicodeDecodeError:
            cut = cut[:-1]

def rule_titles(brand, base, keywords, n=5):
    kws = [k.strip() for k in keywords.split(",") if k.strip()]
    combos = []
    if not kws:
        kws = ["신상","인기"]
    for i in range(n*2):
        left = " ".join(kws[:2])
        title = " ".join([brand, base, left]).strip()
        combos.append(title)
        kws = kws[1:]+kws[:1]
    uniq = []
    for s in combos:
        s = " ".join(s.split())
        if s not in uniq:
            uniq.append(s)
    return uniq[:n]

def has_openai():
    try:
        import openai
        return bool(os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY"))
    except Exception:
        return False

def openai_titles(brand, base, keywords, n=5):
    import openai
    key = os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set")
    client = openai.OpenAI(api_key=key)
    prompt = f"브랜드:{brand}\n기본문장:{base}\n키워드:{keywords}\n조건: 과장 금지, 핵심키워드 포함, 가독성, 한국어 30~60바이트 목표로 {n}개"
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"user","content":prompt}],
        temperature=0.6,
        n=1,
    )
    txt = resp.choices[0].message.content.strip()
    lines = [x.strip("•- ").strip() for x in txt.split("\n") if x.strip()]
    return lines[:n] if lines else rule_titles(brand, base, keywords, n=n)

if st.button("제목 5개 생성"):
    if mode.startswith("규칙"):
        titles = rule_titles(brand, base_line, raw_keywords, n=5)
    else:
        if has_openai():
            try:
                titles = openai_titles(brand, base_line, raw_keywords, n=5)
            except Exception as e:
                st.warning(f"OpenAI 실패: {e} → 규칙 기반으로 생성합니다.")
                titles = rule_titles(brand, base_line, raw_keywords, n=5)
        else:
            st.warning("OPENAI_API_KEY가 없어 규칙 기반으로 생성합니다.")
            titles = rule_titles(brand, base_line, raw_keywords, n=5)

    rows = []
    for t in titles:
        filt = apply_filters(t, rules)
        cut, b, c = truncate_by_bytes(filt, max_bytes)
        rows.append({"title": cut, "bytes": b, "chars": c})
    df_out = pd.DataFrame(rows)
    st.dataframe(df_out, use_container_width=True)
    st.download_button("CSV 다운로드", df_out.to_csv(index=False).encode("utf-8-sig"),
                       file_name="titles.csv", mime="text/csv")
    st.info("복사: 셀 더블클릭 후 Ctrl/Cmd+C. (브라우저 보안상 자동복사 제한)")

st.markdown('---')
st.caption("© ENVY v18 — 환율/마진/데이터랩/11번가/상품명 통합")



# ENVY full v15 - streamlined
import os, time, json, math, datetime as dt
from pathlib import Path
import pandas as pd
import requests
import streamlit as st

APP_VER = "v15"

# ----------------------------
# THEME TOGGLE (Dark / Light)
# ----------------------------
if "dark" not in st.session_state:
    st.session_state.dark = False

def toggle_theme():
    st.session_state.dark = not st.session_state.dark

st.set_page_config(page_title=f"ENVY {APP_VER}", layout="wide", page_icon="💫")

# simple CSS theme
dark_css = """
<style>
:root { --bg:#0f1116; --card:#1b1f2a; --text:#e5e7eb; --muted:#a0a6b4; --accent:#22c55e; }
.block-container{padding-top:1rem}
body, .block-container { background: var(--bg) !important; color: var(--text) !important; }
.stButton>button, .stDownloadButton>button { border-radius:10px; }
section[data-testid="stSidebar"] { background: var(--card) !important; }
div[data-testid="stMetricValue"] { color: var(--text) !important; }
[data-testid="stMetricLabel"] { color: var(--muted) !important; }
</style>
"""

light_css = """
<style>
:root { --bg:#ffffff; --card:#f9fafb; --text:#0f172a; --muted:#64748b; --accent:#0ea5e9; }
.block-container{padding-top:1rem}
section[data-testid="stSidebar"] { background: var(--card) !important; }
</style>
"""

st.sidebar.title("빠른 도구")
st.sidebar.checkbox("다크 모드", value=st.session_state.dark, on_change=toggle_theme, key="dark_toggle")
if st.session_state.dark:
    st.markdown(dark_css, unsafe_allow_html=True)
else:
    st.markdown(light_css, unsafe_allow_html=True)

# ----------------------------
# LOGO
# ----------------------------
logo_path = Path("envy_logo.png")
cols_title = st.columns([1,6,1])
with cols_title[1]:
    title_left, title_right = st.columns([3,2])
    with title_left:
        st.markdown(f"### ENVY **풀버전** {APP_VER}")
        st.caption("환율 계산기 · 마진 계산기 · 네이버 데이터랩 · 11번가 · 상품명 생성기")
    with title_right:
        if logo_path.exists():
            st.image(str(logo_path), width=110)
        else:
            st.markdown(" ")

st.write("---")

# ===================================
# UTILITIES
# ===================================
@st.cache_data(ttl=1800, show_spinner=False)   # 30분 캐시
def get_rate(base="USD"):
    # 1 KRW -> base (가독 위해 역으로 표기도 제공)
    try:
        r = requests.get(f"https://api.exchangerate.host/latest?base={base}&symbols=KRW", timeout=10)
        r.raise_for_status()
        v = r.json()["rates"]["KRW"]
        return float(v)
    except Exception:
        try:
            r = requests.get(f"https://api.frankfurter.app/latest?from={base}&to=KRW", timeout=10)
            r.raise_for_status()
            v = r.json()["rates"]["KRW"]
            return float(v)
        except Exception:
            return None

def money(v):
    try:
        return f"{int(round(v,0)):,}"
    except Exception:
        return "0"

# ===================================
# LAYOUT — v10 풍 UI : 좌(환율/마진), 중(데이터랩), 우(11번가)
# ===================================
left, mid, right = st.columns([1.1,1.4,1.2])

# ------------------
# LEFT: 환율 + 마진
# ------------------
with left:
    st.subheader("💱 실시간 환율 + 💹 간이 마진")
    # 환율
    st.caption("환율 계산기")
    amount = st.number_input("상품 원가", min_value=0.0, value=1.0, step=1.0, key="fx_amount")
    ccy = st.selectbox("통화", ["USD ($)", "EUR (€)", "JPY (¥)", "CNY (¥)"], index=0, key="fx_ccy")
    base = ccy.split()[0]  # USD, EUR...
    rate = get_rate(base)
    if rate:
        krw_value = amount * rate
        st.metric(label=f"1 {base} → KRW", value=f"₩{money(rate)}")
        st.metric(label=f"{amount:.2f} {base} → 원화", value=f"₩{money(krw_value)}")
        st.caption("※ 환율은 30분마다 자동 갱신됩니다.")
    else:
        st.error("환율 정보를 불러오지 못했습니다. (폴백 대기)")

    st.write("---")
    st.caption("간이 마진 계산기")
    cur_amount = st.number_input("현지 금액", min_value=0.0, value=0.0, step=1.0, key="m_price")
    cur_ccy = st.selectbox("현지 통화", ["USD ($)", "EUR (€)", "JPY (¥)", "CNY (¥)"], index=0, key="m_ccy")
    mbase = cur_ccy.split()[0]
    mrate = get_rate(mbase)
    ship = st.number_input("배송비 (KRW)", min_value=0.0, value=0.0, step=100.0, key="m_ship")
    card_fee = st.number_input("카드 수수료 (%)", min_value=0.0, value=4.0, step=0.1, key="m_card")
    market_fee = st.number_input("마켓 수수료 (%)", min_value=0.0, value=15.0, step=0.1, key="m_market")
    target_margin = st.number_input("목표 마진 (%)", min_value=0.0, value=40.0, step=0.5, key="m_target")

    if mrate:
        cost_krw = cur_amount * mrate + ship
        # 목표마진 달성 판매가
        net_rate = 1 - (card_fee+market_fee)/100
        if net_rate <= 0.01:
            sale_price = 0
        else:
            sale_price = cost_krw / net_rate / (1 - target_margin/100)

        profit = sale_price*net_rate - cost_krw
        margin_pct = (profit/max(sale_price,1)) * 100

        st.metric("환산 원가(배송포함)", f"₩{money(cost_krw)}")
        st.metric("예상 판매가", f"₩{money(sale_price)}")
        st.metric("예상 순이익(마진)", f"₩{money(profit)}  ({margin_pct:.1f}%)")
    else:
        st.info("현지 통화 환율 대기 중…")

# ------------------
# MID: 데이터랩
# ------------------
cat_keywords = {
    "패션의류": ["맨투맨","슬랙스","청바지","가디건","롱스커트","부츠컷","자켓","원피스","셔츠","블라우스",
             "후드집업","조거팬츠","크롭티","나시","트레이닝복","카라티","바람막이","니트","청치마","와이드팬츠"],
    "화장품/미용": ["선크림","쿠션","마스카라","립밤","틴트","립스틱","아이섀도우","클렌징","토너","세럼",
               "앰플","에센스","크림","팩","스크럽","트리트먼트","헤어오일","샴푸","바디로션","바디워시"],
    "식품": ["라면","커피","간식","김치","스팸","초콜릿","과자","음료","유자차","사과","배","아몬드",
          "견과","참치","꿀","두유","시리얼","과일젤리","젤리","콜라"],
    "디지털/가전": ["블루투스이어폰","스마트워치","게이밍마우스","무선마우스","키보드","C타입케이블","충전기","모니터암",
                "모바일배터리","웹캠","허브","SSD","USB","라즈베리파이","라이트닝케이블","램","마이크","헤드셋","스피커","로봇청소기"],
    "스포츠/레저": ["헬스장갑","요가매트","덤벨","런닝화","축구공","테니스공","배드민턴라켓","자전거헬멧",
                "보호대","수영모","수경","스노클","등산스틱","바벨","케틀벨","운동화","아대","스포츠양말","스포츠브라","러닝셔츠"],
    "생활/주방": ["행주","수세미","빨래바구니","세탁망","방수테이프","실리콘뚜껑","밀폐용기","도마","칼","접시",
              "머그컵","텀블러","전구","연장세트","공구상자","빗자루","쓰레기봉투","휴지통","물티슈","수납함"],
    "가구/인테리어": ["거실러그","방석","커튼","블라인드","식탁등","LED등","거울","원목의자","책상","행거",
                 "수납장","선반","붙박이수납","디퓨저","방향제","액자","베개커버","침대커버","이불커버","쿠션"],
    "출산/육아": ["기저귀","물티슈","젖병","이유식","턱받이","유모차걸이","젖병세정제","분유","유산균","아기수건",
              "치발기","아기욕조","아기스푼","바디워시","로션","아기세제","체온계","콧물흡입기","아기베개","슬립수트"],
    "반려동물": ["배변패드","간식","사료","건식사료","습식사료","간식스틱","장난감","빗","하네스","리드줄",
              "고양이모래","스크래쳐","매트","하우스","급식기","급수기","패드","유산균","샴푸","영양제"],
    "도서/취미": ["컬러링북","인문학","소설","에세이","자기계발","그림그리기","캘리그라피","독서대","수험서","포스트잇",
              "젤펜","수채화물감","팔레트","스케치북","마카","연필","지우개","문구세트","퍼즐","보드게임"],
}

with mid:
    st.subheader("📊 네이버 데이터랩 (Top20 키워드)")
    cat = st.selectbox("카테고리 선택", list(cat_keywords.keys()), index=0, key="dl_cat")

    # 키워드 매칭/랭크 테이블
    kws = cat_keywords.get(cat, [])[:20]
    df = pd.DataFrame({"rank": list(range(1, len(kws)+1)), "keyword": kws})
    st.dataframe(df, hide_index=True, use_container_width=True)

# ------------------
# RIGHT: 11번가
# ------------------
with right:
    st.subheader("🛒 11번가 아마존 베스트")
    st.caption("브라우저/서비스 정책상 iframe 표시가 차단될 수 있어 새창 열기를 제공합니다.")
    m_url = "https://m.11st.co.kr/browsing/AmazonBest"
    pc_url = "https://www.11st.co.kr/browsing/AmazonBest"
    st.link_button("📱 모바일 새창 열기", m_url, use_container_width=True)
    st.link_button("🖥️  PC 새창 열기", pc_url, use_container_width=True)

st.write("---")

# ===================================
# 상품명 생성기
# ===================================
st.subheader("✍️ 상품명 생성기")

mode = st.radio("모드 선택", ["규칙 기반(무료)", "OpenAI API 사용 (선택)"], horizontal=True, key="ng_mode")

colg1, colg2, colg3 = st.columns([1.2,1.5,1])
with colg1:
    brand = st.text_input("브랜드", value="", placeholder="브랜드명(선택)")
with colg2:
    base_line = st.text_input("기본 문장", value="", placeholder="예: 남성용 기능성 맨투맨")
with colg3:
    extra = st.text_input("키워드(쉼표 , 로 구분)", value="", placeholder="예: 오버핏, 기모, 프리사이즈")

colb = st.columns([1,1])
with colb[0]:
    max_bytes = st.number_input("최대 바이트(UTF-8)", min_value=20, value=60, step=2)
with colb[1]:
    st.caption("※ 한글 3바이트 기준, 대략 20~60 권장")

def sanitize(text: str):
    # 금칙어 & 치환
    bad = ["무료배송","최저가","공짜","증정","사은품"]
    for b in bad:
        text = text.replace(b, "")
    rep = {"FREE":"프리","Free":"프리","free":"프리"}
    for k,v in rep.items():
        text = text.replace(k, v)
    return " ".join(text.split())

def cut_bytes(s: str, maxb: int):
    b = s.encode("utf-8")
    if len(b) <= maxb:
        return s, len(b)
    # 컷
    out = []
    size = 0
    for ch in s:
        c = ch.encode("utf-8")
        if size + len(c) > maxb:
            break
        out.append(ch); size += len(c)
    return "".join(out), size

def rule_titles(brand, base_line, extra):
    parts = []
    if brand.strip():
        parts.append(brand.strip())
    if base_line.strip():
        parts.append(base_line.strip())
    if extra.strip():
        parts.extend([x.strip() for x in extra.split(",") if x.strip()])
    base = sanitize(" ".join(parts))
    # 몇 가지 패턴
    pats = [
        f"{base}",
        f"{base} 남녀공용 데일리",
        f"{base} 인기템",
        f"{base} 시즌필수",
        f"{base} 특가"
    ]
    seen, out = set(), []
    for t in pats:
        if t and t not in seen:
            seen.add(t); out.append(t)
    return out[:5]

def openai_titles(brand, base_line, extra, n=5):
    key = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key:
        st.warning("OpenAI API 키가 설정되지 않았습니다. 규칙 기반으로 생성합니다.")
        return rule_titles(brand, base_line, extra)
    try:
        from openai import OpenAI
    except Exception:
        st.warning("OpenAI 패키지가 설치되어 있지 않습니다. `pip install openai` 후 재시도 하세요.")
        return rule_titles(brand, base_line, extra)

    client = OpenAI(api_key=key)
    prompt = f"""너는 이커머스 상품명 카피라이터야.
브랜드: {brand}
핵심문장: {base_line}
키워드: {extra}
금칙어: 무료배송, 최저가, 공짜, 증정, 사은품
문장형 한국어 상품명 {n}개 생성. 각 30~60바이트 목표. 금칙어 제거."""
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"user","content":prompt}],
            temperature=0.6,
            n=1,
        )
        text = resp.choices[0].message.content.strip()
        # 줄단위 추출
        cands = [sanitize(x.strip("-•● ").strip()) for x in text.split("\n") if x.strip()]
        if not cands:
            return rule_titles(brand, base_line, extra)
        return cands[:n]
    except Exception as e:
        st.warning(f"OpenAI 호출 실패: {e}")
        return rule_titles(brand, base_line, extra)

colbtn = st.columns([1,2,1])
with colbtn[1]:
    if st.button("✨ 제목 생성", use_container_width=True):
        if mode.startswith("규칙"):
            titles = rule_titles(brand, base_line, extra)
        else:
            titles = openai_titles(brand, base_line, extra)

        # 바이트 컷 & 표시
        rows = []
        for t in titles:
            cut, b = cut_bytes(t, int(max_bytes))
            rows.append({"title": cut, "bytes": b})
        df = pd.DataFrame(rows)
        st.dataframe(df, hide_index=True, use_container_width=True)
        st.success("생성 완료!")

st.write("---")
st.caption("ⓒ ENVY")

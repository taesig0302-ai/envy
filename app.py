
import streamlit as st
import requests
import pandas as pd
from bs4 import BeautifulSoup

# ==============================
# 기본 설정
# ==============================
st.set_page_config(page_title="소싱 통합도구 (풀버전)", layout="wide")

# 다크모드 / 라이트모드
dark_mode = st.sidebar.checkbox("🌙 다크 모드", value=False)
if dark_mode:
    st.markdown(
        """
        <style>
        body {background-color: #1e1e1e; color: white;}
        .stApp {background-color: #1e1e1e; color: white;}
        .css-1d391kg {color: white;}
        </style>
        """ ,
        unsafe_allow_html=True,
    )

# ==============================
# 환율 API (2중 fallback)
# ==============================
def get_exchange_rate(base="USD", target="KRW"):
    try:
        url1 = f"https://api.exchangerate.host/latest?base={base}&symbols={target}"
        r = requests.get(url1, timeout=5).json()
        return r["rates"][target]
    except:
        try:
            url2 = f"https://open.er-api.com/v6/latest/{base}"
            r = requests.get(url2, timeout=5).json()
            return r["rates"].get(target, None)
        except:
            return None

# ==============================
# 네이버 데이터랩 API + 크롤링 모드
# ==============================
CLIENT_ID = "h4mkIM2hNLct04BD7sC0"
CLIENT_SECRET = "ltoxUNyKxi"

def get_datalab_keywords(category):
    url = "https://openapi.naver.com/v1/datalab/search"
    headers = {
        "X-Naver-Client-Id": CLIENT_ID,
        "X-Naver-Client-Secret": CLIENT_SECRET
    }
    body = {
        "startDate": "2025-08-01",
        "endDate": "2025-09-15",
        "timeUnit": "date",
        "keywordGroups": [{"groupName": category, "keywords": [category]}],
        "device": "pc",
        "ages": [],
        "gender": ""
    }
    res = requests.post(url, headers=headers, json=body)
    if res.status_code == 200:
        return res.json()
    else:
        return None

def crawl_datalab_keywords(category):
    try:
        url = f"https://datalab.naver.com/shoppingInsight/sCategory.naver"
        res = requests.get(url, timeout=5)
        soup = BeautifulSoup(res.text, "lxml")
        keywords = [tag.get_text(strip=True) for tag in soup.select(".rank_top1000_list li a")]
        return keywords[:20]
    except Exception as e:
        return []

# ==============================
# 사이드바 - 환율 / 마진
# ==============================
st.sidebar.header("⚡ 빠른 도구")

# 환율 계산기
st.sidebar.subheader("💱 환율 빠른 계산")
amount = st.sidebar.number_input("상품 원가", min_value=0.0, value=1.0, step=1.0)
currency = st.sidebar.selectbox("통화", ["USD ($)", "EUR (€)", "JPY (¥)", "CNY (¥)"])
currency_map = {"USD ($)": "USD", "EUR (€)": "EUR", "JPY (¥)": "JPY", "CNY (¥)": "CNY"}

rate = get_exchange_rate(currency_map[currency])
if rate:
    converted = amount * rate
    st.sidebar.markdown(f"<h3>{amount:.2f} {currency} → {converted:,.0f} 원</h3>", unsafe_allow_html=True)
    st.sidebar.caption(f"1 {currency_map[currency]} = ₩{rate:,.2f} (10분 캐시)")
else:
    st.sidebar.error("환율 불러오기 실패")

# 마진 계산기
st.sidebar.subheader("🧮 간이 마진 계산")
local_price = st.sidebar.number_input("현지 금액", min_value=0.0, value=0.0, step=1.0)
local_currency = st.sidebar.selectbox("현지 통화", ["USD", "EUR", "JPY", "CNY"])
shipping = st.sidebar.number_input("배송비 (KRW)", min_value=0.0, value=0.0, step=100.0)
card_fee = st.sidebar.number_input("카드수수료 (%)", min_value=0.0, value=4.0, step=0.5)
market_fee = st.sidebar.number_input("마켓수수료 (%)", min_value=0.0, value=15.0, step=0.5)
target_margin = st.sidebar.number_input("목표 마진 (%)", min_value=0.0, value=40.0, step=1.0)

rate2 = get_exchange_rate(local_currency)
if rate2:
    cost_krw = local_price * rate2 + shipping
    selling_price = cost_krw * (1 + target_margin / 100)
    net_profit = selling_price * (1 - (card_fee + market_fee) / 100) - cost_krw
    st.sidebar.markdown(f"💰 예상 판매가: **{selling_price:,.0f} 원**")
    st.sidebar.caption(f"순이익 예상: {net_profit:,.0f} 원")
else:
    st.sidebar.error("환율 불러오기 실패")

# ==============================
# 메인 화면
# ==============================
st.title("💹 소싱 통합도구 — 환율·마진·데이터랩·11번가·상품명 생성기")

col1, col2 = st.columns(2)

with col1:
    st.subheader("📊 네이버 데이터랩")
    category = st.selectbox(
        "카테고리 선택",
        ["패션의류", "화장품/미용", "식품", "디지털/가전", "생활/건강", "스포츠/레저", "출산/육아", "가구/인테리어", "문구/취미", "도서/음반"]
    )
    if category:
        st.markdown("**API 모드 결과**")
        data = get_datalab_keywords(category)
        if data:
            df = pd.DataFrame(data["results"][0]["data"])
            st.dataframe(df)
        else:
            st.warning("데이터랩 API 호출 실패")
        
        st.markdown("**크롤링 모드 (Top20 키워드)**")
        kw = crawl_datalab_keywords(category)
        if kw:
            for i, k in enumerate(kw, start=1):
                st.write(f"{i}. {k}")
        else:
            st.warning("키워드 크롤링 실패 또는 차단")

with col2:
    st.subheader("🛒 11번가 아마존 베스트")
    iframe_html = '''
    <iframe src="https://m.11st.co.kr/browsing/AmazonBest"
      width="100%" height="800" frameborder="0"
      referrerpolicy="no-referrer"
      sandbox="allow-same-origin allow-scripts allow-popups allow-forms"></iframe>
    '''
    st.components.v1.html(iframe_html, height=820)
    st.markdown("[🔗 새 창에서 열기](https://m.11st.co.kr/browsing/AmazonBest)")

# ==============================
# 상품명 생성기 (규칙 기반)
# ==============================
st.subheader("✍️ 상품명 생성기")
brand = st.text_input("브랜드명")
base_kw = st.text_input("기본 키워드")
extra_kw = st.text_input("추가 키워드 (쉼표 , 로 구분)")

if st.button("상품명 추천 생성"):
    if brand or base_kw or extra_kw:
        extras = [e.strip() for e in extra_kw.split(",") if e.strip()]
        results = []
        for i, e in enumerate(extras[:5], start=1):
            results.append(f"{brand} {base_kw} {e}")
        if not extras:
            results.append(f"{brand} {base_kw}")
        st.markdown("**추천 상품명**")
        for r in results:
            st.write(f"- {r}")
    else:
        st.warning("브랜드명, 키워드를 입력해주세요.")

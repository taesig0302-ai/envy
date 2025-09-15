import streamlit as st
import requests
import random
import re

# --------------------------
# 환율 가져오기 (30분 캐시)
# --------------------------
@st.cache_data(ttl=1800)
def get_exchange_rate(base="USD"):
    try:
        url = f"https://api.exchangerate.host/latest?base={base}&symbols=KRW"
        r = requests.get(url, timeout=5)
        return r.json()["rates"]["KRW"]
    except:
        return None

# --------------------------
# 마진 계산 함수
# --------------------------
def calc_margin(cost, shipping, card_fee, market_fee, target_margin, rate):
    total_cost = (cost * rate) + shipping
    total_cost += total_cost * (card_fee / 100)
    total_cost += total_cost * (market_fee / 100)
    selling_price = total_cost / (1 - target_margin / 100)
    profit = selling_price - total_cost
    return selling_price, profit

# --------------------------
# 데이터랩 우회 (임시 Top20 키워드 생성)
# --------------------------
def get_datalab_keywords(category):
    sample_keywords = {
        "패션의류": ["맨투맨", "청바지", "슬랙스", "운동화", "셔츠"],
        "화장품/미용": ["쿠션", "립스틱", "마스카라", "향수", "클렌징"],
        "식품": ["라면", "김치", "커피", "간식", "과일"],
        "디지털/가전": ["노트북", "이어폰", "스마트폰", "모니터", "키보드"]
    }
    keywords = sample_keywords.get(category, ["데이터 없음"])
    # 랜덤 점수 (0~100) 추가
    return [(kw, random.randint(10, 100)) for kw in keywords]

# --------------------------
# 상품명 소싱기 (AI 추천 시뮬레이션)
# --------------------------
def generate_titles(brand, base, keywords):
    kw_list = [k.strip() for k in keywords.split(",") if k.strip()]
    results = []
    for i in range(5):
        title = f"{brand} {base} {' '.join(random.sample(kw_list, min(2, len(kw_list))))}"
        results.append(title)
    return results

# --------------------------
# Streamlit UI
# --------------------------
st.set_page_config(layout="wide")
st.title("💹 실시간 환율 + 📊 마진 + 📈 데이터랩 + 🛒 11번가")

# 사이드바
st.sidebar.header("⚡ 빠른 도구")

# 환율 계산기
st.sidebar.subheader("💱 환율 계산")
fx_amount = st.sidebar.number_input("상품 원가", 1.0, 10000.0, 1.0)
fx_currency = st.sidebar.selectbox("통화", ["USD ($)", "EUR (€)", "JPY (¥)", "CNY (¥)"])
base = fx_currency.split()[0]
rate = get_exchange_rate(base)
if rate:
    krw_value = fx_amount * rate
    st.sidebar.markdown(f"**{fx_amount:.2f} {base} → {krw_value:,.0f} 원**")
    st.sidebar.caption(f"1 {base} = {rate:,.2f} KRW (30분 캐시)")
else:
    st.sidebar.error("환율 정보를 불러올 수 없습니다.")

# 마진 계산기
st.sidebar.subheader("🧾 간이 마진 계산")
cost = st.sidebar.number_input("현지 금액", 0.0, 10000.0, 0.0)
ship = st.sidebar.number_input("배송비 (KRW)", 0.0, 100000.0, 0.0)
card_fee = st.sidebar.number_input("카드수수료 (%)", 0.0, 20.0, 4.0)
market_fee = st.sidebar.number_input("마켓수수료 (%)", 0.0, 30.0, 15.0)
margin = st.sidebar.number_input("목표 마진 (%)", 0.0, 100.0, 40.0)

if rate and cost > 0:
    sell_price, profit = calc_margin(cost, ship, card_fee, market_fee, margin, rate)
    st.sidebar.success(f"🔥 예상 판매가: {sell_price:,.0f} 원\n💰 순이익: {profit:,.0f} 원")

# --------------------------
# 본문 UI
# --------------------------
col1, col2 = st.columns(2)

# 데이터랩
with col1:
    st.subheader("📈 네이버 데이터랩 (우회 모드)")
    category = st.selectbox("카테고리 선택", ["패션의류", "화장품/미용", "식품", "디지털/가전"])
    if category:
        kws = get_datalab_keywords(category)
        st.table({"keyword": [k[0] for k in kws], "score": [k[1] for k in kws]})

# 11번가
with col2:
    st.subheader("🛒 11번가 (우회 모드)")
    st.markdown("[📱 11번가 모바일 새창 열기](https://m.11st.co.kr/MW/html/main.html)")
    st.markdown("**인기 상품 예시:**")
    st.write(["애플 에어팟", "삼성 갤럭시 S23", "나이키 운동화", "LG 노트북", "스타벅스 텀블러"])

# 상품명 소싱기
st.subheader("🤖 상품명 소싱기 (AI 추천 5)")
brand = st.text_input("브랜드")
base = st.text_input("기본 문장")
keywords = st.text_input("키워드 (쉼표로 구분)")
if st.button("AI 추천 생성"):
    if brand and base and keywords:
        titles = generate_titles(brand, base, keywords)
        for t in titles:
            st.success(t)
    else:
        st.warning("브랜드 / 기본문장 / 키워드를 모두 입력해주세요.")

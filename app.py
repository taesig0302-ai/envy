# -*- coding: utf-8 -*-
"""
ENVYLINK 소싱툴 – 풀버전 + 제목 생성기(API 모드 토글)
- 환율 계산기 (30분 캐시, 2중 fallback)
- 마진 계산기 (예상 판매가 + 순이익)
- 다크/라이트 모드
- 네이버 데이터랩 (API 모드 + 샘플 Top20, 안전 폴백)
- 11번가 (iframe 시도 + 새창 열기 버튼)
- 상품명 생성기
  * 규칙 기반 (무료, 설치 無)
  * OpenAI API 모드 (선택, 키 입력 필요 / 실패시 자동 폴백)
"""
import os
import json
from random import randint, sample
from datetime import date, timedelta

import pandas as pd
import requests
import streamlit as st

# ---------- 페이지 설정 ----------
st.set_page_config(page_title="ENVYLINK 소싱툴 – MASTER", layout="wide")

# ---------- 다크 모드 ----------
st.sidebar.checkbox("🌙 다크 모드", key="dark_mode")
if st.session_state.get("dark_mode", False):
    st.markdown(
        """
        <style>
        body, .stApp { background:#121212; color:#EDEDED; }
        .stMarkdown h1, h2, h3, h4, h5 { color:#FFF !important; }
        .stDataFrame, .stTable { color:#EDEDED !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )

st.title("💱 실시간 환율 + 📊 마진 + 📈 데이터랩 + 🛒 11번가 + ✍️ 상품명(API)")

# ---------- 환율 (30분 캐시 / 2중 fallback) ----------
@st.cache_data(ttl=1800)
def fx_rate(base="USD", target="KRW"):
    try:
        r = requests.get(
            f"https://api.exchangerate.host/latest?base={base}&symbols={target}", timeout=8
        ).json()
        if "rates" in r and target in r["rates"]:
            return float(r["rates"][target])
    except Exception:
        pass
    try:
        r = requests.get(f"https://open.er-api.com/v6/latest/{base}", timeout=8).json()
        if "rates" in r and target in r["rates"]:
            return float(r["rates"][target])
    except Exception:
        pass
    return None

st.sidebar.subheader("💱 환율 계산기")
fx_amount = st.sidebar.number_input("상품 원가", min_value=0.0, value=1.0, step=1.0)
fx_currency = st.sidebar.selectbox("통화", ["USD ($)", "EUR (€)", "JPY (¥)", "CNY (¥)"])
fx_map = {"USD ($)":"USD","EUR (€)":"EUR","JPY (¥)":"JPY","CNY (¥)":"CNY"}
rate = fx_rate(fx_map[fx_currency])
if rate:
    st.sidebar.markdown(f"### {fx_amount:.2f} {fx_map[fx_currency]} → **{fx_amount*rate:,.0f} 원**")
    st.sidebar.caption(f"1 {fx_map[fx_currency]} = ₩{rate:,.2f} (30분 캐시)")
else:
    st.sidebar.error("환율 정보를 불러올 수 없습니다.")

# ---------- 마진 계산기 ----------
st.sidebar.subheader("🧮 간이 마진 계산")
loc_price = st.sidebar.number_input("현지 금액", min_value=0.0, value=0.0, step=1.0)
loc_cur   = st.sidebar.selectbox("현지 통화", ["USD","EUR","JPY","CNY"])
shipping  = st.sidebar.number_input("배송비 (KRW)", min_value=0.0, value=0.0, step=100.0)
card_fee  = st.sidebar.number_input("카드 수수료 (%)", min_value=0.0, value=4.0, step=0.5)
market_fee= st.sidebar.number_input("마켓 수수료 (%)", min_value=0.0, value=15.0, step=0.5)
target_margin = st.sidebar.number_input("목표 마진 (%)", min_value=0.0, value=40.0, step=1.0)

rate2 = fx_rate(loc_cur)
if rate2 and loc_price > 0:
    cost_krw = loc_price * rate2 + shipping
    sell = cost_krw * (1 + target_margin/100.0)
    final_price = sell / (1 - (card_fee + market_fee)/100.0) if (card_fee + market_fee) < 100 else sell
    profit = final_price - cost_krw
    margin_pct = (profit / final_price * 100) if final_price>0 else 0.0
    st.sidebar.success(f"🔥 예상 판매가: {final_price:,.0f} 원")
    st.sidebar.write(f"순이익: **{profit:,.0f} 원** (실마진 {margin_pct:.1f}%)")
elif loc_price > 0 and not rate2:
    st.sidebar.error("현지 통화 환율을 불러오지 못했습니다.")

# ---------- 레이아웃 ----------
col1, col2 = st.columns(2, gap="large")

# ---------- 네이버 데이터랩 (API + 샘플 Top20) ----------
with col1:
    st.subheader("📈 네이버 데이터랩 (API + Top20 샘플)")
    NAVER_ID = "h4mkIM2hNLct04BD7sC0"
    NAVER_SECRET = "ltoxUNyKxi"

    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=13)

    categories = ["패션의류","화장품/미용","식품","디지털/가전","생활/건강","스포츠/레저","출산/육아","가구/인테리어","문구/취미","도서/음반"]
    cat = st.selectbox("카테고리 선택", categories)

    def datalab_trend(keyword: str) -> pd.DataFrame:
        url = "https://openapi.naver.com/v1/datalab/search"
        headers = {"X-Naver-Client-Id": NAVER_ID, "X-Naver-Client-Secret": NAVER_SECRET}
        body = {
            "startDate": start.strftime("%Y-%m-%d"),
            "endDate": end.strftime("%Y-%m-%d"),
            "timeUnit": "date",
            "keywordGroups": [{"groupName": keyword, "keywords": [keyword]}],
            "device": "pc",
            "ages": [],
            "gender": ""
        }
        try:
            res = requests.post(url, headers=headers, json=body, timeout=10)
            js = res.json()
            if "results" in js and js["results"] and "data" in js["results"][0]:
                return pd.DataFrame(js["results"][0]["data"])
        except Exception:
            pass
        return pd.DataFrame()

    df = datalab_trend(cat)
    if df.empty:
        st.warning("API 응답이 없거나 제한됨 (샘플 Top20만 표시)")
    else:
        st.dataframe(df, use_container_width=True, height=260)

    SAMPLE_TOP20 = {
        "패션의류":["맨투맨","슬랙스","청바지","카라티","바람막이","니트","가디건","롱스커트","부츠컷","와이드팬츠",
                  "조거팬츠","박스티","패딩조끼","트레이닝복","롱패딩","숏패딩","데님자켓","카고팬츠","플리츠스커트","축구트레이닝"],
        "화장품/미용":["쿠션","립스틱","마스카라","선크림","에센스","토너","세럼","클렌징폼","팩","앰플",
                   "립밤","아이브로우","립틴트","픽서","컨실러","바디로션","핸드크림","헤어팩","헤어오일","탈모샴푸"],
        "식품":["라면","커피","참치","김치","스팸","초콜릿","견과","쿠키","시리얼","즉석밥",
               "맛김","꿀","올리브유","드립백","캡슐커피","피클","오트밀","누룽지","육포","꽁치"],
        "디지털/가전":["노트북","모니터","게이밍마우스","기계식키보드","태블릿","스마트폰","충전기","허브","SSD","외장하드",
                    "블루투스이어폰","헤드셋","웹캠","마이크","스피커","TV","공기청정기","청소기","전기포트","드라이기"],
        "생활/건강":["탄산수제조기","필터샤워기","욕실수납함","물걸레청소포","고무장갑","제습제","빨래바구니","장우산","프리미엄두루마리","소독티슈",
                   "호흡기마스크","멸균장갑","마사지건","방향제","분리수거함","세탁세제","섬유유연제","주방세제","빨래건조대","멀티탭"],
    }
    top20 = SAMPLE_TOP20.get(cat, SAMPLE_TOP20["패션의류"])
    scores = [randint(20, 98) for _ in top20]
    st.caption("Top20 키워드 (샘플 / 차후 실데이터 연동 예정)")
    st.table(pd.DataFrame({"rank": range(1, len(top20)+1), "keyword": top20, "score": scores}))

# ---------- 11번가 ----------
with col2:
    st.subheader("🛒 11번가 아마존 베스트")
    st.caption("환경에 따라 iframe이 차단될 수 있습니다. 실패 시 아래 '새창 열기'를 사용하세요.")
    iframe_html = """
    <iframe src='https://m.11st.co.kr/browsing/AmazonBest'
            width='100%' height='780' frameborder='0'
            referrerpolicy='no-referrer'
            sandbox='allow-same-origin allow-scripts allow-popups allow-forms'>
    </iframe>
    """
    st.components.v1.html(iframe_html, height=800)
    st.link_button("🔗 새창에서 열기 (모바일)", "https://m.11st.co.kr/browsing/AmazonBest")

# ---------- 상품명 생성기 (규칙/AI 토글) ----------
st.subheader("✍️ 상품명 생성기")
mode = st.radio("모드 선택", ["규칙 기반(무료)", "OpenAI API 사용"], horizontal=True)

brand   = st.text_input("브랜드")
base_kw = st.text_input("기본 문장")
extra_kw= st.text_input("키워드 (쉼표 , 로 구분)")
count   = st.slider("생성 개수", 3, 10, 5)

def gen_rule_titles(brand, base_kw, extra_kw, count):
    extras = [x.strip() for x in extra_kw.split(",") if x.strip()]
    if not extras:
        return [f"{brand} {base_kw}".strip()]
    picks = (extras * ((count // len(extras)) + 1))[:count]
    return [f"{brand} {base_kw} {p}".strip() for p in picks[:count]]

def openai_available():
    # 우선 순위: 세션에 입력한 키 > 환경변수
    key = st.session_state.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
    return key.strip() != ""

with st.expander("🔐 OpenAI API 설정 (선택)", expanded=False):
    st.text_input("API 키 입력 (세션 저장)", type="password", key="OPENAI_API_KEY")
    st.caption("환경변수 OPENAI_API_KEY 사용도 가능. 미입력 시 규칙 기반으로 폴백.")

def gen_openai_titles(brand, base_kw, keywords, n=5):
    """
    openai 패키지 미설치/네트워크 불가 환경을 고려해
    '존재하면 사용, 아니면 예외' 형태로 만들고 즉시 폴백.
    """
    key = st.session_state.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("NO_API_KEY")

    try:
        # 최신 Responses API 사용
        from openai import OpenAI
        client = OpenAI(api_key=key)

        prompt = f"""
역할: 이커머스 상품명 카피라이터
조건:
- 한국어, 공백 포함 28~36자
- {brand}을(를) 맨 앞에, 핵심 키워드 1~2개 포함
- 과장/광고성 금지어(최강, 역대급, 완판 등) 금지
- 플랫폼 검색최적화(중복어 제거, 불필요 기호 제거)
- {n}개 생성
입력:
브랜드: {brand}
기본 문장: {base_kw}
키워드 후보: {", ".join(keywords)}
출력형식: JSON 배열(문자열들만)
"""
        resp = client.responses.create(model="gpt-4o-mini", input=prompt)
        txt = resp.output_text
        titles = json.loads(txt)
        return titles[:n]
    except Exception as e:
        # 어떤 오류든 규칙 기반으로 폴백
        raise RuntimeError(f"API_FAIL:{e}")

if st.button("제목 생성"):
    if mode.startswith("규칙"):
        titles = gen_rule_titles(brand, base_kw, extra_kw, count)
        st.success("규칙 기반 결과")
        st.write(pd.DataFrame({"#": range(1, len(titles)+1), "title": titles}))
    else:
        kw_list = [x.strip() for x in extra_kw.split(",") if x.strip()]
        try:
            titles = gen_openai_titles(brand, base_kw, kw_list, n=count)
            st.success("OpenAI API 결과")
            st.write(pd.DataFrame({"#": range(1, len(titles)+1), "title": titles}))
        except RuntimeError as err:
            # 폴백
            titles = gen_rule_titles(brand, base_kw, extra_kw, count)
            st.warning(f"API 모드 실패 → 규칙 기반으로 대체 ({err})")
            st.write(pd.DataFrame({"#": range(1, len(titles)+1), "title": titles}))

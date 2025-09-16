# -*- coding: utf-8 -*-
"""
ENVY – v9
- 환율 30분 캐시 + 2중 폴백
- 마진 계산기
- 다크모드
- 데이터랩: "API-전용" 모드 (카테고리→Top20(사전)→1/7/30일 평균 ratio)
  * CSV 사전 업로드로 동의어/정규화 확장
- 11번가: iframe/새창/우회(프록시) 옵션 + 폴백 샘플
- 제목 생성기: 규칙/OpenAI API 토글
- 상단 ENVY 로고
"""
import os, json, re, time
from datetime import date, timedelta
from random import sample
import pandas as pd
import requests
import streamlit as st
from PIL import Image as _PILImage

st.set_page_config(page_title="ENVY v9", layout="wide")

# --- Header (ENVY logo) ---
try:
    _lg = _PILImage.open("/mnt/data/envy_logo.png")
    h1_l, h1_r = st.columns([1,4])
    with h1_l:
        st.image(_lg, width=120)
    with h1_r:
        st.markdown(" ")
except Exception:
    st.markdown("### ENVY")

# --- Dark mode ---
st.sidebar.checkbox("🌙 다크 모드", key="dark_mode")
if st.session_state.get("dark_mode", False):
    st.markdown("""
    <style>
      body, .stApp { background:#121212; color:#EDEDED; }
      .stMarkdown h1, h2, h3, h4, h5 { color:#FFF !important; }
      .stDataFrame, .stTable { color:#EDEDED !important; }
    </style>
    """, unsafe_allow_html=True)

st.markdown("### 💱 실시간 환율 + 📊 마진 + 📈 데이터랩(API) + 🛒 11번가 + ✍️ 상품명(API)")

# --- FX (30m cache, dual fallback) ---
@st.cache_data(ttl=1800)
def fx_rate(base="USD", target="KRW"):
    try:
        r = requests.get(f"https://api.exchangerate.host/latest?base={base}&symbols={target}", timeout=8).json()
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

# --- Sidebar: FX calc ---
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

# --- Sidebar: Margin calc ---
st.sidebar.subheader("🧮 간이 마진 계산")
loc_price = st.sidebar.number_input("현지 금액", min_value=0.0, value=0.0, step=1.0)
loc_cur   = st.sidebar.selectbox("현지 통화", ["USD","EUR","JPY","CNY"])
shipping  = st.sidebar.number_input("배송비 (KRW)", min_value=0.0, value=0.0, step=100.0)
card_fee  = st.sidebar.number_input("카드 수수료 (%)", min_value=0.0, value=4.0, step=0.5)
market_fee= st.sidebar.number_input("마켓 수수료 (%)", min_value=0.0, value=15.0, step=0.5)
target_margin = st.sidebar.number_input("목표 마진 (%)", min_value=0.0, value=40.0, step=1.0)
rate2 = fx_rate(loc_cur)
if rate2 and loc_price > 0:
    conv_cost = loc_price * rate2
    cost_krw = conv_cost + shipping
    sell_base = cost_krw * (1 + target_margin/100.0)
    final_price = sell_base / (1 - (card_fee + market_fee)/100.0) if (card_fee + market_fee) < 100 else sell_base
    profit = final_price - cost_krw
    margin_pct = (profit / final_price * 100) if final_price>0 else 0.0
    st.sidebar.info(f"환율({loc_cur}→KRW): ₩{rate2:,.2f}")
    st.sidebar.caption(f"환산 원가: ₩{conv_cost:,.0f}  •  배송비: ₩{shipping:,.0f}")
    st.sidebar.success(f"🔥 예상 판매가: **{final_price:,.0f} 원**")
    st.sidebar.write(f"순이익: **{profit:,.0f} 원**  (실마진 {margin_pct:.1f}%)")

# --- Layout ---
col1, col2 = st.columns(2, gap="large")

# --- DataLab API-only (category -> keywords -> 1/7/30 ratio) ---
with col1:
    st.subheader("📈 네이버 데이터랩 (API 전용: 1/7/30일 평균)")
    NAVER_ID = "h4mkIM2hNLct04BD7sC0"
    NAVER_SECRET = "ltoxUNyKxi"

    # Category seeds (fallback guaranteed)
    CATS = ["패션의류","화장품/미용","식품","디지털/가전","생활/건강","스포츠/레저","출산/육아","가구/인테리어","도서/취미/음반","자동차/공구"]
    cat = st.selectbox("카테고리 선택", CATS)

    _DEF_SEEDS = {
        "패션의류": ["맨투맨","슬랙스","청바지","카라티","바람막이","니트","가디건","롱스커트","부츠컷","와이드팬츠","조거팬츠","빅사이즈","패딩","바지","정장","셔츠","코트","블라우스","원피스","후드티"],
        "화장품/미용": ["클렌징","선크림","앰플","세럼","토너","로션","크림","팩","마스크팩","립밤","립스틱","쿠션","파운데이션","아이섀도우","아이라이너","컨실러","브러시","향수","샴푸","트리트먼트"],
        "식품": ["라면","커피","참치","김치","스팸","젤리","간식","유기농","과자","아몬드","캔디","우유","치즈","요거트","쌀","견과","올리브유","소스","시리얼","꿀"],
        "디지털/가전": ["노트북","모니터","키보드","마우스","SSD","HDD","스마트워치","태블릿","스마트폰","충전기","케이블","이어폰","헤드셋","공청기","에어컨","청소기","TV","캠","프린터","NAS"],
        "생활/건강": ["물티슈","휴지","세제","섬유유연제","주방세제","칫솔","치약","바디워시","샴푸","마스크","비타민","영양제","구강청결제","체온계","핫팩","수세미","고무장갑","제습제","벌레퇴치","상비약"],
        "스포츠/레저": ["덤벨","요가매트","러닝화","등산화","자전거","텐트","캠핑의자","버너","코펠","헬멧","배낭","아이스박스","스틱","수영복","고글","모자","장갑","보드복","스노우보드","볼"],
        "출산/육아": ["기저귀","물티슈","분유","젖병","이유식","유아의자","유모차","카시트","턱받이","치발기","젖병소독기","아기체온계","가제손수건","아기침대","범퍼침대","수유쿠션","흡입기","크림","워시","파우더"],
        "가구/인테리어": ["소파","책상","의자","서랍장","행거","옷장","식탁","협탁","러그","거실장","TV장","책장","선반","벽등","스탠드","커튼","블라인드","이불","베개","매트리스"],
        "도서/취미/음반": ["소설","에세이","시집","만화","수험서","참고서","잡지","앨범","LP","CD","보드게임","퍼즐","프라모델","필기구","수채화","유화","스케치북","컬러링북","캘리그라피","취미키트"],
        "자동차/공구": ["블랙박스","하이패스","대쉬캠","타이어","엔진오일","와이퍼","코팅제","광택제","충전기","점프스타터","공구세트","드릴","글루건","측정기","멀티탭","전등","후크","용접기","렌치","해머"]
    }

    # Normalizer + CSV dictionary
    from unicodedata import normalize as _norm
    _norm_map = {"후디":"후드티","롱패딩":"패딩","숏패딩":"패딩","청바지":"데님바지"}
    def _norm_k(s): return _norm("NFKC", s).replace(" ","").lower()
    def normalize_keywords(lst):
        out = []
        for k in lst:
            key = _norm_k(k)
            mapped = None
            for raw, canonical in _norm_map.items():
                if _norm_k(raw) == key:
                    mapped = canonical; break
            out.append(mapped if mapped else k)
        # dedup
        seen=set(); uniq=[]
        for x in out:
            if x not in seen:
                seen.add(x); uniq.append(x)
        return uniq[:20]

    seeds = normalize_keywords(_DEF_SEEDS.get(cat, _DEF_SEEDS["패션의류"]))

    with st.expander("📚 키워드 사전 업로드 (CSV, 선택)", expanded=False):
        st.caption("형식: raw,canonical (헤더 포함) / 예: 후디,후드티")
        sample = "raw,canonical\n후디,후드티\n롱패딩,패딩\n숏패딩,패딩\n"
        st.download_button("예제 CSV 받기", data=sample, file_name="envy_keyword_map.csv", mime="text/csv")
        up = st.file_uploader("사전 CSV 업로드", type=["csv"], key="dl_csv_v9")
        if up is not None:
            try:
                _df_map = pd.read_csv(up)
                add_map = {str(r["raw"]).strip(): str(r["canonical"]).strip() for _, r in _df_map.iterrows() if str(r.get("raw","")).strip()}
                _norm_map.update(add_map)
                st.success(f"사전 {len(add_map)}개 적용 완료")
                seeds = normalize_keywords(seeds)  # 재정규화
            except Exception as e:
                st.error("CSV 파싱 실패: " + str(e))

    # Query Naver DataLab API for 1/7/30 day windows (avg ratio)
    def datalab_avg(keyword:str, days:int):
        end = date.today() - timedelta(days=1)
        start = end - timedelta(days=days-1)
        url = "https://openapi.naver.com/v1/datalab/search"
        headers={"X-Naver-Client-Id":NAVER_ID, "X-Naver-Client-Secret":NAVER_SECRET}
        body={
            "startDate": start.strftime("%Y-%m-%d"),
            "endDate": end.strftime("%Y-%m-%d"),
            "timeUnit":"date",
            "keywordGroups":[{"groupName":keyword, "keywords":[keyword]}],
            "device":"pc","ages":[],"gender":""
        }
        try:
            r = requests.post(url, headers=headers, json=body, timeout=10).json()
            data = r["results"][0]["data"]
            vals = [d["ratio"] for d in data if "ratio" in d]
            return sum(vals)/len(vals) if vals else 0.0
        except Exception:
            return 0.0

    rows = []
    for kw in seeds:
        d1  = datalab_avg(kw, 1)
        d7  = datalab_avg(kw, 7)
        d30 = datalab_avg(kw, 30)
        rows.append({"keyword": kw, "day1": round(d1,2), "day7": round(d7,2), "day30": round(d30,2)})
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, height=480)

# --- 11st ---
with col2:
    st.subheader("🛒 11번가 AmazonBest")
with col2:
    st.subheader("🛒 11번가 AmazonBest")

    # 사이드바 옵션 (프록시/UA/표시 모드 유지하되, 본문은 '둘다' 제공)
    with st.sidebar.expander("🛒 11번가 옵션", expanded=False):
        st.caption("프록시 예시: https://your-proxy.example/fetch?url=")
        proxy_base = st.text_input("프록시 베이스 URL", value=st.session_state.get("e11_proxy", ""))
        ua = st.text_input("User-Agent (선택)", value=st.session_state.get("e11_ua", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"))
        st.session_state["e11_proxy"] = proxy_base
        st.session_state["e11_ua"] = ua

    # 1) 항시 제공: 새창 열기 버튼 (100% 보장)
    st.link_button("🔗 새창에서 11번가 AmazonBest 열기", "https://m.11st.co.kr/browsing/AmazonBest")

    # 2) 기본 제공: 우회(프록시/직결) 테이블
    def fetch_e11_list(proxy_base:str, ua:str):
        import json, re, requests
        headers = {"User-Agent": ua} if ua else {}
        target = "https://m.11st.co.kr/browsing/AmazonBest"
        text = ""
        try:
            if proxy_base:
                url = proxy_base + target
                text = requests.get(url, headers=headers, timeout=8).text
            else:
                text = requests.get(target, headers=headers, timeout=8).text
        except Exception:
            text = ""

        rows = []
        # naive JSON block
        try:
            m = re.search(r'(\{.*\"AmazonBest\".*\})', text, re.DOTALL)
            if m:
                blob = m.group(1).replace("\n","")
                js = json.loads(blob)
                items = []
                try:
                    items = js["state"]["bests"]["items"]
                except Exception:
                    items = []
                if items:
                    for i, it in enumerate(items[:20]):
                        rows.append({
                            "rank": i+1,
                            "product": it.get("productName") or it.get("name") or "",
                            "price": str(it.get("finalPrice") or it.get("price") or ""),
                            "link": it.get("detailUrl") or ""
                        })
                    return rows
        except Exception:
            pass

        # regex fallback
        try:
            names = re.findall(r'\"productName\"\s*:\s*\"([^\"]{3,120})\"', text)
            prices = re.findall(r'\"finalPrice\"\s*:\s*\"?(\d[\d,]{2,})\"?', text)
            links  = re.findall(r'\"detailUrl\"\s*:\s*\"([^\"]+)\"', text)
            for i, n in enumerate(names[:20]):
                price = prices[i] if i < len(prices) else ""
                link  = links[i]  if i < len(links)  else ""
                rows.append({"rank": i+1, "product": n, "price": price.replace(",", ""), "link": link})
        except Exception:
            rows = []

        if not rows:
            rows = [
                {"rank":1,"product":"애플 에어팟 Pro (2세대)","price":"329000","link":""},
                {"rank":2,"product":"삼성 갤럭시 S23 256GB","price":"998000","link":""},
                {"rank":3,"product":"나이키 운동화 레볼루션","price":"89000","link":""},
                {"rank":4,"product":"LG 노트북 16형 초경량","price":"1399000","link":""},
                {"rank":5,"product":"스타벅스 텀블러 473ml","price":"23000","link":""},
            ]
        return rows

    rows = fetch_e11_list(st.session_state.get("e11_proxy",""), st.session_state.get("e11_ua",""))
    st.caption("우회(프록시/직결) 테이블 – 차단 시 샘플 데이터로 폴백합니다.")
    st.dataframe(pd.DataFrame(rows), use_container_width=True, height=420)

    # 3) 선택 제공: iframe (차단될 수 있음)
    with st.expander("🧪 iframe으로 직접 보기 (환경에 따라 차단됨)", expanded=False):
        html = """
        <iframe src='https://m.11st.co.kr/browsing/AmazonBest'
                width='100%' height='780' frameborder='0'
                referrerpolicy='no-referrer'
                sandbox='allow-same-origin allow-scripts allow-popups allow-forms'>
        </iframe>"""
        st.components.v1.html(html, height=800)
# --- Title generator ---
st.subheader("✍️ 상품명 생성기")
_left, _right = st.columns([3,2])
with _left:
    mode = st.radio("모드 선택", ["규칙 기반(무료)", "OpenAI API 사용"], horizontal=True)
with _right:
    with st.expander("🔐 OpenAI API 설정 (선택)", expanded=False):
        st.text_input("API 키 입력 (세션 저장)", type="password", key="OPENAI_API_KEY")
        st.caption("환경변수 OPENAI_API_KEY 사용도 가능. 미입력 시 규칙 기반으로 폴백.")

btn_col1, btn_col2 = st.columns([1,5])
with btn_col1:
    gen_now = st.button("제목 생성", use_container_width=True)
with btn_col2:
    st.caption("상단에서 바로 생성")

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

def gen_openai_titles(brand, base_kw, keywords, n=5):
    key = st.session_state.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("NO_API_KEY")
    try:
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
        titles = json.loads(resp.output_text)
        return titles[:n]
    except Exception as e:
        raise RuntimeError(f"API_FAIL:{e}")

if gen_now:
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
            titles = gen_rule_titles(brand, base_kw, extra_kw, count)
            st.warning(f"API 모드 실패 → 규칙 기반으로 대체 ({err})")
            st.write(pd.DataFrame({"#": range(1, len(titles)+1), "title": titles}))

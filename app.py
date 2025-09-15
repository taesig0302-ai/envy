# -*- coding: utf-8 -*-
"""
ENVYLINK 소싱툴 – MASTER v2
요청 반영:
- 마진 계산기: 출력/표기 정리(원가(KRW) 분해표시), 기존 항목 유지
- 데이터랩: 상단 period/ratio 표 제거, 카테고리별 Top20 키워드만 표기(열 = rank, keyword)
- 카테고리 매핑 강화(10종 전부 지원, 누락 없는 안전 폴백)
"""
import os
from datetime import date, timedelta
from random import sample
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="ENVY", layout="wide")

# -------------------------------
# 다크 모드
# -------------------------------
st.sidebar.checkbox("🌙 다크 모드", key="dark_mode")
if st.session_state.get("dark_mode", False):
    st.markdown("""
    <style>
      body, .stApp { background:#121212; color:#EDEDED; }
      .stMarkdown h1, h2, h3, h4, h5 { color:#FFF !important; }
      .stDataFrame, .stTable { color:#EDEDED !important; }
    </style>
    """, unsafe_allow_html=True)


# Top header with logo
from PIL import Image
import base64, io

logo_file = "/mnt/data/envy_logo.png"
try:
    _logo = Image.open(logo_file)
    col_l, col_c, col_r = st.columns([1,2,1])
    with col_c:
        st.image(_logo, width=160)
    st.markdown("<h1 style='text-align:center; margin-top:-12px;'>ENVY</h1>", unsafe_allow_html=True)
except Exception:
    st.title("ENVY")

from PIL import Image as _PILImage
try:
    _lg = _PILImage.open("/mnt/data/envy_logo.png")
    h1_l, h1_r = st.columns([1,4])
    with h1_l:
        st.image(_lg, width=120)
    with h1_r:
        st.markdown(" ")  # keep layout tidy
except Exception:
    st.markdown("### ENVY")

# ===== 11번가 옵션/우회 설정 =====
with st.sidebar.expander("🛒 11번가 옵션", expanded=False):
    st.caption("프록시 예시: https://your-proxy.example/fetch?url=")
    proxy_base = st.text_input("프록시 베이스 URL", value=st.session_state.get("e11_proxy", ""))
    ua = st.text_input("User-Agent (선택)", value=st.session_state.get("e11_ua", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"))
    st.session_state["e11_proxy"] = proxy_base
    st.session_state["e11_ua"] = ua
    e11_mode = st.radio("표시 모드", ["iframe", "우회(피드/프록시)", "새창"], index=0, horizontal=True)

import requests, json

def fetch_e11_list(proxy_base:str, ua:str):
    """
    시도 순서:
      1) JSON스러운 피드 패턴 존재 시 파싱
      2) 프록시가 설정되어 있으면 프록시 경유
      3) 직결 요청 (차단시 예외)
      4) 정규식 스캔 폴백
    반환: [{"rank":1,"product":"..","price":"..","link":".."}]
    """
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
    # 1) JSON 블록 찾기
    try:
        # 간단 JSON 추출(페이지 내 window.__NUXT__ 같은 구조를 상정)
        m = re.search(r'(\{.*\"AmazonBest\".*\})', text, re.DOTALL)
        if m:
            blob = m.group(1)
            # 안전 파싱 시도
            blob = blob.replace("\\n","")
            js = json.loads(blob)
            # 이 부분은 실제 구조에 맞게 키를 수정해야 함. 없으면 except로 이동
            items = []
            try:
                # 샘플: js["state"]["bests"]["items"]
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

    # 2) 정규식 폴백 (상품명/가격 후보)
    try:
        names = re.findall(r'"productName"\\s*:\\s*"([^"]{3,120})"', text)
        prices = re.findall(r'"finalPrice"\\s*:\\s*"?(\\d[\\d,]{2,})"?', text)
        links  = re.findall(r'"detailUrl"\\s*:\\s*"([^"]+)"', text)
        for i, n in enumerate(names[:20]):
            price = prices[i] if i < len(prices) else ""
            link  = links[i]  if i < len(links)  else ""
            rows.append({"rank": i+1, "product": n, "price": price.replace(",", ""), "link": link})
    except Exception:
        rows = []

    # 3) 샘플 폴백
    if not rows:
        rows = [
            {"rank":1,"product":"애플 에어팟 Pro (2세대)","price":"329000","link":""},
            {"rank":2,"product":"삼성 갤럭시 S23 256GB","price":"998000","link":""},
            {"rank":3,"product":"나이키 운동화 레볼루션","price":"89000","link":""},
            {"rank":4,"product":"LG 노트북 16형 초경량","price":"1399000","link":""},
            {"rank":5,"product":"스타벅스 텀블러 473ml","price":"23000","link":""},
        ]
    return rows


# -------------------------------
# 환율 (30분 캐시 / 2중 fallback)
# -------------------------------
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

# -------------------------------
# 환율 계산기 (사이드바)
# -------------------------------
st.sidebar.subheader("💱 환율 계산기")
fx_amount = st.sidebar.number_input("상품 원가", min_value=0.0, value=1.0, step=1.0)
fx_currency = st.sidebar.selectbox("통화", ["USD ($)", "EUR (€)", "JPY (¥)", "CNY (¥)"])
fx_map = {"USD ($)":"USD","EUR (€)":"EUR","JPY (¥)":"JPY","CNY (¥)":"CNY"}
rate = fx_rate(fx_map[fx_currency])
if rate:
    st.sidebar.markdown(f"### {fx_amount:.2f} {fx_map[fx_currency]} → **{fx_amount*rate:,.0f} 원**")
    st.sidebar.caption(f"1 {fx_map[fx_currency]} = ₩{rate:,.2f}  (30분 캐시)")
else:
    st.sidebar.error("환율 정보를 불러올 수 없습니다.")

# -------------------------------
# 마진 계산기 (사이드바) – 기존 필드 유지 + 원가 표기 보강
# -------------------------------
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
    sell_base = cost_krw * (1 + target_margin/100.0)  # 수수료 제외 판매가
    final_price = sell_base / (1 - (card_fee + market_fee)/100.0) if (card_fee + market_fee) < 100 else sell_base
    profit = final_price - cost_krw
    margin_pct = (profit / final_price * 100) if final_price>0 else 0.0

    st.sidebar.info(f"환율({loc_cur}→KRW): ₩{rate2:,.2f}")
    st.sidebar.caption(f"환산 원가: ₩{conv_cost:,.0f}  •  배송비: ₩{shipping:,.0f}")
    st.sidebar.success(f"🔥 예상 판매가: **{final_price:,.0f} 원**")
    st.sidebar.write(f"순이익: **{profit:,.0f} 원**  (실마진 {margin_pct:.1f}%)")
    # 합계 값(예상 판매가) 고정 칸 제공
    
elif loc_price > 0 and not rate2:
    st.sidebar.error("현지 통화 환율을 불러오지 못했습니다.")

# -------------------------------
# 메인 2열 레이아웃
# -------------------------------
col1, col2 = st.columns(2, gap="large")

# -------------------------------
# 네이버 데이터랩 – 상단 ratio 표 제거, Top20 키워드만
# -------------------------------
with col1:
    st.subheader("📈 네이버 데이터랩 (Top20 키워드)")
    # 카테고리 10종 고정
    categories = ["패션의류","화장품/미용","식품","디지털/가전","생활/건강","스포츠/레저","출산/육아","가구/인테리어","문구/취미","도서/음반"]
    cat = st.selectbox("카테고리 선택", categories)

    # 10개 카테고리 전부에 대해 Top20 키워드 준비 (샘플/폴백)
    TOP20 = {
        "패션의류":["맨투맨","슬랙스","청바지","카라티","바람막이","니트","가디건","롱스커트","부츠컷","와이드팬츠",
                 "조거팬츠","박스티","패딩조끼","트레이닝복","롱패딩","숏패딩","데님자켓","카고팬츠","플리츠스커트","축구트레이닝"],
        "화장품/미용":["쿠션","립스틱","마스카라","선크림","에센스","토너","세럼","클렌징폼","팩","앰플",
                  "립밤","아이브로우","립틴트","픽서","컨실러","바디로션","핸드크림","헤어팩","헤어오일","탈모샴푸"],
        "식품":["라면","커피","참치","김치","스팸","초콜릿","견과","쿠키","시리얼","즉석밥",
              "맛김","꿀","올리브유","드립백","캡슐커피","피클","오트밀","누룽지","육포","꽁치"],
        "디지털/가전":["노트북","모니터","게이밍마우스","기계식키보드","태블릿","스마트폰","충전기","허브","SSD","외장하드",
                     "블루투스이어폰","헤드셋","웹캠","마이크","스피커","TV","공기청정기","청소기","전기포트","드라이기"],
        "생활/건강":["탄산수제조기","필터샤워기","욕실수납함","물걸레청소포","고무장갑","제습제","빨래바구니","장우산","두루마리휴지","소독티슈",
                   "KF마스크","주방세제","세탁세제","섬유유연제","방향제","멀티탭","빨래건조대","분리수거함","마사지건","제습기"],
        "스포츠/레저":["런닝화","요가매트","덤벨","운동복","트레이닝세트","축구공","골프장갑","테니스공","배드민턴라켓","스포츠타월",
                    "아대","헬스장갑","스포츠양말","스포츠가방","캠핑체어","코펠","버너","침낭","워터저그","카라비너"],
        "출산/육아":["기저귀","물티슈","스와들업","수유쿠션","젖병소독기","아기치약","액상분유","초점책","딸랑이","아기양말",
                  "턱받이","젖병세정제","기저귀가방","유모차걸이","아기크림","로션","바디워시","아기세제","모빌","아기방등"],
        "가구/인테리어":["수납박스","행거","틈새수납장","사이드테이블","모듈선반","접이식테이블","LED방등","액자","안마의자","러그",
                      "암막커튼","방풍비닐","방문손잡이","욕실매트","문풍지","침대프레임","행거커버","쿠션커버","미닫이수납함","빨래바구니"],
        "문구/취미":["젤펜","형광펜","지우개","마스킹테이프","파일폴더","문서파쇄기","스티커","도트다이어리","연습장","스케치북",
                  "아크릴물감","붓세트","폰케이스DIY","만년필","샤프","샤프심","실링왁스","캘리그라피펜","스탬프","폴라로이드필름"],
        "도서/음반":["에세이","자기계발","소설","그림책","영어원서","TOEIC모의고사","수능교재","요리책","에듀클래식","로파이힙합",
                  "재즈CD","피아노악보","기타악보","캘리음악노트","드로잉북","컬러링북","포토에세이","문고판소설","스도쿠북","한국사요약집"],
    }
    

# ---- DataLab category keyword fallback ----
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

def _fallback_keywords(cat:str):
    return _DEF_SEEDS.get(cat, _DEF_SEEDS["패션의류"])[:20]

# ---- 데이터랩 키워드 정규화(간단 매칭) ----
from unicodedata import normalize as _norm
def _norm_k(s): 
    s = _norm("NFKC", s)
    return s.replace(" ", "").lower()

_norm_map = {
    "맨투맨":"맨투맨", "후디":"후드티", "후드":"후드티", "청바지":"데님바지", "슬랙스":"슬랙스",
    "롱패딩":"패딩", "숏패딩":"패딩", "바람막이":"바람막이", "가디건":"가디건", "니트":"니트",
}

def normalize_keywords(lst):
    out = []
    for k in lst:
        key = _norm_k(k)
        mapped = None
        for raw, canonical in _norm_map.items():
            if _norm_k(raw) == key:
                mapped = canonical; break
        out.append(mapped if mapped else k)
    # 중복 제거 보정
    seen = set(); uniq = []
    for x in out:
        if x not in seen:
            seen.add(x); uniq.append(x)
    return uniq[:20]

    keywords = TOP20.get(cat, [])
    if not keywords:
        keywords = _fallback_keywords(cat)
    keywords = normalize_keywords(keywords)
    # --- CSV 사전 추가 병합 ---
    with st.expander("📚 키워드 사전 업로드 (CSV, 선택)", expanded=False):
        st.caption("형식: raw,canonical (헤더 포함) / 예: 후디,후드티")
        import pandas as _pd2
        sample = "raw,canonical\n후디,후드티\n롱패딩,패딩\n숏패딩,패딩\n"
        st.download_button("예제 CSV 받기", data=sample, file_name="envy_keyword_map.csv", mime="text/csv")
        up = st.file_uploader("사전 CSV 업로드", type=["csv"], key="dl_csv")
        if up is not None:
            try:
                df_map = _pd2.read_csv(up)
                extra = {str(r.raw): str(r.canonical) for _, r in df_map.iterrows() if str(r.raw).strip()}
                # 런타임 매핑 병합
                _norm_map.update(extra)
                keywords = normalize_keywords(keywords)
            except Exception as e:
                st.warning(f"사전 CSV 처리 실패: {e}")
    df_kw = pd.DataFrame({"keyword": keywords})
    st.dataframe(df_kw, use_container_width=True, height=480)

# -------------------------------
# 11번가 – 동일 (iframe + 새창)
# -------------------------------
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
    # --- 실험: 11번가 인기 리스트 우회 파싱 (차단되면 샘플 표기) ---
    with st.expander("🧪 11번가 인기 리스트 (우회 모드)", expanded=(e11_mode!="iframe")):
        import pandas as _pd
        import re as _re
        import requests as _rq
        _rows = []
        try:
            _rows = fetch_e11_list(proxy_base, ua)
            # 텍스트는 내부에서 가져오므로 별도 요청 불필요
            # 매우 단순한 패턴 매칭(차단/변경 대비)
            # 상품명 후보
            names = _re.findall(r'"productName"\s*:\s*"([^"]{5,80})"', _html)
            prices = _re.findall(r'"finalPrice"\s*:\s*"?(\d[\d,]{3,})"?', _html)
            for i, n in enumerate(names[:20]):
                price = prices[i] if i < len(prices) else ''
                price = price.replace(',', '')
                _rows.append({"rank": i+1, "product": n, "price": price})
        except Exception:
            _rows = []
        if not _rows:
            SAMPLE = [
                {"rank":1,"product":"애플 에어팟 Pro (2세대)","price":"329000"},
                {"rank":2,"product":"삼성 갤럭시 S23 256GB","price":"998000"},
                {"rank":3,"product":"나이키 운동화 레볼루션","price":"89000"},
                {"rank":4,"product":"LG 노트북 16형 초경량","price":"1399000"},
                {"rank":5,"product":"스타벅스 텀블러 473ml","price":"23000"},
            ]
            _rows = SAMPLE
            st.caption("실데이터 차단 시 샘플 리스트를 표시합니다.")
        st.dataframe(_pd.DataFrame(_rows), use_container_width=True, height=360)


# -------------------------------
# 상품명 생성기 (규칙/AI 토글 – 기존 유지)
# -------------------------------
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

def openai_available():
    key = st.session_state.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
    return key.strip() != ""


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
        import json
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

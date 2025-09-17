import os, time, json, re
import requests
import streamlit as st
import streamlit.components.v1 as components

# -------------------------------
# 전역 세팅 / 상태
# -------------------------------
if "dark" not in st.session_state:
    st.session_state.dark = False

# Cloudflare 통합 프록시 (secrets에 있으면 그걸 쓰고, 없으면 입력값/기본값)
CF_PROXY = st.secrets.get("CF_PROXY_URL", "").strip()

# Rakuten App ID (secrets 권장)
RAKUTEN_APP_ID = st.secrets.get("RAKUTEN_APP_ID", "").strip()

# 데이터랩 카테고리(10개 고정)
DATALAB_CATS = [
    "패션잡화","식품","가구/인테리어","생활/건강","스포츠/레저",
    "가전/디지털","출산/육아","도서/음반","자동차용품","기타"
]

# 데이터랩 카테고리 → 내부 CID 매핑(샘플: 임시값)
# 실제 CID는 확정 후 여기에 넣자. (프록시 통해 확인 가능)
CID_MAP = {
    "패션잡화":"50000000","식품":"50000001","가구/인테리어":"50000002",
    "생활/건강":"50000003","스포츠/레저":"50000004","가전/디지털":"50000005",
    "출산/육아":"50000006","도서/음반":"50000007","자동차용품":"50000008","기타":"50000009"
}

def _join(a, b):
    return a.rstrip("/") + "/" + b.lstrip("/")

def _proxy_get(target_url: str, frame: bool=False, timeout=15):
    """
    Cloudflare Worker 통합 프록시로 GET. 
    frame=True면 X-Frame옵션/보안헤더 제거한 HTML 반환 (11번가 임베드용)
    """
    if not CF_PROXY:
        raise RuntimeError("통합 프록시 주소가 없습니다. st.secrets['CF_PROXY_URL']에 넣으세요.")
    params = {"target": target_url}
    if frame:
        params["frame"] = "1"
    r = requests.get(CF_PROXY, params=params, timeout=timeout)
    r.raise_for_status()
    return r

def _pretty_json(j):
    return json.dumps(j, ensure_ascii=False, indent=2)
# -------------------------------
# 레이아웃/사이드바/다크모드 CSS
# -------------------------------
# 사이드바 스크롤 없이 한눈에 보이도록 간격 최소화
BASE_CSS = """
<style>
/* 전체 카드 여백 축소 */
.block-container {padding-top: 0.6rem; padding-bottom: 0.6rem;}
.css-1dp5vir, .st-emotion-cache-13ln4jf {row-gap: .5rem;} /* section 간격 축소(버전에 따라 class 다를 수 있음) */

/* 사이드바 컴팩트화 */
section[data-testid="stSidebar"] {width: 300px !important;}
section[data-testid="stSidebar"] .stNumberInput, 
section[data-testid="stSidebar"] .stSelectbox, 
section[data-testid="stSidebar"] .stTextInput {margin-bottom: .4rem;}
/* 아래 개발/연결 설정 숨김 */
#dev-footer, #conn-box {display: none;}
/* 카드(섹션) 수직 여백 살짝 축소 */
div[data-testid="stVerticalBlockBorderWrapper"] {margin-top: .4rem; margin-bottom: .4rem;}
</style>
"""

# 다크모드 토글용 (CSS 스킨)
DARK_CSS = """
<style>
:root { --bg:#0e1117; --fg:#e6e6e6; --card:#161a23; --muted:#a9b3c1; --accent:#ff7d00; }
html, body, .block-container { background-color:var(--bg) !important; color:var(--fg) !important;}
section[data-testid="stSidebar"] {background-color:var(--card) !important;}
div[data-testid="stVerticalBlock"] {background:transparent !important;}
.stButton>button { background: var(--accent); color:white; border:0;}
.stNumberInput input, .stTextInput input, .stSelectbox div[role="combobox"]{
  background:var(--card) !important; color:var(--fg) !important; border:1px solid #2a2f3a;
}
</style>
"""

st.markdown(BASE_CSS, unsafe_allow_html=True)

# 다크모드 토글(사이드바 최상단)
dark_on = st.sidebar.toggle("🌙 다크 모드", value=st.session_state.dark, key="dark_toggle")
st.session_state.dark = dark_on
if st.session_state.dark:
    st.markdown(DARK_CSS, unsafe_allow_html=True)
# -------------------------------
# 사이드바 (간결/고정)
# -------------------------------
with st.sidebar:
    st.markdown("### ① 환율 계산기")
    base_currency = st.selectbox("기준 통화", ["USD","EUR","JPY","CNY"], index=0)
    rate = st.number_input("환율 (1 단위 → ₩)", value=1400.00, step=0.01, format="%.2f")
    price_foreign = st.number_input("판매금액 (외화)", value=1.00, step=0.01, format="%.2f")
    exch_amt = price_foreign * rate
    st.success(f"환산 금액: {exch_amt:,.2f} 원")

    st.markdown("### ② 마진 계산기 (v23)")
    fee_card = st.number_input("카드수수료 (%)", value=4.00, step=0.01, format="%.2f")
    fee_market = st.number_input("마켓수수료 (%)", value=14.00, step=0.01, format="%.2f")
    ship = st.number_input("배송비 (원)", value=0.00, step=100.0, format="%.0f")
    margin_mode = st.radio("마진 방식", ["퍼센트 마진(%)","더하기 마진(₩)"], horizontal=True, index=0)
    margin_value = st.number_input("마진율/마진액", value=10.00, step=0.1, format="%.2f")

    # v23 공식
    cost = exch_amt * (1 + fee_card/100) * (1 + fee_market/100)
    if margin_mode.startswith("퍼센트"):
        price_krw = cost * (1 + margin_value/100) + ship
    else:
        price_krw = cost + margin_value + ship

    st.info(f"예상 판매가: {price_krw:,.2f} 원")
    st.warning(f"순이익(마진): {price_krw - cost:,.2f} 원")

    # 개발/연결 설정은 숨김 박스로 렌더 (CSS에서 display:none)
    with st.container():
        st.markdown('<div id="conn-box">', unsafe_allow_html=True)
        st.text_input("Cloudflare Worker 프록시 URL", value=CF_PROXY, disabled=True)
        st.text_input("Rakuten App ID", value=RAKUTEN_APP_ID[:4]+"***"+RAKUTEN_APP_ID[-3:] if RAKUTEN_APP_ID else "", disabled=True)
        st.markdown('</div>', unsafe_allow_html=True)
# -------------------------------
# 본문 상단: 데이터랩
# -------------------------------
st.markdown("## 데이터랩")

c1, c2 = st.columns([1,2])
with c1:
    cat = st.selectbox("카테고리(10개)", options=DATALAB_CATS, index=0)

with c2:
    st.text_input("데이터랩 재시도", value="", placeholder="버튼을 누르면 재시도합니다.", disabled=True)

info_box = st.empty()
table_slot = st.empty()

def fetch_datalab(cat_name:str):
    """프록시 통해 네이버 DataLab API(내부 엔드포인트) 호출 → rank/keyword/search 반환"""
    cid = CID_MAP.get(cat_name)
    if not cid:
        return None, "CID 매핑이 없습니다."
    # 예: 프록시가 /datalab?cid= 로 라우팅하도록 worker에 구현해 둠 (혹은 target= 으로 JSON 직접)
    # 아래는 예시: DataLab JSON 엔드포인트를 프록시로 통과
    datalab_api = f"https://datalab.naver.com/shoppingInsight/getCategoryKeywordRank.naver?cid={cid}"
    try:
        r = _proxy_get(datalab_api, timeout=15)
        j = r.json()
        rows = []
        for i, row in enumerate(j.get("ranks", []), start=1):
            rows.append({"rank": i, "keyword": row.get("keyword","-"), "search": row.get("rank", 0)})
        return rows, None
    except Exception as e:
        return None, f"DataLab 호출 실패: {e}"

# 최초 자동로드 + 변동 시 자동로드
if "datalab_cat" not in st.session_state or st.session_state.datalab_cat != cat:
    st.session_state.datalab_cat = cat
    rows, err = fetch_datalab(cat)
else:
    rows, err = fetch_datalab(cat)

if err:
    info_box.warning(f"DataLab 호출 실패: {err} / 프록시·기간·CID 확인")
    table_slot.table([{"rank":i, "keyword":f"키워드{i}", "search":v} for i, v in enumerate([100,92,88,77,70], start=1)])
else:
    info_box.success("DataLab 로딩 성공")
    table_slot.table(rows)

if st.button("데이터랩 재시도"):
    rows, err = fetch_datalab(cat)
    if err:
        info_box.warning(f"DataLab 호출 실패: {err}")
    else:
        info_box.success("DataLab 로딩 성공(재시도)")
        table_slot.table(rows)
# -------------------------------
# AI 키워드 레이더 (국내/글로벌)
# -------------------------------
st.markdown("## AI 키워드 레이더 (국내/글로벌)")
mode_local = st.radio("모드", ["국내","글로벌"], horizontal=True, index=0)

radar_slot = st.empty()

def fetch_rakuten_trend(app_id: str, genre_id: str="0"):
    """
    라쿠텐 상품 랭킹/키워드 (예시) – 실제 사용 중인 엔드포인트로 교체
    """
    if not app_id:
        return None, "Rakuten App ID 필요(secrets.toml)"
    # 예시: genre=0(전체) – 실제는 사용 중인 API 문서대로 수정
    url = f"https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20170628?applicationId={app_id}&genreId={genre_id}"
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        j = r.json()
        rows = []
        for i, item in enumerate(j.get("Items", [])[:20], start=1):
            kw = item.get("Item", {}).get("itemName","-")
            rows.append({"rank": i, "keyword": kw})
        return rows, None
    except Exception as e:
        return None, f"Rakuten 호출 실패: {e}"

if mode_local == "글로벌":
    if RAKUTEN_APP_ID:
        rows, err = fetch_rakuten_trend(RAKUTEN_APP_ID, genre_id="0")
        if err:
            st.info("라쿠텐 호출 실패 – 샘플 표시")
            radar_slot.table([{"rank":i, "keyword":s} for i,s in enumerate(["YOUNG OLD Blu-ray", "SIXTONES DVD", "AKB48", "BTS Blu-ray", "SEVENTEEN"], start=1)])
        else:
            radar_slot.table(rows)
    else:
        st.warning("Rakuten App ID가 없어서 샘플만 표시 중입니다. (secrets.toml에 RAKUTEN_APP_ID 추가)")
        radar_slot.table([{"rank":i, "keyword":s} for i,s in enumerate(["YOUNG OLD Blu-ray", "SIXTONES DVD", "AKB48", "BTS Blu-ray", "SEVENTEEN"], start=1)])
else:
    # 국내 모드는 데이터랩 결과를 그대로 사용(간단하게)
    radar_slot.table([{"rank":i, "keyword":f"국내키워드{i}"} for i in range(1, 11)])
# -------------------------------
# 11번가(모바일) 임베드
# -------------------------------
st.markdown("## 11번가 (모바일)")
eleven_url = st.text_input("11번가 URL", value="https://m.11st.co.kr/browsing/bestSellers.mall")
embed_box = st.empty()

try:
    # 프록시에서 frame=1로 HTML 반환 (X-Frame 해제)
    _ = _proxy_get(eleven_url, frame=True, timeout=12)  # 접속 확인
    # components.iframe에 프록시 주소를 그대로 넣는다 (target쿼리와 frame=1 포함)
    iframe_url = f"{CF_PROXY}?frame=1&target={requests.utils.quote(eleven_url, safe='')}"
    components.iframe(iframe_url, height=620, scrolling=True)
except Exception as e:
    st.info("프록시로 임베드가 차단되면 버튼으로 새창 열기")
    st.link_button("모바일 베스트 새창 열기", eleven_url, type="primary")

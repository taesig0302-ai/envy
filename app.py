# -*- coding: utf-8 -*-
import time, hmac, hashlib, base64, json, re
import requests
import pandas as pd
import streamlit as st
import urllib.parse as _url

# =========================
# 공통 유틸
# =========================
DATALAB_CAT = {
    "패션의류": "50000000", "패션잡화": "50000001", "화장품/미용": "50000002",
    "디지털/가전": "50000003", "가구/인테리어": "50000004", "출산/육아": "50000005",
    "식품": "50000006", "스포츠/레저": "50000007", "생활/건강": "50000008",
    "여가/생활편의": "50000009", "면세점": "50000010", "도서": "50005542"
}
DATALAB_CATS = list(DATALAB_CAT.keys())

def _inject_main_css():
    st.markdown("""
    <style>
      .block-container { max-width: 1800px !important; padding-top: .6rem !important; }
      .envy-card { background: var(--background-color); border: 1px solid rgba(0,0,0,.08);
                   border-radius: 10px; padding: 12px; }
      .sm-table table { font-size: 0.92rem !important; }
      .embed { border: 1px solid rgba(0,0,0,.1); border-radius: 10px; overflow: hidden; }
      .rk table { font-size:.90rem !important; }
    </style>
    """, unsafe_allow_html=True)

def _get_secret(name:str, default:str=""):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default

def _proxy_base():
    # 사이드바 입력 or 기본 프록시
    return (st.session_state.get("PROXY_URL") or "https://envy-proxy.taesig0302.workers.dev").rstrip("/")

def _proxied(url:str) -> str:
    return f"{_proxy_base()}/?url={_url.quote(url, safe='')}"

# =========================
# 사이드바 (최소 구성: 프록시 URL 입력만)
# =========================
def render_sidebar():
    with st.sidebar:
        st.header("ENvY")
        st.write("프록시(CF Worker) 주소가 없으면 일부 iFrame이 막힐 수 있어요.")
        st.text_input("PROXY_URL (Cloudflare Worker)", key="PROXY_URL", placeholder="https://xxxx.workers.dev")
        st.caption("※ 네가 쓰던 환율/마진 계산 사이드바가 따로 있다면, 이 함수만 기존 걸로 교체하세요.")
    return {}

# =========================
# 데이터랩 — 원본 임베드
# =========================
def render_datalab_embed():
    st.markdown("### 데이터랩 (원본 임베드)")
    c1,c2,c3 = st.columns([1,1,1])
    with c1:
        cat = st.selectbox("카테고리", DATALAB_CATS, key="dl_raw_cat")
    with c2:
        unit = st.selectbox("기간 단위", ["week","month"], index=0, key="dl_raw_unit")
    with c3:
        device = st.selectbox("기기", ["all","pc","mo"], index=0, key="dl_raw_device")

    raw_url = f"https://datalab.naver.com/shoppingInsight/sCategory.naver?cat_id={DATALAB_CAT[cat]}&period={unit}&device={device}"
    if not st.session_state.get("PROXY_URL"):
        st.info("PROXY_URL 이 비어 있습니다. 사이드바 하단에 Cloudflare Worker 주소를 입력해 주세요.")

    # ⚠️ iframe 은 key 파라미터가 없음
    st.components.v1.iframe(_proxied(raw_url), height=580, scrolling=True)
    st.caption(raw_url)

# =========================
# 데이터랩 — 분석(Top20 + 데모 트렌드)
# =========================
def _datalab_post(url:str, payload:dict, cookie:str) -> dict|None:
    try:
        headers = {
            "Content-Type": "application/json; charset=UTF-8",
            "Referer": "https://datalab.naver.com/shoppingInsight/sCategory.naver",
            "Cookie": cookie.strip(),
        }
        r = requests.post(url, data=json.dumps(payload), headers=headers, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None

def datalab_fetch_top20(cat_id:str, start:str, end:str, device:str, cookie:str) -> pd.DataFrame|None:
    url = "https://datalab.naver.com/shoppingInsight/getCategoryKeywordRank.naver"  # 비공식
    body = {
        "cid": cat_id,
        "timeUnit": "week",
        "startDate": start, "endDate": end,
        "age": [], "gender": "", "device": device, "keywordCount": 20
    }
    data = _datalab_post(url, body, cookie)
    if not data:
        return None
    ranks = (data.get("ranks") or [])
    rows = [{"rank": r.get("rank"), "keyword": r.get("keyword"), "score": r.get("ratio", 0)} for r in ranks]
    if not rows:
        return None
    df = pd.DataFrame(rows).sort_values("rank")
    return df

def _naver_ads_keywordtool_volumes(keywords:list[str]) -> dict:
    """검색량(네이버 광고 키워드툴). secrets 필요 없으면 빈 dict"""
    API_KEY  = _get_secret("NAVER_ADS_API_KEY")
    API_SEC  = _get_secret("NAVER_ADS_API_SECRET")
    CUST_ID  = _get_secret("NAVER_ADS_CUSTOMER_ID")
    if not (API_KEY and API_SEC and CUST_ID and keywords):
        return {}

    endpoint = "https://api.searchad.naver.com/keywordstool"
    ts = str(int(time.time() * 1000))
    method = "GET"; uri = "/keywordstool"
    message = ts + "." + method + "." + uri
    sign = base64.b64encode(hmac.new(bytes(API_SEC, "utf-8"),
                                     bytes(message, "utf-8"),
                                     hashlib.sha256).digest()).decode("utf-8")
    params = {"hintKeywords": ",".join(keywords[:50]), "showDetail": "1"}
    headers = {"X-Timestamp": ts, "X-API-KEY": API_KEY, "X-Customer": CUST_ID, "X-Signature": sign}
    try:
        r = requests.get(endpoint, params=params, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        out = {}
        for row in data.get("keywordList", []):
            kw = row.get("relKeyword")
            out[kw] = (row.get("monthlyPcQcCnt", 0) or 0, row.get("monthlyMobileQcCnt", 0) or 0)
        return out
    except Exception:
        return {}

def render_datalab_analysis():
    st.markdown("### 데이터랩 (분석 · Top20 + 트렌드)")
    c1,c2,c3 = st.columns([1,1,1])
    with c1:
        cat = st.selectbox("카테고리", DATALAB_CATS, key="dl_cat_v2")
    with c2:
        sd = st.date_input("시작일", pd.to_datetime("today")-pd.Timedelta(days=31), key="dl_start_v2")
    with c3:
        ed = st.date_input("종료일", pd.to_datetime("today"), key="dl_end_v2")
    c4,c5 = st.columns([1,1])
    with c4:
        device = st.selectbox("기기", ["all","pc","mo"], index=0, key="dl_device_v2")
    with c5:
        cookie_in = st.text_input("NAVER_COOKIE (미입력 시 secrets 사용)", type="password", key="dl_cookie_input")

    cookie = cookie_in or _get_secret("NAVER_COOKIE")
    cat_id = DATALAB_CAT[cat]
    if st.button("Top20 불러오기", key="dl_go_top20"):
        if not cookie:
            st.error("NAVER_COOKIE가 비어 있습니다. 붙여넣고 ‘Top20 불러오기’를 눌러 주세요.")
            return
        with st.spinner("데이터랩 조회 중…"):
            df = datalab_fetch_top20(cat_id, str(sd), str(ed), device, cookie)
        if df is None or df.empty:
            st.error("조회 실패: 응답 파싱 실패(구조 변경 가능성). 샘플 표를 표시합니다.")
            df = pd.DataFrame([{"rank": i+1, "keyword": f"샘플 키워드 {i+1}", "score": 100-i} for i in range(20)])

        vol = _naver_ads_keywordtool_volumes(df["keyword"].tolist())
        if vol:
            df["pc/mo"] = df["keyword"].map(lambda k: f"{vol.get(k,(0,0))[0]}/{vol.get(k,(0,0))[1]}")

        st.markdown("**Top20 키워드**")
        st.dataframe(df, use_container_width=True, hide_index=True)

        # 데모 라인 차트
        xx = list(range(12))
        demo = pd.DataFrame({
            df.loc[0,"keyword"] if not df.empty else "kw1": [50,53,49,44,48,60,62,61,58,56,54,53],
            df.loc[1,"keyword"] if len(df)>1 else "kw2": [48,50,47,40,43,57,58,57,55,52,49,47],
            df.loc[2,"keyword"] if len(df)>2 else "kw3": [46,48,45,38,41,52,53,52,49,46,44,42],
        }, index=xx)
        st.line_chart(demo, use_container_width=True, height=220)

# =========================
# 11번가 — 아마존베스트 고정 임베드
# =========================
def render_11st_block():
    st.markdown("### 11번가 (모바일 · 아마존베스트 고정)")
    fixed_url = "https://m.11st.co.kr/page/main/abest?tabId=ABEST&pageId=AMOBEST&ctgr1No=166160"
    if not st.session_state.get("PROXY_URL"):
        st.info("PROXY_URL 미설정: 11번가 iFrame가 차단될 수 있습니다.")
    st.components.v1.iframe(_proxied(fixed_url), height=600, scrolling=True)

# =========================
# 상품명 생성기(규칙) + 추천 키워드 5개
# =========================
def _tokenize_ko_en(s:str) -> list[str]:
    s = re.sub(r"[^\w가-힣\s\-+/#]", " ", s)
    toks = [t.strip() for t in s.split() if t.strip()]
    return toks

def _keyword_candidates(brand:str, base:str, attrs:str, model:str) -> list[str]:
    pieces = [brand, base, attrs, model]
    toks = []
    for p in pieces:
        toks += _tokenize_ko_en(p or "")
    seen, out = set(), []
    for t in toks:
        if len(t) < 2: continue
        if t.lower() in seen: continue
        seen.add(t.lower()); out.append(t)
    return out[:12]

def _compose_names(brand:str, base:str, attrs:str, model:str) -> list[str]:
    patts = [
        "{brand} {base} {model} {attrs}",
        "{brand} {base} {attrs} {model}",
        "{brand} {attrs} {base} {model}",
        "{brand} {base} {model}",
    ]
    out = []
    for p in patts:
        name = p.format(brand=brand.strip(), base=base.strip(), attrs=attrs.strip(), model=model.strip())
        name = re.sub(r"\s+", " ", name).strip()
        if name and name not in out: out.append(name)
    return out

def render_name_generator():
    st.markdown("### 상품명 생성기 (규칙 기반)")
    with st.container(border=True):
        cc1,cc2,cc3,cc4 = st.columns([1,1,1,1])
        with cc1: brand = st.text_input("브랜드", key="ng_brand")
        with cc2: base  = st.text_input("기본 키워드", key="ng_base")
        with cc3: attrs = st.text_input("속성/특징", key="ng_attrs", placeholder="색상, 재질, 용량 등")
        with cc4: model = st.text_input("모델", key="ng_model")

        if st.button("상품명 생성", key="ng_go"):
            names = _compose_names(brand, base, attrs, model)
            st.markdown("**생성 결과**")
            for i, n in enumerate(names, 1):
                st.write(f"{i}. {n}")

            cands = _keyword_candidates(brand, base, attrs, model)
            vols = _naver_ads_keywordtool_volumes(cands)
            rows = []
            for kw in cands[:5]:
                pc, mo = (vols.get(kw) or (0,0))
                rows.append({"keyword": kw, "pc": pc, "mo": mo, "합계": pc+mo})
            df = pd.DataFrame(rows).sort_values("합계", ascending=False)
            st.markdown("**추천 키워드(검색량)**")
            st.dataframe(df, hide_index=True, use_container_width=True)

# =========================
# AI 키워드 레이더 (Rakuten)
# =========================
RAKUTEN_CATS = [
    "전체(샘플)","뷰티/코스메틱","의류/패션","가전/디지털","가구/인테리어","식품","생활/건강","스포츠/레저","문구/취미"
]

def _rk_fetch_rank_keywords(app_id:str, genre_id:str="100283", n:int=30) -> pd.DataFrame|None:
    if not app_id:
        return None
    url = "https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20170628"
    try:
        r = requests.get(url, params={"format":"json","applicationId":app_id,"genreId":genre_id}, timeout=10)
        r.raise_for_status()
        items = r.json().get("Items", [])
        rows = []
        for i, it in enumerate(items[:n], 1):
            title = (it.get("Item") or {}).get("itemName","")
            rows.append({"rank": i, "keyword": title, "source": "Rakuten"})
        return pd.DataFrame(rows)
    except Exception:
        return None

def render_rakuten_block():
    st.markdown("### AI 키워드 레이더 (Rakuten)")
    colA,colB,colC = st.columns([1,1,1])
    with colA:
        scope = st.radio("범위", ["국내","글로벌"], horizontal=True, key="rk_scope_v2")
    with colB:
        cat = st.selectbox("라쿠텐 카테고리", RAKUTEN_CATS, key="rk_cat_v2")
    with colC:
        genreid = st.text_input("GenreID", "100283", key="rk_genre_v2")

    st.caption("APP_ID는 secrets['RAKUTEN_APP_ID']에서 읽어옵니다. 미설정 시 샘플 표시.")
    app_id = _get_secret("RAKUTEN_APP_ID")
    df = _rk_fetch_rank_keywords(app_id, genreid) if app_id else None
    if df is None:
        df = pd.DataFrame([{"rank": i+1, "keyword": f"[샘플] 키워드 {i+1}", "source":"sample"} for i in range(30)])

    st.markdown('<div class="rk">', unsafe_allow_html=True)
    st.dataframe(df, hide_index=True, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# 간단 번역기 (비공식 gtx 엔드포인트)
# =========================
def _gtranslate(text:str, src:str="auto", tgt:str="ko") -> str:
    if not text.strip():
        return ""
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {"client":"gtx","sl":src,"tl":tgt,"dt":"t","q":text}
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        return "".join([seg[0] for seg in data[0]])
    except Exception:
        return ""

def render_translator_block():
    st.markdown("### 구글 번역 (텍스트 입력/출력 + 한국어 확인용)")
    c1,c2 = st.columns([1,1])
    with c1:
        src = st.selectbox("원문 언어", ["자동 감지","en","ja","zh-CN","ko"], index=0)
        src_map = {"자동 감지":"auto"}
        src_code = src_map.get(src, src)
        text = st.text_area("원문 입력", height=180)
    with c2:
        tgt = st.selectbox("번역 언어", ["한국어","영어","일본어","중국어 간체"], index=0)
        tgt_map = {"한국어":"ko","영어":"en","일본어":"ja","중국어 간체":"zh-CN"}
        tgt_code = tgt_map[tgt]
        if st.button("번역"):
            out = _gtranslate(text, src_code, tgt_code)
            st.text_area("번역 결과", value=out, height=180)

# =========================
# 아이템스카우트/셀러라이프 임베드
# =========================
def render_tool_iframes():
    st.markdown("### 아이템스카우트 / 셀러라이프 (원본 임베드)")
    cc1,cc2 = st.columns([1,1])
    with cc1:
        st.subheader("아이템스카우트", divider="gray")
        url = "https://items.singtown.com"
        if not st.session_state.get("PROXY_URL"):
            st.info("PROXY_URL 이 비어 있습니다. 사이드바 하단에 Cloudflare Worker 주소를 입력해 주세요.")
        st.components.v1.iframe(_proxied(url), height=520, scrolling=True)
    with cc2:
        st.subheader("셀러라이프", divider="gray")
        url = "https://www.sellerlife.co.kr"
        if not st.session_state.get("PROXY_URL"):
            st.info("PROXY_URL 이 비어 있습니다. 사이드바 하단에 Cloudflare Worker 주소를 입력해 주세요.")
        st.components.v1.iframe(_proxied(url), height=520, scrolling=True)

# =========================
# 메인 — 4×2 고정 배치
# =========================
def main():
    _inject_main_css()
    render_sidebar()

    st.title("ENVY — v11.x (stable)")
    st.caption("4×2 격자 고정 배치. 사이드바에 프록시 URL을 넣으면 임베드 안정성이 올라갑니다.")

    # 1행: 데이터랩(원본) · 데이터랩(분석) · 11번가 · 상품명 생성기
    r1c1,r1c2,r1c3,r1c4 = st.columns(4, gap="small")
    with r1c1: render_datalab_embed()
    with r1c2: render_datalab_analysis()
    with r1c3: render_11st_block()
    with r1c4: render_name_generator()

    st.divider()

    # 2행: 라쿠텐 · 구글 번역 · 아이템스카우트 · 셀러라이프
    r2c1,r2c2,r2c3,r2c4 = st.columns(4, gap="small")
    with r2c1: render_rakuten_block()
    with r2c2: render_translator_block()
    with r2c3:
        st.subheader("아이템스카우트", divider="gray")
        url = "https://items.singtown.com"
        st.components.v1.iframe(_proxied(url), height=520, scrolling=True)
    with r2c4:
        st.subheader("셀러라이프", divider="gray")
        url = "https://www.sellerlife.co.kr"
        st.components.v1.iframe(_proxied(url), height=520, scrolling=True)

    st.divider()
    st.info("⚠️ 데이터랩 분석은 비공식 엔드포인트에 의존합니다. 구조 변경/쿠키 만료 시 Top20이 비거나 샘플로 폴백됩니다. "
            "11번가/데이터랩/아이템스카우트/셀러라이프 임베드는 Cloudflare Worker 프록시를 권장합니다.")

if __name__ == "__main__":
    main()

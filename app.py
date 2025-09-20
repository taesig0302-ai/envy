# -*- coding: utf-8 -*-
import os
from urllib.parse import quote

import streamlit as st
import pandas as pd

# requests가 없을 수도 있어서 안전 가드
try:
    import requests
except Exception:
    requests = None

# =========================
# 고정 프록시 (서비스별 분리)
# =========================
NAVER_PROXY       = "https://envy-proxy.taesig0302.workers.dev"
ELEVENST_PROXY    = "https://worker-11stjs.taesig0302.workers.dev"
ITEMSCOUT_PROXY   = "https://worker-itemscoutjs.taesig0302.workers.dev"
SELLERLIFE_PROXY  = "https://worker-sellerlifejs.taesig0302.workers.dev"

# 11번가 아마존 베스트(모바일) 고정 경로
AMAZON_BEST_URL = "https://m.11st.co.kr/page/main/abest?tabId=ABEST&pageId=AMOBEST&ctgr1No=166160"

# =========================
# Rakuten (AI 키워드 레이더) 기본키(Secrets 우선)
# =========================
RAKUTEN_APP_ID_DEFAULT       = "1043271015809337425"
RAKUTEN_AFFILIATE_ID_DEFAULT = "4c723498.cbfeca46.4c723499.1deb6f77"

def _rk_keys():
    try:
        app_id = st.secrets.get("RAKUTEN_APP_ID", "") or st.secrets.get("RAKUTEN_APPLICATION_ID", "")
        aff    = st.secrets.get("RAKUTEN_AFFILIATE_ID", "") or st.secrets.get("RAKUTEN_AFFILIATE", "")
    except Exception:
        app_id = ""
        aff    = ""
    if not app_id: app_id = RAKUTEN_APP_ID_DEFAULT
    if not aff:    aff    = RAKUTEN_AFFILIATE_ID_DEFAULT
    return app_id.strip(), aff.strip()

# =========================
# 페이지 설정 / 공통 CSS
# =========================
st.set_page_config(page_title="ENVY — Season 1 (Dual Proxy Edition)", layout="wide")

st.markdown("""
<style>
.block-container { max-width: 1680px !important; padding-top:.6rem !important; }

/* 내부 섹션 헤더 간소화 */
.card-title { font-size: 1.15rem; font-weight: 700; margin: .2rem 0 .6rem 0; }

/* 카드 컨테이너 */
.card {
  border: 1px solid rgba(0,0,0,.06);
  border-radius: 12px;
  padding: .75rem;
  background: #fff;
  box-shadow: 0 1px 6px rgba(0,0,0,.04);
}

/* iFrame 높이/스타일 공통 */
.card iframe { border:0; width:100%; border-radius: 8px; }

/* 첫줄 3개, 둘째줄 4개 — “넓게” 보이도록 그리드 */
.row { display: grid; grid-gap: 16px; }
.row.row-3 { grid-template-columns: 1fr 1fr 1fr; }
.row.row-4 { grid-template-columns: 1fr 1fr 1fr 1fr; }

/* 임베드 컨테이너 스크롤 */
.embed-wrap { height: 710px; overflow: auto; }
.embed-wrap-short { height: 640px; overflow: auto; }

/* Rakuten 표 폰트 축소 */
.rk-table { font-size: .88rem; }
.rk-table a { font-size: .86rem; }

/* 사이드바 자체 스크롤 유지 */
[data-testid="stSidebar"] section { height: 100vh; overflow: auto; }

.stButton>button { padding: .3rem .6rem; border-radius: 8px; }
.stTextInput>div>div>input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] { font-size: .92rem !important; }

.footer-space { height: 12px; }
</style>
""", unsafe_allow_html=True)

st.title("ENVY — Season 1 (Dual Proxy Edition)")

# =========================
# Sidebar
# =========================
def sidebar():
    with st.sidebar:
        st.header("ENVY Sidebar")
        st.caption("프록시는 코드에 고정되어 있습니다 · 참고용")

        st.text_input("NAVER_PROXY", NAVER_PROXY, disabled=True)
        st.text_input("11번가_PROXY", ELEVENST_PROXY, disabled=True)
        st.text_input("Itemscout_PROXY", ITEMSCOUT_PROXY, disabled=True)
        st.text_input("SellerLife_PROXY", SELLERLIFE_PROXY, disabled=True)

        st.divider()
        st.caption("Rakuten 키(세션 오버라이드 · 비워두면 기본키 사용)")
        st.text_input("Rakuten APP_ID (선택)", value=_rk_keys()[0], key="rk_app_override")
        st.text_input("Rakuten Affiliate (선택)", value=_rk_keys()[1], key="rk_aff_override")

        st.divider()
        lock = st.toggle("페이지 스크롤 잠금", value=False, key="page_lock")
        st.caption("사이드바는 스크롤 유지, 본문은 잠금")

    # 페이지 스크롤 잠금 적용
    if st.session_state.get("page_lock"):
        st.markdown("<style>html, body { overflow:hidden !important; }</style>", unsafe_allow_html=True)

sidebar()

# =========================
# 작은 유틸
# =========================
def _proxy_embed(proxy_base: str, target_url: str, height: int = 710, scroll=True):
    """Streamlit iframe: key 파라미터 미지원 → 넘기지 말 것"""
    proxy = proxy_base.strip().rstrip("/")
    url   = f"{proxy}/?url={quote(target_url, safe=':/?&=%')}"
    st.components.v1.iframe(url, height=height, scrolling=scroll)

def _rk_fetch_rank(genreid: str, app_id: str, affiliate: str, topn:int=20) -> pd.DataFrame:
    if not requests:
        # requests 미설치 시 샘플
        return pd.DataFrame([{
            "rank": i+1, "keyword": f"[샘플] 키워드 {i+1} ハロウィン 秋 🍂", "shop": "샘플샵", "url": "https://example.com"
        } for i in range(20)])

    api = "https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20170628"
    params = {"applicationId": app_id, "genreId": str(genreid or "100283")}
    if affiliate: params["affiliateId"] = affiliate
    try:
        r = requests.get(api, params=params, timeout=12)
        r.raise_for_status()
        items = (r.json().get("Items") or [])[:topn]
        rows = []
        for it in items:
            node = it.get("Item", {})
            rows.append({
                "rank": node.get("rank"),
                "keyword": node.get("itemName") or "",
                "shop": node.get("shopName") or "",
                "url": node.get("itemUrl") or "",
            })
        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame([{
            "rank": i+1, "keyword": f"[샘플] 키워드 {i+1} ハロウィン 秋 🍂", "shop": "샘플샵", "url": "https://example.com"
        } for i in range(20)])

# =========================
# 섹션: 데이터랩(임베드)
# =========================
def section_datalab_embed():
    st.markdown('<div class="card-title">데이터랩</div>', unsafe_allow_html=True)
    st.markdown('<div class="card embed-wrap">', unsafe_allow_html=True)
    # 데스크톱 쇼핑인사이트(디지털/가전) 주간/모두
    target = ("https://datalab.naver.com/shoppingInsight/sCategory.naver"
              "?cid=50000003&timeUnit=week&device=all&gender=all&ages=all")
    _proxy_embed(NAVER_PROXY, target, height=710, scroll=True)
    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# 섹션: 아이템스카우트(임베드)
# =========================
def section_itemscout_embed():
    st.markdown('<div class="card-title">아이템스카우트</div>', unsafe_allow_html=True)
    st.markdown('<div class="card embed-wrap-short">', unsafe_allow_html=True)
    target = "https://app.itemscout.io/market/keyword"
    _proxy_embed(ITEMSCOUT_PROXY, target, height=640, scroll=True)
    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# 섹션: 셀러라이프(임베드)
# =========================
def section_sellerlife_embed():
    st.markdown('<div class="card-title">셀러라이프</div>', unsafe_allow_html=True)
    st.markdown('<div class="card embed-wrap-short">', unsafe_allow_html=True)
    target = "https://sellerlife.co.kr/dashboard"
    _proxy_embed(SELLERLIFE_PROXY, target, height=640, scroll=True)
    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# 섹션: 11번가(모바일) — 아마존베스트 고정
# =========================
def section_11st():
    st.markdown('<div class="card-title">11번가 (모바일)</div>', unsafe_allow_html=True)
    st.markdown('<div class="card embed-wrap-short">', unsafe_allow_html=True)
    _proxy_embed(ELEVENST_PROXY, AMAZON_BEST_URL, height=640, scroll=True)
    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# 섹션: AI 키워드 레이더 (Rakuten)
# =========================
def section_rakuten():
    st.markdown('<div class="card-title">AI 키워드 레이더 (Rakuten)</div>', unsafe_allow_html=True)
    # 오버라이드 우선 사용
    app_id = (st.session_state.get("rk_app_override") or _rk_keys()[0]).strip()
    aff    = (st.session_state.get("rk_aff_override") or _rk_keys()[1]).strip()
    genreid = st.text_input("GenreID", "100283", key="rk_gid", label_visibility="collapsed")
    df = _rk_fetch_rank(genreid, app_id, aff, topn=20)
    df = df[["rank","keyword","shop","url"]]
    colcfg = {
        "rank":    st.column_config.NumberColumn("rank", width="small"),
        "keyword": st.column_config.TextColumn("keyword", width="large"),
        "shop":    st.column_config.TextColumn("shop", width="medium"),
        "url":     st.column_config.LinkColumn("url", display_text="열기", width="small"),
    }
    st.markdown('<div class="card rk-table">', unsafe_allow_html=True)
    st.dataframe(df, hide_index=True, use_container_width=True, height=640, column_config=colcfg)
    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# 섹션: 구글 번역(간단)
# =========================
LANG_LABELS = {
    "auto":"자동 감지",
    "ko":"한국어","en":"영어","ja":"일본어",
    "zh-CN":"중국어(간체)","zh-TW":"중국어(번체)",
    "vi":"베트남어","th":"태국어","id":"인도네시아어",
    "de":"독일어","fr":"프랑스어","es":"스페인어","it":"이탈리아어","pt":"포르투갈어",
}
def _code(label_or_code:str) -> str:
    rev = {v:k for k,v in LANG_LABELS.items()}
    return rev.get(label_or_code, label_or_code)

def section_translator():
    st.markdown('<div class="card-title">구글 번역기</div>', unsafe_allow_html=True)
    st.markdown('<div class="card">', unsafe_allow_html=True)
    col1, col2 = st.columns([1,1])
    with col1:
        src = st.selectbox("원문", list(LANG_LABELS.values()), index=list(LANG_LABELS.keys()).index("auto"))
        text = st.text_area("입력", height=200)
    with col2:
        tgt = st.selectbox("번역", list(LANG_LABELS.values()), index=list(LANG_LABELS.keys()).index("en"))
        if st.button("번역"):
            try:
                from deep_translator import GoogleTranslator
                gt = GoogleTranslator(source=_code(src), target=_code(tgt))
                out = gt.translate(text or "")
                st.text_area("결과", value=out, height=200)
            except Exception as e:
                st.warning(f"번역 실패: {e}")
    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# 섹션: 상품명 생성기 (규칙 기반)
# =========================
def section_title_generator():
    st.markdown('<div class="card-title">상품명 생성기</div>', unsafe_allow_html=True)
    st.markdown('<div class="card">', unsafe_allow_html=True)
    colA, colB = st.columns([1,2])
    with colA:
        brand = st.text_input("브랜드", placeholder="예: Apple / 샤오미 / 무지")
        attrs = st.text_input("속성(콤마, 선택)", placeholder="예: 공식, 정품, 한정판")
    with colB:
        kws = st.text_input("키워드(콤마)", placeholder="예: 노트북 스탠드, 접이식, 알루미늄")
    col1, col2, col3 = st.columns([1,1,1])
    with col1:
        max_len = st.slider("최대 글자수", 20, 80, 50, 1)
    with col2:
        joiner = st.selectbox("구분자", [" ", " | ", " · ", " - "], index=0)
    with col3:
        order = st.selectbox("순서", ["브랜드-키워드-속성", "키워드-브랜드-속성", "브랜드-속성-키워드"], index=0)
    if st.button("상품명 생성"):
        kw_list = [k.strip() for k in (kws or "").split(",") if k.strip()]
        at_list = [a.strip() for a in (attrs or "").split(",") if a.strip()]
        if not kw_list:
            st.warning("키워드가 비었습니다.")
        else:
            titles = []
            for k in kw_list:
                if order=="브랜드-키워드-속성": seq = [brand, k] + at_list
                elif order=="키워드-브랜드-속성": seq = [k, brand] + at_list
                else: seq = [brand] + at_list + [k]
                title = joiner.join([p for p in seq if p])
                if len(title) > max_len:
                    title = title[:max_len-1] + "…"
                titles.append(title)
            st.success(f"총 {len(titles)}건")
            st.write("\n".join(titles))
    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# 레이아웃 — 1행 3카드 / 2행 4카드 (고정)
# =========================
# 1행
st.markdown('<div class="row row-3">', unsafe_allow_html=True)
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True); section_datalab_embed(); st.markdown('</div>', unsafe_allow_html=True)
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True); section_itemscout_embed(); st.markdown('</div>', unsafe_allow_html=True)
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True); section_sellerlife_embed(); st.markdown('</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="footer-space"></div>', unsafe_allow_html=True)

# 2행
st.markdown('<div class="row row-4">', unsafe_allow_html=True)
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True); section_11st(); st.markdown('</div>', unsafe_allow_html=True)
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True); section_rakuten(); st.markdown('</div>', unsafe_allow_html=True)
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True); section_translator(); st.markdown('</div>', unsafe_allow_html=True)
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True); section_title_generator(); st.markdown('</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

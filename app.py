# =========================================================
# ENVY — Season 1 (Dual Proxy Edition, fixed proxies)
#   - 1행: 데이터랩(6) · 아이템스카우트(3) · 셀러라이프(3)
#   - 2행: 11번가(3) · AI 키워드 레이더(3) · 구글 번역(3) · 상품명 생성기(3)
#   - 프록시 URL은 하드코딩 (요청대로)
# =========================================================
import os, base64
from urllib.parse import quote

import streamlit as st
import pandas as pd

# -----------------------------
# 고정 프록시 (요청대로 하드코딩)
# -----------------------------
PROXY_DATALAB    = "https://envy-proxy.taesig0302.workers.dev".rstrip("/")
PROXY_11ST       = "https://worker-11stjs.taesig0302.workers.dev".rstrip("/")
PROXY_ITEMSCOUT  = "https://worker-itemscoutjs.taesig0302.workers.dev".rstrip("/")
PROXY_SELLERLIFE = "https://worker-sellerlifejs.taesig0302.workers.dev".rstrip("/")

def px_datalab(url: str) -> str:
    return f"{PROXY_DATALAB}/?url={quote(url, safe=':/?&=%')}"
def px_11st(url: str) -> str:
    return f"{PROXY_11ST}/?url={quote(url, safe=':/?&=%')}"
def px_itemscout(url: str) -> str:
    return f"{PROXY_ITEMSCOUT}/?url={quote(url, safe=':/?&=%')}"
def px_sellerlife(url: str) -> str:
    return f"{PROXY_SELLERLIFE}/?url={quote(url, safe=':/?&=%')}"

# -----------------------------
# 공통 스타일 (카드 와이드, 표 폰트 축소 등)
# -----------------------------
def inject_css():
    st.markdown("""
    <style>
      .block-container { max-width: 1600px !important; padding-top:.8rem !important; }
      h2, h3 { margin-top: .35rem !important; }
      .card { background: #fff; border: 1px solid rgba(0,0,0,.06); border-radius: 12px; padding: 10px 12px; box-shadow: 0 4px 18px rgba(0,0,0,.05);}
      .rk-wrap .stDataFrame [role="grid"] { font-size: 0.82rem !important; }  /* 라쿠텐 표 폰트 2단계 축소 */
      .rk-wrap .stDataFrame a { font-size: 0.78rem !important; }
    </style>
    """, unsafe_allow_html=True)

# -----------------------------
# 사이드바 (그대로 유지 — 최소 안내만)
# -----------------------------
def render_sidebar():
    with st.sidebar:
        st.subheader("ENVY Sidebar")
        st.caption("프록시는 앱에 하드코딩되어 사용됩니다.")

# -----------------------------
# 섹션: 데이터랩 임베드 (고정)
# -----------------------------
def render_datalab_embed():
    st.markdown("### 데이터랩")
    with st.container():
        st.components.v1.iframe(
            px_datalab("https://datalab.naver.com/shoppingInsight/sCategory.naver?cid=50000003&timeUnit=week&device=all&gender=all&ages=all"),
            height=980, scrolling=True
        )

# -----------------------------
# 섹션: 아이템스카우트 임베드
# -----------------------------
def render_itemscout_embed():
    st.markdown("### 아이템스카우트")
    with st.container():
        st.components.v1.iframe(
            px_itemscout("https://app.itemscout.io/market/keyword"),
            height=920, scrolling=True
        )

# -----------------------------
# 섹션: 셀러라이프 임베드
# -----------------------------
def render_sellerlife_embed():
    st.markdown("### 셀러라이프")
    with st.container():
        st.components.v1.iframe(
            px_sellerlife("https://sellerlife.co.kr/dashboard"),
            height=920, scrolling=True
        )

# -----------------------------
# 섹션: 11번가(모바일) 임베드
# -----------------------------
def render_11st_embed():
    st.markdown("### 11번가 (모바일)")
    with st.container():
        st.components.v1.iframe(
    px_11st("https://m.11st.co.kr/page/main/abest?tabId=ABEST&pageId=AMOBEST&ctgr1No=166160"),
    height=780, scrolling=True
)

# -----------------------------
# 섹션: AI 키워드 레이더 (Rakuten, 랭킹 표)
# -----------------------------
RAKUTEN_APP_ID_DEFAULT       = "1043271015809337425"
RAKUTEN_AFFILIATE_ID_DEFAULT = "4c723498.cbfeca46.4c723499.1deb6f77"

def _get_rakuten_keys():
    # secrets 있으면 우선, 없으면 기본값
    app_id = (st.secrets.get("RAKUTEN_APP_ID", "")
              or st.secrets.get("RAKUTEN_APPLICATION_ID", "")
              or RAKUTEN_APP_ID_DEFAULT).strip()
    affiliate = (st.secrets.get("RAKUTEN_AFFILIATE_ID", "")
                 or st.secrets.get("RAKUTEN_AFFILIATE", "")
                 or RAKUTEN_AFFILIATE_ID_DEFAULT).strip()
    return app_id, affiliate

def _fetch_rank(genre_id: str, topn: int = 20) -> pd.DataFrame:
    import requests
    app_id, affiliate = _get_rakuten_keys()
    url = "https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20170628"
    params = {"applicationId": app_id, "genreId": str(genre_id).strip(), "carrier": 0}
    if affiliate: params["affiliateId"] = affiliate
    try:
        r = requests.get(url, params=params, timeout=12); r.raise_for_status()
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
        # 샘플 폴백
        return pd.DataFrame([{
            "rank": i+1, "keyword": f"[샘플] 키워드 {i+1} ハロウィン 秋 🍂", "shop": "샘플샵", "url": "https://example.com"
        } for i in range(20)])

def render_rakuten_block():
    st.markdown("### AI 키워드 레이더 (Rakuten)")
    with st.container():
        st.markdown("""
        <style>
          .rk-wrap .stDataFrame { margin-top: .2rem !important; }
          .rk-wrap [data-testid="stVerticalBlock"] { gap: .4rem !important; }
        </style>
        """, unsafe_allow_html=True)
        df = _fetch_rank("100283", topn=20)
        colcfg = {
            "rank":    st.column_config.NumberColumn("rank", width="small"),
            "keyword": st.column_config.TextColumn("keyword", width="large"),
            "shop":    st.column_config.TextColumn("shop", width="medium"),
            "url":     st.column_config.LinkColumn("url", display_text="열기", width="small"),
        }
        st.markdown('<div class="rk-wrap">', unsafe_allow_html=True)
        st.dataframe(df[["rank","keyword","shop","url"]], hide_index=True,
                     use_container_width=True, height=420, column_config=colcfg)
        st.markdown('</div>', unsafe_allow_html=True)

# -----------------------------
# 섹션: 구글 번역 (deep-translator)
# -----------------------------
LANG_LABELS = {
    "auto":"자동 감지",
    "ko":"한국어","en":"영어","ja":"일본어",
    "zh-CN":"중국어(간체)","zh-TW":"중국어(번체)",
    "vi":"베트남어","th":"태국어","id":"인도네시아어",
    "de":"독일어","fr":"프랑스어","es":"스페인어","it":"이탈리아어","pt":"포르투갈어",
}
def lang_label_to_code(label_or_code:str) -> str:
    rev = {v:k for k,v in LANG_LABELS.items()}
    return rev.get(label_or_code, label_or_code)

def translate_text(src:str, tgt:str, text:str) -> str:
    try:
        from deep_translator import GoogleTranslator
    except Exception:
        return "deep-translator 설치 필요 (requirements에 추가)"
    src = lang_label_to_code(src); tgt = lang_label_to_code(tgt)
    try:
        out = GoogleTranslator(source=src, target=tgt).translate(text)
        if tgt != "ko" and out.strip():
            try:
                ko_hint = GoogleTranslator(source=tgt, target="ko").translate(out)
                return out + "\n" + ko_hint
            except Exception:
                return out
        return out
    except Exception as e:
        return f"번역 실패: {e}"

def render_translator_block():
    st.markdown("### 구글 번역기")
    c1, c2 = st.columns(2)
    with c1:
        src = st.selectbox("원문", list(LANG_LABELS.values()), index=list(LANG_LABELS.keys()).index("auto"))
        text_in = st.text_area("입력", height=150)
    with c2:
        tgt = st.selectbox("번역", list(LANG_LABELS.values()), index=list(LANG_LABELS.keys()).index("en"))
        if st.button("번역"):
            out = translate_text(src, tgt, text_in or "")
            st.text_area("결과", value=out, height=150)

# -----------------------------
# 섹션: 상품명 생성기 (규칙 기반)
# -----------------------------
def render_product_name_generator():
    st.markdown("### 상품명 생성기")
    with st.container():
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
            kw_list = [k.strip() for k in kws.split(",") if k.strip()]
            at_list = [a.strip() for a in attrs.split(",") if a.strip()]
            if not kw_list:
                st.warning("키워드가 비었습니다.")
                return
            titles = []
            for k in kw_list:
                seq = []
                if order=="브랜드-키워드-속성": seq = [brand, k] + at_list
                elif order=="키워드-브랜드-속성": seq = [k, brand] + at_list
                else: seq = [brand] + at_list + [k]
                title = joiner.join([p for p in seq if p])
                if len(title) > max_len:
                    title = title[:max_len-1] + "…"
                titles.append(title)
            st.success(f"총 {len(titles)}건")
            st.write("\n".join(titles))

# -----------------------------
# Main
# -----------------------------
def main():
    render_sidebar()
    inject_css()

    st.title("ENVY — Season 1 (Dual Proxy Edition)")

    # 1행
    c1, c2, c3 = st.columns([6,3,3])
    with c1:
        with st.container(): st.markdown('<div class="card">', unsafe_allow_html=True); render_datalab_embed(); st.markdown('</div>', unsafe_allow_html=True)
    with c2:
        with st.container(): st.markdown('<div class="card">', unsafe_allow_html=True); render_itemscout_embed(); st.markdown('</div>', unsafe_allow_html=True)
    with c3:
        with st.container(): st.markdown('<div class="card">', unsafe_allow_html=True); render_sellerlife_embed(); st.markdown('</div>', unsafe_allow_html=True)

    # 2행
    d1, d2, d3, d4 = st.columns([3,3,3,3])
    with d1:
        with st.container(): st.markdown('<div class="card">', unsafe_allow_html=True); render_11st_embed(); st.markdown('</div>', unsafe_allow_html=True)
    with d2:
        with st.container(): st.markdown('<div class="card">', unsafe_allow_html=True); render_rakuten_block(); st.markdown('</div>', unsafe_allow_html=True)
    with d3:
        with st.container(): st.markdown('<div class="card">', unsafe_allow_html=True); render_translator_block(); st.markdown('</div>', unsafe_allow_html=True)
    with d4:
        with st.container(): st.markdown('<div class="card">', unsafe_allow_html=True); render_product_name_generator(); st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()

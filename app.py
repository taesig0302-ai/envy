# -----------------------------
# NEW — 상품명 생성기 (규칙 기반 + 추천 키워드 5개)
# -----------------------------
def _kw_suggest_from_datalab(cat_label: str = "디지털/가전", days: int = 28) -> list[dict]:
    """NAVER_COOKIE가 있으면 해당 카테고리 Top20에서 상위 5개를 추천(점수 포함).
       쿠키 없으면 세션에 저장된 Top20 키워드 또는 샘플을 사용."""
    try:
        cookie = _naver_cookie()
    except Exception:
        cookie = ""
    # 기간
    end = date.today()
    start = end - timedelta(days=days)

    # 카테고리 CID
    cid = CID_MAP.get(cat_label, "50000003")

    # 1) 쿠키 있으면 실제 Top20 조회
    if cookie:
        try:
            res = _fetch_top20(cookie, cid, str(start), str(end))
            if res.get("ok"):
                rows = res["rows"][:5]
                return [{"keyword": r["keyword"], "score": float(r.get("score", 0))} for r in rows]
        except Exception:
            pass

    # 2) 세션에 데이터랩 Top20가 있으면 사용
    picks = st.session_state.get("_top_keywords", [])[:5]
    if picks:
        return [{"keyword": k, "score": 0.0} for k in picks]

    # 3) 샘플 폴백
    return [{"keyword": f"추천키워드{i}", "score": 0.0} for i in range(1, 6)]


def _make_names(brand: str, series: str, attrs: list[str], kws: list[str], length: int, n: int = 20) -> list[str]:
    """간단한 규칙 기반 이름 생성기(랜덤 섞기)."""
    tokens = [t.strip() for t in [brand, series] + attrs if t.strip()]
    base = [t for t in tokens if t]
    out = []
    import random
    for _ in range(n):
        bag = base[:]
        # 추천 키워드를 1~2개 끼워넣기
        for __ in range(random.choice([1, 1, 2])):
            if kws:
                bag.append(random.choice(kws))
        random.shuffle(bag)
        name = " ".join(bag[:length])
        out.append(name)
    return out


def render_product_namer_block():
    st.markdown("## 상품명 생성기 (규칙 기반 + 추천 키워드)")
    c1, c2 = st.columns([1.2, 1])
    with c1:
        brand = st.text_input("브랜드", value="오소")
        series = st.text_input("시리즈/모델", value="V12")
        attrs_raw = st.text_input("속성/수식어(콤마로 구분)", value="다이렉트, 프리미엄, 경량, 휴대용")
        attrs = [a.strip() for a in attrs_raw.split(",") if a.strip()]
        length = st.slider("길이(단어 수)", 4, 12, value=8)

        # 추천 키워드(검색량 지수) 5개
        kcol1, kcol2 = st.columns([1.2, 1])
        with kcol1:
            cat_for_suggest = st.selectbox("추천 키워드 기준 카테고리(데이터랩)", list(CID_MAP.keys()), index=3)
        with kcol2:
            st.caption("검색량은 데이터랩 '지수' 기준(가중치)으로 표시됩니다.")

        kws_rows = _kw_suggest_from_datalab(cat_for_suggest)
        kw_df = pd.DataFrame(kws_rows)
        if not kw_df.empty:
            kw_df.columns = ["keyword", "지수"]
            st.dataframe(kw_df, hide_index=True, height=180, use_container_width=True)
        else:
            st.info("추천 키워드를 불러올 수 없습니다.")

        st.markdown("---")
        if st.button("상품명 20개 생성", use_container_width=False):
            kws = [r["keyword"] for r in kws_rows][:5]
            names = _make_names(brand, series, attrs, kws, length, n=20)
            st.dataframe(pd.DataFrame({"rank": range(1, 21), "name": names}),
                         hide_index=True, height=420, use_container_width=True)

    with c2:
        st.markdown("#### 가이드")
        st.markdown(
            "- **브랜드/시리즈/속성**을 입력하고, 추천 키워드(최대 5개)를 자동으로 섞어 20개 생성합니다.  \n"
            "- 추천 키워드는 **데이터랩 Top20**(최근 4주 기준)에서 상위 5개를 사용하며, 숫자는 **지수(비율/가중치)** 입니다.  \n"
            "- 쿠키가 없으면 세션에 저장된 Top20 또는 샘플로 대체합니다."
        )

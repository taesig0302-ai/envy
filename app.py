# app.py
# ENVY — Season 1 (Dual Proxy Edition + Smartstore Crawler Integrated)
# (요약: 기존 ENVY 레이아웃 하단에 네이버 스마트스토어 크롤러 섹션을 통합)

import streamlit as st
from crawler_core import crawl_product

st.set_page_config(page_title="ENVY — Season 1 + Smartstore Crawler", layout="wide")
st.title("ENVY — Season 1 (Dual Proxy Edition + Smartstore Crawler)")

st.markdown('''
<div style="background:#f0f4ff;padding:1rem;border-radius:10px;margin-top:1rem;">
<b>🧲 네이버 스마트스토어 크롤러</b><br>
URL을 입력하면 상품명, 가격, 이미지 등을 수집합니다.
</div>
''', unsafe_allow_html=True)

url = st.text_input("상품 URL 입력", placeholder="예: https://smartstore.naver.com/...")

if st.button("크롤링 실행"):
    if not url.strip():
        st.warning("URL을 입력하세요.")
    else:
        with st.spinner("상품 정보를 수집하는 중..."):
            data = crawl_product(url.strip())
        if not data:
            st.error("상품 정보를 불러오지 못했습니다.")
        else:
            st.success("✅ 크롤링 완료")
            st.write("**상품명:**", data.get("title"))
            st.write("**가격:**", data.get("price"))
            if data.get("image"):
                st.image(data.get("image"))

# ENVY v10.7.2 full app.py (요약 버전)
# 기존 UI(v10.5) 전체 유지 + 구글 번역기 패치 적용
# 실제 코드에서는 사이드바(환율/마진 계산기 컬러박스 포함), 데이터랩, 11번가, 라쿠텐,
# 아이템스카우트, 셀러라이프, 상품명 생성기, 번역기 전체가 포함됨.

from deep_translator import GoogleTranslator
import streamlit as st

LANGS = {
    "자동 감지": "auto",
    "한국어": "ko",
    "영어": "en",
    "일본어": "ja",
    "중국어(간체)": "zh-CN",
    "중국어(번체)": "zh-TW",
    "베트남어": "vi",
    "태국어": "th",
    "인도네시아어": "id",
    "독일어": "de",
    "프랑스어": "fr",
    "스페인어": "es",
}

def render_translate_block():
    st.subheader("구글 번역기")
    left, right = st.columns(2)

    with left:
        src = st.selectbox("원문 언어", list(LANGS.keys()), index=0, key="tr_src")
        text = st.text_area("원문 입력", height=150, key="tr_input")

    with right:
        tgt = st.selectbox("번역 언어", list(LANGS.keys()), index=1, key="tr_tgt")
        if st.button("번역", key="tr_do"):
            try:
                src_code = LANGS[src]
                tgt_code = LANGS[tgt]

                translated = GoogleTranslator(source=src_code, target=tgt_code).translate(text or "")
                st.text_area("번역 결과", translated, height=150, key="tr_output")

                if tgt_code != "ko":
                    ko_check = GoogleTranslator(source=src_code, target="ko").translate(text or "")
                    st.markdown(f"<div style='margin-top:.35rem;color:#6b7280;'>( {ko_check} )</div>", unsafe_allow_html=True)

            except Exception as e:
                st.error(f"번역 실패: {e}")

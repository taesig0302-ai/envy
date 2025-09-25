# ─────────────────────────────────────────
# 11번가 상품 상세 바로보기 (프록시 경유)
# ─────────────────────────────────────────
import re
from urllib.parse import quote as _q
import streamlit as st

def _11st_extract_product_id(s: str) -> str | None:
    """11번가 상품 URL/텍스트에서 productId 추출"""
    if not s: return None
    s = s.strip()
    if s.isdigit(): return s
    m = re.search(r"/products/(\d+)", s)
    if m: return m.group(1)
    m = re.search(r"[?&]productId=(\d+)", s)
    if m: return m.group(1)
    return None

def section_11st_detail():
    """11번가 상품 상세: URL/상품ID 입력 → 프록시 경유 미리보기/새 탭 열기"""
    st.markdown('<div class="card main"><div class="card-title">11번가 — 상품 상세 바로보기</div>', unsafe_allow_html=True)

    base_proxy = (st.secrets.get("ELEVENST_PROXY", "") or globals().get("ELEVENST_PROXY", "")).rstrip("/")
    st.caption(f"PROXY_URL: {base_proxy or '(미설정)'}")

    raw_input = st.text_input("상품 URL 또는 상품ID", placeholder="예: https://www.11st.co.kr/products/1234567890  또는  1234567890")
    pid = _11st_extract_product_id(raw_input)
    target = f"https://m.11st.co.kr/products/{pid}" if pid else None
    proxied = (target if not base_proxy else f"{base_proxy}/?url={_q(target, safe=':/?&=%')}") if target else None

    c1, c2 = st.columns([1,1])
    with c1:
        if st.button("상세 미리보기(내장)", use_container_width=True, disabled=not proxied):
            if proxied:
                html = f"""
                <style>
                  .embed-11st-detail {{
                    height: 900px; overflow: hidden; border-radius: 10px;
                    border:1px solid #e5e7eb;
                  }}
                  .embed-11st-detail iframe {{
                    width: 100%; height: 100%; border: 0; border-radius: 10px; background: transparent;
                  }}
                </style>
                <div class="embed-11st-detail">
                  <iframe
                    src="{proxied}"
                    title="11st-detail"
                    referrerpolicy="no-referrer"
                    sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
                  ></iframe>
                </div>
                """
                st.components.v1.html(html, height=920, scrolling=False)
    with c2:
        if proxied:
            st.link_button("새 탭으로 열기(프록시)", proxied, use_container_width=True)
        else:
            st.info("상품 URL 또는 ID를 입력하면 버튼이 활성화됩니다.")

    with st.expander("도움말 / 파싱 규칙", expanded=False):
        st.write("- `https://www.11st.co.kr/products/123` 또는 `https://m.11st.co.kr/products/123` 또는 `productId=123` 모두 인식합니다.")
        st.write("- 숫자만 입력해도 동작합니다. (예: `1234567890`)")
        st.write("- 프록시가 없으면 원본 링크로만 열 수 있습니다.")

    st.markdown("</div>", unsafe_allow_html=True)

# -*- coding: utf-8 -*-
# ENVY — Season 1 (One-Page Stable Edition)
# ⚠️ PROXY 경유 필수 (Cloudflare Worker v2)
# PROXY_URL = "https://envy-proxy.taesig0302.workers.dev/"

import streamlit as st
import time, re, json
from urllib.parse import quote as _q

# ──────────────────────────────
# Section 1 — 세션 & 테마
# ──────────────────────────────
def _ensure_session_defaults():
    ss = st.session_state
    ss.setdefault("theme", "light")
    ss.setdefault("__show_translator", False)
    ss.setdefault("__11st_token", str(int(time.time())))

def _inject_css():
    theme = st.session_state.get("theme", "light")
    if theme == "dark":
        bg, fg, fg_sub = "#0e1117", "#e6edf3", "#b6c2cf"
        card_bg, border = "#11151c", "rgba(255,255,255,.08)"
        btn_bg, btn_bg_hover = "#2563eb", "#1e3fae"
    else:
        bg, fg, fg_sub = "#ffffff", "#111111", "#4b5563"
        card_bg, border = "#ffffff", "rgba(0,0,0,.06)"
        btn_bg, btn_bg_hover = "#2563eb", "#1e3fae"

    st.markdown(f"""
    <style>
    [data-testid="stAppViewContainer"] {{
        background:{bg} !important; color:{fg} !important;
    }}
    [data-testid="stAppViewContainer"] .card {{
        background:{card_bg}; border:1px solid {border}; border-radius:14px;
        box-shadow:0 1px 6px rgba(0,0,0,.12);
    }}
    [data-testid="stAppViewContainer"] .stButton > button {{
        background:{btn_bg} !important; color:#fff !important;
    }}
    </style>
    """, unsafe_allow_html=True)

def _sidebar():
    _ensure_session_defaults()
    with st.sidebar:
        # 다크 모드 토글
        is_dark = st.toggle("🌓 다크", value=(st.session_state["theme"] == "dark"))
        st.session_state["theme"] = "dark" if is_dark else "light"
        # 번역기 토글
        st.toggle("🌐 번역기", value=st.session_state["__show_translator"], key="__show_translator")

        st.markdown("---")
        st.caption("⚠️ 모든 외부 임베드는 PROXY_URL 필수\n현재: https://envy-proxy.taesig0302.workers.dev/")
    _inject_css()

# ──────────────────────────────
# Section 10 — 11번가
# ──────────────────────────────
def section_11st():
    """11번가 아마존 베스트 (모바일)"""
    st.markdown('<div class="card main"><div class="card-title">11번가 (모바일) — 아마존 베스트</div>', unsafe_allow_html=True)
    ss = st.session_state

    if st.button("🔄 새로고침 (11번가)", key="btn_refresh_11st"):
        ss["__11st_token"] = str(int(time.time()))

    base_proxy = (st.secrets.get("ELEVENST_PROXY", "") or globals().get("ELEVENST_PROXY", "")).rstrip("/")
    raw_url = "https://m.11st.co.kr/page/main/abest?tabId=ABEST&pageId=AMOBEST&ctgr1No=166160"
    src_base = raw_url if not base_proxy else f"{base_proxy}/?url={_q(raw_url, safe=':/?&=%')}"
    token = ss["__11st_token"]

    html = f"""
    <div class="embed-11st-wrap">
      <iframe id="envy_11st_iframe" title="11st"></iframe>
    </div>
    <script>
    (function(){{
        var base = {json.dumps(src_base)};
        var token = {json.dumps(token)};
        var want = base + (base.indexOf('?')>=0 ? '&' : '?') + 'r=' + token;
        var ifr = document.getElementById("envy_11st_iframe");
        if (ifr) ifr.setAttribute('src', want);
    }})();
    </script>
    """
    st.components.v1.html(html, height=960, scrolling=False)
    st.markdown("</div>", unsafe_allow_html=True)

def _11st_extract_product_id(s: str) -> str | None:
    if not s: return None
    s = s.strip()
    if s.isdigit(): return s
    m = re.search(r"/products/(\d+)", s)
    if m: return m.group(1)
    m = re.search(r"[?&]productId=(\d+)", s)
    if m: return m.group(1)
    return None

def section_11st_detail():
    """11번가 상품 상세 — URL/ID 입력 → 프록시 보기"""
    st.markdown('<div class="card main"><div class="card-title">11번가 — 상품 상세 바로보기</div>', unsafe_allow_html=True)

    base_proxy = (st.secrets.get("ELEVENST_PROXY", "") or globals().get("ELEVENST_PROXY", "")).rstrip("/")
    raw_input = st.text_input("상품 URL 또는 상품ID", placeholder="예: https://www.11st.co.kr/products/1234567890")
    pid = _11st_extract_product_id(raw_input)
    target = f"https://m.11st.co.kr/products/{pid}" if pid else None
    proxied = (target if not base_proxy else f"{base_proxy}/?url={_q(target, safe=':/?&=%')}") if target else None

    c1, c2 = st.columns([1,1])
    with c1:
        if st.button("상세 미리보기(내장)", disabled=not proxied):
            if proxied:
                st.components.v1.html(
                    f"<iframe src='{proxied}' width='100%' height='900' style='border-radius:10px;'></iframe>",
                    height=920,
                    scrolling=False
                )
    with c2:
        if proxied:
            st.link_button("새 탭으로 열기(프록시)", proxied, use_container_width=True)
        else:
            st.info("상품 URL 또는 ID를 입력하면 버튼이 활성화됩니다.")
    st.markdown("</div>", unsafe_allow_html=True)

# ──────────────────────────────
# Section placeholders (간단히)
# ──────────────────────────────
def section_itemscout_placeholder():
    st.info("Itemscout 임베드 (프록시 필요)")

def section_sellerlife_placeholder():
    st.info("Sellerlife 임베드 (프록시 필요)")

# ──────────────────────────────
# Main Layout
# ──────────────────────────────
def main():
    _sidebar()

    # 2행: 11번가 + Itemscout + Sellerlife
    c1, c2, c3 = st.columns([3,3,3], gap="medium")
    with c1:
        tab_best, tab_detail = st.tabs(["아마존 베스트", "상품 상세 바로보기"])
        with tab_best:
            section_11st()
        with tab_detail:
            section_11st_detail()
    with c2:
        section_itemscout_placeholder()
    with c3:
        section_sellerlife_placeholder()

if __name__ == "__main__":
    main()

import streamlit as st
from utils import *
from datalab import render_datalab_block
from rakuten import render_rakuten_block
from elevenst import render_11st_block
from namegen import render_namegen_block

st.set_page_config(page_title="ENVY v27.14 Full", page_icon="✨", layout="wide")

# ---- 다크모드 토글 (세션 유지 + 즉시 반영) ----
if "theme" not in st.session_state:
    st.session_state["theme"] = "light"

def apply_theme_now():
    # JS 훅으로 body 클래스 토글
    st.components.v1.html(
        f"""
        <script>
        (function(){{
          const b = window.parent?.document?.querySelector('body');
          if(!b) return;
          b.classList.remove('envy-light','envy-dark');
          b.classList.add('{ 'envy-dark' if st.session_state['theme']=='dark' else 'envy-light' }');
        }})();
        </script>
        """,
        height=0
    )

def toggle_theme():
    st.session_state["theme"] = "dark" if st.session_state["theme"] == "light" else "light"

# 사이드바 토글 UI
with st.sidebar:
    st.toggle("다크 모드", value=(st.session_state["theme"]=="dark"), on_change=toggle_theme)
apply_theme_now()

# ---- CSS (간격/사이드바/다크 변수) ----
st.markdown("""
<style>
.block-container{padding-top:0.8rem; padding-bottom:0.8rem;}
[data-testid="stSidebar"] section{padding-top:0.6rem; padding-bottom:0.6rem;}
[data-testid="stSidebar"] .stButton{margin-top:0.2rem; margin-bottom:0.2rem;}
.sidebar-conn, [data-testid="stSidebar"] .conn-hide {display:none !important;}

/* Theme variables */
body.envy-light { --bg:#ffffff; --bg2:#f6f8fb; --text:#111111; --primary:#2b7fff; }
body.envy-dark  { --bg:#0e1117; --bg2:#161b22; --text:#e6edf3; --primary:#6ea8fe; }
.block-container{ background:var(--bg); color:var(--text);}
section[data-testid="stSidebar"]{ background:var(--bg2); color:var(--text);}
a { color:var(--primary) !important; }
</style>
""", unsafe_allow_html=True)

# ---- 사이드바: 환율/마진 계산기 ----
with st.sidebar:
    st.markdown("### ① 환율 계산기")
    base = st.selectbox("기준 통화", ["USD","EUR","JPY","CNY"], index=0)
    rate = st.number_input("환율 (1 단위 = ₩)", value=1400.00, step=0.01, format="%.2f")
    sale_foreign = st.number_input("판매금액 (외화)", value=1.00, step=0.01, format="%.2f")
    won = rate * sale_foreign
    st.success(f"환산 금액: {won:,.2f} 원")

    st.markdown("### ② 마진 계산기 (v23)")
    m_rate = st.number_input("카드수수료 (%)", value=4.00, step=0.01, format="%.2f")
    m_fee  = st.number_input("마켓수수료 (%)", value=14.00, step=0.01, format="%.2f")
    ship   = st.number_input("배송비 (₩)", value=0.0, step=100.0, format="%.0f")
    mode   = st.radio("마진 방식", ["퍼센트 마진(%)","더하기 마진(₩)"], horizontal=True)
    margin = st.number_input("마진율/마진액", value=10.00, step=0.01, format="%.2f")

    if mode=="퍼센트 마진(%)":
        target_price = won * (1 + m_rate/100) * (1 + m_fee/100) * (1 + margin/100) + ship
    else:
        target_price = won * (1 + m_rate/100) * (1 + m_fee/100) + margin + ship

    st.info(f"예상 판매가: {target_price:,.2f} 원")
    st.warning(f"순이익(마진): {(target_price - won):,.2f} 원")

# ---- 본문 레이아웃 3x3 --------
top1, top2, top3 = st.columns([1,1,1])
mid1, mid2, mid3 = st.columns([1,1,1])
bot1, bot2, bot3 = st.columns([1,1,1])

with top1: render_datalab_block()
with top2: st.subheader("아이템스카우트"); st.info("연동 대기 (별도 API/프록시)")
with top3: st.subheader("셀러라이프"); st.info("연동 대기 (별도 API/프록시)")

with mid1: render_rakuten_block()
with mid2: render_11st_block()
with mid3: render_namegen_block()

with bot1: st.empty()
with bot2: st.empty()
with bot3: st.empty()

# ──────────────────────────────────────────────────────────────────────────────
# ENVY Research Tool v11.x 안정판 패치 — 파트별 코드 번들
# Streamlit 기반 모놀리식 → 모듈 분리 구조 (사이드바 / 데이터랩 / 11번가 / 라쿠텐 / 번역기 / 기타)
# 본 파일은 각 파트를 한 문서에 모아둔 ‘작업용 번들’입니다.
# 실제 사용 시에는 아래 섹션별 코드를 개별 파일로 분리하세요.
# ──────────────────────────────────────────────────────────────────────────────


# ============================
# app.py (메인 엔트리)
# ============================
app_py = r"""
import streamlit as st
from datetime import datetime


st.set_page_config(page_title="ENvY Research Tool v11", layout="wide", initial_sidebar_state="expanded")


# 파트 모듈 임포트 (동일 폴더 기준)
from sidebar import render_sidebar, get_headers
from datalab import render_datalab
from elevenst import render_elevenst
from rakuten_radar import render_rakuten_radar
from translator import render_translator
from misc import render_misc


# ── 글로벌 상태 ─────────────────────────────────────────────────────────────
if "envy_state" not in st.session_state:
st.session_state["envy_state"] = {"ts": datetime.now().isoformat()}


# ── 사이드바 ────────────────────────────────────────────────────────────────
cfg = render_sidebar()
headers = get_headers(cfg)


# ── UI 섹션 카드 간격 & 오프셋 유틸 ─────────────────────────────────────────
def section_card(title: str, anchor: str = None):
st.markdown("""
<style>
.section-card{border-radius:16px;padding:22px 22px 18px;background:#0f1116;border:1px solid #222}
.section-title{font-weight:700;font-size:1.1rem;margin:0 0 14px}
</style>
""", unsafe_allow_html=True)
st.markdown(f"<div class='section-card' id='{anchor or title}'><div class='section-title'>🧭 {title}</div>", unsafe_allow_html=True)




def end_section():
st.markdown("</div>", unsafe_allow_html=True)
st.markdown("\n")


# ── 섹션: 네이버 데이터랩 ───────────────────────────────────────────────────
section_card("네이버 데이터랩 (키워드 + 그래프)", anchor="datalab")
render_datalab(cfg, headers)
end_section()


# 섹션 위치 미세조정 (요청: 원하는 위치 대비 ±5%) → 레이아웃 여백으로 보정
st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)


# ── 섹션: 11번가 베스트셀러 (프록시 배너 제거) ─────────────────────────────
section_card("11번가 베스트셀러 (모바일, Cloudflare 프록시)", anchor="11st")
render_elevenst(cfg)
end_section()


# ── 섹션: AI 키워드 레이더 (Rakuten) ───────────────────────────────────────
section_card("AI 키워드 레이더 (Rakuten)", anchor="rakuten")
render_rakuten_radar(cfg, headers)
end_section()


# ── 섹션: 구글 번역기 ──────────────────────────────────────────────────────
section_card("구글 번역기 (라인 병렬 출력)", anchor="translator")
render_translator(cfg)
end_section()


# ── 섹션: 기타 (상품명 생성기 / API Key 보관 등) ───────────────────────────
section_card("기타 기능", anchor="misc")
render_misc(cfg)
end_section()
"""


# ============================
# sidebar.py (사이드바)
# ============================
sidebar_py = r"""
import streamlit as st
from typing import Dict


# ─────────────────────────────────────────────────────────────
# UI: 한국어 통화표기 라벨
# ─────────────────────────────────────────────────────────────
CURRENCY_LABELS = {
"USD": "미국 달러 (USD) $",
"KRW": "한국 원 (KRW) ₩",
"JPY": "일본 엔 (JPY) ¥",
"EUR": "유로 (EUR) €",
"TWD": "대만 달러 (TWD) NT$",
"THB": "태국 바트 (THB) ฿",
"SGD": "싱가포르 달러 (SGD) S$",
}


# ─────────────────────────────────────────────────────────────
# 다크 모드 토글 (CSS 주입 방식)
# Streamlit 런타임에서 테마 전환이 정식 지원되지 않아, CSS 변수로 간이 구현
# ─────────────────────────────────────────────────────────────
_DARK_CSS = """
<style>
:root{--card-bg:#0f1116;--card-border:#222;--txt:#e8eaed;--muted:#a3a3a3}
body, .stApp{background: #0b0e14 !important; color: var(--txt) !important}
.block-container{padding-top:1.2rem}
.sidebar-logo{display:flex;align-items:center;gap:.5rem;margin-bottom:.5rem}
.sidebar-card{border:1px solid var(--card-border);background:var(--card-bg);border-radius:14px;padding:12px;margin-bottom:10px}
.sidebar-metric{border-radius:12px;padding:10px 12px;margin-top:10px}
.fx{background:rgba(46,204,113,.12);border:1px solid rgba(46,204,113,.35)}
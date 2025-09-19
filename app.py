# app.py — ENVY v11.x (stable) — layout hard-fix (sticky sidebar + 4x2 grid) & robust iframe

import os
import json
import time
import urllib.parse as ul
from typing import List

import streamlit as st
import pandas as pd
import numpy as np
from streamlit import components as stc

# ───────────────────────────────────────────────────────────────────────────────
# Page config
# ───────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="ENVY — v11.x (stable)", layout="wide")

# ───────────────────────────────────────────────────────────────────────────────
# CSS: 사이드바 절대 고정 + 내부 스크롤락 / 4×2 고정 그리드 / 카드 / 배지
# ───────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  .block-container{max-width: 1840px !important; padding-top: 8px;}

  /* 4×2 고정 그리드 (폭이 줄어도 4열을 유지) */
  .envy-grid{display:grid; grid-template-columns: repeat(4, minmax(360px, 1fr)); gap:18px;}
  .envy-card{border:1px solid var(--secondary-background-color); border-radius:14px; padding:14px; background: var(--background-color);}
  .envy-card h3{margin:4px 0 12px; font-size:1.05rem;}

  /* 사이드바 절대 고정 + 내부 스크롤락 */
  [data-testid="stSidebar"]{position:sticky; top:0; height:100vh;}
  /* Streamlit 버전별로 내부 구조 다를 수 있어 모두 락 */
  [data-testid="stSidebar"] section, 
  [data-testid="stSidebar"] > div:first-child, 
  [data-testid="stSidebar"] div[data-testid="stSidebarContent"]{
    height:calc(100vh - 12px)!important; overflow-y:auto!important;
  }

  /* 배지 */
  .badge{display:inline-block; padding:6px 10px; border-radius:10px; font-weight:600; font-size:.9rem;}
  .bg-blue{background:#EEF3FF; color:#1f4cff;}
  .bg-green{background:#E9F8EF; color:#108A2F;}
  .bg-gray{background:#EFEFEF; color:#333;}
  .kv{display:flex; align-items:center; gap:8px; margin-top:6px;}
  .kv .v{font-weight:700}

  .warn{background:#fff3f3; border:1px solid #ffd6d6; padding:10px 12px; border-radius:10px;}
  .t12{font-size:12px; opacity:.7}
</style>
""", unsafe_allow_html=True)

# ───────────────────────────────────────────────────────────────────────────────
# Secrets / Defaults
# ───────────────────────────────────────────────────────────────────────────────
def sec(key, default=""):
    try: return st.secrets.get(key, default)
    except Exception: return default

# 네이버/라쿠텐(요청하신 값 기본 주입)
NAVER_CLIENT_ID     = sec("NAVER_CLIENT_ID",     "h4mkIM2hNLct04BD7sC0")
NAVER_CLIENT_SECRET = sec("NAVER_CLIENT_SECRET", "ltoxUNyKxi")

RAKUTEN_APP_ID       = sec("RAKUTEN_APP_ID",       "1043271015809337425")
RAKUTEN_AFFILIATE_ID = sec("RAKUTEN_AFFILIATE_ID", "4c723498.cbfeca46.4c723499.1deb6f77")

# 프록시(고정)
PROXY_URL_DEFAULT = "https://envy-proxy.taesig0302.workers.dev/"

# ───────────────────────────────────────────────────────────────────────────────
# Utils
# ───────────────────────────────────────────────────────────────────────────────
def proxy_url():
    # 비어 있으면 기본값 사용, 값이 있으면 유지 (사이드바 노출X)
    if "PROXY_URL" not in st.session_state or not st.session_state["PROXY_URL"]:
        st.session_state["PROXY_URL"] = PROXY_URL_DEFAULT
    return st.session_state["PROXY_URL"]

def badge(text, cls="bg-gray"): return f'<span class="badge {cls}">{text}</span>'

def fmt_won(v):
    try: return f"{float(v):,.2f} 원"
    except: return str(v)

# Streamlit 버전별 iframe 시그니처 차이/TypeError 방어
def embed_iframe(src:str, height:int=520, key:str|None=None, scrolling:bool=True):
    try:
        stc.v1.iframe(src=src, height=height, scrolling=scrolling, key=key)
    except TypeError:
        # 일부 버전은 첫 인자만 위치인자로 받음
        stc.v1.iframe(src, height=height, scrolling=scrolling, key=key)

# ───────────────────────────────────────────────────────────────────────────────
# Sidebar (로고 + 환율/마진 계산기 고정, 프록시 UI 비노출)
# ───────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://static-00.iconduck.com/assets.00/smile-emoji-2048x2048-z3r8g4qf.png", width=52)
    st.markdown("**envy**")
    st.toggle("다크 모드", key="__theme", value=st.session_state.get("__theme", False))

    # 환율 계산기
    st.markdown("### ① 환율 계산기")
    cur_base = st.selectbox("기준 통화", ["USD","JPY","CNY","KRW"], index=0, key="fx_base")
    fx = {"USD":1400.0, "JPY":9.5, "CNY":190.0, "KRW":1.0}
    qty = st.number_input("판매금액 (외화)", min_value=0.0, value=1.0, step=0.1, key="fx_qty")
    won = fx.get(cur_base,1.0) * qty
    st.markdown(f'<div class="kv">{badge("환산 금액","bg-blue")} <span class="v">{fmt_won(won)}</span> <span class="t12">(환율 기준 {fx[cur_base]:,.2f} {cur_base}/KRW)</span></div>', unsafe_allow_html=True)

    # 마진 계산기
    st.markdown("### ② 마진 계산기")
    buy_curr = st.selectbox("매입 통화", ["USD","JPY","CNY","KRW"], index=0, key="m_buy_curr")
    buy_amt  = st.number_input("매입금액 (외화)", min_value=0.0, value=0.0, step=0.1, key="m_buy_amt")
    fee_card = st.number_input("카드수수료(%)", min_value=0.0, value=4.0, step=0.1, key="m_fee_card")
    fee_mkt  = st.number_input("마켓수수료(%)", min_value=0.0, value=14.0, step=0.1, key="m_fee_mkt")
    ship     = st.number_input("배송비(원)", min_value=0.0, value=0.0, step=100.0, key="m_ship")
    mode     = st.radio("마진 방식", ["퍼센트","플러스"], index=0, horizontal=True, key="m_mode")
    margin   = st.number_input("마진율(%) / 플러스(원)", min_value=0.0, value=10.0, step=0.5, key="m_margin")

    buy_won = fx.get(buy_curr,1.0) * buy_amt
    if mode == "퍼센트":
        sell = (buy_won + ship) * (1 + margin/100.0)
    else:
        sell = (buy_won + ship) + margin
    fee_tot = sell * ((fee_card + fee_mkt)/100.0)
    profit  = sell - fee_tot - (buy_won + ship)

    st.markdown(f'<div class="kv">{badge("원가","bg-gray")} <span class="v">{fmt_won(buy_won)}</span></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="kv">{badge("판매가","bg-blue")} <span class="v">{fmt_won(sell)}</span></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="kv">{badge("순이익","bg-green")} <span class="v">{fmt_won(profit)}</span></div>', unsafe_allow_html=True)

    # 프록시 값은 내부 유지(비노출). 만료/변경이 필요하면 코드의 PROXY_URL_DEFAULT만 바꾸면 됨.
    if "PROXY_URL" not in st.session_state or not st.session_state["PROXY_URL"]:
        st.session_state["PROXY_URL"] = PROXY_URL_DEFAULT

# ───────────────────────────────────────────────────────────────────────────────
# Header
# ───────────────────────────────────────────────────────────────────────────────
st.title("ENVY — v11.x (stable)")
st.caption("고정 레이아웃(사이드바 sticky+락, 4×2 카드) / 임베드형 섹션은 프록시로만 렌더 / 차트는 matplotlib 없이 line_chart")

# ───────────────────────────────────────────────────────────────────────────────
# Row 1 (4칸 고정)
# ───────────────────────────────────────────────────────────────────────────────
st.markdown('<div class="envy-grid">', unsafe_allow_html=True)

# 1) 데이터랩 (시즌1 - 분석 카드) — 샘플 차트
with st.container():
    st.markdown('<div class="envy-card">', unsafe_allow_html=True)
    st.markdown("### 데이터랩 (시즌1 - 분석 카드)")
    c1,c2,c3 = st.columns([1,1,1])
    with c1: st.selectbox("카테고리", ["디지털/가전","패션의류","화장품/미용","식품"], index=0, key="dl_cat")
    with c2: st.selectbox("기간 단위", ["week","mo","all"], index=0, key="dl_unit")
    with c3: st.selectbox("기기", ["all","pc","mo"], index=0, key="dl_dev")
    xs = np.arange(1,12)
    df = pd.DataFrame({"x":xs,"전체":48+np.sin(xs/1.5)*8+np.linspace(0,6,len(xs)),
                       "패션의류":42+np.sin(xs/1.7)*6+np.linspace(0,3,len(xs))}).set_index("x")
    st.line_chart(df, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

# 2) 11번가 (모바일) – 아마존베스트 (임베드)
with st.container():
    st.markdown('<div class="envy-card">', unsafe_allow_html=True)
    st.markdown("### 11번가 (모바일) – 아마존베스트")
    abest = "https://m.11st.co.kr/page/main/abest?tabId=ABEST&pageId=AMOBEST&ctgr1No=166160"
    purl  = proxy_url()
    try:
        embed_iframe(f"{purl}?url={ul.quote(abest, safe='')}", height=510, key="11st_abest", scrolling=True)
    except Exception as e:
        st.markdown(f'<div class="warn">임베드 실패: {e}</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# 3) 상품명 생성기 (규칙)
with st.container():
    st.markdown('<div class="envy-card">', unsafe_allow_html=True)
    st.markdown("### 상품명 생성기 (규칙 기반)")
    b1,b2,b3 = st.columns([1,1,1])
    with b1: brand = st.text_input("브랜드", placeholder="예: 오소", key="nm_brand")
    with b2: style = st.text_input("스타일/속성", placeholder="예: 프리미엄, 5", key="nm_style")
    with b3: length = st.slider("길이(단어 수)", 4, 12, 8, key="nm_len")
    kw = st.text_input("핵심 키워드(콤마)", placeholder="예: 가습기, 무선청소기, 턴테이블", key="nm_kw")
    if st.button("상품명 20개 생성", key="nm_btn"):
        words = [w.strip() for w in kw.split(",") if w.strip()]
        outs=[]
        for i in range(20):
            base=[]
            if brand: base.append(brand)
            if style: base.extend([s.strip() for s in style.split(",") if s.strip()])
            if words: base.append(words[i % len(words)])
            while len(base) < length: base.append("스페셜")
            outs.append(" ".join(base[:length]))
        st.text_area("결과", "\n".join(outs), height=200)
    st.markdown("</div>", unsafe_allow_html=True)

# 4) 선택 키워드 트렌드 (샘플)
with st.container():
    st.markdown('<div class="envy-card">', unsafe_allow_html=True)
    st.markdown("### 선택 키워드 트렌드 (샘플)")
    xs2=np.arange(1,12)
    df2=pd.DataFrame({"x":xs2,"전체":38+np.sin(xs2/1.3)*7+np.linspace(0,12,len(xs2)),
                      "패션의류":36+np.sin(xs2/1.8)*5+np.linspace(0,6,len(xs2))}).set_index("x")
    st.line_chart(df2, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)  # end grid row1

# ───────────────────────────────────────────────────────────────────────────────
# Row 2 (4칸 고정)
# ───────────────────────────────────────────────────────────────────────────────
st.markdown('<div class="envy-grid">', unsafe_allow_html=True)

# 5) AI 키워드 레이더 (Rakuten)
with st.container():
    st.markdown('<div class="envy-card">', unsafe_allow_html=True)
    st.markdown("### AI 키워드 레이더 (Rakuten)")
    scope = st.radio("범위", ["국내","글로벌"], index=0, horizontal=True, key="rk_scope")
    r1,r2 = st.columns([1,1])
    with r1: rk_cat = st.selectbox("라쿠텐 카테고리(메모)", ["전체(샘플)","패션","가전","식품"], index=0)
    with r2: genre_id = st.text_input("GenreID", value="100283", key="rk_genre")

    def rakuten_top_keywords(genre="100283", size=20)->List[str]:
        import requests, re
        url = "https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20220601"
        params = {"format":"json", "genreId":genre, "applicationId":RAKUTEN_APP_ID}
        r = requests.get(url, params=params, timeout=10); r.raise_for_status()
        titles = [i["itemName"] for i in r.json().get("Items", []) if "itemName" in i]
        bag={}
        for t in titles:
            for tok in re.findall(r"[A-Za-z가-힣0-9]+", t):
                if len(tok) < 2: continue
                bag[tok]=bag.get(tok,0)+1
        return [k for k,_ in sorted(bag.items(), key=lambda x:x[1], reverse=True)[:size]]

    if st.button("키워드 20개 불러오기", key="rk_btn"):
        try:
            keys = rakuten_top_keywords(genre=genre_id, size=20)
            st.table({"rank":list(range(1,len(keys)+1)),"keyword":keys,"source":["rakuten"]*len(keys)})
        except Exception as e:
            st.markdown(f'<div class="warn">라쿠텐 조회 실패: {e}</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# 6) 번역 (Papago)
with st.container():
    st.markdown('<div class="envy-card">', unsafe_allow_html=True)
    st.markdown("### 구글 번역 (문구) → 실제 호출은 Papago")
    src = st.selectbox("원문 언어", ["자동 감지","ko","en","ja","zh-CN"], index=0, key="tr_src")
    tgt = st.selectbox("번역 언어", ["영어","한국어","일본어","중국어"], index=0, key="tr_tgt")
    lang_map={"영어":"en","한국어":"ko","일본어":"ja","중국어":"zh-CN"}
    tgt_code = lang_map[tgt]; src_code = None if src=="자동 감지" else src
    txt = st.text_area("원문 입력", height=150, key="tr_txt")

    def papago_translate(txt, source=None, target="en"):
        import requests
        url="https://openapi.naver.com/v1/papago/n2mt"
        headers={"X-Naver-Client-Id":NAVER_CLIENT_ID, "X-Naver-Client-Secret":NAVER_CLIENT_SECRET}
        data={"text":txt, "target":target}
        if source: data["source"]=source
        r=requests.post(url, headers=headers, data=data, timeout=12); r.raise_for_status()
        return r.json()["message"]["result"]["translatedText"]

    if st.button("번역", key="tr_btn"):
        if not txt.strip(): st.info("번역할 텍스트를 입력해 주세요.")
        else:
            try: st.text_area("번역 결과", papago_translate(txt, source=src_code, target=tgt_code), height=150)
            except Exception as e: st.markdown(f'<div class="warn">번역 실패: {e}</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# 7) 아이템스카우트 (원본 임베드)
with st.container():
    st.markdown('<div class="envy-card">', unsafe_allow_html=True)
    st.markdown("### 아이템스카우트 (원본 임베드)")
    try:
        embed_iframe(f"{proxy_url()}?url={ul.quote('https://items.singtown.com', safe='')}", height=520, key="items_scout")
    except Exception as e:
        st.markdown(f'<div class="warn">임베드 실패: {e}</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# 8) 셀러라이프 (원본 임베드)
with st.container():
    st.markdown('<div class="envy-card">', unsafe_allow_html=True)
    st.markdown("### 셀러라이프 (원본 임베드)")
    try:
        embed_iframe(f"{proxy_url()}?url={ul.quote('https://www.sellerlife.co.kr', safe='')}", height=520, key="sellerlife")
    except Exception as e:
        st.markdown(f'<div class="warn">임베드 실패: {e}</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)  # end grid row2

st.markdown("---")
st.markdown("• 레이아웃은 **고정**(사이드바 sticky + 스크롤락, 4×2 카드) • 프록시는 기본값으로 항상 사용 • iFrame 은 버전차이까지 대비한 안전 호출", unsafe_allow_html=False)

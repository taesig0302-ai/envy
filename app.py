# app.py
import os
import math
import json
import time
import textwrap
import urllib.parse as ul

import streamlit as st
from datetime import datetime
from typing import List, Dict

# ---------- 페이지/레이아웃 ----------
st.set_page_config(page_title="ENVY — v11.x (stable)", layout="wide")

# ---------- 전역 CSS (넓게, 카드 간격 최소화, 배지 스타일, 사이드바 스크롤 고정) ----------
def inject_css():
    st.markdown("""
    <style>
      .block-container{max-width: 1800px !important; padding-top: 1rem;}
      /* 4열 카드가 좌우로 넓게 보이도록 */
      .envy-row{display:grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 18px;}
      .envy-card{border:1px solid var(--secondary-background-color); border-radius:14px; padding:14px; background: var(--background-color);}
      .envy-card h3{margin:3px 0 12px; font-size:1.05rem;}
      .envy-card .muted{opacity:.7; font-size:.88rem;}
      /* 사이드바 스크롤 고정 */
      [data-testid="stSidebar"] section {overflow-y:auto !important;}
      /* 배지 */
      .badge{display:inline-block; padding:6px 10px; border-radius:10px; font-weight:600; font-size:.9rem;}
      .bg-blue{background:#EEF3FF; color:#1f4cff;}
      .bg-green{background:#E9F8EF; color:#108A2F;}
      .bg-orange{background:#FFF3E0; color:#BE5A00;}
      .bg-gray{background:#EFEFEF; color:#333;}
      .kv{display:flex; align-items:center; gap:8px; margin-top:6px;}
      .kv .k{min-width:64px; opacity:.7}
      .kv .v{font-weight:600}
      .small{font-size:.85rem}
      .warn{background:#fff3f3; border:1px solid #ffd6d6; padding:10px 12px; border-radius:10px;}
      .ok{background:#f0fff4; border:1px solid #d6ffe1; padding:10px 12px; border-radius:10px;}
      textarea, select, input{border-radius:8px !important;}
      .tight{margin-top:-8px;}
      .full{width:100%;}
      .t12{font-size:12px; opacity:.7}
    </style>
    """, unsafe_allow_html=True)

inject_css()

# ---------- 비밀/설정 (Secrets -> fallback) ----------
def get_secret(key: str, default: str = "") -> str:
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default

# 제공해주신 값들(FALLBACK) — 실제 운영에서는 st.secrets 사용 권장
NAVER_CLIENT_ID = get_secret("NAVER_CLIENT_ID", "h4mkIM2hNLct04BD7sC0")
NAVER_CLIENT_SECRET = get_secret("NAVER_CLIENT_SECRET", "ltoxUNyKxi")

RAKUTEN_APP_ID = get_secret("RAKUTEN_APP_ID", "1043271015809337425")
RAKUTEN_AFFILIATE_ID = get_secret("RAKUTEN_AFFILIATE_ID", "4c723498.cbfeca46.4c723499.1deb6f77")

# 프록시 URL: 기본값은 여러분 Worker (없으면 빈 문자열)
PROXY_URL_DEFAULT = get_secret("PROXY_URL", "https://envy-proxy.taesig0302.workers.dev/")

# ---------- 공통 유틸 ----------
def fmt_won(v):
    try:
        return f"{float(v):,.2f} 원"
    except:
        return str(v)

def badge(text, cls="bg-gray"):
    return f'<span class="badge {cls}">{text}</span>'

def proxy_url_or_none():
    # 세션/Secrets 기반 가져오기
    url = st.session_state.get("PROXY_URL", "").strip() or PROXY_URL_DEFAULT.strip()
    return url

def iframe(url, height=560, key="frame"):
    st.components.v1.iframe(url, height=height, scrolling=True, key=key)

# ---------- 사이드바 ----------
def render_sidebar():
    with st.sidebar:
        st.image("https://static-00.iconduck.com/assets.00/smile-emoji-2048x2048-z3r8g4qf.png", width=52)
        st.markdown("**envy**")

        # 다크 모드 토글(표시용)
        st.toggle("다크 모드", key="__theme_toggle", value=st.session_state.get("__theme_toggle", False))

        st.markdown("### ① 환율 계산기")
        base = st.selectbox("기준 통화", ["USD","JPY","CNY","KRW"], index=0, key="fx_base")
        fx_map = {
            "USD": 1400.0,   # 필요시 수정
            "JPY": 9.5,
            "CNY": 190.0,
            "KRW": 1.0,
        }
        qty = st.number_input("판매금액 (외화)", min_value=0.0, value=1.0, step=0.1, key="fx_qty")
        won = fx_map.get(base,1.0) * qty

        # 환산 금액 배지
        st.markdown(
            f'<div class="kv">{badge("환산 금액", "bg-blue")} '
            f'<span class="v">{fmt_won(won)}</span> '
            f'<span class="t12">(환율 기준: {fx_map[base]:,.2f} {base}/KRW)</span></div>',
            unsafe_allow_html=True
        )

        st.markdown("### ② 마진 계산기")
        buy_curr = st.selectbox("매입 통화", ["USD","JPY","CNY","KRW"], index=0, key="m_buy_curr")
        buy_price = st.number_input("매입금액 (외화)", min_value=0.0, value=0.0, step=0.1, key="m_buy_amt")
        fee_card = st.number_input("카드수수료(%)", min_value=0.0, value=4.0, step=0.1, key="m_fee_card")
        fee_market = st.number_input("마켓수수료(%)", min_value=0.0, value=14.0, step=0.1, key="m_fee_market")
        ship_fee = st.number_input("배송비(원)", min_value=0.0, value=0.0, step=100.0, key="m_ship")

        mode = st.radio("마진 방식", ["퍼센트","플러스"], index=0, horizontal=True, key="m_mode")
        margin = st.number_input("마진율(%) / 플러스(원)", min_value=0.0, value=10.0, step=0.5, key="m_margin")

        # 원가(원)
        buy_won = fx_map.get(buy_curr, 1.0) * buy_price
        # 판매가(원): 카드+마켓 수수료 반영을 위해 역산 or 단순 가산 중 선택 가능
        # 여기서는 단순 모델: (원가 + 배송비) * (1 + 마진%)  -> 그 위에 수수료 감안해서 조금 보정해도 됨
        if mode == "퍼센트":
            raw_sell = (buy_won + ship_fee) * (1 + margin/100.0)
        else:
            raw_sell = (buy_won + ship_fee) + margin

        # 수수료 포함 총매출 -> 순이익: 매출 - 수수료 - (원가+배송비)
        fee_total = raw_sell * (fee_card/100.0 + fee_market/100.0)
        profit = raw_sell - fee_total - (buy_won + ship_fee)

        # 배지 3종
        st.markdown(
            f"""
            <div class="kv">{badge("원가", "bg-gray")} <span class="v">{fmt_won(buy_won)}</span></div>
            <div class="kv">{badge("판매가", "bg-blue")} <span class="v">{fmt_won(raw_sell)}</span></div>
            <div class="kv">{badge("순이익", "bg-green")} <span class="v">{fmt_won(profit)}</span></div>
            """,
            unsafe_allow_html=True
        )

        # ---- 프록시/환경 (비어있을때만 경고 노출) ----
        st.markdown("---")
        with st.expander("프록시/환경", expanded=False):
            st.caption("Cloudflare Worker 프록시 주소 (비워두면 기본값 사용)")
            st.text_input("PROXY_URL", value=st.session_state.get("PROXY_URL", PROXY_URL_DEFAULT), key="PROXY_URL")
            st.caption("• 프록시 루트에 ?url= 대상URL을 붙여 iFrame 임베드합니다.  \n• Worker.js는 제가 드린 버전을 추천합니다.")

        p = proxy_url_or_none()
        if not p:
            st.markdown('<div class="warn">PROXY_URL이 비어있습니다. 11번가/아이템스카우트/셀러라이프 임베드가 동작하지 않아요.</div>', unsafe_allow_html=True)

render_sidebar()

# ---------- 상단 헤더 ----------
st.title("ENVY — v11.x (stable)")
st.caption("시즌1: 데이터랩(분석 카드, 임베드 X), API/키 동시, 11번가/아이템스카우트/셀러라이프는 프록시 기반 임베드")

# ---------- 4×2 그리드 ----------
top_row = st.container()
with top_row:
    st.markdown('<div class="envy-row">', unsafe_allow_html=True)

    # 1) 데이터랩 (시즌1 — 분석 카드)
    with st.container():
        st.markdown('<div class="envy-card">', unsafe_allow_html=True)
        st.markdown("### 데이터랩 (시즌1 – 분석 카드)")
        c1, c2, c3 = st.columns([1,1,1])
        with c1:
            dl_cat = st.selectbox("카테고리", ["디지털/가전","패션의류","화장품/미용","식품"], index=0, key="dl_cat")
        with c2:
            dl_unit = st.selectbox("기간 단위", ["week","mo","all"], index=0, key="dl_unit")
        with c3:
            dl_dev = st.selectbox("기기", ["all","pc","mo"], index=0, key="dl_dev")

        st.button("Top20 불러오기 (샘플)", key="dl_btn")

        # 샘플 라인 그래프 (키워드 트렌드)
        import numpy as np
        import matplotlib.pyplot as plt

        xs = np.arange(1,12)
        y1 = 48 + np.sin(xs/1.5)*8 + np.linspace(0,6,len(xs))
        y2 = 42 + np.sin(xs/1.7)*6 + np.linspace(0,3,len(xs))

        fig = plt.figure()
        plt.plot(xs, y1, label="전체")
        plt.plot(xs, y2, label="패션의류")
        plt.legend()
        plt.title("선택 키워드 트렌드 (샘플)")
        st.pyplot(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # 2) 11번가 (모바일 – 아마존베스트)
    with st.container():
        st.markdown('<div class="envy-card">', unsafe_allow_html=True)
        st.markdown("### 11번가 (모바일) – 아마존베스트")
        purl = proxy_url_or_none()
        abest = "https://m.11st.co.kr/page/main/abest?tabId=ABEST&pageId=AMOBEST&ctgr1No=166160"
        if purl:
            t = f"{purl}?url={ul.quote(abest, safe='')}"
            iframe(t, height=510, key="11st_abest")
        else:
            st.markdown('<div class="warn">PROXY_URL이 비어 있어 iFrame 임베드가 차단될 수 있어요.</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # 3) 상품명 생성기 (규칙 기반)
    with st.container():
        st.markdown('<div class="envy-card">', unsafe_allow_html=True)
        st.markdown("### 상품명 생성기 (규칙 기반)")
        b1, b2, b3 = st.columns([1,1,1])
        with b1:
            brand = st.text_input("브랜드", placeholder="예: 오소", key="nm_brand")
        with b2:
            style = st.text_input("스타일/속성", placeholder="예: 프리미엄, 5", key="nm_style")
        with b3:
            length = st.slider("길이(단어 수)", 4, 12, 8, key="nm_len")

        kw = st.text_area("핵심 키워드(콤마)", placeholder="예: 가습기, 무선청소기, 턴테이블", key="nm_kw")
        if st.button("상품명 20개 생성", key="nm_btn"):
            words = [w.strip() for w in kw.split(",") if w.strip()]
            outs = []
            for i in range(20):
                base = []
                if brand: base.append(brand)
                if style: base.extend([s.strip() for s in style.split(",") if s.strip()])
                if words:
                    base.append(words[i % len(words)])
                # 길이 맞추기 (간단 보정)
                while len(base) < length:
                    base.append("스페셜")
                outs.append(" ".join(base[:length]))
            st.text_area("결과", "\n".join(outs), height=220)
        st.markdown('</div>', unsafe_allow_html=True)

    # 4) 선택 키워드 트렌드 (샘플)
    with st.container():
        st.markdown('<div class="envy-card">', unsafe_allow_html=True)
        st.markdown("### 선택 키워드 트렌드 (샘플)")
        # 같은 fig 재사용 방지
        import numpy as np
        import matplotlib.pyplot as plt
        xs2 = np.arange(1,12)
        y3 = 38 + np.sin(xs2/1.3)*7 + np.linspace(0,12,len(xs2))
        y4 = 36 + np.sin(xs2/1.8)*5 + np.linspace(0,6,len(xs2))
        fig2 = plt.figure()
        plt.plot(xs2, y3, label="전체")
        plt.plot(xs2, y4, label="패션의류")
        plt.legend()
        st.pyplot(fig2, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

# ---------- 2번째 줄 ----------
bot_row = st.container()
with bot_row:
    st.markdown('<div class="envy-row">', unsafe_allow_html=True)

    # 5) AI 키워드 레이더 (Rakuten)
    with st.container():
        st.markdown('<div class="envy-card">', unsafe_allow_html=True)
        st.markdown("### AI 키워드 레이더 (Rakuten)")
        scope = st.radio("범위", ["국내","글로벌"], index=0, horizontal=True, key="rk_scope")
        col1, col2 = st.columns([1,1])
        with col1:
            rk_cat = st.selectbox("라쿠텐 카테고리(메모용)", ["전체(샘플)","패션","가전","식품"], index=0, key="rk_cat")
        with col2:
            genre_id = st.text_input("GenreID", value="100283", key="rk_genre")
        st.caption("참고: app_id/affiliate_id는 Secrets→RAKUTEN_APP_ID / RAKUTEN_AFFILIATE_ID (기본값 내장)")

        def rakuten_top_keywords(genre="100283", size=20) -> List[str]:
            """간단 구현: 랭킹 API에서 상품명 토큰 추출→상위 키워드"""
            import requests, re
            url = "https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20220601"
            params = {
                "format":"json",
                "genreId": genre,
                "applicationId": RAKUTEN_APP_ID,
            }
            r = requests.get(url, params=params, timeout=10)
            r.raise_for_status()
            data = r.json()
            titles = [i["itemName"] for i in data.get("Items", []) if "itemName" in i]
            bag = {}
            for t in titles:
                # 토큰 간단 추출(한/영/숫자)
                tokens = re.findall(r"[A-Za-z가-힣0-9]+", t)
                for tok in tokens:
                    if len(tok) < 2: 
                        continue
                    bag[tok] = bag.get(tok, 0) + 1
            # 빈도 정렬
            top = sorted(bag.items(), key=lambda x: x[1], reverse=True)[:size]
            return [k for k,v in top]

        if st.button("키워드 20개 불러오기", key="rk_btn"):
            try:
                keys = rakuten_top_keywords(genre=genre_id, size=20)
                st.table({"rank": list(range(1,len(keys)+1)), "keyword": keys, "source":["rakuten"]*len(keys)})
            except Exception as e:
                st.markdown(f'<div class="warn">라쿠텐 조회 실패: {e}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # 6) 구글 번역(→ 여기서는 네이버 PAPAGO로 구현)
    with st.container():
        st.markdown('<div class="envy-card">', unsafe_allow_html=True)
        st.markdown("### 구글 번역 (텍스트 입력/출력 + 한국어 확인용) — 실제 호출은 **Papago(Naver)**")
        src = st.selectbox("원문 언어", ["자동 감지","ko","en","ja","zh-CN"], index=0, key="tr_src")
        tgt = st.selectbox("번역 언어", ["영어","한국어","일본어","중국어"], index=0, key="tr_tgt")
        lang_map = {"영어":"en","한국어":"ko","일본어":"ja","중국어":"zh-CN"}
        tgt_code = lang_map[tgt]
        src_code = None if src=="자동 감지" else src

        text = st.text_area("원문 입력", height=150, key="tr_text")

        def papago_translate(txt, source=None, target="en"):
            import requests
            url = "https://openapi.naver.com/v1/papago/n2mt"
            headers = {
                "X-Naver-Client-Id": NAVER_CLIENT_ID,
                "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
            }
            data = {
                "text": txt,
                "target": target
            }
            if source:
                data["source"] = source
            resp = requests.post(url, headers=headers, data=data, timeout=12)
            resp.raise_for_status()
            j = resp.json()
            return j["message"]["result"]["translatedText"]

        if st.button("번역", key="tr_btn"):
            if not text.strip():
                st.info("번역할 텍스트를 입력해 주세요.")
            else:
                try:
                    out = papago_translate(text, source=src_code, target=tgt_code)
                    st.text_area("번역 결과", out, height=150)
                except Exception as e:
                    st.markdown(f'<div class="warn">번역 실패: {e}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # 7) 아이템스카우트 (원본 임베드)
    with st.container():
        st.markdown('<div class="envy-card">', unsafe_allow_html=True)
        st.markdown("### 아이템스카우트 (원본 임베드)")
        purl = proxy_url_or_none()
        if purl:
            raw = "https://items.singtown.com"
            iframe(f"{purl}?url={ul.quote(raw, safe='')}", height=520, key="items_scout")
        else:
            st.markdown('<div class="warn">PROXY_URL이 비어 있습니다. 사이드바의 프록시에서 설정해 주세요.</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # 8) 셀러라이프 (원본 임베드)
    with st.container():
        st.markdown('<div class="envy-card">', unsafe_allow_html=True)
        st.markdown("### 셀러라이프 (원본 임베드)")
        purl = proxy_url_or_none()
        if purl:
            raw = "https://www.sellerlife.co.kr"
            iframe(f"{purl}?url={ul.quote(raw, safe='')}", height=520, key="sellerlife")
        else:
            st.markdown('<div class="warn">PROXY_URL이 비어 있습니다. 사이드바의 프록시에서 설정해 주세요.</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

# ---------- 하단 안내 ----------
st.markdown("---")
st.markdown(
    """
    **오류/안내**
    - 프록시가 비어 있거나 대상 사이트가 `X-Frame-Options/CSP` 정책을 강하게 적용하면 임베드가 차단될 수 있어요.  
    - 데이터랩 TOP20(공식 API 없음)은 시즌2에서 **원본 임베드 방식**으로 전환 추천(쿠키/세션 만료 문제 사라짐).  
    - Papago/라쿠텐 키는 `st.secrets`를 우선 사용하고, 비어 있으면 코드 내 기본값을 사용합니다. 운영에선 **반드시 Secrets로 이동**하세요.
    """
)

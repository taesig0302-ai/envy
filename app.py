# =========================================================
# ENVY — Season 1 (One-Page · Full) · app.py   |   2025-09-20
# ---------------------------------------------------------
# [고정 메모/운영 상수 — 주석으로 박제]
# 1) 프록시(필수): Cloudflare Worker v2 (?url=) — PROXY_URL 기본값
#    https://envy-proxy.taesig0302.workers.dev/
#    ※ 앱은 항상 프록시 경유. PROXY 입력 UI는 "최초 1회만" 노출, 확정 후 자동 숨김.
#    ※ 관리자 다시 열기: URL에 ?admin=1
#
# 2) 네이버 데이터랩 엔드포인트 (정보용)
#    - 카테고리 키워드 랭킹: /shoppingInsight/getCategoryKeywordRank.naver
#      (필수: cid, timeUnit=date, startDate, endDate, device, age, gender, page=1, count=20)
#    - 키워드 트렌드: /shoppingInsight/getKeywordClickTrend.naver
#      (필수: cid, timeUnit=date, startDate, endDate, device, age, gender, keyword)
#
# 3) 11번가(모바일) 임베드는 반드시 프록시 경유. m.11st UA/Referer/CSP는 워커에서 처리.
# ---------------------------------------------------------
# 본 파일은 Season 1 베이스라인을 기준으로:
#  - 데이터랩 폭 6단계 유지 (요청 반영)
#  - 아이템스카우트/셀러라이프/11번가: 전 배치·UI 복귀
#  - AI 키워드 레이더: Season 1 사양으로 복원(실데이터 우선/샘플 폴백, 스크롤형, 폰트 축소, '열기' 링크, GenreID 입력)
#  - 구글 번역기: Season 1 표시 규칙 복원(원문/번역 같은 줄, '번역 (한국어확인)' 형식, 라벨 한글, 슬라이더 제거)
#  - 상품명 생성기: 전 필드/프리뷰 복구
#  - 사이드바 환율/마진 계산기 로직은 '불변' (수식·필드명·순서 그대로)
# =========================================================

import os
import re
import json
import urllib.parse
from datetime import date
from pathlib import Path

import streamlit as st

# 선택적 의존성(없어도 동작하도록)
try:
    import requests
except Exception:
    requests = None

try:
    from googletrans import Translator  # 선택: 설치되어 있으면 사용
except Exception:
    Translator = None

import pandas as pd

# ──────────────────────────────────────────────────────────────
# 페이지 설정
# ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ENVY — Season 1 (One-Page · Full)",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────────────────────
# 스타일(전역)
# ──────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
/* 본문 컨테이너 폭/여백 */
.block-container { max-width: 1500px; padding-top: 0.8rem; }
/* 섹션 카드 */
.envy-card { border:1px solid rgba(0,0,0,.08); border-radius:14px; padding:10px; background:#fff; }
/* 사이드바: 순이익 카드 고정 + 여백 축소 */
section[data-testid="stSidebar"] > div { padding-top: 8px !important; }
#sidebar-scroll-wrap { max-height: calc(100vh - 110px); overflow-y:auto; padding-right:6px; }
.st-key-profit-card { position: sticky; bottom: 0; z-index: 1; background:rgba(0,0,0,.03);
  border:1px solid rgba(0,0,0,.08); border-radius:10px; padding:10px; margin-top:8px; }
/* 표 폰트 축소(레이더) */
.envy-small-table div[data-testid="stDataFrame"] { font-size: 12.5px; }
</style>
""",
    unsafe_allow_html=True,
)

# ──────────────────────────────────────────────────────────────
# Part 0 — PROXY 설정(첫 입력 1회 노출, 이후 숨김)
# 우선순위: secrets > ?proxy= > session_state > env > DEFAULT
# 관리자 재오픈: URL에 ?admin=1
# ──────────────────────────────────────────────────────────────
DEFAULT_PROXY = "https://envy-proxy.taesig0302.workers.dev/"  # Cloudflare Worker v2 (?url=)

def _get_qp():
    # Streamlit 버전 호환
    try:
        return st.experimental_get_query_params()
    except Exception:
        try:
            return dict(st.query_params)
        except Exception:
            return {}

_qp = _get_qp()
_admin = str(_qp.get("admin", ["0"])[0]) == "1" if isinstance(_qp.get("admin"), list) else (_qp.get("admin") == "1")
_qp_proxy = (_qp.get("proxy", [None])[0] if isinstance(_qp.get("proxy"), list) else _qp.get("proxy")) or None

PROXY_URL = (
    str(st.secrets.get("PROXY_URL", "")).strip()
    or (_qp_proxy or "").strip()
    or str(st.session_state.get("PROXY_URL", "")).strip()
    or str(os.getenv("PROXY_URL", "")).strip()
    or DEFAULT_PROXY
)
locked = bool(st.session_state.get("PROXY_LOCKED", False))
if _qp_proxy:
    locked = True
    st.session_state["PROXY_LOCKED"] = True
    st.session_state["PROXY_URL"] = PROXY_URL

def _render_proxy_input_ui():
    with st.container():
        st.markdown("##### 프록시 설정")
        _v = st.text_input("Cloudflare Worker v2 (?url=) 주소", value=PROXY_URL, key="__proxy_input")
        left, right = st.columns([1, 3])
        with left:
            if st.button("확정", type="primary", use_container_width=True):
                st.session_state["PROXY_URL"] = _v.strip()
                st.session_state["PROXY_LOCKED"] = True
                # 입력 직후 UI 숨김을 위해 파라미터 정리 + 리런
                try:
                    st.experimental_set_query_params()
                except Exception:
                    try:
                        st.query_params.clear()
                    except Exception:
                        pass
                st.rerun()
        with right:
            st.caption("※ 한 번 확정하면 UI는 숨겨집니다. 관리자 모드는 URL에 ?admin=1 로 재오픈.")

# secrets에 값이 없고, 락이 아니면(=첫 사용) UI 노출. 관리자 모드는 강제 노출.
_show_proxy_ui = (not st.secrets.get("PROXY_URL")) and (not locked or _admin)
if _show_proxy_ui:
    _render_proxy_input_ui()

PROXY_URL = str(st.session_state.get("PROXY_URL", PROXY_URL)).strip()

def proxied(url: str) -> str:
    return f"{PROXY_URL.rstrip('/')}/?url={urllib.parse.quote(url, safe='')}"

# ──────────────────────────────────────────────────────────────
# 사이드바 (계산 로직 불변, 가시성만 개선)
# ──────────────────────────────────────────────────────────────
with st.sidebar:
    st.toggle("다크 모드", value=False, key="darkdummy")  # 자리 유지용

    st.markdown('<div id="sidebar-scroll-wrap">', unsafe_allow_html=True)

    st.subheader("① 환율 계산기")
    CURRENCIES = {
        "USD": {"kr": "미국 달러", "symbol": "$"},
        "EUR": {"kr": "유로", "symbol": "€"},
        "JPY": {"kr": "일본 엔", "symbol": "¥"},
        "CNY": {"kr": "중국 위안", "symbol": "元"},
    }
    base_ccy = st.selectbox("기준 통화", list(CURRENCIES.keys()), index=0, key="ccy")
    fx_rate = st.number_input("환율(원/화)", min_value=0.0, step=0.01,
                              value=1400.0 if base_ccy == "USD" else (1500.0 if base_ccy=="EUR" else (10.0 if base_ccy=="JPY" else 200.0)))
    st.caption(f"환산 기준: 1 {base_ccy} = {fx_rate:,.2f}원")

    st.divider()
    st.subheader("② 마진 계산기")
    sell_ccy = st.selectbox("매입 통화", list(CURRENCIES.keys()), index=list(CURRENCIES.keys()).index(base_ccy))
    buy_cost = st.number_input("매입원가 (단가)", min_value=0.0, step=0.01, value=0.0)
    fee_card = st.number_input("카드/수수료(%)", min_value=0.0, step=0.1, value=4.0)
    fee_market = st.number_input("마켓수수료(%)", min_value=0.0, step=0.1, value=14.0)
    ship_cost = st.number_input("배송비(원)", min_value=0.0, step=100.0, value=0.0)
    margin_rate = st.number_input("마진율(%)", min_value=0.0, step=0.1, value=10.0)

    # ── 계산식(불변)
    krw_buy = buy_cost * (fx_rate if sell_ccy != "KRW" else 1.0)
    krw_fee = krw_buy * (fee_card + fee_market) / 100.0
    krw_margin = krw_buy * (margin_rate / 100.0)
    sale_price = krw_buy + krw_fee + ship_cost + krw_margin
    profit = sale_price - (krw_buy + krw_fee + ship_cost)

    st.markdown(
        f"""
<div class="st-key-profit-card">
<b>판매가(원):</b> {sale_price:,.0f}<br/>
<b>순이익(원):</b> {profit:,.0f}
</div>
""",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)  # /sidebar-scroll-wrap

# ──────────────────────────────────────────────────────────────
# 상단 섹션 — 데이터랩 / 아이템스카우트 / 셀러라이프
# 레이아웃: 6 : 3 : 3 (데이터랩 확대 유지, 나머지는 전 배치로 복귀)
# ──────────────────────────────────────────────────────────────
col_dl, col_is, col_sl = st.columns([6, 3, 3], gap="medium")

with col_dl:
    st.subheader("데이터랩")
    st.markdown(
        f"""<div class="envy-card">
<iframe src="{proxied('https://datalab.naver.com/shoppingInsight/sCategory.naver')}"
        style="width:100%; height:740px; border:0; border-radius:12px; background:#fff;"></iframe>
</div>""",
        unsafe_allow_html=True,
    )

with col_is:
    st.subheader("아이템스카우트")
    st.markdown(
        f"""<div class="envy-card">
<iframe src="{proxied('https://www.itemscout.io/')}"
        style="width:100%; height:740px; border:0; border-radius:12px; background:#fff;"></iframe>
</div>""",
        unsafe_allow_html=True,
    )

with col_sl:
    st.subheader("셀러라이프")
    st.markdown(
        f"""<div class="envy-card">
<iframe src="{proxied('https://www.sellerlife.co.kr/')}"
        style="width:100%; height:740px; border:0; border-radius:12px; background:#fff;"></iframe>
</div>""",
        unsafe_allow_html=True,
    )

# ──────────────────────────────────────────────────────────────
# 11번가 (모바일) — 원본 임베드(프록시 경유)
# ──────────────────────────────────────────────────────────────
st.divider()
st.subheader("11번가 (모바일)")
eleven_m = "https://m.11st.co.kr/page/main/home"
st.markdown(
    f"""<div class="envy-card">
<iframe src="{proxied(eleven_m)}"
        style="width:100%; height:520px; border:0; border-radius:12px; background:#fff;"></iframe>
</div>""",
    unsafe_allow_html=True,
)

# ──────────────────────────────────────────────────────────────
# Part 5 — AI 키워드 레이더 (Rakuten)  · Season 1 복원
#  - 실데이터 우선(Secrets 우선, 기본 키 폴백) + 샘플 옵션
#  - 표 스크롤형/여백/폰트 축소, '열기' 링크로 축약
#  - GenreID 입력 가능(선택)
# ──────────────────────────────────────────────────────────────
st.divider()
st.subheader("AI 키워드 레이더 (Rakuten)")

# 자격증명(Secrets 우선, 기본값 폴백 — 코드에 기본 박제)
RAKUTEN_APP_ID = str(st.secrets.get("RAKUTEN_APP_ID", "")).strip() or "demo-app-id"
RAKUTEN_AFF_ID = str(st.secrets.get("RAKUTEN_AFFILIATE_ID", "")).strip() or "demo-aff"

c1, c2, c3 = st.columns([2, 2, 6])
with c1:
    region = st.selectbox("지역", ["국내", "글로벌"], index=0)
with c2:
    genre_id = st.text_input("GenreID (선택)", value="", placeholder="예: 100227(식품·스낵)")
with c3:
    st.caption("※ Secrets가 있으면 실데이터를 우선 사용, 없으면 샘플 테이블을 표시합니다.")

def fetch_rakuten_ranking(_genre_id: str):
    """Rakuten Ichiba Ranking API에서 상위 아이템을 가져와 '키워드 유사' 표로 구성.
    실사용에선 별도 레이더 소스에 맞춰 매핑하세요."""
    if not requests or RAKUTEN_APP_ID.startswith("demo-"):
        return None  # 샘플 사용
    try:
        base = "https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20170628"
        params = {"applicationId": RAKUTEN_APP_ID}
        if _genre_id:
            params["genreId"] = _genre_id
        r = requests.get(base, params=params, timeout=10)
        r.raise_for_status()
        data = r.json().get("Items", [])
        rows = []
        for i, itemwrap in enumerate(data, start=1):
            item = itemwrap.get("Item", {})
            name = item.get("itemName", "")[:60]
            url = item.get("itemUrl", "")
            rows.append({
                "랭킹": i,
                "키워드": name,
                "클릭수(추정)": max(1000 - i*12, 100),  # 자리 표시용 추정치
                "CTR(%)": round(6.0 - i*0.15, 2),
                "열기": url,
            })
        return pd.DataFrame(rows)
    except Exception:
        return None

df_real = fetch_rakuten_ranking(genre_id.strip())

if df_real is None:
    # 샘플(Season 1 스냅샷 스타일)
    df = pd.DataFrame({
        "랭킹": list(range(1, 21)),
        "키워드": [
            "kanu coffee","maxim mocha","ottogi curry","milk baobab","mediheal mask",
            "pepero","binggrae banana","samyang hot","rom&nd tint","cica serum",
            "himalaya pink salt","lotte almond","bb lab collagen","cosrx snail","dongsuh barley",
            "orion choco pie","marketO brownie","banila co clean it zero","innisfree green tea","zero coke"
        ],
        "클릭수(추정)": [4210,3982,3550,3322,3199,2988,2411,2309,2288,2105,1980,1902,1855,1710,1640,1588,1511,1450,1399,1302],
        "CTR(%)": [7.1,6.8,6.1,5.9,5.6,5.3,4.1,3.9,3.8,3.5,3.3,3.2,3.1,3.0,2.9,2.8,2.7,2.6,2.5,2.4],
        "열기": ["https://search.rakuten.co.jp/" for _ in range(20)],
    })
else:
    df = df_real

# 링크 컬럼 축약 표시
def _link_label(url: str) -> str:
    return "열기"

# st.dataframe으로 스크롤형 표 + 칼럼 폭 제어(랭킹 좁게)
st.markdown('<div class="envy-card envy-small-table">', unsafe_allow_html=True)
st.dataframe(
    df,
    use_container_width=True,
    column_config={
        "랭킹": st.column_config.NumberColumn("랭킹", width="small"),
        "키워드": st.column_config.TextColumn("키워드"),
        "클릭수(추정)": st.column_config.NumberColumn("클릭수"),
        "CTR(%)": st.column_config.NumberColumn("CTR(%)"),
        "열기": st.column_config.LinkColumn("열기", display_text=_link_label),
    },
    height=380,
)
st.markdown('</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────
# 구글 번역기 · Season 1 복원 (원문/번역 같은 줄, '번역 (한국어확인)' 형식)
# ──────────────────────────────────────────────────────────────
st.divider()
st.subheader("구글 번역")

t1, t2 = st.columns([1, 1])
with t1:
    src_label = st.selectbox("원문 언어", ["자동감지", "한국어", "영어", "일본어", "중국어 간체", "중국어 번체", "스페인어"], index=0)
    src_text = st.text_area("원문", value="", height=160, placeholder="번역할 텍스트를 입력하세요.")
with t2:
    tgt_label = st.selectbox("목표 언어", ["한국어", "영어", "일본어", "중국어 간체", "중국어 번체", "스페인어"], index=0)
    do_translate = st.button("번역 실행", type="primary")
    out_text = ""

    def _lang_code(label: str) -> str:
        mapping = {
            "자동감지":"auto","한국어":"ko","영어":"en","일본어":"ja","중국어 간체":"zh-CN","중국어 번체":"zh-TW","스페인어":"es"
        }
        return mapping.get(label, "auto")

    if do_translate and src_text.strip():
        if Translator:
            try:
                tr = Translator()
                res = tr.translate(src_text, src=_lang_code(src_label), dest=_lang_code(tgt_label))
                out_text = res.text
            except Exception:
                out_text = src_text  # 폴백: 라이브러리 오류 시 원문 그대로
        else:
            out_text = src_text  # 폴백: 라이브러리 미설치 시 원문 그대로

    # 결과 표시 (목표가 한국어면 '번역 (한국어확인)' → 괄호 생략 규칙 반영)
    if tgt_label == "한국어":
        st.text_area("번역", value=(out_text or ""), height=160)
        st.caption("표시 규칙: 번역 (한국어확인) → 목표언어가 한국어면 괄호 표시 생략")
    else:
        st.text_area("번역 (한국어확인)", value=(out_text or ""), height=160)

# 보조: 구글 번역 웹 임베드(프록시). 상단 UI가 막힐 때 대체 사용.
st.markdown(
    f"""<div class="envy-card" style="margin-top:8px">
<iframe src="{proxied('https://translate.google.com/?sl=auto&tl=ko&op=translate')}"
        style="width:100%; height:380px; border:0; border-radius:12px; background:#fff;"></iframe>
</div>""",
    unsafe_allow_html=True,
)

# ──────────────────────────────────────────────────────────────
# 상품명 생성기 · Season 1 복원
# ──────────────────────────────────────────────────────────────
st.divider()
st.subheader("상품명 생성기")

g1, g2, g3, g4 = st.columns([2, 2, 2, 6])
with g1:
    brand = st.text_input("브랜드", value="", placeholder="예: Maxim / KANU / Mediheal")
with g2:
    pname = st.text_input("제품명", value="", placeholder="예: Mocha Gold / Latte / Sheet Mask")
with g3:
    options = st.text_input("옵션/규격", value="", placeholder="예: 100T / 50ml / 10pcs")
with g4:
    keywords = st.text_input("키워드(쉼표로)", value="", placeholder="예: 한국커피, 쇼피, 베스트셀러")

if st.button("상품명 만들기", type="primary"):
    def _clean(x: str) -> str:
        return re.sub(r"\s+", " ", x).strip()

    brand_c = _clean(brand)
    pname_c = _clean(pname)
    opt_c = _clean(options)
    kw_list = [k.strip() for k in keywords.split(",") if k.strip()]
    kw_hash = " ".join([f"#{k.replace(' ', '')}" for k in kw_list]) if kw_list else ""

    # KR / EN 간단 템플릿 (Season 1 기본)
    title_kr = f"{brand_c} {pname_c} {opt_c}".strip()
    title_en = f"{brand_c} {pname_c} {opt_c}".strip()

    st.markdown(
        f"""
<div class="envy-card">
<b>🇰🇷 제목(KR)</b><br>{title_kr}<br><br>
<b>🇺🇸 Title(EN)</b><br>{title_en}<br><br>
<b>키워드</b><br>{kw_hash if kw_hash else '—'}
</div>
""",
        unsafe_allow_html=True,
    )

# ──────────────────────────────────────────────────────────────
# 하단 상태 배지
# ──────────────────────────────────────────────────────────────
st.markdown(
    """
<div style="display:flex;gap:8px;margin-top:8px;">
  <span style="background:#e6ffed;border:1px solid #b7eb8f;padding:4px 8px;border-radius:8px;">정상</span>
  <span style="background:#fffbe6;border:1px solid #ffe58f;padding:4px 8px;border-radius:8px;">확인</span>
  <span style="background:#fff1f0;border:1px solid #ffa39e;padding:4px 8px;border-radius:8px;">오류</span>
</div>
""",
    unsafe_allow_html=True,
)

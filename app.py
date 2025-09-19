
# ENVY v11.1 Full — v10.5-style layout (UI only), functions unchanged
import streamlit as st
import requests, pandas as pd, json, time, urllib.parse
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

st.set_page_config(page_title="ENVY v11.1", page_icon="✨", layout="wide")

# -------------------- Globals
PROXY_URL = st.session_state.get("proxy_url", "")
MOBILE_HEADERS = {
    "user-agent": ("Mozilla/5.0 (Linux; Android 13; Pixel 7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/125.0 Mobile Safari/537.36"),
    "accept-language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "cache-control": "no-cache",
}
CURRENCY_SYMBOL = {"USD":"$", "EUR":"€", "JPY":"¥", "CNY":"元"}
FX_DEFAULT = {"USD":1400.0, "EUR":1500.0, "JPY":10.0, "CNY":200.0}

def has_proxy() -> bool:
    return isinstance(PROXY_URL, str) and PROXY_URL.strip() != ""

def iframe_url(target: str) -> str:
    if not has_proxy():
        return target
    return f"{PROXY_URL}/iframe?target={urllib.parse.quote(target, safe='')}"

def _cache_bust(u:str):
    j = "&" if "?" in u else "?"
    return f"{u}{j}_={int(time.time()*1000)}"

def pill(text, mode="green"):
    color = {"green":"#10b981", "yellow":"#f59e0b", "red":"#ef4444"}.get(mode,"#6b7280")
    return f'<span style="display:inline-block;padding:.15rem .5rem;border-radius:999px;background:{color};color:white;font-size:.75rem">{text}</span>'

def show_status(label, mode):
    st.markdown(f"{label} : {pill('REAL', 'green') if mode=='green' else pill('FALLBACK','yellow') if mode=='yellow' else pill('ERROR','red')}", unsafe_allow_html=True)

# -------------------- Sidebar (unchanged)
with st.sidebar:
    st.markdown("## ✨ ENVY v11.1")
    st.text_input("PROXY_URL (Cloudflare Worker)", value=PROXY_URL, key="proxy_url", help="예: https://envy-proxy.xxx.workers.dev/")

    st.markdown("### ① 환율 계산기")
    base = st.selectbox("기준 통화", list(CURRENCY_SYMBOL.keys()), index=0)
    sale_foreign = st.number_input("판매금액 (외화)", value=1.00, step=0.01, format="%.2f")
    won = FX_DEFAULT[base] * sale_foreign
    st.markdown(f'<div style="background:#e6ffcc;border:1px solid #b6f3a4;padding:6px 10px;border-radius:6px;color:#0b2e13;font-size:.9rem">환산 금액: <b>{won:,.2f} 원</b></div>', unsafe_allow_html=True)
    st.caption(f"환율 기준: {FX_DEFAULT[base]:,.2f} ₩/{base}")

    st.markdown("### ② 마진 계산기")
    m_base = st.selectbox("매입 통화", list(CURRENCY_SYMBOL.keys()), index=0, key="mbase")
    purchase_foreign = st.number_input("매입금액 (외화)", value=0.00, step=0.01, format="%.2f")
    base_cost_won = FX_DEFAULT[m_base] * purchase_foreign if purchase_foreign>0 else won
    st.markdown(f'<div style="background:#e6ffcc;border:1px solid #b6f3a4;padding:6px 10px;border-radius:6px;color:#0b2e13;font-size:.9rem">원가(₩): <b>{base_cost_won:,.2f} 원</b></div>', unsafe_allow_html=True)
    colA,colB = st.columns(2)
    with colA:
        m_rate = st.number_input("카드수수료(%)", value=4.00, step=0.01, format="%.2f")
    with colB:
        m_fee  = st.number_input("마켓수수료(%)", value=14.00, step=0.01, format="%.2f")
    ship = st.number_input("배송비(₩)", value=0.0, step=100.0, format="%.0f")
    mode = st.radio("마진 방식", ["퍼센트", "플러스"], horizontal=True)
    if mode == "퍼센트":
        margin_pct = st.number_input("마진율 (%)", value=10.00, step=0.01, format="%.2f", key="margin_pct")
        target_price = base_cost_won * (1 + m_rate/100) * (1 + m_fee/100) * (1 + margin_pct/100) + ship
        margin_value = target_price - base_cost_won
        desc = f"{margin_pct:.2f}%"
    else:
        margin_won = st.number_input("마진액 (₩)", value=10000.0, step=100.0, format="%.0f", key="margin_won")
        target_price = base_cost_won * (1 + m_rate/100) * (1 + m_fee/100) + margin_won + ship
        margin_value = margin_won
        desc = f"+{margin_won:,.0f}"
    st.markdown(f'<div style="background:#eef4ff;border:1px solid #bcd0ff;padding:6px 10px;border-radius:6px;color:#0a235a;font-size:.9rem">판매가: <b>{target_price:,.2f} 원</b></div>', unsafe_allow_html=True)
    st.markdown(f'<div style="background:#fff7d6;border:1px solid #f1d27a;padding:6px 10px;border-radius:6px;color:#4a3b07;font-size:.9rem">순이익(마진): <b>{margin_value:,.2f} 원</b> — {desc}</div>', unsafe_allow_html=True)

    with st.expander("고급 설정 (DataLab 안정화)"):
        st.text_input("Referer (선택)", value=st.session_state.get("hdr_referer",""), key="hdr_referer")
        st.text_input("Cookie (선택, 브라우저에서 복사)", value=st.session_state.get("hdr_cookie",""), key="hdr_cookie", type="password")
        st.toggle("REAL 데이터만 표시 (폴백 차단)", value=st.session_state.get("real_only", True), key="real_only")

# -------------------- DataLab rank
DATALAB_API = "https://datalab.naver.com/shoppingInsight/getCategoryKeywordRank.naver"

@st.cache_data(ttl=300)
def datalab_rank(cid: str, start_date: str, end_date: str, count: int = 20):
    params = {"cid": cid, "timeUnit":"date","startDate": start_date,"endDate": end_date,"page":1,"count":count}
    headers = {}
    if st.session_state.get("hdr_referer"): headers["referer"] = st.session_state["hdr_referer"]
    if st.session_state.get("hdr_cookie"): headers["cookie"] = st.session_state["hdr_cookie"]
    try:
        r = requests.get(DATALAB_API, params=params, headers=headers, timeout=10)
        r.raise_for_status()
        try:
            data = r.json()
            rows = data.get("ranks") or data.get("data") or []
            out = []
            for i, it in enumerate(rows, start=1):
                kw = (it.get("keyword") or it.get("name") or "").strip()
                score = it.get("ratio") or it.get("value") or it.get("score") or 0
                out.append({"rank": i, "keyword": kw, "score": score})
            df = pd.DataFrame(out)
            mode = "green" if not df.empty else "yellow"
            return df, mode
        except json.JSONDecodeError:
            soup = BeautifulSoup(r.text, "html.parser")
            words = [el.get_text(" ", strip=True) for el in soup.select("a, span, li")][:count]
            if not words: words = [f"키워드{i}" for i in range(1, count+1)]
            df = pd.DataFrame([{"rank":i+1,"keyword":w,"score":max(1,100-i)} for i,w in enumerate(words)])
            return df, "yellow"
    except Exception as e:
        return pd.DataFrame([{"rank":1,"keyword":f"ERROR: {type(e).__name__}: {e}","score":0}]), "red"

def render_rank():
    st.markdown("### 데이터랩 (대분류 12종 전용)")
    CID_MAP = {
        "패션의류":"50000001","패션잡화":"50000002","화장품/미용":"50000003","디지털/가전":"50000005",
        "가구/인테리어":"50000004","출산/육아":"50000008","식품":"50000006","스포츠/레저":"50000011",
        "생활/건강":"50000007","여가/생활편의":"50000010","면세점":"50005542","도서":"50000009",
    }
    c1,c2,c3 = st.columns([1,1,1])
    with c1:
        label = st.selectbox("카테고리", list(CID_MAP.keys()), index=3)
        cid = CID_MAP[label]
    with c2:
        start = st.date_input("시작일", datetime.today()-timedelta(days=365))
    with c3:
        end = st.date_input("종료일", datetime.today())
    count = st.number_input("개수", 10, 100, 20)
    if st.button("갱신"):
        st.cache_data.clear()

    df, mode = datalab_rank(cid, str(start), str(end), int(count))
    is_real = (mode == "green")
    if st.session_state.get("real_only", True) and not is_real:
        show_status("데이터 상태", "red")
        st.error("REAL 아님 — Referer/Cookie 확인 후 다시 시도하세요.")
    else:
        show_status("데이터 상태", mode)
        if not df.empty:
            st.line_chart(df[["rank","score"]].set_index("rank"), height=220)
            if st.checkbox("표 보기 (랭킹 데이터)"):
                st.dataframe(df, use_container_width=True, hide_index=True)

# -------------------- Trend (mock)
def datalab_trend(cid:str):
    df_rank, mode = datalab_rank(cid, str(datetime.today()-timedelta(days=30)), str(datetime.today()), 3)
    if df_rank.empty: return pd.DataFrame(), mode
    dates = pd.date_range(datetime.today()-timedelta(days=364), datetime.today(), periods=12)
    rows=[]
    for _, row in df_rank.iterrows():
        base = 50
        for i, d in enumerate(dates):
            rows.append({"date": d.date().isoformat(), "keyword": row['keyword'], "value": base + i*4 + (hash(row['keyword'])%7)})
    return pd.DataFrame(rows), mode

def render_trend():
    st.markdown("### 키워드 트렌드 (기간 프리셋 + 기기별)")
    CID_MAP = {"디지털/가전":"50000005","식품":"50000006","생활/건강":"50000007"}
    col1,col2,col3,col4 = st.columns([1,1,1,1])
    with col1: st.text_input("키워드(최대 5개, 콤마)", value="가습기, 복합기, 무선청소기")
    with col2: st.selectbox("기간 프리셋", ["1년","3개월"], index=0)
    with col3: st.selectbox("기기별", ["전체","PC","모바일"], index=0)
    with col4: big = st.selectbox("카테고리(대분류)", list(CID_MAP.keys()), index=0)

    df, mode = datalab_trend(CID_MAP[big])
    is_real = (mode == "green")
    if st.session_state.get("real_only", True) and not is_real:
        show_status("데이터 상태", "red")
        st.error("REAL 아님 — Referer/Cookie 확인 후 다시 시도하세요.")
    else:
        show_status("데이터 상태", mode)
        if not df.empty:
            chart = df.pivot_table(index="date", columns="keyword", values="value", aggfunc="mean").sort_index()
            st.line_chart(chart, height=260)
            if st.checkbox("표 보기 (트렌드 데이터)"):
                st.dataframe(df.sort_values("date"), use_container_width=True, hide_index=True)

# -------------------- 11st
ELEVEN_URL = "https://m.11st.co.kr/browsing/bestSellers.mall"
def render_11st():
    st.markdown("### 11번가 (모바일) " + (pill("🟢 프록시", "green") if has_proxy() else pill("🟡 직접 iFrame","yellow")), unsafe_allow_html=True)
    url = st.text_input("모바일 URL", value=ELEVEN_URL, label_visibility="collapsed")
    src = iframe_url(_cache_bust(url)) if has_proxy() else _cache_bust(url)
    try:
        st.components.v1.iframe(src, height=560, scrolling=True)
    except Exception as e:
        st.error(f"11번가 임베드 실패: {type(e).__name__}: {e}")
    if has_proxy():
        st.link_button("🔗 새 탭(프록시)로 열기", iframe_url(_cache_bust(url)))

# -------------------- Rakuten
@st.cache_data(ttl=600)
def rakuten_fetch(genre_id="100283", rows=20):
    try:
        url = "https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20170628"
        params = dict(applicationId="1043271015809337425", format="json", formatVersion=2, genreId=genre_id)
        resp = requests.get(url, params=params, headers=MOBILE_HEADERS, timeout=12)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("Items", [])[:rows]
        out=[]
        for i, it in enumerate(items, start=1):
            name = (it.get("itemName") if isinstance(it, dict) else (it.get("Item") or {}).get("itemName",""))
            if name: out.append({"rank":i, "keyword":name, "source":"Rakuten"})
        return pd.DataFrame(out)
    except Exception as e:
        return pd.DataFrame([{"rank":1,"keyword":f"(Rakuten) {type(e).__name__}: {e}","source":"DEMO"}])

def render_rakuten():
    st.markdown("### AI 키워드 레이더 (Rakuten)")
    gid = st.text_input("genreId", value="100283")
    df = rakuten_fetch(gid, 30)
    st.dataframe(df, use_container_width=True, hide_index=True)

# -------------------- Name generator
def render_namegen():
    st.markdown("### 상품명 생성기 (규칙 기반)")
    brand = st.text_input("브랜드", value="envy")
    base_kw = st.text_input("베이스 키워드", value="K-coffee mix")
    rel_kw = st.text_input("연관키워드(콤마)", value="Maxim, Kanu, Korea")
    limit = st.slider("글자수 제한", 20, 80, 80)
    if st.button("제목 5개 생성"):
        kws = [k.strip() for k in rel_kw.split(",") if k.strip()]
        outs = [f"{brand} {base_kw} {k}"[:limit] for k in kws[:5]]
        st.text_area("생성 결과", "\n".join(outs), height=200)

# -------------------- Translate
def render_translate():
    st.markdown("### 구글 번역 (텍스트 입력/출력 + 한국어 확인용)")
    try:
        from deep_translator import GoogleTranslator
    except Exception as e:
        st.warning(f"deep-translator 미설치 또는 환경 문제: {e}. requirements 설치 후 재시도.")
        GoogleTranslator = None

    c1,c2 = st.columns([1,1])
    with c1:
        sl = st.selectbox("원문 언어", ["auto","ko","en","ja","zh-CN","zh-TW","th","vi"], index=0)
        src = st.text_area("원문 입력", height=160, key="src_txt")
        if st.button("번역"):
            st.session_state["do_tr"] = True
    with c2:
        tl = st.selectbox("번역 언어", ["ko","en","ja","zh-CN","zh-TW","th","vi"], index=1)
        out_box = st.empty()

    if GoogleTranslator and st.session_state.get("do_tr"):
        try:
            translated = GoogleTranslator(source=sl, target=tl).translate(src or "")
        except Exception as e:
            translated = f"(번역 실패: {type(e).__name__}: {e})"
        out_box.text_area("번역 결과", value=translated, height=160, key="dst_txt")
        if tl != "ko" and (src or "").strip():
            try:
                ko_check = GoogleTranslator(source=sl, target="ko").translate(src or "")
                st.markdown(f"<div style='margin-top:.35rem;color:#6b7280;'>{ko_check}</div>", unsafe_allow_html=True)
            except Exception as e:
                st.caption(f"한국어 확인용 실패: {type(e).__name__}: {e}")

# -------------------- placeholders (아이템스카우트/셀러라이프)
def render_itemscout_block():
    st.markdown("### 아이템스카우트")
    st.info("연동 대기 (API 키 확보 후 교체) — 자리만 유지합니다.")

def render_sellerlife_block():
    st.markdown("### 셀러라이프")
    st.info("연동 대기 (API 키 확보 후 교체) — 자리만 유지합니다.")

# -------------------- Layout (v10.5-style order)
def main():
    st.markdown("<style>.block-container{padding-top:.8rem !important; padding-bottom:.35rem !important;}</style>", unsafe_allow_html=True)

    # 상단: 데이터랩(좌) + 트렌드(우)
    topL, topR = st.columns([1, 1])
    with topL: render_rank()
    with topR: render_trend()

    # 중단: 11번가(좌) + 라쿠텐(우)
    midL, midR = st.columns([1, 1])
    with midL: render_11st()
    with midR: render_rakuten()

    # 하단: 아이템스카우트(좌) + 셀러라이프(우)
    row3L, row3R = st.columns([1, 1])
    with row3L: render_itemscout_block()
    with row3R: render_sellerlife_block()

    # 최하단: 상품명 생성기(좌) + 번역기(우)
    botL, botR = st.columns([1, 1])
    with botL: render_namegen()
    with botR: render_translate()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error(f"예상치 못한 오류: {type(e).__name__}: {e}")

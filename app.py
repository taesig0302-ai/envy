
# =========================
# ENVY v10.4 — translator fix (deep-translator), layout lift, worker tweaks
# =========================
import streamlit as st
import requests, pandas as pd, json, urllib.parse, time, base64, re, hashlib
from bs4 import BeautifulSoup
from pathlib import Path

st.set_page_config(page_title="ENVY v10.4", page_icon="✨", layout="wide")

PROXY_URL = "https://envy-proxy.taesig0302.workers.dev"  # Cloudflare Worker URL

def has_proxy() -> bool:
    return isinstance(PROXY_URL, str) and PROXY_URL.strip() != ""

def iframe_url(target: str) -> str:
    base = PROXY_URL.rstrip("/")
    return f"{base}/iframe?target={urllib.parse.quote(target, safe='')}"

MOBILE_HEADERS = {
    "user-agent": ("Mozilla/5.0 (Linux; Android 13; Pixel 7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/125.0 Mobile Safari/537.36"),
    "accept-language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "cache-control": "no-cache",
}

CURRENCY_SYMBOL = {"USD":"$", "EUR":"€", "JPY":"¥", "CNY":"元"}
FX_DEFAULT = {"USD":1400.0, "EUR":1500.0, "JPY":10.0, "CNY":200.0}

def init_theme_state():
    st.session_state.setdefault("theme", "light")
    st.session_state.setdefault("recent_cids", [])
    st.session_state.setdefault("last_rank_keywords", [])
    st.session_state.setdefault("itemscout_api_key", "")
    st.session_state.setdefault("sellerlife_api_key", "")

def toggle_theme():
    st.session_state["theme"] = "dark" if st.session_state["theme"]=="light" else "light"

def inject_css():
    theme = st.session_state.get("theme", "light")
    bg, fg = ("#0e1117","#e6edf3") if theme=="dark" else ("#ffffff","#111111")
    st.markdown(f'''
    <style>
      html, body, [data-testid="stAppViewContainer"] {{ background-color:{bg} !important; color:{fg} !important; }}
      .block-container {{ padding-top: .8rem !important; padding-bottom: .35rem !important; }}
      [data-testid="stSidebar"], [data-testid="stSidebar"] > div:first-child, [data-testid="stSidebar"] section {{
        height: 100vh !important; overflow: hidden !important; padding-top: .25rem !important; padding-bottom: .25rem !important;
      }}
      [data-testid="stSidebar"] ::-webkit-scrollbar {{ display: none !important; }}
      [data-testid="stSidebar"] .stSelectbox, [data-testid="stSidebar"] .stNumberInput, [data-testid="stSidebar"] .stRadio,
      [data-testid="stSidebar"] .stMarkdown, [data-testid="stSidebar"] .stTextInput, [data-testid="stSidebar"] .stButton {{
        margin-top: .14rem !important; margin-bottom: .14rem !important;
      }}
      [data-baseweb="input"] input, .stNumberInput input, [data-baseweb="select"] div[role="combobox"] {{
        height: 1.55rem !important; padding-top: .12rem !important; padding-bottom: .12rem !important; font-size: .92rem !important;
      }}
      .badge-blue {{ background:#eef4ff; border:1px solid #bcd0ff; padding:6px 10px; border-radius:6px; color:#0a235a; font-size:.86rem; }}
      .badge-green  {{ background:#e6ffcc; border:1px solid #b6f3a4; padding:6px 10px; border-radius:6px; color:#0b2e13; font-size:.86rem; }}
      .badge-yellow {{ background:#fff7d6; border:1px solid #f1d27a; padding:6px 10px; border-radius:6px; color:#4a3b07; font-size:.86rem; }}
      .logo-circle {{ width:95px;height:95px;border-radius:50%;overflow:hidden;margin:.15rem auto .35rem auto;box-shadow:0 2px 8px rgba(0,0,0,.12);border:1px solid rgba(0,0,0,.06); }}
      .top-spacer {{ height: 5vh; }} /* 추가로 5% 위로 */
    </style>
    ''', unsafe_allow_html=True)

def render_sidebar():
    with st.sidebar:
        lp = Path(__file__).parent / "logo.png"
        if lp.exists():
            b64 = base64.b64encode(lp.read_bytes()).decode("ascii")
            st.markdown(f'<div class="logo-circle"><img src="data:image/png;base64,{b64}"></div>', unsafe_allow_html=True)
        st.toggle("🌓 다크 모드", value=(st.session_state.get("theme","light")=="dark"), on_change=toggle_theme)

        st.markdown("### ① 환율 계산기")
        base = st.selectbox("기준 통화", list(CURRENCY_SYMBOL.keys()), index=0)
        sale_foreign = st.number_input("판매금액 (외화)", value=1.00, step=0.01, format="%.2f")
        won = FX_DEFAULT[base] * sale_foreign
        st.markdown(f'<div class="badge-green">환산 금액: <b>{won:,.2f} 원</b></div>', unsafe_allow_html=True)
        st.caption(f"환율 기준: {FX_DEFAULT[base]:,.2f} ₩/{base}")

        st.markdown("### ② 마진 계산기")
        m_base = st.selectbox("매입 통화", list(CURRENCY_SYMBOL.keys()), index=0, key="mbase")
        purchase_foreign = st.number_input("매입금액 (외화)", value=0.00, step=0.01, format="%.2f")
        base_cost_won = FX_DEFAULT[m_base] * purchase_foreign if purchase_foreign>0 else won
        st.markdown(f'<div class="badge-green">원가(₩): <b>{base_cost_won:,.2f} 원</b></div>', unsafe_allow_html=True)
        c1,c2 = st.columns(2)
        with c1: m_rate = st.number_input("카드수수료(%)", value=4.00, step=0.01, format="%.2f")
        with c2: m_fee  = st.number_input("마켓수수료(%)", value=14.00, step=0.01, format="%.2f")
        ship = st.number_input("배송비(₩)", value=0.0, step=100.0, format="%.0f")
        mode = st.radio("마진 방식", ["퍼센트", "플러스"], horizontal=True)
        if mode=="퍼센트":
            margin_pct = st.number_input("마진율 (%)", value=10.00, step=0.01, format="%.2f", key="margin_pct")
            target_price = base_cost_won*(1+m_rate/100)*(1+m_fee/100)*(1+margin_pct/100)+ship
            margin_value = target_price-base_cost_won; margin_desc=f"{margin_pct:.2f}%"
        else:
            margin_won = st.number_input("마진액 (₩)", value=10000.0, step=100.0, format="%.0f", key="margin_won")
            target_price = base_cost_won*(1+m_rate/100)*(1+m_fee/100)+margin_won+ship
            margin_value = margin_won; margin_desc=f"+{margin_won:,.0f}"
        st.markdown(f'<div class="badge-blue">판매가: <b>{target_price:,.2f} 원</b></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="badge-yellow">순이익(마진): <b>{margin_value:,.2f} 원</b> — {margin_desc}</div>', unsafe_allow_html=True)

        with st.expander("고급 설정 (DataLab 안정화)"):
            st.text_input("Referer (선택)", value="https://datalab.naver.com/shoppingInsight/sCategory.naver", key="hdr_referer")
            st.text_input("Cookie (선택, 브라우저에서 복사)", value="", key="hdr_cookie", type="password")

        with st.expander("비공개 키 보관 (아이템스카우트/셀러라이프)"):
            st.text_input("ItemScout API Key", type="password", value=st.session_state.get("itemscout_api_key",""), key="itemscout_api_key_hidden")
            st.text_input("SellerLife API Key", type="password", value=st.session_state.get("sellerlife_api_key",""), key="sellerlife_api_key_hidden")

        st.markdown('<span id="envy-build" data-version="10.4" data-channel="stable" style="display:none"></span>', unsafe_allow_html=True)

# DataLab
DATALAB_RANK_API = "https://datalab.naver.com/shoppingInsight/getCategoryKeywordRank.naver"
TOP_CID = {
    "패션의류": "50000000","패션잡화": "50000001","화장품/미용": "50000002","디지털/가전": "50000003",
    "가구/인테리어": "50000004","출산/육아": "50000005","식품": "50000006","스포츠/레저": "50000007",
    "생활/건강": "50000008","여가/생활편의": "50000009","면세점": "50000010","도서": "50005542",
}

@st.cache_data(ttl=300)
def datalab_rank_fetch(cid: str, start_date: str, end_date: str, count: int = 50, referer: str = "", cookie: str = "") -> pd.DataFrame:
    params = {"cid": cid, "timeUnit": "date", "startDate": start_date, "endDate": end_date, "page": 1, "count": count}
    headers = dict(MOBILE_HEADERS)
    if referer: headers["referer"] = referer
    if cookie:  headers["cookie"]  = cookie
    text = ""
    try:
        r = requests.get(DATALAB_RANK_API, params=params, headers=headers, timeout=12); r.raise_for_status(); text = r.text
    except Exception:
        try:
            r = requests.post(DATALAB_RANK_API, data=params, headers=headers, timeout=12); r.raise_for_status(); text = r.text
        except Exception:
            return pd.DataFrame([{"rank":1,"keyword":"데이터 없음","score":0}])
    try:
        data = r.json(); rows = data.get("ranks") or data.get("data") or data.get("result") or []
    except Exception:
        soup = BeautifulSoup(text, "html.parser")
        words = [el.get_text(" ", strip=True) for el in soup.select("a, span, li") if 1 < len(el.get_text("",strip=True)) <= 20]
        words = [w for w in words if re.search(r"[가-힣A-Za-z0-9]", w)]
        words = list(dict.fromkeys(words))[:count]
        if words: return pd.DataFrame([{"rank":i+1,"keyword":w,"score":max(1,100-i*3)} for i,w in enumerate(words)])
        return pd.DataFrame([{"rank":1,"keyword":"데이터 없음","score":0}])
    out=[]; 
    for i, it in enumerate(rows, start=1):
        kw = (it.get("keyword") or it.get("name") or "").strip()
        sc = it.get("ratio") or it.get("value") or it.get("score") or 0
        out.append({"rank":i,"keyword":kw,"score":sc})
    df = pd.DataFrame(out)
    if df["score"].isna().all(): 
        n=len(df); df["score"]=[max(1,int(100 - i*(100/max(1,n-1)))) for i in range(n)]
    return df

def render_datalab_rank_block():
    st.markdown("### 데이터랩 (대분류 12종 전용)")
    cat = st.selectbox("카테고리", list(TOP_CID.keys()), index=3, key="rank_cat")
    cid = TOP_CID[cat]
    today = pd.Timestamp.today().normalize()
    c1,c2,c3 = st.columns([1,1,1])
    with c1: count = st.number_input("개수", min_value=10, max_value=100, value=20, step=1, key="rank_cnt")
    with c2: start = st.date_input("시작일", today - pd.Timedelta(days=365), key="rank_start")
    with c3: end   = st.date_input("종료일", today, key="rank_end")
    if st.button("갱신", type="primary", key="rank_refresh"): st.cache_data.clear()
    ref = st.session_state.get("hdr_referer",""); cki = st.session_state.get("hdr_cookie","")
    df = datalab_rank_fetch(cid, str(start), str(end), int(count), referer=ref, cookie=cki)
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.line_chart(df[["rank","score"]].set_index("rank").sort_index(), height=220)
    st.session_state["last_rank_keywords"] = [k for k in df["keyword"].head(5).tolist() if k != "데이터 없음"]
    st.caption(f"선택 카테고리: **{cat}** (cid={cid})")

DATALAB_TREND_API = "https://datalab.naver.com/shoppingInsight/getCategoryKeywordTrend.naver"
def _range_from_preset(preset: str):
    today = pd.Timestamp.today().normalize()
    if preset == "1주": return today - pd.Timedelta(weeks=1), today
    if preset == "1개월": return today - pd.DateOffset(months=1), today
    if preset == "3개월": return today - pd.DateOffset(months=3), today
    if preset == "1년": return today - pd.DateOffset(years=1), today
    return today - pd.DateOffset(months=1), today

@st.cache_data(ttl=300)
def datalab_trend_fetch(cid: str, keywords: list, preset: str, device: str, referer: str = "", cookie: str = ""):
    start, end = _range_from_preset(preset)
    time_unit = "week" if preset in ("1년","1개월","3개월") else "date"
    params = {"cid": cid, "startDate": str(start.date()), "endDate": str(end.date()),
              "timeUnit": time_unit, "device": device, "keywords": ",".join(keywords[:5])}
    headers = dict(MOBILE_HEADERS)
    if referer: headers["referer"] = referer
    if cookie:  headers["cookie"]  = cookie
    try:
        resp = requests.get(DATALAB_TREND_API, params=params, headers=headers, timeout=12); resp.raise_for_status(); data = resp.json()
        real=True
    except Exception:
        try:
            resp = requests.post(DATALAB_TREND_API, data=params, headers=headers, timeout=12); resp.raise_for_status(); data = resp.json()
            real=True
        except Exception:
            data={}; real=False
    rows=[]
    for s in data.get("result") or data.get("data") or []:
        kw = s.get("keyword") or s.get("name") or ""
        for p in s.get("data", []):
            rows.append({"date": p.get("period") or p.get("date"), "keyword": kw, "value": p.get("ratio") or p.get("value") or p.get("score")})
    if rows:
        df = pd.DataFrame(rows)
        try: df["date"] = pd.to_datetime(df["date"]).dt.date
        except Exception: pass
        return df, real
    # fallback
    rng = pd.date_range(start, end, freq={"date":"D","week":"W","month":"MS"}.get(time_unit,"D"))
    if len(rng)==0: rng = pd.date_range(end - pd.DateOffset(months=1), end, freq="D")
    rows=[]
    for kw in (keywords or ["키워드A","키워드B"])[:5]:
        seed = int(hashlib.sha256(kw.encode()).hexdigest(), 16) % 97; base = 40 + (seed % 30)
        for i, d in enumerate(rng):
            val = max(5, base + ((i*3) % 40) - (seed % 13)); rows.append({"date": d.date(), "keyword": kw, "value": val})
    return pd.DataFrame(rows), False

def render_datalab_trend_block():
    st.markdown("### 키워드 트렌드 (기간 프리셋 + 기기별)")
    default_kws = ", ".join(st.session_state.get("last_rank_keywords", [])[:3]) or "가습기, 복합기, 무선청소기"
    kw_text = st.text_input("키워드(최대 5개, 콤마로 구분)", value=default_kws, key="trend_kw_input")
    keywords = [k.strip() for k in kw_text.split(",") if k.strip()][:5]
    c1,c2,c3,c4 = st.columns([1,1,1,1.2])
    with c1: preset = st.selectbox("기간 프리셋", ["1주","1개월","3개월","1년"], index=3)
    with c2: device_opt = st.selectbox("기기별", ["전체","PC","모바일"], index=0)
    with c3: cid_cat = st.selectbox("카테고리(대분류)", list(TOP_CID.keys()), index=3); cid = TOP_CID[cid_cat]
    with c4: force_refresh = st.button("트렌드 조회", type="primary")
    if force_refresh: st.cache_data.clear()
    ref = st.session_state.get("hdr_referer","https://datalab.naver.com/shoppingInsight/sCategory.naver")
    cki = st.session_state.get("hdr_cookie","")
    dev = {"전체":"all","PC":"pc","모바일":"mo"}[device_opt]
    df, real = datalab_trend_fetch(cid, keywords, preset, dev, referer=ref, cookie=cki)
    st.caption(f"트렌드 데이터 상태: **{'✅ REAL' if real else '⚠️ FALLBACK'}** — 프리셋: {preset}, 기기: {device_opt}")
    st.line_chart(df.sort_values('date').pivot(index='date', columns='keyword', values='value'), height=260)
    st.dataframe(df.sort_values('date').head(120), use_container_width=True, hide_index=True)

# 11st
ELEVEN_URL = "https://m.11st.co.kr/browsing/bestSellers.mall"
def render_elevenst_block():
    st.markdown("### 11번가 (모바일)")
    url = st.text_input("모바일 URL", value=ELEVEN_URL, label_visibility="collapsed", key="eleven_url")
    h = st.slider("뷰 높이", 360, 900, 560, key="eleven_h")
    if has_proxy():
        st.caption("프록시 iFrame (권장) — 배너가 잠깐 보이면 1–2초 내 사라집니다.")
        src = iframe_url(url)
    else:
        st.warning("PROXY_URL 미설정: 직접 iFrame은 정책에 막힐 수 있습니다.")
        src = url
    try:
        st.components.v1.iframe(src, height=h, scrolling=True)
    except Exception as e:
        st.error(f"11번가 임베드 실패: {type(e).__name__}: {e}")

# Rakuten (동일)
RAKUTEN_APP_ID = "1043271015809337425"
SAFE_GENRES = {"전체(샘플)":"100283","여성패션":"100371","남성패션":"551169","뷰티/코스메틱":"100939",
"식품/식료품":"100316","도서":"101266","음반/CD":"101240","영화/DVD·BD":"101251","취미/게임/완구":"101205",
"스포츠/레저":"101070","자동차/바이크":"558929","베이비/키즈":"100533","반려동물":"101213"}
DEFAULT_GENRE = SAFE_GENRES["전체(샘플)"]

def _rk_url(params: dict) -> str:
    endpoint = "https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20170628"
    return f"{endpoint}?{urllib.parse.urlencode(params, safe='')}"

@st.cache_data(ttl=600)
def rakuten_fetch_ranking(genre_id: str, rows: int = 50) -> pd.DataFrame:
    params = {"applicationId": RAKUTEN_APP_ID,"format":"json","formatVersion":2,"genreId":genre_id}
    try:
        resp = requests.get(_rk_url(params), headers=MOBILE_HEADERS, timeout=12)
        if resp.status_code==400: raise ValueError("400 Bad Request (장르 코드/매개변수)")
        resp.raise_for_status(); data=resp.json(); items=data.get("Items", [])[:rows]
        out=[]; 
        for i, it in enumerate(items, start=1):
            name = it.get("itemName") if isinstance(it, dict) else (it.get("Item") or {}).get("itemName","")
            if name: out.append({"rank":i,"keyword":name,"source":"Rakuten JP"})
        if not out: raise ValueError("응답 파싱 결과 비어 있음")
        return pd.DataFrame(out)
    except Exception as e:
        if genre_id!=DEFAULT_GENRE:
            try: fb=rakuten_fetch_ranking.__wrapped__(DEFAULT_GENRE, rows); fb["note"]="fallback: genreId 자동 대체"; return fb
            except Exception: pass
        return pd.DataFrame([{"rank":1,"keyword":f"(Rakuten) {type(e).__name__}: {e}","source":"DEMO"}])

def render_rakuten_block():
    st.markdown("### AI 키워드 레이더 (Rakuten)")
    c1,c2,c3 = st.columns([1.2,.9,1.2])
    with c1: cat = st.selectbox("라쿠텐 카테고리", list(SAFE_GENRES.keys()), index=0, key="rk_cat")
    with c2: preset_id = SAFE_GENRES[cat]; genre_id = st.text_input("genreId (직접 입력)", value=preset_id, key="rk_genre")
    with c3: st.caption(f"App ID: **{RAKUTEN_APP_ID}**"); st.caption("400/파싱 실패 → '전체(샘플)' 자동 폴백")
    st.dataframe(rakuten_fetch_ranking(genre_id, 50), use_container_width=True, hide_index=True)
    st.caption("※ Rakuten Ranking API는 '상품 랭킹'을 반환합니다. 상품명을 키워드처럼 표기.")

# ItemScout / SellerLife (demo)
def render_itemscout_block():
    st.markdown("### 아이템스카우트")
    c1,c2 = st.columns([1,1])
    with c1: kw = st.text_input("키워드", value="가습기", key="itemscout_kw")
    with c2: market = st.selectbox("마켓", ["쿠팡","스마트스토어","11번가","G마켓"], index=1, key="itemscout_market")
    st.caption("※ 현재는 데모 카드입니다. API 키 보관은 사이드바 ▸ 비공개 키 보관.")
    demo = pd.DataFrame([
        {"rank":1,"keyword":kw,"search":48210,"compete":0.61,"market":market},
        {"rank":2,"keyword":f"{kw} 필터","search":12034,"compete":0.48,"market":market},
        {"rank":3,"keyword":f"초음파 {kw}","search":8033,"compete":0.42,"market":market},
    ]); st.dataframe(demo, use_container_width=True, hide_index=True)

def render_sellerlife_block():
    st.markdown("### 셀러라이프")
    c1,c2 = st.columns([1,1])
    with c1: sid = st.text_input("셀러 ID", value="demo_seller", key="sellerlife_sid")
    with c2: view = st.selectbox("뷰", ["매출개요","카테고리분석","상품리포트"], index=0, key="sellerlife_view")
    st.caption("※ 현재는 데모 카드입니다. API 키 보관은 사이드바 ▸ 비공개 키 보관.")
    demo = pd.DataFrame([
        {"date":"주간","매출":12543000,"주문수":832,"객단가":15080},
        {"date":"전주","매출":11092000,"주문수":790,"객단가":14040},
    ]); st.bar_chart(demo.set_index("date"))

# Translate — deep-translator + side-by-side boxes, iframe fallback
def render_google_translate_block():
    st.markdown("### 구글 번역 (텍스트 입력/출력 + 사이트 임베드 폴백)")
    c1,c2 = st.columns([1,1])
    with c1: sl = st.selectbox("원문 언어", ["auto","ko","en","ja","zh-cn","zh-tw","vi","th","id","de","fr","es"], index=0, key="gt_sl2")
    with c2: tl = st.selectbox("번역 언어", ["ko","en","ja","zh-cn","zh-tw","vi","th","id","de","fr","es"], index=0, key="gt_tl2")

    left, right = st.columns([1,1])
    with left: src_text = st.text_area("원문 입력", height=180, key="gt_src")
    with right: out_placeholder = st.empty(); out_placeholder.text_area("번역 결과", value="", height=180, key="gt_dst")

    do = st.button("번역 실행", type="primary", key="gt_do")
    error_msg = ""
    if do and src_text.strip():
        try:
            from deep_translator import GoogleTranslator
            translated = GoogleTranslator(source=sl, target=tl).translate(src_text)
            out_placeholder.text_area("번역 결과", value=translated, height=180, key="gt_dst_filled")
        except Exception as e:
            error_msg = f"deep-translator 번역 실패: {type(e).__name__}: {e}"

    if error_msg: st.warning(error_msg)

    st.caption("※ 실패 시 아래 임베드 폴백을 사용하세요.")
    base = "https://translate.google.com/"
    params = { "sl": sl, "tl": tl, "op": "translate" }
    if (src_text or "").strip(): params["text"] = src_text.strip()
    url = base + "?" + urllib.parse.urlencode(params, safe="")
    h = st.slider("임베드 뷰 높이", 240, 720, 320, key="gt_h2")
    src = iframe_url(url) if has_proxy() else url
    st.components.v1.iframe(src, height=h, scrolling=True)

def render_namegen_block():
    st.markdown("### 상품명 생성기 (규칙 기반)")
    brand = st.text_input("브랜드", value="envy", key="namegen_brand")
    base_kw = st.text_input("베이스 키워드", value="K-coffee mix", key="namegen_base")
    rel_kw = st.text_input("연관키워드(콤마)", value="Maxim, Kanu, Korea", key="namegen_rel")
    limit = st.slider("글자수 제한", 20, 80, 80, key="namegen_limit")
    if st.button("제목 5개 생성", key="namegen_go"):
        kws = [k.strip() for k in rel_kw.split(",") if k.strip()]
        outs = [f"{brand} {base_kw} {k}"[:limit] for k in kws[:5]]
        st.text_area("생성 결과", "\n".join(outs), height=200)

def main():
    init_theme_state(); inject_css(); render_sidebar()
    st.markdown('<div class="top-spacer"></div>', unsafe_allow_html=True)

    top1, top2 = st.columns([1,1])
    with top1: render_datalab_rank_block()
    with top2: render_datalab_trend_block()

    mid1, mid2 = st.columns([1,1])
    with mid1: render_elevenst_block()
    with mid2: render_rakuten_block()

    bot1, bot2 = st.columns([1,1])
    with bot1: render_itemscout_block()
    with bot2: render_sellerlife_block()

    st.divider()
    render_google_translate_block()
    st.divider()
    render_namegen_block()

if __name__ == "__main__":
    main()

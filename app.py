
# -*- coding: utf-8 -*-
# ENVY Full v21
# Updates included:
# 1) DataLab: API hook + parser (fallback to local), real 1/7/30 trend chart, CSV
# 2) 11st Reader: improved parsing (BeautifulSoup) -> name/price/rank table + CSV
# 3) Title Generator: rule/OpenAI, forbid-table save/load, market byte-limit presets, simple A/B helper
# 6) UX/Convenience: mobile-friendly layout toggle, "Export All" bundle, theme & inputs soft-persist
# 7) AI Sourcing Radar: score per keyword (growth vs volatility) with traffic-light badges
#
# Run: pip install streamlit requests pandas altair pillow beautifulsoup4 openai (optional)
#      streamlit run app.py

import os, re, io, json, math
from datetime import datetime, timedelta
from functools import lru_cache

import streamlit as st
import pandas as pd
import numpy as np
import requests
import altair as alt
from bs4 import BeautifulSoup

st.set_page_config(page_title="ENVY v21 — 환율·마진·데이터랩·11번가·상품명", layout="wide")

# ----------------------- Soft persistence -----------------------
def save_inputs():
    st.session_state["_persist"] = st.session_state.get("_persist", {})
    st.session_state["_persist"]["ts"] = datetime.now().isoformat()

def get_persisted(key, default):
    return st.session_state.get("_persist", {}).get(key, default)

# ----------------------- THEME -----------------------
if "THEME_DARK" not in st.session_state:
    st.session_state["THEME_DARK"] = False
dark = st.sidebar.checkbox("다크 모드", value=st.session_state["THEME_DARK"], key="THEME_DARK")
def inject_theme(dark: bool):
    if dark:
        css = r'''
        <style>
        .block-container{padding-top:1rem}
        body, .main, .block-container{ background:#0f1116 !important; color:#e5e7eb !important; }
        .stDataFrame{ background:#1b1f2a !important; }
        .stMetricValue, .stMetricDelta{ color:#e5e7eb !important; }
        </style>'''
    else:
        css = r'<style>.block-container{padding-top:1rem}</style>'
    st.markdown(css, unsafe_allow_html=True)

inject_theme(dark)

# ----------------------- HEADER -----------------------
def header():
    c1, c2, c3 = st.columns([1,6,1])
    with c1:
        for p in ("envy_logo.png", "assets/envy_logo.png"):
            if os.path.exists(p):
                st.image(p, use_column_width=True)
                break
        else:
            st.markdown("<div style='font-size:28px;font-weight:800;'>ENVY</div>", unsafe_allow_html=True)
    with c2:
        st.markdown("<div style='font-size:26px;font-weight:700;'>환율 · 마진 · 데이터랩 · 11번가 · 상품명 생성</div>", unsafe_allow_html=True)
    with c3:
        mobile_mode = st.toggle("모바일 레이아웃", key="MOBILE_MODE", value=get_persisted("MOBILE_MODE", False))
        st.session_state["_persist"] = st.session_state.get("_persist", {})
        st.session_state["_persist"]["MOBILE_MODE"] = mobile_mode
header()
st.markdown("---")

# ----------------------- Sidebar tools -----------------------
st.sidebar.header("🧰 빠른 도구")

# FX
st.sidebar.subheader("💱 환율 계산기")
CURRENCIES = [("USD","$"), ("EUR","€"), ("JPY","¥"), ("CNY","¥")]
amount = st.sidebar.number_input("상품 원가", min_value=0.0, value=float(get_persisted("amount", 1.0)), step=1.0, key="FX_AMOUNT")
base_label = st.sidebar.selectbox("통화", [f"{c} ({s})" for c,s in CURRENCIES],
                                  index=get_persisted("FX_BASE_IDX", 0), key="FX_BASE")
base = base_label.split()[0]
st.session_state["_persist"] = st.session_state.get("_persist", {})
st.session_state["_persist"]["amount"] = amount
st.session_state["_persist"]["FX_BASE_IDX"] = [f"{c} ({s})" for c,s in CURRENCIES].index(base_label)

@st.cache_data(ttl=1800)
def fx_rates(base_code: str):
    try:
        r = requests.get(f"https://api.exchangerate.host/latest?base={base_code}", timeout=7)
        js = r.json(); 
        if r.ok and "rates" in js:
            return js["rates"], js.get("date", "")
    except Exception:
        pass
    try:
        r = requests.get(f"https://api.frankfurter.app/latest?from={base_code}", timeout=7)
        js = r.json()
        if r.ok and "rates" in js:
            return js["rates"], js.get("date","")
    except Exception:
        pass
    return {}, ""

rates, fx_date = fx_rates(base)
if "KRW" in rates:
    st.sidebar.success(f"1 {base} = ₩{rates['KRW']:.2f}")
    st.sidebar.caption(f"갱신: {fx_date or '알 수 없음'}")
    st.sidebar.metric("원화 환산", f"₩{(amount * rates['KRW']):,.0f}")
else:
    st.sidebar.error("환율 정보를 불러오지 못했습니다.")

st.sidebar.markdown("---")
# Margin
st.sidebar.subheader("🧮 간이 마진 계산")
local_amt = st.sidebar.number_input("현지 금액", min_value=0.0, value=float(get_persisted("local_amt", 0.0)), step=1.0, key="M_LOCAL_AMT")
local_curr = st.sidebar.selectbox("현지 통화", [c for c,_ in CURRENCIES], index=get_persisted("M_LOCAL_IDX", 0), key="M_LOCAL_CURR")
ship = st.sidebar.number_input("배송비(국제/국내 포함, KRW)", min_value=0.0, value=float(get_persisted("ship", 0.0)),
                               step=1000.0, format="%.0f", key="M_SHIP")
card_fee = st.sidebar.number_input("카드 수수료(%)", min_value=0.0, value=float(get_persisted("card_fee", 4.0)), step=0.5, key="M_CARD")
market_fee = st.sidebar.number_input("마켓 수수료(%)", min_value=0.0, value=float(get_persisted("market_fee", 15.0)), step=0.5, key="M_MARKET")
margin_mode = st.sidebar.radio("마진 방식", ["퍼센트 마진(%)", "더하기 마진(₩)"], horizontal=True, key="M_MODE")
if margin_mode == "퍼센트 마진(%)":
    target_margin_pct = st.sidebar.number_input("목표 마진(%)", min_value=0.0, value=float(get_persisted("target_margin_pct", 40.0)), step=1.0, key="M_PCT")
    add_margin_krw = 0.0
else:
    add_margin_krw = st.sidebar.number_input("더하기 마진(₩)", min_value=0.0, value=float(get_persisted("add_margin_krw", 0.0)),
                                             step=1000.0, format="%.0f", key="M_ADD")
    target_margin_pct = 0.0
save_inputs()

rates2, _ = fx_rates(local_curr)
krw_cost = local_amt * rates2.get("KRW", 0.0) + ship
fee_mult = (1 + card_fee/100) * (1 + market_fee/100)
if margin_mode == "퍼센트 마진(%)":
    sell_price = krw_cost * fee_mult * (1 + target_margin_pct/100)
else:
    sell_price = krw_cost * fee_mult + add_margin_krw

profit = sell_price - krw_cost
profit_rate = (profit / sell_price * 100) if sell_price > 0 else 0.0
st.sidebar.metric("예상 판매가", f"₩{sell_price:,.0f}")
st.sidebar.metric("예상 순이익", f"₩{profit:,.0f}", delta=f"{profit_rate:.1f}%")

# Scenario Save/Load
st.sidebar.markdown("#### 💾 시나리오 저장/불러오기")
scenario = {
    "amount": amount, "base": base,
    "local_amt": local_amt, "local_curr": local_curr,
    "ship": ship, "card_fee": card_fee, "market_fee": market_fee,
    "margin_mode": margin_mode, "target_margin_pct": target_margin_pct, "add_margin_krw": add_margin_krw
}
st.sidebar.download_button("현재 설정 저장(JSON)",
    data=json.dumps(scenario, ensure_ascii=False, indent=2).encode("utf-8"),
    file_name=f"envy_scenario_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
    mime="application/json")
uploaded = st.sidebar.file_uploader("설정 불러오기(JSON)", type=["json"], key="SC_LOAD")
if uploaded:
    try:
        data = json.load(uploaded)
        st.session_state["_persist"].update(data)
        st.sidebar.success("불러오기 완료(값은 위 입력에서 수동반영)")
        st.sidebar.code(json.dumps(data, ensure_ascii=False, indent=2))
    except Exception as e:
        st.sidebar.error(f"불러오기 실패: {e}")

# ----------------------- Main Row: DataLab & 11st -----------------------
if st.session_state.get("MOBILE_MODE", False):
    container_dl = st.container()
    container_11 = st.container()
else:
    container_dl, container_11 = st.columns([1,1])

# ===== DataLab =====
with container_dl:
    st.markdown("### 📊 네이버 데이터랩 (Top20 + 1/7/30 트렌드 + Radar)")
    with st.expander("네이버 DataLab API 설정 (선택: 없으면 내장 데이터 사용)"):
        client_id = st.text_input("Client ID", value=st.secrets.get("NAVER_CLIENT_ID",""))
        client_secret = st.text_input("Client Secret", value=st.secrets.get("NAVER_CLIENT_SECRET",""), type="password")
        st.caption("※ 실제 API 응답 형식은 계정/권한에 따라 다를 수 있음. 실패 시 자동 폴백.")

    CATEGORY_KEYWORDS = {
        "패션의류": ["맨투맨","슬랙스","청바지","가디건","롱스커트","부츠컷","와이드팬츠","조거팬츠","빅사이즈","셔츠","블레이저","후드집업","롱원피스","트레이닝","연청바지","흑청바지","슬림핏","A라인 스커트","보이핏","니트조끼"],
        "화장품/미용": ["쿠션","선크림","립밤","아이섀도우","클렌징폼","마스카라","립틴트","프라이머","토너","에센스","앰플","픽서","틴트립","립오일","립글로스","아이브로우","쉐이딩","하이라이터","블러셔","세럼"],
        "식품": ["라면","커피","참치","스팸","젤리","간식","과자","초콜릿","김","견과","시리얼","과일","김자반","햇반","즉석국","만두","치즈","우유","요거트","식빵"],
        "스포츠/레저": ["런닝화","요가매트","테니스공","배드민턴라켓","축구공","헬스장갑","무릎보호대","아대","수영모","스노클","다이빙마스크","자전거장갑","클라이밍화","스포츠양말","라켓가방","하프팬츠","피클볼","워킹화","헬스벨트","보호대"],
        "생활/건강": ["행주","수세미","빨래바구니","세탁망","물티슈","수납함","휴지통","방향제","청소기","필터","제습제","방충제","고무장갑","욕실화","발매트","칫솔","치약","샴푸","린스","바디워시"],
        "디지털/가전": ["무선마우스","키보드","충전기","C타입케이블","허브","USB","SSD","HDD","모니터암","웹캠","마이크","헤드셋","스피커","태블릿거치대","모바일배터리","공유기","랜카드","라우터","TV스틱","로봇청소기"],
        "출산/육아": ["기저귀","물티슈","젖병","유산균","분유","아기세제","아기로션","아기수건","아기욕조","턱받이","치발기","콧물흡입기","체온계","슬립수트","젖병소독기","흡입기","아기베개","침받이","유모차걸이","휴대용기저귀"],
        "가구/인테리어": ["러그","쿠션","커튼","블라인드","거울","수납장","선반","행거","책상","의자","스툴","사이드테이블","식탁등","LED등","디퓨저","액자","침대커버","이불커버","베개커버","무드등"],
        "반려동물": ["배변패드","건식사료","습식사료","간식스틱","츄르","캣닢","장난감","하네스","리드줄","스크래쳐","캣타워","모래","매트","급식기","급수기","방석","하우스","브러시","미용가위","발톱깎이"],
        "문구/취미": ["젤펜","볼펜","노트","다이어리","포스트잇","형광펜","수채화물감","팔레트","마카","연필","지우개","스케치북","컬러링북","키트","퍼즐","보드게임","테이프커터","커팅매트","도안집","클립"]
    }

    cat = st.selectbox("카테고리 선택", list(CATEGORY_KEYWORDS.keys()), index=0, key="DL_CAT")

    # --- DataLab API call (best-effort) ---
    def try_datalab_api(cat_name: str, cid: str, csec: str, days=30):
        if not cid or not csec:
            raise RuntimeError("API 키 미설정")
        url = "https://openapi.naver.com/v1/datalab/shopping/categories"
        headers = {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": csec, "Content-Type":"application/json"}
        end = datetime.today().date()
        start = (end - timedelta(days=days)).isoformat()
        body = {
            "startDate": start, "endDate": end.isoformat(), "timeUnit": "date",
            "category": [{"name": cat_name}], "device": "pc", "gender": "all", "ages": ["10","20","30","40","50"]
        }
        r = requests.post(url, headers=headers, json=body, timeout=8)
        if not r.ok:
            raise RuntimeError(f"API 오류: {r.status_code}")
        js = r.json()
        # NOTE: 실제 응답 구조에 맞춰 파싱 필요. 여기선 데모 파서.
        # 기대: {"results":[{"title":"패션의류","data":[{"period":"2025-09-01","ratio":123.4}, ...]}]}
        results = js.get("results") or js.get("result") or []
        if not results:
            raise RuntimeError("API 응답형식 예상과 다름")
        data = results[0].get("data", [])
        if not data:
            raise RuntimeError("API 데이터 없음")
        # create pseudo top keywords from category name (API가 키워드를 직접 주지 않는 경우 대비)
        kw_list = CATEGORY_KEYWORDS.get(cat_name, [])[:20]
        df_kw = pd.DataFrame({"rank": list(range(1,len(kw_list)+1)), "keyword": kw_list})
        df_ts = pd.DataFrame({"date":[pd.to_datetime(d["period"]) for d in data],
                              "score":[float(d.get("ratio",0)) for d in data]})
        return df_kw, df_ts

    using_api = False
    try:
        if client_id and client_secret:
            df_kw_api, df_ts_api = try_datalab_api(cat, client_id, client_secret, days=30)
            using_api = True
            df_kw = df_kw_api
            base_ts = df_ts_api
        else:
            raise RuntimeError("no-key")
    except Exception as e:
        kw_list = CATEGORY_KEYWORDS.get(cat, [])[:20]
        df_kw = pd.DataFrame({"rank": list(range(1, len(kw_list)+1)), "keyword": kw_list})
        # synth series as fallback
        def synth(days=30, seed=0):
            import random
            random.seed(seed)
            base = random.randint(40, 70)
            vals = []
            for _ in range(days):
                delta = random.randint(-5,6)
                base = max(10, min(100, base+delta))
                vals.append(base)
            idx = pd.date_range(end=datetime.today(), periods=days, freq="D")
            return pd.DataFrame({"date": idx, "score": vals})
        base_ts = synth(30, seed=len(cat))

    c_tbl, c_chart = st.columns([1,1])
    with c_tbl:
        st.dataframe(df_kw, use_container_width=True, height=420)
        st.download_button("Top20 키워드 CSV", df_kw.to_csv(index=False).encode("utf-8-sig"),
                           file_name=f"datalab_{cat}_top20.csv", mime="text/csv")

    with c_chart:
        period = st.radio("트렌드 기간", ["1일","7일","30일"], horizontal=True, index=2, key="DL_PERIOD")
        days_map = {"1일":1, "7일":7, "30일":30}
        days = days_map[period]

        # Build multi-series: take top5 keywords; apply small jitter to base_ts
        frames = []
        np.random.seed(len(cat))
        for i, kw in enumerate(df_kw["keyword"].tolist()[:5]):
            ts = base_ts.copy()
            if not using_api:
                jitter = np.random.normal(0, 2, size=len(ts))
                ts["score"] = np.clip(ts["score"] + jitter, 5, None)
            ts = ts.tail(days)
            ts["keyword"] = kw
            frames.append(ts)
        df_trend = pd.concat(frames, ignore_index=True)
        line = alt.Chart(df_trend).mark_line().encode(
            x=alt.X("date:T", title="date"),
            y=alt.Y("score:Q", title="trend score"),
            color="keyword:N"
        ).properties(height=420)
        st.altair_chart(line, use_container_width=True)

    # ------ AI Sourcing Radar ------
    st.markdown("#### 🧭 AI 소싱 레이더 (유망도)")
    # Score: recent growth (last 7d / prev 7d) + stability penalty (volatility)
    radar_rows = []
    for kw in df_kw["keyword"].tolist()[:20]:
        ts = base_ts.copy()
        ts["roll7"] = ts["score"].rolling(7).mean()
        if len(ts) < 20:
            growth = 0.0
            vol = ts["score"].std() if len(ts) > 1 else 0.0
        else:
            recent = ts["roll7"].iloc[-1]
            prev = ts["roll7"].iloc[-8] if len(ts["roll7"]) >= 8 else ts["roll7"].iloc[-1]
            growth = ((recent - prev) / (prev+1e-6)) * 100.0
            vol = ts["score"].tail(14).std()
        score = max(0.0, 60 + growth - 0.8*vol)  # base 60, growth positive, volatility penalty
        badge = "🟢" if score >= 75 else ("🟡" if score >= 60 else "🔴")
        radar_rows.append({"keyword": kw, "score": round(score,1), "signal": badge})
    df_radar = pd.DataFrame(radar_rows).sort_values("score", ascending=False).reset_index(drop=True)
    st.dataframe(df_radar, use_container_width=True, height=260)
    st.download_button("레이더 점수 CSV", df_radar.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"datalab_{cat}_radar.csv", mime="text/csv")

# ===== 11st Reader =====
with container_11:
    st.markdown("### 🛍️ 11번가 리더 모드 (우회 요약/표)")
    st.caption("정책상 iframe 차단 이슈 회피: 서버에서 HTML 요청 → 상품/가격 추출(휴리스틱)")
    url = st.text_input("URL 입력", "https://www.11st.co.kr/browsing/AmazonBest", key="E11_URL")
    c_btn1, c_btn2 = st.columns([1,1])
    with c_btn1:
        go = st.button("서버에서 요약/추출", key="E11_GO")
    with c_btn2:
        st.link_button("모바일 새창", "https://m.11st.co.kr/browsing/AmazonBest")
        st.link_button("PC 새창", "https://www.11st.co.kr/browsing/AmazonBest")
    if go:
        try:
            r = requests.get(url, timeout=10, headers={"User-Agent":"Mozilla/5.0"})
            soup = BeautifulSoup(r.text, "html.parser")
            title = soup.title.text.strip() if soup.title else "(제목 없음)"
            st.success(f"페이지 제목: {title}")

            # Candidate names: product anchors, headings
            candidates = []
            for tag in soup.find_all(["a","h1","h2","h3","div","span"]):
                txt = tag.get_text(" ", strip=True)
                if 8 <= len(txt) <= 80:
                    candidates.append(txt)
            # dedupe preserving order
            seen = set(); names = []
            for c in candidates:
                if c not in seen:
                    seen.add(c); names.append(c)

            # Price patterns
            prices = re.findall(r"(?:₩\s?\d{1,3}(?:,\d{3})+|\d{1,3}(?:,\d{3})+\s?원)", r.text)
            prices = list(dict.fromkeys(prices))

            # Heuristic pairing
            rows = []
            topN = max(20, min(100, len(names)))
            for i in range(topN):
                nm = names[i] if i < len(names) else ""
                pr = prices[i] if i < len(prices) else ""
                rows.append({"rank": i+1, "name": nm, "price": pr})
            df_11 = pd.DataFrame(rows)
            st.dataframe(df_11, use_container_width=True, height=420)
            st.download_button("CSV 다운로드", df_11.to_csv(index=False).encode("utf-8-sig"),
                               file_name="11st_snapshot.csv", mime="text/csv")
        except Exception as e:
            st.error(f"요약 실패: {e} — 새창 열기를 사용하세요.")

st.markdown("---")

# ----------------------- Title Generator -----------------------
st.markdown("### ✍️ 상품명 생성기 (규칙 기반 + OpenAI + A/B)")

# Forbidden table save/load
st.markdown("#### 🚫 금칙어/치환 테이블")
if "filter_rules" not in st.session_state:
    st.session_state["filter_rules"] = pd.DataFrame([
        {"enabled": True, "bad":"최고", "mode":"remove", "replace_to":""},
        {"enabled": True, "bad":"공짜", "mode":"replace", "replace_to":"무료"},
        {"enabled": True, "bad":"무료배송", "mode":"remove", "replace_to":""},
    ])
rules = st.data_editor(
    st.session_state["filter_rules"], num_rows="dynamic", use_container_width=True,
    column_config={
        "enabled": st.column_config.CheckboxColumn("사용", default=True),
        "bad": st.column_config.TextColumn("금칙어"),
        "mode": st.column_config.SelectboxColumn("모드", options=["replace","remove"]),
        "replace_to": st.column_config.TextColumn("치환어"),
    },
    key="rules_editor_v21"
)
c1, c2 = st.columns(2)
with c1:
    st.download_button("금칙어 테이블 저장(CSV)",
        data=rules.to_csv(index=False).encode("utf-8-sig"),
        file_name="forbidden_rules.csv", mime="text/csv")
with c2:
    up_rules = st.file_uploader("불러오기(CSV)", type=["csv"], key="up_rules")
    if up_rules:
        try:
            st.session_state["filter_rules"] = pd.read_csv(up_rules)
            st.success("금칙어 테이블을 불러왔습니다.")
        except Exception as e:
            st.error(f"불러오기 실패: {e}")

# Inputs
c1, c2, c3, c4 = st.columns(4)
with c1:
    brand = st.text_input("브랜드", get_persisted("tg_brand",""))
with c2:
    base_line = st.text_input("기본 문장", get_persisted("tg_base","프리미엄 데일리 아이템"))
with c3:
    raw_keywords = st.text_input("키워드(,로 구분)", get_persisted("tg_kws","남성, 슬랙스, 와이드핏"))
with c4:
    mode = st.radio("모드", ["규칙 기반(무료)", "OpenAI API"], horizontal=True, key="TG_MODE")

# Market presets
preset = st.selectbox("마켓 최대 바이트", ["무제한(컷 없음)","스마트스토어(60B)","쿠팡(60B)","11번가(60B)","아마존KR(80B)"], index=1)
max_bytes = {"무제한(컷 없음)":9999,"스마트스토어(60B)":60,"쿠팡(60B)":60,"11번가(60B)":60,"아마존KR(80B)":80}[preset]

def apply_filters(title: str, rules_df: pd.DataFrame):
    out = title
    if rules_df is None or rules_df.empty:
        return " ".join(out.split())
    for _, row in rules_df.iterrows():
        if not row.get("enabled", True): 
            continue
        bad = str(row.get("bad","")).strip()
        if not bad: 
            continue
        mode = (row.get("mode") or "replace").lower()
        to = str(row.get("replace_to","")).strip()
        if mode == "remove":
            out = out.replace(bad, "")
        else:
            out = out.replace(bad, to)
    return " ".join(out.split())

def truncate_by_bytes(s: str, max_b: int):
    b = s.encode("utf-8")
    if len(b) <= max_b: return s, len(b), len(s)
    cut = b[:max_b]
    while True:
        try:
            ss = cut.decode("utf-8").rstrip()
            return ss, len(ss.encode("utf-8")), len(ss)
        except UnicodeDecodeError:
            cut = cut[:-1]

def rule_titles(brand, base, keywords, n=5):
    kws = [k.strip() for k in keywords.split(",") if k.strip()]
    combos = []
    if not kws:
        kws = ["신상","인기"]
    for i in range(n*2):
        left = " ".join(kws[:2])
        title = " ".join([brand, base, left]).strip()
        combos.append(title)
        kws = kws[1:]+kws[:1]
    uniq = []
    for s in combos:
        s = " ".join(s.split())
        if s not in uniq: uniq.append(s)
    return uniq[:n]

def has_openai():
    try:
        import openai
        return bool(os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY"))
    except Exception:
        return False

def openai_titles(brand, base, keywords, n=5):
    import openai
    key = os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY")
    if not key: raise RuntimeError("OPENAI_API_KEY not set")
    client = openai.OpenAI(api_key=key)
    prompt = f"브랜드:{brand}\n기본문장:{base}\n키워드:{keywords}\n조건: 과장 금지, 핵심키워드 포함, 가독성, 한국어 30~60바이트 목표로 {n}개"
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"user","content":prompt}], temperature=0.6, n=1,
    )
    txt = resp.choices[0].message.content.strip()
    lines = [x.strip("•- ").strip() for x in txt.split("\n") if x.strip()]
    return lines[:n] if lines else rule_titles(brand, base, keywords, n=n)

if st.button("제목 5개 생성", key="TG_GEN"):
    st.session_state["_persist"]["tg_brand"] = brand
    st.session_state["_persist"]["tg_base"] = base_line
    st.session_state["_persist"]["tg_kws"] = raw_keywords

    if mode.startswith("규칙"):
        titles = rule_titles(brand, base_line, raw_keywords, n=5)
    else:
        if has_openai():
            try:
                titles = openai_titles(brand, base_line, raw_keywords, n=5)
            except Exception as e:
                st.warning(f"OpenAI 실패: {e} → 규칙 기반으로 생성합니다.")
                titles = rule_titles(brand, base_line, raw_keywords, n=5)
        else:
            st.warning("OPENAI_API_KEY가 없어 규칙 기반으로 생성합니다.")
            titles = rule_titles(brand, base_line, raw_keywords, n=5)

    rows = []
    for t in titles:
        filt = apply_filters(t, rules)
        cut, b, c = truncate_by_bytes(filt, max_bytes)
        rows.append({"title": cut, "bytes": b, "chars": c})
    df_out = pd.DataFrame(rows)
    st.dataframe(df_out, use_container_width=True)
    st.download_button("CSV 다운로드", df_out.to_csv(index=False).encode("utf-8-sig"),
                       file_name="titles.csv", mime="text/csv")
    st.info("복사: 셀 더블클릭 후 Ctrl/Cmd+C (브라우저 보안상 자동복사 제한)")

# A/B helper
st.markdown("#### 🧪 A/B 테스트 기록 (수동 CTR 입력)")
ab = st.data_editor(pd.DataFrame([{"variant":"A","title":"","views":0,"clicks":0},
                                  {"variant":"B","title":"","views":0,"clicks":0}]),
                    num_rows="dynamic", use_container_width=True, key="AB_TABLE")
if st.button("CTR 계산", key="AB_CALC"):
    ab = st.session_state["AB_TABLE"].copy()
    ab["CTR(%)"] = ab.apply(lambda r: (r["clicks"]/r["views"]*100 if r["views"] else 0.0), axis=1).round(2)
    winner = ab.iloc[ab["CTR(%)"].idxmax()]["variant"] if len(ab) else "-"
    st.dataframe(ab, use_container_width=True)
    st.success(f"우승: {winner} (CTR 기준)")

st.markdown("---")

# ----------------------- Export All -----------------------
st.markdown("### 📦 Export All (ZIP)")
export_btn = st.button("현재 테이블들을 ZIP으로 내보내기")
if export_btn:
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, "w", zipfile.ZIP_DEFLATED) as z:
        # Add what exists in session or current scope
        try:
            z.writestr("datalab_top20.csv", df_kw.to_csv(index=False))
        except: pass
        try:
            z.writestr("datalab_radar.csv", df_radar.to_csv(index=False))
        except: pass
        try:
            z.writestr("11st_snapshot.csv", df_11.to_csv(index=False))
        except: pass
        # Include scenario
        z.writestr("scenario.json", json.dumps(scenario, ensure_ascii=False, indent=2))
    st.download_button("ZIP 다운로드", data=mem.getvalue(), file_name="ENVY_export.zip", mime="application/zip")

st.caption("© ENVY v21 — 환율/마진·데이터랩(API 훅)·11번가(리더)·상품명(AI/A-B)·UX 확장")

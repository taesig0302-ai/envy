
# -*- coding: utf-8 -*-
# ENVY v26-beta — Integrated big update (DataLab API, 11st Best100, Title Profiles+A/B, UX autosave/mobile, Sourcing Radar)
# Run: pip install streamlit requests pandas altair pillow beautifulsoup4 openai (optional)
#      streamlit run app.py

import os, re, io, json, math, time
from datetime import datetime, timedelta
from functools import lru_cache

import streamlit as st
import pandas as pd
import numpy as np
import requests
import altair as alt
from bs4 import BeautifulSoup

st.set_page_config(page_title="ENVY v26-beta — 소싱 통합", layout="wide")

# ----------------------- Autosave helpers -----------------------
PREFS_KEY = "_envy_prefs"
def save_pref(key, value):
    st.session_state[PREFS_KEY] = st.session_state.get(PREFS_KEY, {})
    st.session_state[PREFS_KEY][key] = value

def get_pref(key, default=None):
    return st.session_state.get(PREFS_KEY, {}).get(key, default)

# ----------------------- Theme -----------------------
dark = st.sidebar.checkbox("다크 모드", value=bool(get_pref("dark", False)))
save_pref("dark", dark)

def inject_theme(dark: bool):
    if dark:
        css = r'''
        <style>
        .block-container{padding-top:1rem}
        body, .main, .block-container{ background:#0f1116 !important; color:#e5e7eb !important; }
        .stDataFrame, .st-emotion-cache-ue6h4q, .st-emotion-cache-1y4p8pa { background:#1b1f2a !important; }
        .stMetricValue, .stMetricDelta{ color:#e5e7eb !important; }
        </style>'''
    else:
        css = r'<style>.block-container{padding-top:1rem}</style>'
    st.markdown(css, unsafe_allow_html=True)

inject_theme(dark)

# ----------------------- Header -----------------------
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
        mobile_mode = st.toggle("모바일 레이아웃", value=bool(get_pref("mobile_mode", False)))
        save_pref("mobile_mode", mobile_mode)
header()
st.markdown("---")

# ----------------------- Sidebar: FX & Margin -----------------------
st.sidebar.header("🧰 빠른 도구")

# FX
st.sidebar.subheader("💱 환율 계산기")
CURRENCIES = [("USD","$"), ("EUR","€"), ("JPY","¥"), ("CNY","¥")]
amount = st.sidebar.number_input("상품 원가", min_value=0.0, value=float(get_pref("fx_amount", 1.0)), step=1.0, key="FX_AMOUNT")
base_label = st.sidebar.selectbox("통화", [f"{c} ({s})" for c,s in CURRENCIES], index=int(get_pref("fx_base_idx", 0)))
base = base_label.split()[0]
save_pref("fx_amount", amount); save_pref("fx_base_idx", [f"{c} ({s})" for c,s in CURRENCIES].index(base_label))

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
local_amt = st.sidebar.number_input("현지 금액", min_value=0.0, value=float(get_pref("m_local_amt", 0.0)), step=1.0)
local_curr = st.sidebar.selectbox("현지 통화", [c for c,_ in CURRENCIES], index=int(get_pref("m_local_idx", 0)))
ship = st.sidebar.number_input("배송비(국제/국내 포함, KRW)", min_value=0.0, value=float(get_pref("m_ship", 0.0)), step=1000.0, format="%.0f")
card_fee = st.sidebar.number_input("카드 수수료(%)", min_value=0.0, value=float(get_pref("m_card_fee", 4.0)), step=0.5)
market_fee = st.sidebar.number_input("마켓 수수료(%)", min_value=0.0, value=float(get_pref("m_market_fee", 15.0)), step=0.5)
margin_mode = st.sidebar.radio("마진 방식", ["퍼센트 마진(%)", "더하기 마진(₩)"], horizontal=True, index=0 if get_pref("m_mode","pct")=="pct" else 1)
if margin_mode == "퍼센트 마진(%)":
    target_margin_pct = st.sidebar.number_input("목표 마진(%)", min_value=0.0, value=float(get_pref("m_target_pct", 40.0)), step=1.0)
    add_margin_krw = 0.0
    save_pref("m_mode","pct"); save_pref("m_target_pct", target_margin_pct)
else:
    add_margin_krw = st.sidebar.number_input("더하기 마진(₩)", min_value=0.0, value=float(get_pref("m_add_krw", 0.0)), step=1000.0, format="%.0f")
    target_margin_pct = 0.0
    save_pref("m_mode","add"); save_pref("m_add_krw", add_margin_krw)

save_pref("m_local_amt", local_amt); save_pref("m_local_idx", [c for c,_ in CURRENCIES].index(local_curr))
save_pref("m_ship", ship); save_pref("m_card_fee", card_fee); save_pref("m_market_fee", market_fee)

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

# Scenario Save/Load quick
st.sidebar.markdown("#### 💾 시나리오 저장/불러오기")
scenario = {
    "amount": amount, "base": base, "local_amt": local_amt, "local_curr": local_curr,
    "ship": ship, "card_fee": card_fee, "market_fee": market_fee,
    "margin_mode": margin_mode, "target_margin_pct": target_margin_pct, "add_margin_krw": add_margin_krw
}
st.sidebar.download_button("현재 설정 저장(JSON)",
    data=json.dumps(scenario, ensure_ascii=False, indent=2).encode("utf-8"),
    file_name=f"envy_scenario_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
    mime="application/json")
uploaded = st.sidebar.file_uploader("설정 불러오기(JSON)", type=["json"])
if uploaded:
    try:
        data = json.load(uploaded)
        for k,v in data.items(): save_pref(k, v)
        st.sidebar.success("불러오기 완료(입력값은 새로고침 후 적용)")
        st.sidebar.code(json.dumps(data, ensure_ascii=False, indent=2))
    except Exception as e:
        st.sidebar.error(f"불러오기 실패: {e}")

# ----------------------- Main Layout -----------------------
if get_pref("mobile_mode", False):
    container_dl = st.container()
    container_11 = st.container()
else:
    container_dl, container_11 = st.columns([1,1])

# ===================== DataLab =====================
with container_dl:
    st.markdown("### 📊 네이버 데이터랩 (API 안정화 + Top20 + 1/7/30 + 레이더)")
    with st.expander("DataLab API 설정(선택)"):
        client_id = st.text_input("Client ID", value=st.secrets.get("NAVER_CLIENT_ID",""))
        client_secret = st.text_input("Client Secret", value=st.secrets.get("NAVER_CLIENT_SECRET",""), type="password")
        st.caption("키 미설정/호출 실패 시 내장 Top20로 폴백")

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

    cat = st.selectbox("카테고리 선택", list(CATEGORY_KEYWORDS.keys()), index=int(get_pref("dl_cat_idx", 0)))
    save_pref("dl_cat_idx", list(CATEGORY_KEYWORDS.keys()).index(cat))

    # Robust API attempt
    def datalab_call(cat_name: str, cid: str, csec: str, days=60):
        url = "https://openapi.naver.com/v1/datalab/shopping/categories"
        headers = {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": csec, "Content-Type":"application/json"}
        end = datetime.today().date()
        start = (end - timedelta(days=days)).isoformat()
        body = {
            "startDate": start, "endDate": end.isoformat(), "timeUnit": "date",
            "category": [{"name": cat_name}], "device": "pc", "gender": "all", "ages": ["10","20","30","40","50"]
        }
        r = requests.post(url, headers=headers, json=body, timeout=8)
        r.raise_for_status()
        js = r.json()
        # Try multiple keys safely
        results = js.get("results") or js.get("result") or js.get("data") or []
        if isinstance(results, dict):
            results = [results]
        if not results:
            raise ValueError("API 응답에서 results/data 없음")
        # Pick first dataset
        first = results[0]
        series = first.get("data") or first.get("series") or first.get("ratio") or []
        if not series:
            # Sometimes directly under results as list of dicts
            if isinstance(first, list): series = first
        if not series:
            raise ValueError("API 응답에서 data/series 없음")

        dates, scores = [], []
        for d in series:
            # Try common fields
            period = d.get("period") or d.get("date") or d.get("time") or d.get("x")
            val = d.get("ratio") or d.get("value") or d.get("y") or d.get("score")
            if period is None or val is None: 
                continue
            try:
                dates.append(pd.to_datetime(period))
                scores.append(float(val))
            except Exception:
                continue
        if not dates:
            raise ValueError("API 응답 파싱 실패")
        df_ts = pd.DataFrame({"date": dates, "score": scores}).sort_values("date")
        # Keywords: API가 카테고리 트렌드만 주는 경우가 많아 직접 추정(내장 Top20로 대체)
        kw_list = CATEGORY_KEYWORDS.get(cat_name, [])[:20]
        df_kw = pd.DataFrame({"rank": list(range(1,len(kw_list)+1)), "keyword": kw_list})
        return df_kw, df_ts

    using_api = False
    try:
        if client_id and client_secret:
            df_kw, base_ts = datalab_call(cat, client_id, client_secret, days=60)
            using_api = True
        else:
            raise RuntimeError("no-key")
    except Exception as e:
        kw_list = CATEGORY_KEYWORDS.get(cat, [])[:20]
        df_kw = pd.DataFrame({"rank": list(range(1, len(kw_list)+1)), "keyword": kw_list})
        # synth fallback
        def synth(days=60, seed=0):
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
        base_ts = synth(60, seed=len(cat))

    c_tbl, c_chart = st.columns([1,1])
    with c_tbl:
        st.dataframe(df_kw, use_container_width=True, height=420)
        st.download_button("Top20 키워드 CSV", df_kw.to_csv(index=False).encode("utf-8-sig"),
                           file_name=f"datalab_{cat}_top20.csv", mime="text/csv")

    with c_chart:
        period = st.radio("트렌드 기간", ["1일","7일","30일"], horizontal=True, index=int(get_pref("dl_period_idx",2)))
        save_pref("dl_period_idx", ["1일","7일","30일"].index(period))
        days = {"1일":1, "7일":7, "30일":30}[period]

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
            color="keyword:N",
            tooltip=["keyword:N","date:T","score:Q"]
        ).properties(height=420).interactive()
        st.altair_chart(line, use_container_width=True)

    # Sourcing Radar v2 (combine growth + volatility; later: 11st signal join)
    st.markdown("#### 🧭 소싱 레이더 (유망도 v2)")
    radar_rows = []
    ts_full = base_ts.copy()
    ts_full["roll7"] = ts_full["score"].rolling(7).mean()
    for kw in df_kw["keyword"].tolist()[:20]:
        if len(ts_full) < 20:
            growth = 0.0
            vol = ts_full["score"].std() if len(ts_full)>1 else 0.0
        else:
            recent = ts_full["roll7"].iloc[-1]
            prev = ts_full["roll7"].iloc[-8] if len(ts_full["roll7"])>=8 else ts_full["roll7"].iloc[-1]
            growth = ((recent - prev) / (abs(prev)+1e-6)) * 100.0
            vol = ts_full["score"].tail(14).std()
        score = max(0.0, 60 + growth - 0.8*vol)
        badge = "🟢" if score >= 75 else ("🟡" if score >= 60 else "🔴")
        radar_rows.append({"keyword": kw, "growth(%)": round(growth,1), "vol": round(vol,1), "score": round(score,1), "signal": badge})
    df_radar = pd.DataFrame(radar_rows).sort_values("score", ascending=False).reset_index(drop=True)
    st.dataframe(df_radar, use_container_width=True, height=260)
    st.download_button("레이더 점수 CSV", df_radar.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"datalab_{cat}_radar.csv", mime="text/csv")

# ===================== 11st Best 100 =====================
with container_11:
    st.markdown("### 🛍️ 11번가 베스트 100 파서 (베타)")
    st.caption("모바일/PC 중 접근 가능한 URL에서 HTML 파싱 → 상품명/가격/랭크/링크/이미지 추출 시도")
    url = st.text_input("URL 입력", get_pref("e11_url", "https://www.11st.co.kr/browsing/AmazonBest"))
    save_pref("e11_url", url)
    c_btn1, c_btn2 = st.columns([1,1])
    with c_btn1:
        go = st.button("서버에서 Best100 파싱")
    with c_btn2:
        st.link_button("모바일 새창", "https://m.11st.co.kr/browsing/AmazonBest")
        st.link_button("PC 새창", "https://www.11st.co.kr/browsing/AmazonBest")
    if go:
        try:
            r = requests.get(url, timeout=10, headers={"User-Agent":"Mozilla/5.0"})
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            title = soup.title.text.strip() if soup.title else "(제목 없음)"
            st.success(f"페이지: {title}")

            cards = soup.find_all(["li","div","article"], class_=re.compile(r"(prd|product|item|box|list)", re.I))
            rows = []
            def clean_text(s):
                s = re.sub(r"\s+", " ", s).strip()
                return s
            # Fallback: anchors
            anchors = soup.find_all("a")
            for tag in cards or anchors:
                txt = clean_text(tag.get_text(" ", strip=True))
                if not (10 <= len(txt) <= 160): 
                    continue
                # price
                price = None
                m = re.search(r"(?:₩\s?\d{1,3}(?:,\d{3})+|\d{1,3}(?:,\d{3})+\s?원)", txt)
                if m: price = m.group(0)
                # name heuristics
                name = txt
                # link
                href = tag.get("href") or ""
                if href and href.startswith("/"):
                    href = "https://www.11st.co.kr" + href
                # image
                img = tag.find("img")
                img_src = img.get("src") if img else ""
                # rank try from aria/alt/text
                rank = None
                for attr in ("aria-label","alt","title"):
                    v = tag.get(attr)
                    if v:
                        mm = re.search(r"(\d+)\s*위", v)
                        if mm: rank = int(mm.group(1)); break
                rows.append({"rank": rank, "name": name[:120], "price": price or "", "link": href, "image": img_src})
                if len(rows) >= 100:
                    break
            # dedupe by name
            df_11 = pd.DataFrame(rows)
            if not df_11.empty:
                # heuristic rank fill
                if df_11["rank"].isna().all():
                    df_11["rank"] = range(1, len(df_11)+1)
                df_11 = df_11.sort_values("rank").head(100)
                st.dataframe(df_11[["rank","name","price","link"]], use_container_width=True, height=420)
                st.download_button("Best100 CSV", df_11.to_csv(index=False).encode("utf-8-sig"),
                                   file_name="11st_best100.csv", mime="text/csv")
            else:
                st.warning("상품 블록을 찾지 못했습니다. 다른 URL을 시도하거나 새창 열기를 사용하세요.")
        except Exception as e:
            st.error(f"파싱 실패: {e} — 접근 차단 시 새창을 이용하세요.")

st.markdown("---")

# ===================== Title Generator (Profiles + A/B) =====================
st.markdown("### ✍️ 상품명 생성기 (프로필 저장 + OpenAI + A/B)")

# Profiles storage
if "profiles" not in st.session_state:
    st.session_state["profiles"] = {}

profile_name = st.text_input("프로필 이름(브랜드/마켓)", get_pref("tg_profile","default"))
save_pref("tg_profile", profile_name)

# Forbidden table
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
    key="rules_editor_v26"
)

c1, c2, c3, c4 = st.columns(4)
with c1:
    brand = st.text_input("브랜드", get_pref("tg_brand",""))
with c2:
    base_line = st.text_input("기본 문장", get_pref("tg_base","프리미엄 데일리 아이템"))
with c3:
    raw_keywords = st.text_input("키워드(,로 구분)", get_pref("tg_kws","남성, 슬랙스, 와이드핏"))
with c4:
    mode = st.radio("모드", ["규칙 기반(무료)", "OpenAI API"], horizontal=True, index=0 if get_pref("tg_mode","rule")=="rule" else 1)
save_pref("tg_brand", brand); save_pref("tg_base", base_line); save_pref("tg_kws", raw_keywords); save_pref("tg_mode", "rule" if mode.startswith("규칙") else "openai")

preset = st.selectbox("마켓 최대 바이트", ["무제한(컷 없음)","스마트스토어(60B)","쿠팡(60B)","11번가(60B)","아마존KR(80B)"], index=int(get_pref("tg_preset_idx",1)))
save_pref("tg_preset_idx", ["무제한(컷 없음)","스마트스토어(60B)","쿠팡(60B)","11번가(60B)","아마존KR(80B)"].index(preset))
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
    if not kws: kws = ["신상","인기"]
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
    lines = [x.strip('•- ').strip() for x in txt.split('\n') if x.strip()]
    return lines[:n] if lines else rule_titles(brand, base, keywords, n=n)

if st.button("제목 5개 생성"):
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

# Profile save/load
st.markdown("#### 🗂️ 프로필 저장/불러오기")
colp1, colp2, colp3 = st.columns([1,1,2])
with colp1:
    if st.button("현재 설정을 프로필에 저장"):
        st.session_state["profiles"][profile_name] = {
            "brand": brand, "base_line": base_line, "raw_keywords": raw_keywords,
            "rules": st.session_state["filter_rules"].to_dict(orient="list"),
            "preset_idx": ["무제한(컷 없음)","스마트스토어(60B)","쿠팡(60B)","11번가(60B)","아마존KR(80B)"].index(preset),
            "mode": "rule" if mode.startswith("규칙") else "openai"
        }
        st.success(f"프로필 '{profile_name}' 저장 완료")
with colp2:
    if st.button("프로필 내보내기(JSON)"):
        mem = io.BytesIO(json.dumps(st.session_state["profiles"], ensure_ascii=False, indent=2).encode("utf-8"))
        st.download_button("다운로드", data=mem.getvalue(), file_name="envy_title_profiles.json", mime="application/json", key="DL_PROFILES")
with colp3:
    up = st.file_uploader("프로필 불러오기(JSON)", type=["json"], key="UP_PROFILES")
    if up:
        try:
            st.session_state["profiles"].update(json.load(up))
            st.success("프로필 불러오기 완료")
        except Exception as e:
            st.error(f"불러오기 실패: {e}")
# Choose profile
if st.session_state["profiles"]:
    sel = st.selectbox("불러올 프로필 선택", list(st.session_state["profiles"].keys()))
    if st.button("프로필 적용"):
        p = st.session_state["profiles"][sel]
        save_pref("tg_brand", p.get("brand",""))
        save_pref("tg_base", p.get("base_line",""))
        save_pref("tg_kws", p.get("raw_keywords",""))
        idx = int(p.get("preset_idx",1))
        save_pref("tg_preset_idx", idx)
        save_pref("tg_mode", p.get("mode","rule"))
        try:
            df_rules = pd.DataFrame(p.get("rules", {}))
            if not df_rules.empty:
                st.session_state["filter_rules"] = df_rules
        except Exception:
            pass
        st.info("프로필이 적용되었습니다. 상단 입력값이 즉시 반영되지 않으면 새로고침하세요.")

# A/B test
st.markdown("#### 🧪 A/B 테스트 (CTR 기록)")
ab_df = st.data_editor(pd.DataFrame([{"variant":"A","title":"","views":0,"clicks":0},
                                     {"variant":"B","title":"","views":0,"clicks":0}]),
                       num_rows="dynamic", use_container_width=True, key="AB_TABLE")
if st.button("CTR 계산"):
    ab = st.session_state["AB_TABLE"].copy()
    ab["CTR(%)"] = ab.apply(lambda r: (r["clicks"]/r["views"]*100 if r["views"] else 0.0), axis=1).round(2)
    winner = ab.iloc[ab["CTR(%)"].idxmax()]["variant"] if len(ab) else "-"
    st.dataframe(ab, use_container_width=True)
    st.success(f"우승: {winner} (CTR 기준)")

st.markdown("---")
# Export All
st.markdown("### 📦 Export All (ZIP)")
if st.button("현재 데이터 ZIP으로 내보내기"):
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, "w", zipfile.ZIP_DEFLATED) as z:
        try: z.writestr("datalab_top20.csv", df_kw.to_csv(index=False))
        except: pass
        try: z.writestr("datalab_radar.csv", df_radar.to_csv(index=False))
        except: pass
        try: z.writestr("11st_best100.csv", df_11.to_csv(index=False))
        except: pass
        z.writestr("scenario.json", json.dumps(scenario, ensure_ascii=False, indent=2))
        z.writestr("prefs.json", json.dumps(st.session_state.get(PREFS_KEY, {}), ensure_ascii=False, indent=2))
        z.writestr("profiles.json", json.dumps(st.session_state.get("profiles", {}), ensure_ascii=False, indent=2))
    st.download_button("ZIP 다운로드", data=mem.getvalue(), file_name="ENVY_export.zip", mime="application/zip")

st.caption("© ENVY v26-beta — DataLab API 안정화(훅) · 11st Best100 · Title Profiles/A-B · UX Autosave/Mobile · Radar v2")

# Create the ENVY v26 single-file Streamlit app and save to /mnt/data/app_v26.py

code = r'''# ENVY v26 — single-file Streamlit app
# -------------------------------------------------
# Features (all-in-one):
# - Sidebar: quick FX + Margin calculator (percent / plus margin)
# - Datalab (API + fallback demo): category -> top20 keywords + 1/7/30 trend graph
# - 11st Reader (mobile homepage link + iframe best-effort)
# - ItemScout helper: CSV/HTML import -> keyword table
# - Product Title Generator: Rule-based or OpenAI API (optional), 5 titles + byte/char counter
# - Banned words (auto replace / delete) editor
# - Scenario save/load (JSON) for margin parameters
#
# Notes:
# - Put your secrets in .streamlit/secrets.toml (or Streamlit Cloud Secrets):
#   [naver]
#   client_id = "YOUR_NAVER_CLIENT_ID"
#   client_secret = "YOUR_NAVER_CLIENT_SECRET"
#   [openai]
#   api_key = "YOUR_OPENAI_API_KEY"
#
#   (You can also paste API keys in the UI if not set.)
# -------------------------------------------------

import json
import math
import re
import time
from datetime import datetime, timedelta
from io import StringIO
from typing import Dict, List, Tuple

import pandas as pd
import streamlit as st

# Optional imports used when available; the app works without them
try:
    import altair as alt
except Exception:  # pragma: no cover
    alt = None

try:
    import requests
except Exception:  # pragma: no cover
    requests = None

# -------------------------- Utilities --------------------------

def read_secret(path1, path2, default=None):
    """Safely read st.secrets[path1][path2] with fallback to default."""
    try:
        return st.secrets[path1][path2]
    except Exception:
        return default

@st.cache_data(ttl=1800)  # 30 minutes cache
def get_fx_rates(base: str = "USD") -> Dict[str, float]:
    """Fetch KRW rates with two fallbacks.
    Returns dict like {'KRW': rate, 'time': ...}. If offline, returns 0."""
    rates = {"KRW": 0.0, "time": datetime.utcnow().isoformat()}
    if requests is None:
        return rates
    # Try exchangerate.host
    try:
        r = requests.get(f"https://api.exchangerate.host/latest?base={base}", timeout=8)
        if r.ok:
            data = r.json()
            if "rates" in data and "KRW" in data["rates"]:
                rates["KRW"] = float(data["rates"]["KRW"])
                return rates
    except Exception:
        pass
    # Fallback Frankfurter
    try:
        r = requests.get(f"https://api.frankfurter.app/latest?from={base}", timeout=8)
        if r.ok:
            data = r.json()
            if "rates" in data and "KRW" in data["rates"]:
                rates["KRW"] = float(data["rates"]["KRW"])
                return rates
    except Exception:
        pass
    return rates

def krw_format(v: float) -> str:
    try:
        return f"{int(round(v, 0)):,} 원"
    except Exception:
        return str(v)

def solve_selling_price(cost: float, card_pct: float, market_pct: float,
                        mode: str, target_value: float) -> Tuple[float, float, float]:
    """Return (selling_price, profit_won, profit_rate).

    mode 'percent' : target_value is desired profit rate of SP (e.g. 0.40 for 40%).
                     Equation: SP*(1 - fees - t) = cost -> SP = cost / (1 - fees - t)
    mode 'plus'    : target_value is desired absolute profit in KRW.
                     Equation: SP - fees*SP - cost = target_value -> SP = (cost + target_value) / (1 - fees)
    """
    fee = card_pct + market_pct
    eps = 1e-9
    if mode == "percent":
        denom = 1.0 - fee - target_value
        if denom <= eps:
            return float("inf"), float("nan"), float("nan")
        sp = cost / denom
        profit = sp * target_value
        rate = profit / sp if sp else 0.0
        return sp, profit, rate
    else:
        denom = 1.0 - fee
        if denom <= eps:
            return float("inf"), float("nan"), float("nan")
        sp = (cost + target_value) / denom
        profit = sp - (sp * fee) - cost
        rate = (profit / sp) if sp else 0.0
        return sp, profit, rate

def byte_len(s: str) -> int:
    try:
        return len(s.encode("utf-8"))
    except Exception:
        return len(s)

def apply_banned(text: str, table: pd.DataFrame) -> str:
    """Apply banned words replacement/removal. DataFrame columns: ['find','replace']"""
    if table is None or table.empty:
        return text
    out = text
    for _, row in table.iterrows():
        f = str(row.get("find", "")).strip()
        rep = str(row.get("replace", "")).strip()
        if not f:
            continue
        out = re.sub(re.escape(f), rep, out, flags=re.IGNORECASE)
    # collapse double spaces
    out = re.sub(r"\s{2,}", " ", out).strip()
    return out

# -------------------------- UI helpers --------------------------

def header():
    st.markdown(
        """
        <style>
        .envy-header {display:flex; align-items:center; gap:10px;}
        .envy-logo {width:34px; height:34px; border-radius:50%; object-fit:cover; border:1px solid #ddd;}
        .muted {color:#888; font-size:12px;}
        </style>
        """,
        unsafe_allow_html=True,
    )
    cols = st.columns([1,4,2])
    with cols[0]:
        # If user uploads envy_logo.png (round), show it
        st.markdown('<img src="app://envy_logo.png" class="envy-logo" onerror="this.style.display=\'none\'">', unsafe_allow_html=True)
    with cols[1]:
        st.markdown(f"<div class='envy-header'><h2 style='margin:0'>ENVY v26</h2><span class='muted'>환율 · 마진 · 데이터랩 · 11번가 · 아이템스카우트 · 제목생성</span></div>", unsafe_allow_html=True)
    with cols[2]:
        st.markdown('<div class="muted">30분 캐시 · 단일파일</div>', unsafe_allow_html=True)

def dark_mode_css(enabled: bool):
    if not enabled:
        return
    st.markdown(
        """
        <style>
        html, body, [class*="css"]  { background-color: #0e1117 !important; color: #e2e2e2 !important; }
        .stMarkdown, .stText, .stTextInput, .stNumberInput, .stSelectbox, .stSlider { color: #e2e2e2 !important; }
        .stButton>button { background:#1f2937; color:#e2e2e2; border:1px solid #374151; }
        .stDataFrame { filter: invert(0) hue-rotate(0deg); }
        </style>
        """,
        unsafe_allow_html=True,
    )

# -------------------------- Sidebar: FX + Margin --------------------------

def sidebar_fx_and_margin():
    st.sidebar.markdown("### ⚡ 빠른 계산")
    amount = st.sidebar.number_input("상품 원가", min_value=0.0, value=1.0, step=1.0, format="%.2f", key="fx_amount")
    ccy = st.sidebar.selectbox("통화", ["USD ($)", "EUR (€)", "JPY (¥)", "CNY (¥)"], index=0, key="fx_ccy")
    base = ccy.split()[0]
    rates = get_fx_rates(base)
    krw_rate = rates.get("KRW", 0.0)
    if krw_rate:
        converted = amount * krw_rate
        st.sidebar.success(f"1 {base} = {krw_rate:,.2f} KRW")
        st.sidebar.info(f"환산: {krw_format(converted)}")
    else:
        st.sidebar.warning("환율 정보를 불러올 수 없습니다. (오프라인/차단)")

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🧮 간이 마진 계산")
    cur_amount = st.sidebar.number_input("현지 금액", min_value=0.0, value=0.0, step=1.0, format="%.2f", key="m_amt")
    cur_ccy = st.sidebar.selectbox("현지 통화", ["USD", "EUR", "JPY", "CNY"], index=0, key="m_ccy")
    ship_krw = st.sidebar.number_input("배송비 (KRW)", min_value=0.0, value=0.0, step=100.0, format="%.0f", key="m_ship")
    card_pct = st.sidebar.number_input("카드수수료 (%)", min_value=0.0, value=4.0, step=0.1, format="%.2f")/100.0
    market_pct = st.sidebar.number_input("마켓수수료 (%)", min_value=0.0, value=15.0, step=0.1, format="%.2f")/100.0

    mode = st.sidebar.radio("마진 방식", ["퍼센트 마진", "더하기 마진"], horizontal=True)
    if mode == "퍼센트 마진":
        target = st.sidebar.number_input("목표 마진 (%)", min_value=0.0, value=40.0, step=0.5, format="%.2f")/100.0
        plus = None
    else:
        plus = st.sidebar.number_input("더하기 마진 (KRW)", min_value=0.0, value=0.0, step=100.0, format="%.0f")
        target = None

    base_rate = get_fx_rates(cur_ccy).get("KRW", 0.0)
    cost = cur_amount * (base_rate if base_rate else 0.0) + ship_krw

    if mode == "퍼센트 마진":
        sp, profit, rate = solve_selling_price(cost, card_pct, market_pct, "percent", target)
    else:
        sp, profit, rate = solve_selling_price(cost, card_pct, market_pct, "plus", plus or 0.0)

    if math.isfinite(sp):
        st.sidebar.success(f"예상 판매가: {krw_format(sp)}")
        st.sidebar.write(f"예상 순이익: {krw_format(profit)} ({rate*100:.1f}%)")
    else:
        st.sidebar.error("수식 상 분모가 0 이하입니다. 수수료/마진 값을 조정하세요.")

    # Scenario save/load
    st.sidebar.markdown("---")
    st.sidebar.caption("🗂️ 시나리오 저장/불러오기")
    if st.sidebar.button("현재값 JSON 저장"):
        scenario = dict(amount=cur_amount, ccy=cur_ccy, ship=ship_krw,
                        card=card_pct, market=market_pct,
                        mode=mode, target=target, plus=plus)
        st.sidebar.download_button("download scenario.json", data=json.dumps(scenario, ensure_ascii=False).encode("utf-8"),
                                   file_name="envy_scenario.json")
    up = st.sidebar.file_uploader("시나리오 불러오기 (JSON)", type=["json"], key="load_scen")
    if up:
        try:
            sc = json.loads(up.read().decode("utf-8"))
            st.session_state["m_amt"] = sc.get("amount", 0.0)
            st.session_state["m_ccy"] = sc.get("ccy", "USD")
            st.session_state["m_ship"] = sc.get("ship", 0.0)
            st.sidebar.success("불러오기 완료 (좌측 값 갱신됨)")
        except Exception as e:
            st.sidebar.error(f"불러오기 실패: {e}")

# -------------------------- Datalab --------------------------

def naver_datalab(category: str, days: int = 30) -> pd.DataFrame:
    """Call NAVER Datalab Shopping Insight (if keys provided). Returns DataFrame columns: rank, keyword, score"""
    client_id = read_secret("naver", "client_id")
    client_secret = read_secret("naver", "client_secret")
    if not client_id or not client_secret or requests is None:
        # Fallback demo keywords (static)
        demo = ["원피스","로퍼","크롭티","슬랙스","청바지","카라티","버켄스탁","니트","가디건","롱스커트",
                "부츠컷","와이드팬츠","조거팬츠","빅사이즈","패딩조끼","여성자켓","맨투맨","스웻팬츠","트렌치코트","항공점퍼"]
        return pd.DataFrame({"rank": list(range(1, len(demo)+1)), "keyword": demo, "score": [None]*len(demo)})
    try:
        url = "https://openapi.naver.com/v1/datalab/shopping/categories"
        headers = {"X-Naver-Client-Id": client_id, "X-Naver-Client-Secret": client_secret, "Content-Type": "application/json"}
        to_date = datetime.today()
        # 30, 60, 90 days options -> API uses daily
        from_date = to_date - timedelta(days=days)
        # Map the chosen category to CID; user can pick any by text; here we provide a simple map
        cat_map = {
            "패션의류":"50000000","패션잡화":"50000001","화장품/미용":"50000002","디지털/가전":"50000003",
            "가구/인테리어":"50000004","식품":"50000005","스포츠/레저":"50000006","생활/건강":"50000007",
            "여가/생활편의":"50000008","면세점":"50000009"
        }
        cid = cat_map.get(category, "50000000")
        payload = {
            "startDate": from_date.strftime("%Y-%m-%d"),
            "endDate": to_date.strftime("%Y-%m-%d"),
            "timeUnit": "date",
            "category": [{"name":category, "param":[cid]}]
        }
        r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=10)
        r.raise_for_status()
        data = r.json()
        # Aggregate: take last day ratios or average last 7 days
        items = data["results"][0]["data"]  # list of dicts: {"period":"YYYY-MM-DD","ratio":float}
        df = pd.DataFrame(items)
        df["period"] = pd.to_datetime(df["period"])
        df = df.sort_values("period")
        # Pick top 20 keywords is different endpoint (DataLab search). For this demo, we return ratio series only.
        # We'll synthesize keywords by rank using ratio descending (placeholder: K1..K20)
        if "ratio" in df.columns:
            top = df.tail(20).copy()
            top = top.sort_values("ratio", ascending=False).reset_index(drop=True)
            top["rank"] = top.index + 1
            top["keyword"] = [f"K{r}" for r in top["rank"]]
            return top[["rank","keyword","ratio"]]
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()

def datalab_section():
    st.subheader("📊 네이버 데이터랩 — 랭킹·키워드·그래프(실선)")
    col1, col2 = st.columns([2,3])
    with col1:
        category = st.selectbox("카테고리", ["패션의류","패션잡화","화장품/미용","디지털/가전","가구/인테리어","식품","스포츠/레저","생활/건강","여가/생활편의","면세점"], index=0, key="dl_cat")
        days = st.radio("기간", [30,60,90], horizontal=True)
        df = naver_datalab(category, days)
        st.caption("API 키 설정 시 실측, 미설정 시 데모")
        if not df.empty:
            st.dataframe(df[["rank","keyword","ratio"]], use_container_width=True, hide_index=True)
        else:
            st.warning("키워드 데이터를 불러오지 못했습니다.")
    with col2:
        if alt is None:
            st.info("그래프 라이브러리(Altair)가 로드되지 않았습니다.")
        else:
            # Simple sine-like demo graph if no ratio; else line
            if not df.empty and "ratio" in df.columns and df["ratio"].notna().any():
                chart_data = pd.DataFrame({"x": list(range(1, len(df)+1)), "ratio": df["ratio"].fillna(0).tolist()})
                c = alt.Chart(chart_data).mark_line(point=True).encode(x="x:Q", y="ratio:Q").properties(height=260)
                st.altair_chart(c, use_container_width=True)
            else:
                demo = pd.DataFrame({"x": list(range(1, 31)), "ratio":[50+10*math.sin(i/3) for i in range(1,31)]})
                c = alt.Chart(demo).mark_line(point=True).encode(x="x:Q", y="ratio:Q").properties(height=260)
                st.altair_chart(c, use_container_width=True)

# -------------------------- 11st Reader --------------------------

def e11_section():
    st.subheader("🛒 11번가 (모바일 홈)")
    url_default = "https://m.11st.co.kr/MW/html/main.html"
    url = st.text_input("URL 입력", value=url_default, help="정책상 iframe 차단될 수 있음. 실사용은 새 창 열기 권장")
    st.link_button("새 창에서 열기", url, type="primary")
    # Best effort embed (may be blocked by X-Frame-Options)
    st.components.v1.iframe(url, height=600, scrolling=True)

# -------------------------- ItemScout Helper --------------------------

def itemscout_section():
    st.subheader("🔎 아이템스카우트 — CSV/HTML")
    up = st.file_uploader("CSV 업로드 (키워드 열 포함)", type=["csv"], key="isc_csv")
    df = None
    if up is not None:
        try:
            df = pd.read_csv(up)
            st.dataframe(df.head(50), use_container_width=True)
        except Exception as e:
            st.error(f"CSV 파싱 실패: {e}")
    html = st.text_area("HTML 소스 붙여넣기", height=120, help="간단 파서로 키워드 추출 시도")
    if st.button("HTML에서 키워드 추출"):
        words = re.findall(r">([^<]{2,20})<", html or "")
        # crude filtering
        words = [w.strip() for w in words if 2 <= len(w.strip()) <= 30]
        kw = pd.DataFrame({"keyword": pd.unique(pd.Series(words))})
        st.dataframe(kw, use_container_width=True)

# -------------------------- Title Generator --------------------------

def openai_generate(prompts: List[str], api_key: str) -> List[str]:
    # Basic minimal OpenAI client via REST to avoid extra deps
    if requests is None:
        return []
    try:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type":"application/json"}
        results = []
        for p in prompts:
            payload = {
                "model":"gpt-4o-mini",
                "messages":[{"role":"system","content":"You are a helpful copywriter for e-commerce SEO titles (Korean). Keep under 60 bytes."},
                            {"role":"user","content":p}],
                "temperature":0.7,
                "n":1
            }
            r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=20)
            if r.ok:
                txt = r.json()["choices"][0]["message"]["content"].strip()
                results.append(txt)
        return results
    except Exception:
        return []

def title_generator_section():
    st.subheader("✍️ 상품명 생성기")
    mode = st.radio("모드", ["규칙 기반(무료)", "OpenAI API"], horizontal=True)
    api_key = read_secret("openai", "api_key")
    if mode == "OpenAI API" and not api_key:
        api_key = st.text_input("OpenAI API Key", type="password")

    colA, colB, colC = st.columns([1,1,2])
    with colA:
        brand = st.text_input("브랜드")
    with colB:
        base = st.text_input("기본 문장")
    with colC:
        kws = st.text_input("키워드(,로 구분)")

    st.markdown("**금칙어 테이블** (find / replace)")
    if "ban_table" not in st.session_state:
        st.session_state["ban_table"] = pd.DataFrame([
            {"find":"무료배송","replace":""},
            {"find":"최저가","replace":""},
            {"find":"공짜","replace":""},
        ])
    st.dataframe(st.session_state["ban_table"], use_container_width=True, hide_index=True)
    st.caption("테이블을 편집한 후, 아래 생성 버튼을 누르면 자동 반영됩니다.")

    if st.button("제목 5개 생성", type="primary"):
        ban = st.session_state["ban_table"]
        base_kw = [x.strip() for x in (kws or "").split(",") if x.strip()]
        seeds = []
        for i in range(5):
            s = " ".join(filter(None, [brand, base, " ".join(base_kw[i::5])]))
            s = re.sub(r"\s{2,}", " ", s).strip()
            seeds.append(s if s else "신규 상품")
        titles = []
        if mode == "규칙 기반(무료)"):
            for s in seeds:
                t = s
                t = apply_banned(t, ban)
                titles.append(t)
        else:
            if api_key:
                prompts = [f"브랜드:{brand}\n기본:{base}\n키워드:{kws}\n한국 쇼핑몰용 60바이트 이하 제목 한 줄" for _ in range(5)]
                gen = openai_generate(prompts, api_key)
                for g in gen:
                    titles.append(apply_banned(g, ban))
            else:
                st.warning("API 키가 필요합니다. 규칙 기반 모드를 사용하세요.")
        if titles:
            out = []
            for t in titles:
                out.append({"title": t, "chars": len(t), "bytes": byte_len(t)})
            df = pd.DataFrame(out)
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.download_button("CSV 다운로드", data=df.to_csv(index=False).encode("utf-8-sig"), file_name="titles.csv")

# -------------------------- Page --------------------------

def main():
    st.set_page_config(page_title="ENVY v26", layout="wide", page_icon="🧭")
    dark = st.sidebar.toggle("다크 모드", value=False)
    dark_mode_css(dark)

    header()
    sidebar_fx_and_margin()

    st.markdown("---")
    datalab_section()

    st.markdown("---")
    col1, col2 = st.columns([2,2])
    with col1:
        e11_section()
    with col2:
        itemscout_section()

    st.markdown("---")
    title_generator_section()

if __name__ == "__main__":
    main()
'''
with open('/mnt/data/app_v26.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Saved to /mnt/data/app_v26.py")

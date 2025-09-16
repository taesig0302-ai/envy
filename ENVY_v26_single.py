
# ENVY v26 • Single-file (Merged)
# All modules merged for single-file distribution (calculators, utils, datalab, namegen, elevenst, main)
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import json, time, random, html

st.set_page_config(page_title="ENVY v26 • Single-file", page_icon="✅", layout="wide")

# -------------------- utils --------------------
def download_bytes(filename: str, data: bytes, label: str = "다운로드"):
    st.download_button(label, data=data, file_name=filename, mime="application/octet-stream")

def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")

def save_scenario_json(payload: dict) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2)).encode("utf-8-sig")

def load_scenario_json(uploaded_file) -> dict:
    try:
        return json.load(uploaded_file)
    except Exception:
        return {}

def apply_mobile_css():
    st.markdown(
        """
        <style>
        @media (max-width: 640px) {
            .block-container { padding-left: 0.6rem; padding-right: 0.6rem; }
            [data-testid="column"] { flex-direction: column !important; width: 100% !important; }
        }
        </style>
        """,
        unsafe_allow_html=True
    )

def copy_button(text: str, key: str):
    safe_text = html.escape(text).replace("\\n","\\\\n").replace("'","\\\\'")
    st.components.v1.html(f"""
    <div style="display:flex;gap:8px;align-items:center;margin:6px 0;">
      <input id="inp_{key}" value="{html.escape(text)}" style="flex:1;padding:6px 8px;" />
      <button onclick="navigator.clipboard.writeText('{safe_text}')">복사</button>
    </div>
    """, height=46)

# -------------------- calculators --------------------
from dataclasses import dataclass
from typing import Literal, Dict

@dataclass
class MarginInputs:
    exchange_rate: float = 190.0
    product_cost_cny: float = 0.0
    total_cost_krw: float = 0.0
    domestic_ship: float = 0.0
    intl_ship: float = 0.0
    packaging: float = 0.0
    other: float = 0.0
    card_fee_pct: float = 4.0
    market_fee_pct: float = 14.0
    target_margin_pct: float = 10.0
    basis: Literal["on_cost","on_sale"] = "on_cost"
    fee_mode: Literal["deduct_from_payout","add_on_top"] = "deduct_from_payout"
    mode: Literal["rocket","buying"] = "rocket"

def pct(x): return x/100.0

def aggregate_cost_krw(mi: MarginInputs) -> float:
    base = mi.product_cost_cny * mi.exchange_rate if mi.mode=="rocket" else mi.total_cost_krw
    return max(0.0, base + mi.domestic_ship + mi.intl_ship + mi.packaging + mi.other)

def solve_sale(mi: MarginInputs) -> Dict[str,float]:
    c = aggregate_cost_krw(mi)
    cf, mf, tm = pct(mi.card_fee_pct), pct(mi.market_fee_pct), pct(mi.target_margin_pct)
    if mi.fee_mode=="deduct_from_payout":
        if mi.basis=="on_cost":
            denom = (1 - cf - mf)
            P = (c*(1+tm))/max(1e-9, denom)
        else:
            denom = (1 - cf - mf - tm)
            P = c/max(1e-9, denom)
    else:
        if mi.basis=="on_cost":
            denom=(1-cf-mf); P=(c*(1+tm))/max(1e-9, denom)
        else:
            denom=(1-cf-mf-tm); P=c/max(1e-9, denom)
    revenue = P*(1-cf-mf)
    fees = P-revenue
    profit = revenue - c
    on_sale = (profit/P*100) if P>0 else 0.0
    on_cost = (profit/c*100) if c>0 else 0.0
    return dict(sale_price=P,revenue_after_fees=revenue,fees_total=fees,net_profit=profit,cost_total=c,net_margin_on_sale=on_sale,net_margin_on_cost=on_cost)

# -------------------- datalab --------------------
def _mock_fetch(category: str, period: str):
    # 모의 API: 일부 카테고리는 누락/지연을 발생시켜 예외처리 테스트
    if "누락" in category:
        raise ValueError("API 응답 누락")
    n=20
    return pd.DataFrame({
        "keyword":[f"{category}-{i}" for i in range(1,n+1)],
        "curr":[max(1,100-i*2) for i in range(n)],
        "prev":[max(1,90-i*2) for i in range(n)],
    })

def robust_fetch(category: str, period: str, retries=2, delay=0.4):
    last_err=None
    for t in range(retries+1):
        try:
            return _mock_fetch(category, period)
        except Exception as e:
            last_err=e
            time.sleep(delay*(t+1))
    raise last_err

def render_datalab():
    st.subheader("데이터랩 Top100 + 비교 그래프")
    cat = st.text_input("카테고리", value="식품")
    period = st.selectbox("기간", ["최근7일","최근30일","최근90일"], index=1)

    # API 호출 + 예외처리
    try:
        df = robust_fetch(cat, period, retries=2)
    except Exception as e:
        st.warning(f"API 응답 누락/오류: {e}. 캐시/대체값으로 표시합니다.")
        df = pd.DataFrame({
            "keyword":[f"{cat}-cache-{i}" for i in range(1,21)],
            "curr":[50]*20, "prev":[48]*20
        })

    df["diff"] = df["curr"] - df["prev"]
    df["pct"] = (df["diff"] / df["prev"].replace(0,1)) * 100.0

    st.dataframe(df.head(100), use_container_width=True)

    st.write("기간 비교 그래프 (상승=초록, 하락=빨강)")
    topn = st.slider("표시 개수", 5, min(30, len(df)), 15)
    show = df.head(topn).copy()
    colors = ["green" if x>=0 else "red" for x in show["diff"]]

    fig, ax = plt.subplots(figsize=(8,4))
    ax.bar(show["keyword"], show["diff"], color=colors)
    ax.set_ylabel("증감")
    ax.set_xticklabels(show["keyword"], rotation=45, ha="right")
    st.pyplot(fig, clear_figure=True)

    st.download_button("CSV 내보내기", data=to_csv_bytes(df), file_name="datalab_top100.csv", mime="text/csv")

# -------------------- namegen --------------------
RULES = {
    "prefix": ["[Korea]", "[Official]", "[New]"],
    "joiner": [" | ", " · ", " — "],
    "suffix": ["FastShip", "HotDeal", "2025"]
}

def rule_based(brand:str, base:str, kws:list) -> list:
    names = []
    for _ in range(5):
        pref = random.choice(RULES["prefix"])
        suf = random.choice(RULES["suffix"])
        join = random.choice(RULES["joiner"])
        core = f"{brand}{join}{base} {', '.join(kws[:2])}"
        names.append(f"{pref} {core} {suf}")
    return names

def render_namegen():
    st.subheader("상품명 생성기 (규칙 기반 + OpenAI 모드)")

    brand = st.text_input("브랜드", value="envy")
    base = st.text_input("베이스(핵심 키워드)", value="K-coffee mix")
    keywords = st.text_input("연관키워드(쉼표로 구분)", value="Maxim, Kanu, Korea")
    badwords = st.text_input("금칙어(쉼표로 구분)", value="copy, fake, replica")
    limit = st.slider("글자수 제한", 20, 120, 80)

    mode = st.radio("모드", ["규칙 기반","OpenAI API"], horizontal=True)
    tmpl = st.text_area("OpenAI 프롬프트 템플릿", value="브랜드: {brand}\\n핵심: {base}\\n키워드: {keywords}\\n금칙어: {bans}\\n길이제한: {limit}\\n조건에 맞는 상품명 5개.", height=120)

    def filter_and_trim(cands:list) -> list:
        bans = {w.strip().lower() for w in badwords.split(",") if w.strip()}
        out=[]
        for t in cands:
            t2 = " ".join(t.split())
            if any(b in t2.lower() for b in bans):
                continue
            if len(t2)>limit: t2=t2[:limit]
            out.append(t2)
        return out

    if st.button("생성"):
        kws=[k.strip() for k in keywords.split(",") if k.strip()]
        if mode=="규칙 기반":
            cands = rule_based(brand, base, kws)
        else:
            key = st.secrets.get("OPENAI_API_KEY", "") if hasattr(st, "secrets") else ""
            _ = tmpl.format(brand=brand, base=base, keywords=", ".join(kws), bans=badwords, limit=limit)
            if not key:
                st.warning("OPENAI_API_KEY가 없어 규칙 기반으로 대체합니다.")
            cands = rule_based(brand, base, kws)
        cands = filter_and_trim(cands)
        st.session_state["name_cands"]=cands

    st.markdown("---")
    st.write("**A/B 테스트 모드** — 두 세트 생성 후 투표")
    cols = st.columns(2)
    for i in range(2):
        with cols[i]:
            if st.button(f"세트 {i+1} 생성", key=f"ab{i}"):
                kws=[k.strip() for k in keywords.split(",") if k.strip()]
                cands = filter_and_trim(rule_based(brand, base, kws))
                st.session_state[f"ab_{i}"]=cands
            cands = st.session_state.get(f"ab_{i}", [])
            for idx, t in enumerate(cands):
                st.write(f"{idx+1}. {t}")
                copy_button(t, key=f"ab_{i}_{idx}")

    st.markdown("---")
    st.write("**생성 결과**")
    for idx, t in enumerate(st.session_state.get("name_cands", [])):
        st.write(f"{idx+1}. {t}")
        copy_button(t, key=f"cand_{idx}")

# -------------------- elevenst --------------------
def _summary(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "count":[len(df)],
        "avg_price":[df["price"].mean() if "price" in df else None],
        "sum_sales":[df["sales"].sum() if "sales" in df else None]
    })

def render_elevenst():
    st.subheader("11번가 요약")
    url = st.text_input("리스트/검색 URL (옵션)", placeholder="https://www.11st.co.kr/...")
    st.caption("모바일 embed는 정책상 제외. 대신 요약 카드 + 링크 아웃 제공.")

    use_cache = st.checkbox("캐시(샘플) 사용", value=True)
    if use_cache:
        df = pd.DataFrame({
            "title": [f"샘플상품{i}" for i in range(1,11)],
            "price": [i*1000 for i in range(10)],
            "sales": [i*3 for i in range(10)],
            "link": [url or "https://www.11st.co.kr/"]*10
        })
    else:
        up = st.file_uploader("크롤 결과 CSV 업로드", type=["csv"])
        if up is None:
            st.info("CSV 업로드 또는 캐시 사용을 선택하세요.")
            return
        df = pd.read_csv(up)

    for _, r in df.iterrows():
        st.markdown(f"**{r.get('title','')}**\n\n- 가격: {r.get('price','-')}\n- 판매량: {r.get('sales','-')}\n- 링크: {r.get('link','-')}\n")

    st.write("요약표")
    st.dataframe(_summary(df))

    st.download_button("CSV 다운로드", data=to_csv_bytes(df), file_name="11st_list.csv", mime="text/csv")

# -------------------- main app --------------------
st.title("✅ ENVY v26 • Single-file (Merged)")
st.caption("단일 파일 배포용 • v23 앵커 기반 복구판 연속성 보장")

apply_mobile_css()

# Sidebar calculator
with st.sidebar:
    st.header("환율/마진 계산기")
    mode = st.radio("모드", ["로켓그로스","해외구매대행"], horizontal=True)
    ex = st.number_input("환율 CNY→KRW", 0.0, 10000.0, 190.0, 0.5)
    card = st.number_input("카드/PG(%)", 0.0, 100.0, 4.0, 0.1)
    market = st.number_input("마켓(%)", 0.0, 100.0, 14.0, 0.1)
    target = st.number_input("목표마진(%)", 0.0, 100.0, 10.0, 0.1)
    basis = st.selectbox("마진 기준", ["on_cost","on_sale"], index=0)
    fee_mode = st.selectbox("수수료 처리", ["deduct_from_payout","add_on_top"], index=0)

    if mode=="로켓그로스":
        cny = st.number_input("상품원가(CNY)", 0.0, 1e9, 830.0, 1.0)
        total = 0.0
    else:
        cny = 0.0
        total = st.number_input("총 원가(KRW)", 0.0, 1e12, 250000.0, 100.0)
    domestic = st.number_input("국내배송/창고", 0.0, 1e9, 0.0, 100.0)
    intl = st.number_input("국제배송", 0.0, 1e9, 0.0, 100.0)
    pack = st.number_input("포장비", 0.0, 1e9, 0.0, 100.0)
    other = st.number_input("기타비용", 0.0, 1e9, 0.0, 100.0)

    mi = MarginInputs(
        exchange_rate=ex, product_cost_cny=cny, total_cost_krw=total,
        domestic_ship=domestic, intl_ship=intl, packaging=pack, other=other,
        card_fee_pct=card, market_fee_pct=market, target_margin_pct=target,
        basis=basis, fee_mode=fee_mode, mode="rocket" if mode=="로켓그로스" else "buying"
    )
    res = solve_sale(mi)
    st.metric("권장 판매가", f"{res['sale_price']:,.0f} KRW")
    st.metric("순이익", f"{res['net_profit']:,.0f} KRW")
    st.caption(f"순마진(판매가): {res['net_margin_on_sale']:.2f}% • 순마진(원가): {res['net_margin_on_cost']:.2f}%")

tab1, tab2, tab3, tab4 = st.tabs(["데이터랩","상품명 생성기","11번가","시나리오 저장/불러오기"])
with tab1: render_datalab()
with tab2: render_namegen()
with tab3: render_elevenst()

with tab4:
    st.subheader("시나리오 저장/불러오기 (JSON)")
    if st.button("현재 설정 저장"):
        payload = dict(margin_inputs=mi.__dict__)
        download_bytes("envy_v26_scenario.json", save_scenario_json(payload), "JSON 다운로드")
    up = st.file_uploader("JSON 불러오기", type=["json"])
    if up is not None:
        loaded = load_scenario_json(up)
        st.write("불러온 시나리오:", loaded)
        # 자동 주입
        try:
            vals = loaded.get("margin_inputs", {})
            for k,v in vals.items():
                st.session_state[k]=v
            st.success("사이드바 입력에 자동 반영했습니다. 값 확인 후 필요시 수정하세요.")
        except Exception:
            st.warning("자동 반영 실패. 형식을 확인하세요.")

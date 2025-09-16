
# ENVY v26.3 • Full Version (UI Fix + Sourcing + NameGen with HuggingFace KoGPT2)
# ⚠️ HuggingFace API Key is hardcoded (local test only, do not share)
import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import json, random, html, requests

st.set_page_config(page_title="ENVY v26.3 Full", page_icon="🚀", layout="wide")

HF_API_KEY = "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"

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
    safe_text = html.escape(text).replace("\n","\\n").replace("'","\\'")
    html_str = f"""
    <div style='display:flex;gap:8px;align-items:center;margin:6px 0;'>
      <input id='inp_{key}' value='{html.escape(text)}' style='flex:1;padding:6px 8px;' />
      <button onclick="navigator.clipboard.writeText('{safe_text}')">복사</button>
    </div>
    """
    st.components.v1.html(html_str, height=46)

# -------------------- calculators --------------------
class MarginInputs:
    def __init__(self, exchange_rate=190.0, product_cost_cny=0.0, total_cost_krw=0.0,
                 domestic_ship=0.0, intl_ship=0.0, packaging=0.0, other=0.0,
                 card_fee_pct=4.0, market_fee_pct=14.0, target_margin_pct=10.0,
                 basis="on_cost", fee_mode="deduct_from_payout", mode="rocket"):
        self.exchange_rate=exchange_rate; self.product_cost_cny=product_cost_cny; self.total_cost_krw=total_cost_krw
        self.domestic_ship=domestic_ship; self.intl_ship=intl_ship; self.packaging=packaging; self.other=other
        self.card_fee_pct=card_fee_pct; self.market_fee_pct=market_fee_pct; self.target_margin_pct=target_margin_pct
        self.basis=basis; self.fee_mode=fee_mode; self.mode=mode

def pct(x): return x/100.0

def aggregate_cost_krw(mi: MarginInputs) -> float:
    base = mi.product_cost_cny * mi.exchange_rate if mi.mode=="rocket" else mi.total_cost_krw
    return max(0.0, base + mi.domestic_ship + mi.intl_ship + mi.packaging + mi.other)

def solve_sale(mi: MarginInputs):
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
    return dict(sale_price=P,revenue_after_fees=revenue,fees_total=fees,net_profit=profit,
                cost_total=c,net_margin_on_sale=on_sale,net_margin_on_cost=on_cost)

# -------------------- tab contents --------------------
def render_datalab():
    st.subheader("데이터랩 Top100 (네이버 API 자리)")
    df = pd.DataFrame({
        "keyword":[f"키워드{i}" for i in range(1,21)],
        "curr":np.random.randint(50,200,20),
        "prev":np.random.randint(50,200,20)
    })
    df["diff"]=df["curr"]-df["prev"]
    df["color"]=np.where(df["diff"]>=0,"green","red")
    chart = alt.Chart(df).mark_bar().encode(
        x="keyword", y="diff", color=alt.Color("color", scale=None),
        tooltip=["keyword","curr","prev","diff"]
    ).properties(width=600,height=300)
    st.altair_chart(chart,use_container_width=True)

def render_itemscout():
    st.subheader("아이템스카우트 (무료 placeholder)")
    st.table(pd.DataFrame({
        "키워드":["예시1","예시2","예시3"],
        "검색량":[1234,4321,2222],
        "경쟁도":["낮음","높음","중간"]
    }))

def render_elevenst():
    st.subheader("11번가 요약 (샘플)")
    df = pd.DataFrame({
        "title":[f"상품{i}" for i in range(1,6)],
        "price":[i*1000 for i in range(1,6)],
        "sales":[i*10 for i in range(1,6)]
    })
    st.dataframe(df)

def render_sourcing():
    st.subheader("소싱레이더")
    st.markdown("### 국내")
    st.write("- 네이버 데이터랩 (API 자리)")
    st.write("- 아이템스카우트 (무료 placeholder)")
    st.write("- 셀러라이프 (무료 placeholder)")
    st.markdown("### 글로벌")
    st.write("- Amazon Best Seller (크롤링 placeholder)")
    st.write("- Rakuten Ichiba Ranking (API placeholder)")

def render_namegen():
    st.subheader("상품명 생성기 (규칙 + HuggingFace KoGPT2)")
    brand = st.text_input("브랜드", "envy")
    base = st.text_input("베이스 키워드", "K-coffee mix")
    keywords = st.text_input("연관키워드", "Maxim, Kanu, Korea")
    badwords = st.text_input("금칙어", "copy, fake, replica")
    limit = st.slider("글자수 제한", 20, 120, 80)
    mode = st.radio("모드 선택", ["규칙 기반","HuggingFace AI"], horizontal=True)

    def filter_and_trim(cands:list) -> list:
        bans = {w.strip().lower() for w in badwords.split(",") if w.strip()}
        out=[]
        for t in cands:
            t2 = " ".join(t.split())
            if any(b in t2.lower() for b in bans): continue
            if len(t2)>limit: t2=t2[:limit]
            out.append(t2)
        return out

    if st.button("생성"):
        kws=[k.strip() for k in keywords.split(",") if k.strip()]
        cands=[]
        if mode=="규칙 기반":
            for _ in range(5):
                pref=random.choice(["[New]","[Hot]","[Korea]"])
                suf=random.choice(["2025","FastShip","HotDeal"])
                join=random.choice([" | "," · "," - "])
                cands.append(f"{pref} {brand}{join}{base} {', '.join(kws[:2])} {suf}")
        else:
            if not HF_API_KEY:
                st.warning("HuggingFace Key 없음 → 규칙 기반으로 대체")
                for _ in range(5):
                    cands.append(f"{brand} {base} {random.choice(kws)}")
            else:
                st.info("HuggingFace Inference API 호출 (모델: skt/kogpt2-base-v2)")
                API_URL = "https://api-inference.huggingface.co/models/skt/kogpt2-base-v2"
                headers = {"Authorization": f"Bearer {HF_API_KEY}" }
                payload = {"inputs": f"상품명 추천: {brand} {base} {', '.join(kws)}"}
                try:
                    resp = requests.post(API_URL, headers=headers, json=payload, timeout=15)
                    if resp.status_code==200:
                        data = resp.json()
                        text = data[0].get("generated_text","")
                        lines = [line.strip() for line in text.split("\n") if line.strip()]
                        cands = lines[:5] if lines else [text[:limit]]
                    else:
                        st.error(f"HuggingFace API 오류: {resp.status_code}")
                except Exception as e:
                    st.error(f"HuggingFace 호출 실패: {e}")
        cands = filter_and_trim(cands)
        st.session_state["name_cands"]=cands

    st.markdown("---")
    st.write("생성 결과")
    for idx, t in enumerate(st.session_state.get("name_cands", [])):
        st.write(f"{idx+1}. {t}")
        copy_button(t, key=f"cand_{idx}")

def render_sellerlife():
    st.subheader("셀러라이프 (무료 placeholder)")
    st.table(pd.DataFrame({
        "키워드":["샘플1","샘플2","샘플3"],
        "트렌드":["상승","하락","유지"]
    }))

def render_scenario(mi):
    st.subheader("시나리오 저장/불러오기")
    if st.button("현재 설정 저장"):
        payload = dict(margin_inputs=mi.__dict__)
        download_bytes("envy_v26_scenario.json", save_scenario_json(payload), "JSON 다운로드")
    up = st.file_uploader("JSON 불러오기", type=["json"])
    if up:
        loaded = load_scenario_json(up)
        st.write("불러온 시나리오:", loaded)

# -------------------- main --------------------
st.title("🚀 ENVY v26.3 Full Version")
st.caption("UI Fix + 소싱레이더 + HuggingFace 한국어 모델")

apply_mobile_css()

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
    mi = MarginInputs(exchange_rate=ex,product_cost_cny=cny,total_cost_krw=total,
        domestic_ship=domestic,intl_ship=intl,packaging=pack,other=other,
        card_fee_pct=card,market_fee_pct=market,target_margin_pct=target,
        basis=basis,fee_mode=fee_mode,mode="rocket" if mode=="로켓그로스" else "buying")
    res = solve_sale(mi)
    st.metric("권장 판매가", f"{res['sale_price']:,.0f} KRW")
    st.metric("순이익", f"{res['net_profit']:,.0f} KRW")
    st.caption(f"순마진(판매가): {res['net_margin_on_sale']:.2f}% • 순마진(원가): {res['net_margin_on_cost']:.2f}%")

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(
    ["데이터랩","아이템스카우트","11번가","소싱레이더","상품명 생성기","셀러라이프","시나리오 저장/불러오기"]
)

with tab1: render_datalab()
with tab2: render_itemscout()
with tab3: render_elevenst()
with tab4: render_sourcing()
with tab5: render_namegen()
with tab6: render_sellerlife()
with tab7: render_scenario(mi)

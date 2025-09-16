
# ENVY v26.5 • Full (DataLab line chart + 11st mobile embed attempt)
# ⚠️ HF API Key is hardcoded for local testing. Do NOT share.
import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import json, random, html, requests, textwrap

st.set_page_config(page_title="ENVY v26.5 Full", page_icon="🚀", layout="wide")
HF_API_KEY = "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"

# -------------------- utils --------------------
def download_bytes(filename: str, data: bytes, label: str = "다운로드"):
    st.download_button(label, data=data, file_name=filename, mime="application/octet-stream")

def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")

def apply_mobile_css():
    st.markdown(
        """
        <style>
        @media (max-width: 640px) {
            .block-container { padding-left: 0.6rem; padding-right: 0.6rem; }
        }
        .card { padding: 12px 14px; border: 1px solid #eee; border-radius: 10px; }
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

# -------------------- margin calc --------------------
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
    revenue = P*(1-cf-mf); fees = P-revenue; profit = revenue - c
    on_sale = (profit/P*100) if P>0 else 0.0; on_cost = (profit/c*100) if c>0 else 0.0
    return dict(sale_price=P, revenue_after_fees=revenue, fees_total=fees, net_profit=profit,
                cost_total=c, net_margin_on_sale=on_sale, net_margin_on_cost=on_cost)

# -------------------- sections --------------------
def sec_datalab(container):
    with container:
        st.subheader("데이터랩 (카테고리/키워드 표시 + 실선 그래프)")
        # Inputs visible
        colA, colB, colC = st.columns([1,1,1])
        with colA:
            category = st.text_input("카테고리", "식품 > 커피/믹스/차")
        with colB:
            keyword = st.text_input("대표 키워드", "커피 믹스")
        with colC:
            period = st.selectbox("기간", ["최근7일","최근30일","최근90일"], index=1)
        # Mock data; replace with real API later
        n=20
        df = pd.DataFrame({
            "rank": list(range(1, n+1)),
            "keyword": [f"{keyword}-{i}" for i in range(1, n+1)],
            "curr": np.clip(np.random.normal(120, 25, n).astype(int), 10, None),
            "prev": np.clip(np.random.normal(100, 25, n).astype(int), 5, None),
        })
        st.caption(f"카테고리: {category} • 키워드 예시: {keyword}")
        # Line chart (solid lines)
        dfm = df.melt(id_vars=["rank","keyword"], value_vars=["curr","prev"], var_name="series", value_name="value")
        line = alt.Chart(dfm).mark_line().encode(
            x=alt.X("rank:Q", title="랭크(1=상위)"),
            y=alt.Y("value:Q", title="검색량(지수)"),
            color=alt.Color("series:N", title="기간", scale=alt.Scale(domain=["curr","prev"], range=["#1f77b4","#ff7f0e"])),
            tooltip=["rank","keyword","series","value"]
        ).properties(height=230)
        st.altair_chart(line, use_container_width=True)
        st.download_button("CSV 내보내기", data=to_csv_bytes(df), file_name="datalab_top.csv", mime="text/csv")

def sec_itemscout(container):
    with container:
        st.subheader("아이템스카우트")
        st.dataframe(pd.DataFrame({
            "키워드":["예시1","예시2","예시3","예시4"],
            "검색량":[1234,4321,2222,3100],
            "경쟁도":["낮음","높음","중간","낮음"]
        }), use_container_width=True)

def sec_11st(container):
    with container:
        st.subheader("11번가 (모바일 화면 임베드 시도)")
        url = st.text_input("상품/리스트 URL", "https://www.11st.co.kr/")
        st.caption("모바일 뷰 임베드가 차단되면 요약표와 링크만 표시됩니다.")
        # Try to embed mobile view
        mobile_url = url.replace("www.11st.co.kr","m.11st.co.kr")
        iframe_html = f"""
        <div style="width:100%;height:520px;border:1px solid #eee;border-radius:10px;overflow:hidden">
            <iframe src="{mobile_url}" width="100%" height="100%" frameborder="0" sandbox="allow-same-origin allow-scripts allow-popups allow-forms"></iframe>
        </div>
        """
        st.components.v1.html(iframe_html, height=540)
        # Fallback summary
        df = pd.DataFrame({
            "title":[f"상품{i}" for i in range(1,6)],
            "price":[i*1000 for i in range(1,6)],
            "sales":[i*7 for i in range(1,6)],
            "link":[url]*5
        })
        with st.expander("임베드 실패 대비 요약표 보기"):
            st.dataframe(df, use_container_width=True)
            st.download_button("CSV 다운로드", data=to_csv_bytes(df), file_name="11st_list.csv", mime="text/csv")

def sec_sourcing(container):
    with container:
        st.subheader("소싱레이더")
        st.markdown("- 국내: 네이버(실API 자리), 아이템스카우트/셀러라이프 placeholder")
        st.markdown("- 글로벌: Amazon Best Seller(크롤링 자리), Rakuten Ranking(API 자리)")

def sec_namegen(container):
    with container:
        st.subheader("상품명 생성기 (규칙 + HuggingFace KoGPT2)")
        brand = st.text_input("브랜드", "envy", key="ng_brand")
        base = st.text_input("베이스 키워드", "K-coffee mix", key="ng_base")
        keywords = st.text_input("연관키워드", "Maxim, Kanu, Korea", key="ng_kws")
        badwords = st.text_input("금칙어", "copy, fake, replica", key="ng_bans")
        limit = st.slider("글자수 제한", 20, 120, 80, key="ng_limit")
        mode = st.radio("모드", ["규칙 기반","HuggingFace AI"], horizontal=True, key="ng_mode")

        def filter_and_trim(cands:list) -> list:
            bans = {w.strip().lower() for w in st.session_state["ng_bans"].split(",") if w.strip()}
            out=[]
            for t in cands:
                t2 = " ".join(t.split())
                if any(b in t2.lower() for b in bans): continue
                if len(t2)>st.session_state["ng_limit"]: t2=t2[:st.session_state["ng_limit"]]
                out.append(t2)
            return out

        if st.button("생성", key="ng_go"):
            kws=[k.strip() for k in st.session_state["ng_kws"].split(",") if k.strip()]
            cands=[]
            if st.session_state["ng_mode"]=="규칙 기반":
                for _ in range(5):
                    pref=random.choice(["[New]","[Hot]","[Korea]"])
                    suf=random.choice(["2025","FastShip","HotDeal"])
                    join=random.choice([" | "," · "," - "])
                    cands.append(f"{pref} {st.session_state['ng_brand']}{join}{st.session_state['ng_base']} {', '.join(kws[:2])} {suf}")
            else:
                API_URL = "https://api-inference.huggingface.co/models/skt/kogpt2-base-v2"
                headers = {"Authorization": f"Bearer {HF_API_KEY}", "X-Wait-For-Model": "true"}
                prompt = f"상품명 추천 5개: 브랜드={st.session_state['ng_brand']}, 베이스={st.session_state['ng_base']}, 키워드={', '.join(kws)}. 한국어로 간결하게."
                payload = {"inputs": prompt, "parameters": {"max_new_tokens": 64, "return_full_text": False}}
                try:
                    resp = requests.post(API_URL, headers=headers, json=payload, timeout=30)
                    if resp.status_code==200:
                        data = resp.json()
                        if isinstance(data, list) and data and "generated_text" in data[0]:
                            text = data[0]["generated_text"]
                        else:
                            text = json.dumps(data, ensure_ascii=False)
                        lines = [line.strip("-• ").strip() for line in text.split("\n") if line.strip()]
                        if len(lines)<5:
                            lines = [s.strip() for s in textwrap.fill(text, 120).split(".") if s.strip()]
                        cands = lines[:5]
                    else:
                        try:
                            err = resp.json()
                        except Exception:
                            err = resp.text
                        st.error(f"HuggingFace API 오류: {resp.status_code} / {err}")
                except Exception as e:
                    st.error(f"HuggingFace 호출 실패: {e}")
            st.session_state["name_cands"]=filter_and_trim(cands)

        for i, t in enumerate(st.session_state.get("name_cands", []), start=1):
            st.write(f"{i}. {t}")
            copy_button(t, key=f"name_{i}")

def sec_sellerlife(container):
    with container:
        st.subheader("셀러라이프")
        st.dataframe(pd.DataFrame({
            "키워드":["샘플1","샘플2","샘플3"],
            "트렌드":["상승","하락","유지"]
        }), use_container_width=True)

# -------------------- main --------------------
st.title("🚀 ENVY v26.5 Full (DataLab 라인차트 + 11번가 모바일 임베드)")
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

# Layout: 3 + 3 columns
c1, c2, c3 = st.columns(3)
sec_datalab(c1)
sec_itemscout(c2)
sec_11st(c3)

c4, c5, c6 = st.columns(3)
sec_sourcing(c4)
sec_namegen(c5)
sec_sellerlife(c6)

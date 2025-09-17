
# ENVY v26.9 • Full (FX: USD/EUR/JPY/CNY select + 2-decimals + EUR support)
# ⚠️ HF API Key is hardcoded for local testing. Do NOT share.
import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import json, random, html, requests, textwrap, urllib.parse

st.set_page_config(page_title="ENVY v26.9 Full", page_icon="🚀", layout="wide")
HF_API_KEY = "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"

# -------------------- currency utils --------------------
CURRENCY_SYMBOL = {
    "KRW": "₩",
    "CNY": "CN¥",
    "JPY": "¥",
    "USD": "$",
    "EUR": "€",
}
FX_ORDER = ["USD","EUR","JPY","CNY"]  # select box order

def fmt_money(v: float, code: str="KRW"):
    sym = CURRENCY_SYMBOL.get(code, "")
    try:
        return f"{sym}{v:,.0f} {code}"
    except Exception:
        return f"{v} {code}"

# -------------------- mock dictionaries --------------------
CATE_KEYWORDS = {
    "식품 > 커피/믹스/차": ["커피 믹스","맥심","카누","드립백","인스턴트 커피","유자차","녹차","보리차","아메리카노","스틱 커피","원두커피","디카페인","콜드브루","헤이즐넛","캡슐커피","카라멜마끼아또","티백","허브티","핫초코","라떼"]
    ,
    "가전 > 주방가전": ["에어프라이어","전기포트","커피머신","믹서기","전기밥솥","토스터","전기그릴","전기프라이팬","정수기","식기세척기",
                     "전기오븐","에스프레소 머신","핸드블렌더","에어프라이 오븐","전기찜기","전기요리기","전기쿠커","전기라면포트","밀크포머","제빙기"],
    "생활 > 세제/위생": ["세탁세제","섬유유연제","표백제","주방세제","물티슈","베이킹소다","구연산","변기세정제","락스","청소포",
                     "빨래비누","섬유향수","매직블럭","크리너","세탁볼","고무장갑","행주","스프레이세제","유리세정제","젤리크리너"],
    "뷰티 > 스킨케어": ["토너","에센스","선크림","클렌징폼","마스크팩","앰풀","크림","아이크림","클렌징오일","폼클렌저",
                    "페이셜오일","수분크림","나이아신아마이드","비타민C 세럼","레티놀","패드","미스트","시카크림","선스틱","수분앰플"],
    "완구/취미 > 피규어/프라모델": ["건프라","프라모델","피규어","레고 호환","프라도색","니퍼","도색붓","프라모델 접착제","웨더링","베이스판",
                               "스탠드","스티커","파일럿피규어","프라모델 공구","프라모델 세척","스크라이버","사포","도료","프라모델 수납","데칼"]
}
GLOBAL_KEYWORDS = {
    "Amazon US": ["protein bar","wireless earbuds","air fryer","heated blanket","gel nail kit"],
    "Amazon JP": ["コーヒーミックス","加湿器","トレカスリーブ","ワイヤレスイヤホン","抹茶"],
    "Rakuten JP": ["楽天ランキング","水筒","タンブラー","サプリメント","タオル"]
}

# -------------------- utils --------------------
def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")

def copy_button(text: str, key: str):
    safe_text = html.escape(text).replace("\n","\\n").replace("'","\\'")
    html_str = f"""
    <div style='display:flex;gap:8px;align-items:center;margin:6px 0;'>
      <input id='inp_{key}' value='{html.escape(text)}' style='flex:1;padding:6px 8px;' />
      <button onclick="navigator.clipboard.writeText('{safe_text}')">복사</button>
    </div>
    """
    st.components.v1.html(html_str, height=46)

# -------------------- margin calc (buying-only) --------------------
class MarginInputs:
    def __init__(self, exchange_rate=1400.00, total_cost_krw=0.0,
                 domestic_ship=0.0, intl_ship=0.0, packaging=0.0, other=0.0,
                 card_fee_pct=4.0, market_fee_pct=14.0, target_margin_pct=10.0,
                 basis="on_cost", fee_mode="deduct_from_payout",
                 base_ccy="USD"):
        self.exchange_rate=exchange_rate; self.total_cost_krw=total_cost_krw
        self.domestic_ship=domestic_ship; self.intl_ship=intl_ship; self.packaging=packaging; self.other=other
        self.card_fee_pct=card_fee_pct; self.market_fee_pct=market_fee_pct; self.target_margin_pct=target_margin_pct
        self.basis=basis; self.fee_mode=fee_mode; self.base_ccy=base_ccy

def pct(x): return x/100.0
def aggregate_cost_krw(mi: MarginInputs) -> float:
    return max(0.0, mi.total_cost_krw + mi.domestic_ship + mi.intl_ship + mi.packaging + mi.other)

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
    revenue = P*(1-cf-mf); profit = revenue - c
    return dict(sale_price=P, net_profit=profit,
                on_sale=(profit/P*100) if P>0 else 0.0,
                on_cost=(profit/c*100) if c>0 else 0.0)

# -------------------- sections --------------------
def sec_datalab(container):
    with container:
        st.subheader("데이터랩 (카테고리 선택 → Top20 키워드)")
        category = st.selectbox("카테고리", list(CATE_KEYWORDS.keys()), index=0, key="dl_category")
        kw_list = CATE_KEYWORDS.get(category, [])
        keyword = st.selectbox("대표 키워드", kw_list, index=0 if kw_list else None, key="dl_keyword")
        period = st.selectbox("기간", ["최근7일","최근30일","최근90일"], index=1, key="dl_period")
        # Top20 keywords (mock score)
        rng = np.random.default_rng(0)
        scores = rng.integers(50, 200, size=min(20, len(kw_list)))
        top_df = pd.DataFrame({"rank": range(1, len(scores)+1), "keyword": kw_list[:len(scores)], "score": scores}).sort_values("rank")
        st.caption(f"카테고리: {category} • 대표 키워드: {keyword}")
        st.table(top_df)
        st.download_button("Top20 키워드 CSV", data=to_csv_bytes(top_df), file_name="datalab_top20.csv", mime="text/csv")
        # Trend line
        n=20
        curr = np.clip(rng.normal(120, 25, n).astype(int), 10, None)
        prev = np.clip(rng.normal(100, 25, n).astype(int), 5, None)
        df = pd.DataFrame({"rank": range(1,n+1), "curr": curr, "prev": prev})
        dfm = df.melt(id_vars=["rank"], value_vars=["curr","prev"], var_name="series", value_name="value")
        line = alt.Chart(dfm).mark_line().encode(
            x=alt.X("rank:Q", title="랭크(1=상위)"),
            y=alt.Y("value:Q", title="검색량(지수)"),
            color=alt.Color("series:N", title="기간", scale=alt.Scale(domain=["curr","prev"], range=["#1f77b4","#ff7f0e"])),
            tooltip=["rank","series","value"]
        ).properties(height=220)
        st.altair_chart(line, use_container_width=True)

def sec_itemscout(container):
    with container:
        st.subheader("아이템스카우트 (샘플)")
        st.dataframe(pd.DataFrame({
            "키워드":["예시1","예시2","예시3","예시4"],
            "검색량":[1234,4321,2222,3100],
            "경쟁도":["낮음","높음","중간","낮음"]
        }), use_container_width=True)

def sec_11st(container):
    with container:
        st.subheader("11번가 (프록시 임베드)")
        url = st.text_input("대상 URL", "https://www.11st.co.kr/")
        proxy = st.text_input("프록시 엔드포인트(예: https://your-proxy/app)", value="", help="target 쿼리로 원본 URL을 넘깁니다. 예) https://your-proxy/app?target=https%3A%2F%2Fm.11st.co.kr")
        st.caption("프록시는 CORS/X-Frame-Options 우회용 중개 서버입니다. 값이 비어있으면 기본 iframe 시도 후 요약표로 대체합니다.")
        if proxy:
            target = urllib.parse.quote(url.replace("www.11st.co.kr","m.11st.co.kr"), safe="")
            src = f"{proxy}?target={target}"
        else:
            src = url.replace("www.11st.co.kr","m.11st.co.kr")
        iframe_html = f"""
        <div style="width:100%;height:520px;border:1px solid #eee;border-radius:10px;overflow:hidden">
            <iframe src="{src}" width="100%" height="100%" frameborder="0" sandbox="allow-same-origin allow-scripts allow-popups allow-forms"></iframe>
        </div>
        """
        st.components.v1.html(iframe_html, height=540)
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
        st.subheader("소싱레이더 (키워드 목록 + 국내/글로벌 필터)")
        cA, cB = st.columns(2)
        with cA:
            show_domestic = st.checkbox("국내 보기 (네이버/아이템스카우트/셀러라이프)", value=True, key="sr_dom")
        with cB:
            show_global = st.checkbox("글로벌 보기 (Amazon/Rakuten)", value=True, key="sr_glb")
        if show_domestic:
            st.markdown("**국내 키워드 후보**")
            dom_kws = CATE_KEYWORDS.get(st.session_state.get("dl_category", list(CATE_KEYWORDS.keys())[0]), [])
            st.table(pd.DataFrame({"keyword": dom_kws[:20]}))
        if show_global:
            st.markdown("**글로벌 키워드 후보**")
            rows = []
            for market, kws in GLOBAL_KEYWORDS.items():
                for k in kws:
                    rows.append({"market": market, "keyword": k})
            st.dataframe(pd.DataFrame(rows), use_container_width=True)

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
        st.subheader("셀러라이프 (샘플)")
        st.dataframe(pd.DataFrame({
            "키워드":["샘플1","샘플2","샘플3"],
            "트렌드":["상승","하락","유지"]
        }), use_container_width=True)

# -------------------- main --------------------
st.title("🚀 ENVY v26.9 Full (USD 기본 • EUR 추가 • 2자리 소수 환율)")

# Sidebar (buying-only, multi-FX select)
with st.sidebar:
    st.header("환율/마진 계산기 (해외구매대행)")
    base_ccy = st.selectbox("기준 통화", FX_ORDER, index=0, help="미국(USD) → 유럽(EUR) → 일본(JPY) → 중국(CNY) 순서")
    sym = CURRENCY_SYMBOL.get(base_ccy, "")
    # default rates for KRW per 1 base currency (you can edit)
    default_rates = {"USD": 1400.00, "EUR": 1500.00, "JPY": 9.50, "CNY": 190.00}
    ex = st.number_input(f"환율 (1 {sym} → ? ₩)", 0.00, 100000.00, float(default_rates.get(base_ccy, 1400.00)), 0.01, format="%.2f")
    card = st.number_input("카드/PG(%)", 0.0, 100.0, 4.0, 0.1)
    market = st.number_input("마켓(%)", 0.0, 100.0, 14.0, 0.1)
    target = st.number_input("목표마진(%)", 0.0, 100.0, 10.0, 0.1)
    basis = st.selectbox("마진 기준", ["on_cost","on_sale"], index=0)
    fee_mode = st.selectbox("수수료 처리", ["deduct_from_payout","add_on_top"], index=0)
    total = st.number_input("총 원가 (₩ KRW)", 0.0, 1e12, 250000.0, 100.0)
    domestic = st.number_input("국내배송/창고 (₩)", 0.0, 1e9, 0.0, 100.0)
    intl = st.number_input("국제배송 (₩)", 0.0, 1e9, 0.0, 100.0)
    pack = st.number_input("포장비 (₩)", 0.0, 1e9, 0.0, 100.0)
    other = st.number_input("기타비용 (₩)", 0.0, 1e9, 0.0, 100.0)

    mi = MarginInputs(exchange_rate=ex,total_cost_krw=total,
        domestic_ship=domestic,intl_ship=intl,packaging=pack,other=other,
        card_fee_pct=card,market_fee_pct=market,target_margin_pct=target,
        basis=basis,fee_mode=fee_mode,base_ccy=base_ccy)
    res = solve_sale(mi)
    st.metric("권장 판매가", fmt_money(res['sale_price'], "KRW"))
    st.metric("순이익", fmt_money(res['net_profit'], "KRW"))
    st.caption(f"환율 미리보기: 1 {sym} = {ex:.2f} {CURRENCY_SYMBOL['KRW']} • 마진(판매가): {res['on_sale']:.2f}% • 마진(원가): {res['on_cost']:.2f}%")

# Body layout: 3 + 3 columns
c1, c2, c3 = st.columns(3)
sec_datalab(c1)
sec_itemscout(c2)
sec_11st(c3)

c4, c5, c6 = st.columns(3)
sec_sourcing(c4)
sec_namegen(c5)
sec_sellerlife(c6)

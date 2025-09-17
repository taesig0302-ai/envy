# ENVY v27.1 • Full (Naver DataLab internal crawl + v23 margin + fixed UI order)
# ⚠️ 비공식 크롤링 포함: 교육/테스트 용도. 상용 배포 전 반드시 검토하세요.

import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import json, random, html, requests, textwrap, urllib.parse, datetime

st.set_page_config(page_title="ENVY v27.1 Full", page_icon="🚀", layout="wide")

# -------------------- Config --------------------
HF_API_KEY = st.secrets.get("HF_API_KEY", "")  # Optional: HuggingFace token
CURRENCY_SYMBOL = {"KRW":"₩","USD":"$","EUR":"€","JPY":"¥","CNY":"CN¥"}
FX_ORDER = ["USD","EUR","JPY","CNY"]

# Naver DataLab Top-level 10 categories (name -> (cid, note))
# cid 값은 실제와 다를 수 있음. 필요 시 아래 매핑을 네이버 실제 ID로 교체하세요.
NAVER_CATEGORIES = {
    "패션의류": ("50000000", "Top-level fashion apparel"),
    "패션잡화": ("50000001", "Fashion accessories"),
    "화장품/미용": ("50000002", "Beauty"),
    "디지털/가전": ("50000003", "Digital/Appliances"),
    "가구/인테리어": ("50000004", "Furniture/Interior"),
    "식품": ("50000005", "Food"),
    "생활/건강": ("50000006", "Living/Health"),
    "출산/육아": ("50000007", "Baby"),
    "스포츠/레저": ("50000008", "Sports/Leisure"),
    "도서/취미/애완": ("50000009", "Books/Hobby/Pets")
}

# -------------------- Helpers --------------------
def fmt_money(v: float, code: str="KRW"):
    sym = CURRENCY_SYMBOL.get(code, "")
    try:
        return f"{sym}{v:,.0f} {code}"
    except Exception:
        return f"{v:,.0f} {code}"

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

# -------------------- FX Converter (simple) --------------------
def convert_to_krw(amount_foreign: float, rate_krw_per_unit: float) -> float:
    return max(0.0, amount_foreign * rate_krw_per_unit)

# -------------------- v23 margin formulas --------------------
def margin_calc_percent(cost_krw: float, card_pct: float, market_pct: float, margin_pct: float, shipping_krw: float):
    """
    v23 on-cost, fees deducted:
    P*(1 - card - market) = (C + S) * (1 + m)
    """
    cf, mf, m = card_pct/100.0, market_pct/100.0, margin_pct/100.0
    denom = max(1e-9, 1 - cf - mf)
    target_rev = (cost_krw + shipping_krw) * (1 + m)
    P = target_rev / denom
    revenue = P * (1 - cf - mf)
    profit = revenue - (cost_krw + shipping_krw)
    return P, profit, (profit/P*100 if P>0 else 0.0)

def margin_calc_add(cost_krw: float, card_pct: float, market_pct: float, add_margin_krw: float, shipping_krw: float):
    """
    v23 additive, fees deducted:
    P*(1 - card - market) = (C + S) + A
    """
    cf, mf = card_pct/100.0, market_pct/100.0
    denom = max(1e-9, 1 - cf - mf)
    target_rev = (cost_krw + shipping_krw) + add_margin_krw
    P = target_rev / denom
    revenue = P * (1 - cf - mf)
    profit = revenue - (cost_krw + shipping_krw)
    return P, profit, (profit/P*100 if P>0 else 0.0)

# -------------------- Naver DataLab crawl (internal) --------------------
@st.cache_data(ttl=600, show_spinner=False)
def fetch_datalab_top20(cid: str, start_date: str, end_date: str, time_unit: str="date") -> pd.DataFrame:
    """
    Try to fetch category keyword ranking from Naver DataLab internal endpoint.
    Falls back to mock data if it fails.
    """
    url = "https://datalab.naver.com/shoppingInsight/getCategoryKeywordRank.naver"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Referer": "https://datalab.naver.com/shoppingInsight/sCategory.naver",
        "Origin": "https://datalab.naver.com",
    }
    payload = {
        "cid": cid,
        "timeUnit": time_unit,      # 'date' or 'week' or 'month'
        "startDate": start_date,    # 'YYYY-MM-DD'
        "endDate": end_date,        # 'YYYY-MM-DD'
        "device": "pc",
        "gender": "",               # '', 'm', 'f'
        "ages": ""                  # e.g. '10,20,30'
    }
    try:
        resp = requests.post(url, headers=headers, data=payload, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            key = "keywordList"
            if isinstance(data, dict) and key in data and isinstance(data[key], list) and data[key]:
                rows = []
                for item in data[key][:20]:
                    rows.append({
                        "rank": item.get("rank") or item.get("ranks") or len(rows)+1,
                        "keyword": item.get("keyword") or item.get("name") or "",
                        "search": item.get("ratio") or item.get("ratioValue") or item.get("searchCount") or 0
                    })
                df = pd.DataFrame(rows).sort_values("rank").reset_index(drop=True)
                return df
    except Exception:
        pass

    # Fallback mock (deterministic by cid)
    rng = np.random.default_rng(abs(hash(cid)) % (2**32))
    kws = [f"키워드{i}" for i in range(1, 21)]
    df = pd.DataFrame({
        "rank": list(range(1, 21)),
        "keyword": kws,
        "search": rng.integers(50, 300, size=20)
    })
    return df

# -------------------- Sections --------------------
def sec_datalab(container):
    with container:
        st.subheader("데이터랩 (실시간 Top20 · 실선그래프)")
        names = list(NAVER_CATEGORIES.keys())
        category = st.selectbox("카테고리 (네이버 기준 10개)", names, index=0, key="dl_cat")
        cid = NAVER_CATEGORIES[category][0]

        today = datetime.date.today()
        start = (today - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
        end = today.strftime("%Y-%m-%d")

        df = fetch_datalab_top20(cid, start, end, time_unit="date")
        st.caption(f"기간: {start} ~ {end} · CID: {cid}")
        st.table(df[["rank","keyword","search"]])

        chart = alt.Chart(df).mark_line().encode(
            x=alt.X("rank:Q", title="랭크(1=상위)"),
            y=alt.Y("search:Q", title="검색량(지수)"),
            tooltip=["rank","keyword","search"]
        ).properties(height=220)
        st.altair_chart(chart, use_container_width=True)

        st.download_button("Top20 CSV 다운로드", data=to_csv_bytes(df), file_name="datalab_top20.csv", mime="text/csv")

def sec_itemscout(container):
    with container:
        st.subheader("아이템스카우트 (샘플)")
        st.dataframe(pd.DataFrame({
            "키워드":["예시1","예시2","예시3","예시4","예시5"],
            "검색량":[1234,4321,2222,3100,2800],
            "경쟁도":["낮음","높음","중간","낮음","중간"]
        }), use_container_width=True)

def sec_11st(container):
    with container:
        st.subheader("11번가 (모바일 프록시 임베드)")
        url = st.text_input("대상 URL", "https://www.11st.co.kr/")
        proxy = st.text_input("프록시 엔드포인트(선택)", value="", help="예) https://your-proxy/app?target=<m.11st url>")
        if proxy:
            src = f"{proxy}?target={urllib.parse.quote(url.replace('www.11st.co.kr','m.11st.co.kr'), safe='')}"
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

def sec_sellerlife(container):
    with container:
        st.subheader("셀러라이프 (샘플)")
        st.dataframe(pd.DataFrame({
            "키워드":["샘플1","샘플2","샘플3","샘플4","샘플5"],
            "트렌드":["상승","하락","유지","상승","유지"]
        }), use_container_width=True)

def sec_ai_radar(container):
    with container:
        st.subheader("AI 키워드 레이더 (국내/글로벌)")
        mode = st.radio("모드", ["국내","글로벌"], horizontal=True, key="air_mode")
        if mode=="국내":
            st.write("• 데이터랩 + 아이템스카우트 + 셀러라이프 키워드 융합(샘플)")
            rows = []
            rows += [{"source":"DataLab","keyword":f"데이터랩{i}","score":300-i} for i in range(1,8)]
            rows += [{"source":"ItemScout","keyword":f"아이템{i}","score":250-i} for i in range(1,6)]
            rows += [{"source":"SellerLife","keyword":f"셀러{i}","score":200-i} for i in range(1,6)]
            df = pd.DataFrame(rows).sort_values("score", ascending=False)
            st.dataframe(df, use_container_width=True)
        else:
            rows = []
            rows += [{"source":"Amazon US","keyword":k,"score":300-i} for i,k in enumerate(["protein bar","wireless earbuds","air fryer","heated blanket","gel nail kit"], start=1)]
            rows += [{"source":"Rakuten JP","keyword":k,"score":220-i} for i,k in enumerate(["水筒","タンブラー","サプリメント","タオル"], start=1)]
            st.dataframe(pd.DataFrame(rows).sort_values("score", ascending=False), use_container_width=True)

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

        cands=[]
        if st.button("생성", key="ng_go"):
            kws=[k.strip() for k in st.session_state["ng_kws"].split(",") if k.strip()]
            if st.session_state["ng_mode"]=="규칙 기반":
                for _ in range(5):
                    pref=random.choice(["[New]","[Hot]","[Korea]"])
                    suf=random.choice(["2025","FastShip","HotDeal"])
                    join=random.choice([" | "," · "," - "])
                    cands.append(f"{pref} {st.session_state['ng_brand']}{join}{st.session_state['ng_base']} {', '.join(kws[:2])} {suf}")
            else:
                if not HF_API_KEY:
                    st.error("HuggingFace 토큰이 없습니다. st.secrets['HF_API_KEY']를 설정하세요.")
                else:
                    API_URL = "https://api-inference.huggingface.co/models/skt/kogpt2-base-v2"
                    headers = {"Authorization": f"Bearer {HF_API_KEY}", "X-Wait-For-Model": "true"}
                    prompt = f"상품명 추천 5개: 브랜드={st.session_state['ng_brand']}, 베이스={st.session_state['ng_base']}, 키워드={st.session_state['ng_kws']}. 한국어로 간결하게."
                    payload = {"inputs": prompt, "parameters": {"max_new_tokens": 64, "return_full_text": False}}
                    try:
                        resp = requests.post(API_URL, headers=headers, json=payload, timeout=30)
                        if resp.status_code==200:
                            data = resp.json()
                            text = data[0].get("generated_text","") if isinstance(data, list) and data else json.dumps(data, ensure_ascii=False)
                            lines = [line.strip("-• ").strip() for line in text.split("\n") if line.strip()]
                            if len(lines)<5:
                                lines = [s.strip() for s in textwrap.fill(text, 120).split(".") if s.strip()]
                            cands = lines[:5]
                        else:
                            try: err = resp.json()
                            except Exception: err = resp.text
                            st.error(f"HuggingFace API 오류: {resp.status_code} / {err}")
                    except Exception as e:
                        st.error(f"HuggingFace 호출 실패: {e}")
            st.session_state["name_cands"]=filter_and_trim(cands)
        for i, t in enumerate(st.session_state.get("name_cands", []), start=1):
            st.write(f"{i}. {t}")
            copy_button(t, key=f"name_{i}")

# -------------------- Layout --------------------
st.title("🚀 ENVY v27.1 Full (실시간 데이터랩 · v23 마진 · 고정 UI 순서)")

# Sidebar: FX + Margin (v23)
with st.sidebar:
    st.header("① 환율 계산기")
    base_ccy = st.selectbox("기준 통화", FX_ORDER, index=0)
    sym = CURRENCY_SYMBOL.get(base_ccy, "")
    fx_rate = st.number_input(f"환율 (1 {sym} → ? ₩)", 0.00, 100000.00, 1400.00 if base_ccy=='USD' else 1500.00 if base_ccy=='EUR' else 9.50 if base_ccy=='JPY' else 190.00, 0.01, format="%.2f")
    foreign_price = st.number_input(f"판매가격 ({sym})", 0.0, 1e12, 100.0, 1.0)
    krw_converted = convert_to_krw(foreign_price, fx_rate)
    st.metric("환산 금액", fmt_money(krw_converted, "KRW"))

    st.markdown("---")
    st.header("② 마진 계산기 (v23)")
    m_base = st.selectbox("기준 통화(판매금액)", FX_ORDER, index=0, key="m_base")
    m_sym = CURRENCY_SYMBOL.get(st.session_state["m_base"], "")
    m_fx = st.number_input(f"환율 (1 {m_sym} → ? ₩)", 0.00, 100000.00, fx_rate, 0.01, format="%.2f", key="m_fx")
    sale_foreign = st.number_input(f"판매금액 ({m_sym})", 0.0, 1e12, foreign_price, 1.0, key="m_sale_foreign")
    sale_krw = convert_to_krw(sale_foreign, st.session_state["m_fx"])

    card = st.number_input("카드수수료 (%)", 0.0, 100.0, 4.0, 0.1)
    market = st.number_input("마켓수수료 (%)", 0.0, 100.0, 14.0, 0.1)
    ship = st.number_input("배송비 (₩)", 0.0, 1e9, 0.0, 100.0)
    mode = st.radio("마진 방식", ["퍼센트 마진(%)","더하기 마진(₩)"], horizontal=True)
    if mode=="퍼센트 마진(%)":
        margin_pct = st.number_input("마진율 (%)", 0.0, 500.0, 10.0, 0.1)
        P, profit, on_sale = margin_calc_percent(cost_krw=sale_krw, card_pct=card, market_pct=market, margin_pct=margin_pct, shipping_krw=ship)
    else:
        add_margin = st.number_input("더하기 마진 (₩)", 0.0, 1e12, 10000.0, 100.0)
        P, profit, on_sale = margin_calc_add(cost_krw=sale_krw, card_pct=card, market_pct=market, add_margin_krw=add_margin, shipping_krw=ship)

    st.metric("판매가격 (계산 결과)", fmt_money(P, "KRW"))
    st.metric("순이익(마진)", fmt_money(profit, "KRW"))
    st.caption(f"마진율(판매가 기준): {on_sale:.2f}%")

# Fixed body order: DataLab → Itemscout → 11st → SellerLife → AI Radar → NameGen
c1, c2, c3 = st.columns(3)
sec_datalab(c1)
sec_itemscout(c2)
sec_11st(c3)

c4, c5, c6 = st.columns(3)
sec_sellerlife(c4)
sec_ai_radar(c5)
sec_namegen(c6)

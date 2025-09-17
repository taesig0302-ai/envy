
import streamlit as st
import requests, pandas as pd, re, json
from bs4 import BeautifulSoup
from pathlib import Path

# -----------------------------
# 로고 출력 (사이드바 상단)
# -----------------------------
logo_path = Path(__file__).parent / "logo.png"
with st.sidebar:
    if logo_path.exists():
        st.image(str(logo_path), width=120)
    else:
        st.markdown("**envy**")

# -----------------------------
# 다크모드 토글
# -----------------------------
if "theme" not in st.session_state:
    st.session_state["theme"] = "light"

def toggle_theme():
    st.session_state["theme"] = "dark" if st.session_state["theme"]=="light" else "light"

st.sidebar.toggle("다크 모드", value=False, on_change=toggle_theme)

# -----------------------------
# 환율 계산기
# -----------------------------
st.sidebar.markdown("### 환율 계산기")
base = st.sidebar.selectbox("기준 통화", ["USD","EUR","JPY","CNY"], index=0)
sale_foreign = st.sidebar.number_input("판매금액 (외화)", value=1.00, step=0.01, format="%.2f")
rate_map = {"USD":"$", "EUR":"€", "JPY":"¥", "CNY":"元"}
rate = {"USD":1400, "EUR":1500, "JPY":10, "CNY":200}[base]  # 샘플 고정환율
won = rate * sale_foreign
st.sidebar.success(f"환산 금액: {won:,.2f} 원 ({rate_map.get(base, '')}{sale_foreign})")

# -----------------------------
# 마진 계산기
# -----------------------------
st.sidebar.markdown("### 마진 계산기")
m_rate = st.sidebar.number_input("카드수수료 (%)", value=4.00, step=0.01, format="%.2f")
m_fee  = st.sidebar.number_input("마켓수수료 (%)", value=14.00, step=0.01, format="%.2f")
ship   = st.sidebar.number_input("배송비 (₩)", value=0.0, step=100.0, format="%.0f")
mode   = st.sidebar.radio("마진 방식", ["퍼센트 마진(%)","더하기 마진(₩)"])
margin = st.sidebar.number_input("마진율/마진액", value=10.00, step=0.01, format="%.2f")

if mode=="퍼센트 마진(%)":
    target_price = won * (1 + m_rate/100) * (1 + m_fee/100) * (1 + margin/100) + ship
else:
    target_price = won * (1 + m_rate/100) * (1 + m_fee/100) + margin + ship

st.sidebar.info(f"판매가: {target_price:,.2f} 원")
st.sidebar.warning(f"순이익(마진): {(target_price - won):,.2f} 원")

# -----------------------------
# DataLab 크롤링
# -----------------------------
def fetch_datalab_keywords_crawl():
    url = "https://datalab.naver.com/shoppingInsight/sCategory.naver"
    try:
        r = requests.get(url, headers={"user-agent": "Mozilla/5.0"}, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        scripts = soup.find_all("script")
        rows = []
        for s in scripts:
            m = re.search(r"__NEXT_DATA__\s*=\s*({.*})", s.text)
            if m:
                try:
                    data = json.loads(m.group(1))
                    def walk(obj):
                        if isinstance(obj, dict):
                            for v in obj.values():
                                res = walk(v)
                                if res: return res
                        elif isinstance(obj, list):
                            if all(isinstance(x, dict) and ("keyword" in x or "rank" in x) for x in obj[:5]):
                                return obj
                            for v in obj:
                                res = walk(v)
                                if res: return res
                        return None
                    items = walk(data) or []
                    for i,it in enumerate(items[:20], start=1):
                        kw = it.get("keyword") or it.get("name") or str(it)
                        rows.append({"rank": i, "keyword": kw})
                    if rows:
                        return pd.DataFrame(rows)
                except Exception:
                    pass
        return pd.DataFrame([{"rank":1,"keyword":"맥심 커피믹스"},{"rank":2,"keyword":"카누 미니"}])
    except Exception as e:
        return pd.DataFrame([{"rank":1,"keyword":"에러 발생"}])

# -----------------------------
# 11번가 모바일 크롤링
# -----------------------------
def fetch_11st_best_crawl():
    url = "https://m.11st.co.kr/browsing/bestSellers.mall"
    try:
        r = requests.get(url, headers={"user-agent":"Mozilla/5.0"}, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        rows=[]
        for i, li in enumerate(soup.select("li[class*=prd]")[:50], start=1):
            a = li.select_one("a[href]")
            title = (li.select_one(".name") or li.select_one(".title") or a).get_text(strip=True) if a else ""
            price = (li.select_one(".price") or li.select_one(".value") or li.select_one(".num"))
            price = price.get_text(strip=True) if price else ""
            rows.append({"rank":i,"title":title,"price":price})
        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame([{"rank":1,"title":"에러 발생","price":""}])

# -----------------------------
# 본문 3x3
# -----------------------------
top1, top2, top3 = st.columns([1,1,1])
mid1, mid2, mid3 = st.columns([1,1,1])

with top1:
    st.subheader("데이터랩")
    df = fetch_datalab_keywords_crawl()
    st.dataframe(df, use_container_width=True, hide_index=True)

with top2:
    st.subheader("아이템스카우트")
    st.info("연동 대기")

with top3:
    st.subheader("셀러라이프")
    st.info("연동 대기")

with mid1:
    st.subheader("11번가 (모바일)")
    df11 = fetch_11st_best_crawl()
    st.dataframe(df11, use_container_width=True, hide_index=True)

with mid2:
    st.subheader("상품명 생성기 (규칙 기반)")
    brand = st.text_input("브랜드", value="envy")
    base_kw = st.text_input("베이스 키워드", value="K-coffee mix")
    rel_kw = st.text_input("연관키워드(콤마)", value="Maxim, Kanu, Korea")
    limit = st.slider("글자수 제한", 20, 80, 80)
    if st.button("제목 5개 생성"):
        kws = [k.strip() for k in rel_kw.split(",") if k.strip()]
        outs=[f"{brand} {base_kw} {k}"[:limit] for k in kws[:5]]
        st.text_area("생성 결과", "\n".join(outs), height=200)

with mid3:
    st.empty()

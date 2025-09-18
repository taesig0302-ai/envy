import streamlit as st
import requests, pandas as pd, json, urllib.parse, time, base64
from bs4 import BeautifulSoup
from pathlib import Path
from deep_translator import GoogleTranslator

st.set_page_config(page_title="ENVY v10.7.1", page_icon="✨", layout="wide")

# ========== Part 0: 공통 ==========
PROXY_URL = "https://envy-proxy.taesig0302.workers.dev"
def has_proxy(): return isinstance(PROXY_URL,str) and PROXY_URL.strip()!=""
def iframe_url(target:str)->str: return f"{PROXY_URL}/iframe?target={urllib.parse.quote(target,safe='')}" if has_proxy() else target

MOBILE_HEADERS = {"user-agent":"Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Mobile Safari/537.36"}
CURRENCY_SYMBOL = {"USD":"$","EUR":"€","JPY":"¥","CNY":"元"}
FX_DEFAULT = {"USD":1400.0,"EUR":1500.0,"JPY":10.0,"CNY":200.0}

def init_theme_state():
    if "theme" not in st.session_state: st.session_state["theme"]="light"
def toggle_theme(): st.session_state["theme"] = "dark" if st.session_state["theme"]=="light" else "light"
def inject_css():
    st.markdown("""<style>.block-container{padding-top:1rem;}</style>""", unsafe_allow_html=True)

# ========== Part 1: 사이드바 ==========
def render_sidebar():
    with st.sidebar:
        # 로고
        lp = Path(__file__).parent/"logo.png"
        if lp.exists():
            b64=base64.b64encode(lp.read_bytes()).decode("ascii")
            st.markdown(f'<div style="width:95px;height:95px;border-radius:50%;overflow:hidden;margin:auto;"><img src="data:image/png;base64,{b64}" style="width:100%;height:100%;object-fit:cover;"></div>',unsafe_allow_html=True)
        # 테마 토글
        st.toggle("🌓 다크 모드", value=(st.session_state.get("theme","light")=="dark"), on_change=toggle_theme)
        # 환율 계산기
        st.subheader("① 환율 계산기")
        base=st.selectbox("기준 통화", list(CURRENCY_SYMBOL.keys()))
        sale_foreign=st.number_input("판매금액 (외화)",value=1.0,step=0.01)
        won=FX_DEFAULT[base]*sale_foreign
        st.write(f"환산 금액: {won:,.2f} 원")
        # 마진 계산기
        st.subheader("② 마진 계산기")
        m_base=st.selectbox("매입 통화", list(CURRENCY_SYMBOL.keys()))
        purchase_foreign=st.number_input("매입금액 (외화)",value=0.0,step=0.01)
        base_cost_won=FX_DEFAULT[m_base]*purchase_foreign if purchase_foreign>0 else won
        m_rate=st.number_input("카드수수료(%)",value=4.0)
        m_fee=st.number_input("마켓수수료(%)",value=14.0)
        ship=st.number_input("배송비(₩)",value=0.0)
        mode=st.radio("마진 방식",["퍼센트","플러스"],horizontal=True)
        if mode=="퍼센트": margin_pct=st.number_input("마진율(%)",value=10.0); target_price=base_cost_won*(1+m_rate/100)*(1+m_fee/100)*(1+margin_pct/100)+ship
        else: margin_won=st.number_input("마진액(₩)",value=10000.0); target_price=base_cost_won*(1+m_rate/100)*(1+m_fee/100)+margin_won+ship
        st.write(f"판매가: {target_price:,.2f} 원")


# ========== Part 2: 데이터랩 (간단화) ==========
DATALAB_API="https://datalab.naver.com/shoppingInsight/getCategoryKeywordRank.naver"
def datalab_fetch(cid,start,end,count=50):
    params={"cid":cid,"timeUnit":"date","startDate":start,"endDate":end,"count":count}
    r=requests.get(DATALAB_API,params=params,timeout=10)
    try:
        data=r.json(); rows=data.get("ranks",[])
        out=[{"rank":i+1,"keyword":it.get("keyword",""),"score":it.get("ratio",0)} for i,it in enumerate(rows)]
        return pd.DataFrame(out)
    except: return pd.DataFrame([])

def render_datalab_block():
    st.subheader("데이터랩")
    cid=st.text_input("cid", value="50000006")
    today=pd.Timestamp.today().normalize()
    start=st.date_input("시작일", today-pd.Timedelta(days=30))
    end=st.date_input("종료일", today)
    if st.button("조회"): 
        df=datalab_fetch(cid,str(start),str(end))
        if not df.empty: st.dataframe(df,use_container_width=True)

# ========== Part 5: 11번가 ==========
ELEVEN_URL="https://m.11st.co.kr/browsing/bestSellers.mall"
def render_elevenst_block():
    st.subheader("11번가 (모바일)")
    url=st.text_input("모바일 URL", value=ELEVEN_URL)
    src=f"{url}?_={int(time.time())}"
    if has_proxy(): st.components.v1.iframe(iframe_url(src),height=720)
    else: st.components.v1.iframe(src,height=720)

# ========== Part 6: 번역기 ==========
LANGS={"자동 감지":"auto","한국어":"ko","영어":"en","일본어":"ja","중국어(간체)":"zh-CN","중국어(번체)":"zh-TW"}
def render_translate_block():
    st.subheader("구글 번역기")
    c1,c2=st.columns(2)
    with c1:
        src=st.selectbox("원문 언어", list(LANGS.keys()))
        text=st.text_area("원문 입력",height=150)
    with c2:
        tgt=st.selectbox("번역 언어", list(LANGS.keys()), index=1)
        if st.button("번역"):
            try:
                translated=GoogleTranslator(source=LANGS[src],target=LANGS[tgt]).translate(text)
                st.text_area("번역 결과", translated, height=150)
                if LANGS[tgt]!="ko": st.caption("(한국어 확인용)")
            except Exception as e: st.error(str(e))

# ========== Part 7: 상품명 생성기 ==========
def render_namegen_block():
    st.subheader("상품명 생성기")
    brand=st.text_input("브랜드",value="envy")
    base_kw=st.text_input("베이스 키워드",value="K-coffee mix")
    rel_kw=st.text_input("연관 키워드",value="Maxim,Kanu")
    if st.button("생성"):
        kws=[k.strip() for k in rel_kw.split(",") if k.strip()]
        outs=[f"{brand} {base_kw} {k}" for k in kws]
        st.text_area("결과", "\n".join(outs))

# ========== Layout ==========
def main():
    init_theme_state(); inject_css(); render_sidebar()
    top1,top2=st.columns(2)
    with top1: render_datalab_block()
    with top2: render_elevenst_block()
    mid1,mid2=st.columns(2)
    with mid1: render_translate_block()
    with mid2: render_namegen_block()

if __name__=="__main__": main()

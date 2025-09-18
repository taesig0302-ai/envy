
import streamlit as st
import requests, pandas as pd, json, urllib.parse, time, base64, re, hashlib
from bs4 import BeautifulSoup
from pathlib import Path

st.set_page_config(page_title="ENVY v10.5", page_icon="✨", layout="wide")

PROXY_URL = "https://envy-proxy.taesig0302.workers.dev"

def has_proxy(): return isinstance(PROXY_URL, str) and PROXY_URL.strip() != ""
def iframe_url(target: str) -> str:
    return f"{PROXY_URL.rstrip('/')}/iframe?target={urllib.parse.quote(target, safe='')}"

MOBILE_HEADERS = {
    "user-agent": ("Mozilla/5.0 (Linux; Android 13; Pixel 7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/125.0 Mobile Safari/537.36"),
    "accept-language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "cache-control": "no-cache",
}

def init_state():
    st.session_state.setdefault("theme","light")
    st.session_state.setdefault("last_rank_keywords",[])
    st.session_state.setdefault("hdr_referer","https://datalab.naver.com/shoppingInsight/sCategory.naver")
    st.session_state.setdefault("hdr_cookie","")

def toggle_theme():
    st.session_state["theme"] = "dark" if st.session_state["theme"]=="light" else "light"

def inject_css():
    theme = st.session_state.get("theme","light")
    bg, fg = ("#0e1117","#e6edf3") if theme=="dark" else ("#ffffff","#111111")
    st.markdown(f"""
    <style>
      html, body, [data-testid="stAppViewContainer"] {{ background-color:{bg} !important; color:{fg} !important; }}
      .block-container {{ padding-top:.8rem !important; padding-bottom:.35rem !important; }}
      [data-testid="stSidebar"], [data-testid="stSidebar"] > div:first-child, [data-testid="stSidebar"] section {{
        height:100vh !important; overflow:hidden !important; padding-top:.25rem !important; padding-bottom:.25rem !important;
      }}
      [data-testid="stSidebar"] ::-webkit-scrollbar {{ display:none !important; }}
      .logo-circle {{ width:95px;height:95px;border-radius:50%;overflow:hidden;margin:.15rem auto .35rem auto;box-shadow:0 2px 8px rgba(0,0,0,.12);border:1px solid rgba(0,0,0,.06); }}
      .top-spacer {{ height:2vh; }} /* 5vh → 2vh (추가 3% 상승) */
    </style>
    """, unsafe_allow_html=True)

def render_sidebar():
    with st.sidebar:
        lp = Path(__file__).parent/"logo.png"
        if lp.exists():
            st.markdown(f'<div class="logo-circle"><img src="data:image/png;base64,{base64.b64encode(lp.read_bytes()).decode()}" /></div>', unsafe_allow_html=True)
        st.toggle("🌓 다크 모드", value=(st.session_state.get("theme")=="dark"), on_change=toggle_theme)

        with st.expander("고급 설정 (DataLab 안정화)"):
            st.text_input("Referer", key="hdr_referer")
            st.text_input("Cookie", type="password", key="hdr_cookie")

        st.markdown('<span id="envy-build" data-version="10.5" style="display:none"></span>', unsafe_allow_html=True)

# ----- DataLab rank -----
DATALAB_RANK_API="https://datalab.naver.com/shoppingInsight/getCategoryKeywordRank.naver"
TOP_CID={"패션의류":"50000000","패션잡화":"50000001","화장품/미용":"50000002","디지털/가전":"50000003",
"가구/인테리어":"50000004","출산/육아":"50000005","식품":"50000006","스포츠/레저":"50000007",
"생활/건강":"50000008","여가/생활편의":"50000009","면세점":"50000010","도서":"50005542"}

@st.cache_data(ttl=300)
def datalab_rank(cid,start_date,end_date,count,ref,cookie):
    headers=dict(MOBILE_HEADERS); 
    if ref: headers["referer"]=ref
    if cookie: headers["cookie"]=cookie
    try:
        r=requests.get(DATALAB_RANK_API, params={"cid":cid,"timeUnit":"date","startDate":start_date,"endDate":end_date,"page":1,"count":count}, headers=headers, timeout=12); r.raise_for_status()
        data=r.json(); rows=data.get("ranks") or data.get("data") or data.get("result") or []
        out=[{"rank":i+1,"keyword":(it.get("keyword") or it.get("name") or "").strip(),"score":it.get("ratio") or it.get("value") or it.get("score") or 0} for i,it in enumerate(rows)]
        if not out: raise ValueError("empty")
        return pd.DataFrame(out)
    except Exception:
        # HTML 휴리스틱
        try:
            t=r.text
        except Exception:
            t=""
        soup=BeautifulSoup(t,"html.parser")
        words=[el.get_text(" ",strip=True) for el in soup.select("a,span,li") if 1<len(el.get_text("",strip=True))<=20]
        words=[w for w in words if re.search(r"[가-힣A-Za-z0-9]",w)]
        words=list(dict.fromkeys(words))[:count] or ["데이터 없음"]
        return pd.DataFrame([{"rank":i+1,"keyword":w,"score":max(1,100-i*3)} for i,w in enumerate(words)])

def render_rank():
    st.markdown("### 데이터랩 (대분류 12종 전용)")
    cat=st.selectbox("카테고리", list(TOP_CID.keys()), index=3, key="rank_cat")
    cid=TOP_CID[cat]
    today=pd.Timestamp.today().normalize()
    c1,c2,c3=st.columns(3)
    with c1: count=st.number_input("개수",10,100,20,1,key="rank_cnt")
    with c2: start=st.date_input("시작일", today - pd.DateOffset(months=12), key="rank_start")
    with c3: end=st.date_input("종료일", today, key="rank_end")
    if st.button("갱신", key="rank_refresh"): st.cache_data.clear()
    df=datalab_rank(cid,str(start),str(end),int(count),st.session_state.get("hdr_referer"),st.session_state.get("hdr_cookie"))
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.line_chart(df[["rank","score"]].set_index("rank"), height=220)
    st.session_state["last_rank_keywords"]=[k for k in df["keyword"].head(5).tolist() if k!="데이터 없음"]

# ----- DataLab trend -----
DATALAB_TREND_API="https://datalab.naver.com/shoppingInsight/getCategoryKeywordTrend.naver"
def _range(preset):
    t=pd.Timestamp.today().normalize()
    mapping={"1주":t-pd.Timedelta(weeks=1), "1개월":t-pd.DateOffset(months=1), "3개월":t-pd.DateOffset(months=3), "1년":t-pd.DateOffset(years=1)}
    return mapping.get(preset,t-pd.DateOffset(months=1)), t

@st.cache_data(ttl=300)
def datalab_trend(cid,keywords,preset,device,ref,cookie):
    s,e=_range(preset); unit="week" if preset in ("1년","1개월","3개월") else "date"
    headers=dict(MOBILE_HEADERS); 
    if ref: headers["referer"]=ref
    if cookie: headers["cookie"]=cookie
    try:
        resp=requests.get(DATALAB_TREND_API, params={"cid":cid,"startDate":str(s.date()),"endDate":str(e.date()),"timeUnit":unit,"device":device,"keywords":",".join(keywords[:5])}, headers=headers, timeout=12)
        resp.raise_for_status(); data=resp.json(); real=True
    except Exception:
        data={}; real=False
    rows=[]
    for s in data.get("result") or data.get("data") or []:
        kw=s.get("keyword") or s.get("name") or ""
        for p in s.get("data", []):
            rows.append({"date":p.get("period") or p.get("date"), "keyword":kw, "value":p.get("ratio") or p.get("value") or p.get("score")})
    if rows:
        df=pd.DataFrame(rows); 
        try: df["date"]=pd.to_datetime(df["date"]).dt.date
        except: pass
        return df, real
    # fallback
    rng=pd.date_range(s,e,freq="W" if unit=="week" else "D")
    seeds=(keywords or ["키워드A","키워드B"])[:5]
    vals=[]
    for kw in seeds:
        h=int(hashlib.sha256(kw.encode()).hexdigest(),16)%97; base=45+(h%25)
        for i,d in enumerate(rng): vals.append({"date":d.date(),"keyword":kw,"value":max(8, base+((i*3)%40)-(h%13))})
    return pd.DataFrame(vals), False

def render_trend():
    st.markdown("### 키워드 트렌드 (기간 프리셋 + 기기별)")
    default=", ".join(st.session_state.get("last_rank_keywords",[])[:3]) or "가습기, 복합기, 무선청소기"
    kw_text=st.text_input("키워드(최대 5개, 콤마)", value=default, key="trend_kw")
    keywords=[k.strip() for k in kw_text.split(",") if k.strip()][:5]
    c1,c2,c3,c4=st.columns([1,1,1,1.2])
    with c1: preset=st.selectbox("기간 프리셋", ["1주","1개월","3개월","1년"], index=3)
    with c2: dev=st.selectbox("기기별", ["전체","PC","모바일"], index=0)
    with c3: cat=st.selectbox("카테고리(대분류)", list(TOP_CID.keys()), index=3); cid=TOP_CID[cat]
    with c4: go=st.button("트렌드 조회", type="primary")
    if go: st.cache_data.clear()
    df,real=datalab_trend(cid,keywords,preset, {"전체":"all","PC":"pc","모바일":"mo"}[dev], st.session_state.get("hdr_referer"), st.session_state.get("hdr_cookie"))
    st.caption(f"트렌드 데이터 상태: {'✅ REAL' if real else '⚠️ FALLBACK'} — 프리셋:{preset}, 기기:{dev}")
    if not df.empty:
        st.line_chart(df.sort_values('date').pivot(index='date',columns='keyword',values='value'), height=260)
        st.dataframe(df.sort_values('date').head(120), use_container_width=True, hide_index=True)

# ----- 11st -----
ELEVEN_URL="https://m.11st.co.kr/browsing/bestSellers.mall"
def render_11st():
    st.markdown("### 11번가 (모바일)")
    url=st.text_input("모바일 URL", value=ELEVEN_URL, label_visibility="collapsed")
    src=iframe_url(url) if has_proxy() else url
    st.components.v1.iframe(src, height=560, scrolling=True)

# ----- Rakuten (same as before; omitted details) -----
RAKUTEN_APP_ID="1043271015809337425"
SAFE_GENRES={"전체(샘플)":"100283","여성패션":"100371","남성패션":"551169","뷰티/코스메틱":"100939","식품/식료품":"100316","도서":"101266","음반/CD":"101240","영화/DVD·BD":"101251","취미/게임/완구":"101205","스포츠/레저":"101070","자동차/바이크":"558929","베이비/키즈":"100533","반려동물":"101213"}

def rk_url(p): return "https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20170628?"+urllib.parse.urlencode(p,safe="")
@st.cache_data(ttl=600)
def rk_fetch(genre,rows=50):
    try:
        r=requests.get(rk_url({"applicationId":RAKUTEN_APP_ID,"format":"json","formatVersion":2,"genreId":genre}), headers=MOBILE_HEADERS, timeout=12); r.raise_for_status(); data=r.json()
        items=data.get("Items",[])[:rows]; out=[]
        for i,it in enumerate(items,1):
            name=it.get("itemName") if isinstance(it,dict) else (it.get("Item") or {}).get("itemName","")
            if name: out.append({"rank":i,"keyword":name,"source":"Rakuten JP"})
        if not out: raise ValueError("empty")
        return pd.DataFrame(out)
    except Exception as e:
        return pd.DataFrame([{"rank":1,"keyword":f"(Rakuten) {type(e).__name__}: {e}","source":"DEMO"}])

def render_rakuten():
    st.markdown("### AI 키워드 레이더 (Rakuten)")
    c1,c2=st.columns([1.2,1.2])
    with c1:
        cat=st.selectbox("라쿠텐 카테고리", list(SAFE_GENRES.keys()), index=0)
        gid=SAFE_GENRES[cat]
    with c2:
        gid=st.text_input("genreId (직접 입력)", value=gid)
        st.caption(f"App ID: **{RAKUTEN_APP_ID}**")
    st.dataframe(rk_fetch(gid), use_container_width=True, hide_index=True)

# ----- Translator (deep-translator) -----
LANGS=[
    ("자동 감지","auto"),
    ("한국어","ko"),
    ("영어","en"),
    ("일본어","ja"),
    ("중국어(간체)","zh-CN"),
    ("중국어(번체)","zh-TW"),
    ("베트남어","vi"),
    ("태국어","th"),
    ("인도네시아어","id"),
    ("독일어","de"),
    ("프랑스어","fr"),
    ("스페인어","es"),
]

def render_translate():
    st.markdown("### 구글 번역 (텍스트 입력/출력)")
    c1,c2=st.columns(2)
    with c1: sl_label=st.selectbox("원문 언어", [l for l,_ in LANGS], index=0, key="sl_lab"); sl=dict(LANGS)[sl_label]
    with c2: tl_label=st.selectbox("번역 언어", [l for l,_ in LANGS if _!="auto"], index=1, key="tl_lab"); tl=dict(LANGS)[tl_label]
    left,right=st.columns(2)
    with left: src=st.text_area("원문 입력", height=180, key="src_txt")
    with right: out=st.empty(); out.text_area("번역 결과", value="", height=180, key="dst_txt")
    if st.button("번역 실행", type="primary", key="tr_do") and src.strip():
        try:
            from deep_translator import GoogleTranslator
            res=GoogleTranslator(source=sl, target=tl).translate(src)
            out.text_area("번역 결과", value=res, height=180, key="dst_txt2")
        except Exception as e:
            st.error(f"deep-translator 실패: {type(e).__name__}: {e}")

def main():
    init_state(); inject_css(); render_sidebar()
    st.markdown('<div class="top-spacer"></div>', unsafe_allow_html=True)

    a,b=st.columns(2)
    with a: render_rank()
    with b: render_trend()

    c,d=st.columns(2)
    with c: render_11st()
    with d: render_rakuten()

    st.divider()
    render_translate()

if __name__=="__main__":
    main()

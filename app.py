
# -*- coding: utf-8 -*-
# ENVY v21 — Layout & features per request

import os, re, math
from datetime import datetime, timedelta
from typing import List, Tuple
import requests
import pandas as pd
from bs4 import BeautifulSoup
import altair as alt
import streamlit as st

st.set_page_config(page_title="ENVY", page_icon="🦊", layout="wide")

# ---------- Branding ----------
st.markdown(r"""
<style>
.block-container { padding-top: 0.4rem; }
header, footer { visibility: hidden; height: 0; }
.topbar { display:flex; align-items:center; justify-content:space-between; gap:12px; margin:4px 0 10px 0; }
.brand { font-size:22px; font-weight:800; }
.badge { background:#111827; color:#fff; padding:2px 8px; border-radius:8px; font-size:12px; }
.note { font-size:12px; opacity:.7; }
.iframe-wrap { position:relative; width:100%; padding-top: 62%; border:1px solid rgba(0,0,0,.1); border-radius:8px; overflow:hidden; }
.iframe-wrap iframe { position:absolute; top:0; left:0; width:100%; height:100%; border:0; }
</style>
""", unsafe_allow_html=True)
st.markdown(r"""
<div class="topbar">
  <div class="brand">ENVY <span class="badge">v21</span></div>
  <div class="note">소싱 · 키워드 · 가격</div>
</div>
""", unsafe_allow_html=True)

REQ_HEADERS = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}

@st.cache_data(ttl=1800)
def fetch_html(url: str, timeout=12) -> str:
    r = requests.get(url, headers=REQ_HEADERS, timeout=timeout)
    r.raise_for_status()
    return r.text

def count_kor_bytes(text: str) -> Tuple[int,int]:
    chars = len(text)
    b = 0
    for ch in text:
        if re.match(r"[ㄱ-힣]", ch): b += 3
        else: b += len(ch.encode("utf-8"))
    return chars, b

def apply_rules(t: str, rules: List[Tuple[str,str]]) -> str:
    for bad, repl in rules:
        t = re.sub(re.escape(bad), repl, t, flags=re.IGNORECASE)
    return " ".join(t.split())

def wt_recent(df: pd.DataFrame, col="ratio", w7=0.6, w3=0.3, w1=0.1) -> float:
    if df.empty: return 0.0
    s1 = df[col].tail(1).sum()
    s3 = df[col].tail(3).sum()
    s7 = df[col].tail(7).sum()
    return w7*s7 + w3*s3 + w1*s1

# ---------- Sidebar: 환율 · 마진(두 모드) ----------
st.sidebar.markdown("### ⚙️ 마진 계산기")

cur_amt = st.sidebar.number_input("현지 금액", min_value=0.0, value=0.0, step=1.0)
cur_code = st.sidebar.selectbox("현지 통화", ["USD","EUR","JPY","CNY"], index=0)
ship_domestic = st.sidebar.number_input("국제배송비(=국내배송비)", min_value=0.0, value=0.0, step=100.0)
fee_card = st.sidebar.number_input("카드 수수료(%)", min_value=0.0, value=4.0, step=0.5)
fee_market = st.sidebar.number_input("마켓 수수료(%)", min_value=0.0, value=15.0, step=0.5)

margin_mode = st.sidebar.radio("마진 방식", ["퍼센트마진(%)", "더하기마진(원)"], horizontal=False)
target_margin_pct = st.sidebar.number_input("목표 마진(%)", min_value=0.0, value=40.0, step=1.0, disabled=(margin_mode!="퍼센트마진(%)"))
target_add_krw = st.sidebar.number_input("더하기 마진(원)", min_value=0.0, value=0.0, step=100.0, disabled=(margin_mode!="더하기마진(원)"))

CC = {"USD":1391.7, "EUR":1510.0, "JPY":9.2, "CNY":191.3}
KRW_cost = cur_amt * CC[cur_code]
C_total = KRW_cost + ship_domestic
r_card = max(0.0, 1 - fee_card/100.0)
r_market = max(0.0, 1 - fee_market/100.0)

if margin_mode == "퍼센트마진(%)":
    r_margin = max(0.0, 1 - target_margin_pct/100.0)
    denom = r_card * r_market * r_margin
    est_sell = (C_total / denom) if denom > 0 else 0.0
else:
    denom = r_card * r_market
    est_sell = (C_total + target_add_krw) / denom if denom > 0 else 0.0

real_margin = est_sell - C_total
real_margin_rate = (real_margin / est_sell * 100) if est_sell else 0
st.sidebar.metric("예상 판매가", f"₩{est_sell:,.0f}")
st.sidebar.metric("예상 순이익(마진)", f"₩{real_margin:,.0f} / {real_margin_rate:.1f}%")

# ---------- Top Row: DataLab / Itemscout / Recent-3d ----------
c1, c2, c3 = st.columns([1.6, 1.2, 1.0])

with c1:
    st.markdown("#### 📊 네이버 데이터랩 — Top20 + 트렌드")
    with st.expander("API 키 설정", expanded=False):
        cid = st.text_input("Client ID", value=os.getenv("NAVER_CLIENT_ID",""))
        csec = st.text_input("Client Secret", value=os.getenv("NAVER_CLIENT_SECRET",""), type="password")
        st.caption("※ 키 미입력시 데모 시드로 동작")

    cat = st.selectbox("카테고리", ["패션의류","화장품/미용","식품","스포츠/레저","생활/건강","디지털/가전","출산/유아동","가구/인테리어","반려동물","문구/취미"], index=0)
    period = st.radio("기간", ["30일","60일","90일"], horizontal=True, index=0)
    days = int(period.replace("일",""))
    end_date = datetime.today().date()
    start_date = end_date - timedelta(days=days-1)

    SEED = {
        "패션의류": ["맨투맨","슬랙스","청바지","가디건","롱스커트","부츠컷","와이드팬츠","조거팬츠","니트","셔츠","블레이저","후드집업","롱원피스","트레이닝","연청바지","흑청바지","슬림핏","A라인 스커트","니트조끼","보이핏"],
        "화장품/미용": ["쿠션","선크림","립밤","아이섀도우","클렌징폼","마스카라","립틴트","프라이머","토너","에센스","앰플","픽서","립오일","립글로스","아이브로우","쉐이딩","하이라이터","블러셔","세럼","클렌징오일"],
        "식품": ["라면","커피","참치","스팸","젤리","간식","과자","초콜릿","김","견과","시리얼","과일","김자반","햇반","즉석국","만두","치즈","우유","요거트","식빵"],
        "스포츠/레저": ["런닝화","요가매트","테니스공","배드민턴라켓","축구공","헬스장갑","무릎보호대","수영모","스노클","자전거장갑","스포츠양말","라켓가방","하프팬츠","피클볼","워킹화","헬스벨트","덤벨","폼롤러","보호대","배드민턴공"],
        "생활/건강": ["행주","수세미","빨래바구니","세탁망","물티슈","수납함","휴지통","방향제","청소기","필터","제습제","방충제","고무장갑","욕실화","발매트","칫솔","치약","샴푸","린스","바디워시"],
        "디지털/가전": ["무선마우스","키보드","충전기","C타입케이블","허브","USB","SSD","HDD","모니터암","웹캠","마이크","헤드셋","스피커","태블릿거치대","모바일배터리","공유기","랜카드","라우터","TV스틱","로봇청소기"],
        "출산/유아동": ["기저귀","물티슈","젖병","유산균","분유","아기세제","아기로션","아기수건","아기욕조","턱받이","치발기","콧물흡입기","체온계","슬립수트","젖병소독기","아기베개","유모차걸이","휴대용기저귀","보온병","컵"],
        "가구/인테리어": ["러그","쿠션","커튼","블라인드","거울","수납장","선반","행거","책상","의자","스툴","사이드테이블","식탁등","LED등","디퓨저","액자","침대커버","이불커버","베개커버","무드등"],
        "반려동물": ["배변패드","건식사료","습식사료","간식스틱","츄르","캣닢","장난감","하네스","리드줄","스크래쳐","캣타워","모래","매트","급식기","급수기","방석","하우스","브러시","발톱깎이","미용가위"],
        "문구/취미": ["젤펜","볼펜","노트","다이어리","포스트잇","형광펜","수채화물감","팔레트","마카","연필","지우개","스케치북","컬러링북","키트","퍼즐","보드게임","테이프커터","커팅매트","도안집","클립"],
    }

    @st.cache_data(ttl=900)
    def datalab_search_trend(client_id: str, client_secret: str, keywords: List[str], start: str, end: str) -> pd.DataFrame:
        url = "https://openapi.naver.com/v1/datalab/search"
        headers = {"X-Naver-Client-Id": client_id, "X-Naver-Client-Secret": client_secret, "Content-Type":"application/json"}
        groups = [{"groupName": kw, "keywords":[kw]} for kw in keywords]
        body = {"startDate": start, "endDate": end, "timeUnit":"date", "keywordGroups": groups, "device":"pc,mobile", "ages":[], "gender":""}
        r = requests.post(url, headers=headers, json=body, timeout=10)
        r.raise_for_status()
        js = r.json()
        rows = []
        for res in js.get("results", []):
            kw = res.get("title")
            for point in res.get("data", []):
                rows.append({"keyword": kw, "date": point["period"], "ratio": point["ratio"]})
        df = pd.DataFrame(rows)
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
        return df

    try:
        if cid and csec:
            df_ts = datalab_search_trend(cid, csec, SEED[cat], (datetime.today()-timedelta(days=days-1)).date().isoformat(), datetime.today().date().isoformat())
            tops = []
            for kw, g in df_ts.groupby("keyword"):
                tops.append({"keyword": kw, "score_recent": round(wt_recent(g, "ratio"), 2)})
            df_top = pd.DataFrame(tops).sort_values("score_recent", ascending=False).head(20).reset_index(drop=True)
            df_top.index = df_top.index + 1
            st.success("API 모드: 최근성 가중 Top20")
        else:
            raise RuntimeError("키 미입력")
    except Exception as e:
        st.warning(f"API 미사용/실패 → 데모 Top20 사용 ({e})")
        df_top = pd.DataFrame({"keyword": SEED[cat][:20]})
        df_top["score_recent"] = 0.0
        df_top.index = df_top.index + 1

    st.dataframe(df_top.rename_axis("rank").reset_index(), use_container_width=True, hide_index=True)

    # 오른쪽 작은 그래프(Top5 라인) — 패널 안 표시 (expander X)
    if cid and csec and not df_top.empty:
        pick = df_top["keyword"].head(5).tolist()
        frames = []
        for kw in pick:
            dfp = datalab_search_trend(cid, csec, [kw], (datetime.today()-timedelta(days=days-1)).date().isoformat(), datetime.today().date().isoformat())
            dfp["keyword"] = kw
            frames.append(dfp)
        if frames:
            df_plot = pd.concat(frames)
            chart = alt.Chart(df_plot).mark_line().encode(
                x="date:T", y="ratio:Q", color="keyword:N", tooltip=["keyword:N","date:T","ratio:Q"]
            ).properties(height=200).interactive()
            st.altair_chart(chart, use_container_width=True)
    else:
        st.caption("API 키 입력 시 트렌드 그래프 표시")

with c2:
    st.markdown("#### 🔎 아이템스카우트 — CSV/HTML")
    csvfile = st.file_uploader("CSV 업로드 (내보내기 파일)", type=["csv"], key="is_csv_v21")
    if csvfile:
        try:
            df_is = pd.read_csv(csvfile)
            st.dataframe(df_is.head(50), use_container_width=True)
        except Exception as e:
            st.error(f"CSV 파싱 실패: {e}")
    html_txt = st.text_area("HTML 소스 붙여넣기", height=120, key="is_html_v21")
    if st.button("HTML에서 키워드 추출", key="is_btn_v21"):
        try:
            soup = BeautifulSoup(html_txt, "html.parser")
            texts = [t.get_text(" ", strip=True) for t in soup.find_all(["a","span","div"])]
            from collections import Counter
            cand = []
            for t in texts:
                if 1 <= len(t) <= 30 and re.search(r"[가-힣A-Za-z]", t):
                    cand.append(t)
            cnt = Counter(cand)
            df_html_kw = pd.DataFrame(cnt.most_common(50), columns=["keyword","freq"])
            st.dataframe(df_html_kw, use_container_width=True)
        except Exception as e:
            st.error(f"추출 실패: {e}")

with c3:
    st.markdown("#### 🏆 최근 3일 베스트 (Placeholder)")
    demo_b3 = pd.DataFrame({
        "#": list(range(1,11)),
        "상품명": [f"데모 상품 {i}" for i in range(1,11)],
        "가격": [i*10000 for i in range(1,11)]
    })
    st.dataframe(demo_b3, use_container_width=True, hide_index=True)

# ---------- Bottom Row: 11번가 / 소싱 레이더 / 타이틀 ----------
b1, b2 = st.columns([1.4, 1.6])

with b1:
    st.markdown("#### 🛍️ 11번가 아마존 베스트 (모바일 — 요약 표)")
    url_11 = st.text_input("URL", value="https://m.11st.co.kr/MW/html/main.html", key="u11_v21")
    if st.button("불러오기", key="u11_btn_v21"):
        try:
            html = fetch_html(url_11)
            soup = BeautifulSoup(html, "html.parser")
            items = []
            selectors = ["li", "div"]
            for sel in selectors:
                for li in soup.select(sel):
                    txt = li.get_text(" ", strip=True)
                    if not txt: continue
                    m = re.search(r"(\d{1,3}(?:,\d{3})+)\s*원", txt)
                    price = int(m.group(1).replace(",","")) if m else None
                    a = li.find("a", href=True)
                    link = ""
                    if a:
                        href = a["href"]
                        link = ("https:" + href) if href.startswith("//") else href
                    img = li.find("img")
                    thumb = img["src"] if img and img.has_attr("src") else ""
                    items.append({"상품명": txt[:120], "가격": price, "링크": link, "썸네일": thumb})
                    if len(items) >= 100: break
                if items: break
            df11 = pd.DataFrame(items)
            if df11.empty:
                st.warning("파싱 결과가 비었습니다. (구조변경/차단 가능)")
            else:
                st.dataframe(df11, use_container_width=True, hide_index=True)
                st.download_button("CSV 다운로드", data=df11.to_csv(index=False).encode("utf-8-sig"), file_name="11st_best.csv", mime="text/csv")
        except Exception as e:
            st.error(f"요청 실패: {e}")
    st.caption("※ 직접 임베드는 정책상 차단될 수 있어 요약표로 대체.")

with b2:
    st.markdown("#### 🧭 AI 소싱 레이더 — 점수")
    # 레이더 계산: 데이터랩 Top20 점수 + 노출 가중치
    if 'df_top' in locals() and not df_top.empty:
        df_kw_score = df_top[["keyword","score_recent"]].copy()
        expo_w = st.slider("노출 가중치(11번가)", 0.0, 20.0, 10.0, 1.0)
        df_kw_score["score"] = df_kw_score["score_recent"] + expo_w
        df_kw_score = df_kw_score.sort_values("score", ascending=False).reset_index(drop=True)
        st.dataframe(df_kw_score.head(20), use_container_width=True)
        ch = alt.Chart(df_kw_score.head(15)).mark_bar().encode(
            x=alt.X("score:Q", title="score"),
            y=alt.Y("keyword:N", sort="-x", title="keyword"),
            tooltip=["keyword","score"]
        ).properties(height=240)
        st.altair_chart(ch, use_container_width=True)
    else:
        st.info("데이터랩 Top20이 생성되면 점수를 계산합니다.")

# ---- 타이틀 생성기 + 금칙어 (하단 전체 폭) ----
st.markdown("#### ✍️ 상품명 생성기 + 🚫 금칙어")
brand = st.text_input("브랜드", value="", key="brand_v21")
base = st.text_input("기본 문장", value="", key="base_v21")
kw_raw = st.text_input("키워드(,)", value="슬랙스, 와이드, 기모", key="kraw_v21")
limit_chars = st.number_input("최대 글자수", 1, 120, 50, key="lchars_v21")
limit_bytes = st.number_input("최대 바이트수", 1, 200, 80, key="lbytes_v21")

if "ban_df" not in st.session_state:
    st.session_state["ban_df"] = pd.DataFrame({"금칙어":["무료배송","증정","초특가"],"대체어":["","","특가"]})
ban_df = st.data_editor(st.session_state["ban_df"], num_rows="dynamic", use_container_width=True, key="bandf_v21")
st.session_state["ban_df"] = ban_df
rules = [(r["금칙어"], r["대체어"]) for _, r in ban_df.dropna().iterrows() if r["금칙어"]]

def gen_titles(brand, base, kws, rules, limit_chars, limit_bytes, n=5):
    out = []
    for i in range(n):
        kk = kws[i:] + kws[:i]
        title = " ".join([brand, base, " ".join(kk)]).strip()
        title = apply_rules(title, rules)
        ch, bt = count_kor_bytes(title)
        while (ch > limit_chars or bt > limit_bytes) and kk:
            kk = kk[:-1]
            title = " ".join([brand, base, " ".join(kk)]).strip()
            title = apply_rules(title, rules)
            ch, bt = count_kor_bytes(title)
        out.append({"제목": title, "글자수": ch, "바이트": bt})
    return pd.DataFrame(out)

if st.button("제목 5개 생성", key="gent_v21"):
    kws = [k.strip() for k in kw_raw.split(",") if k.strip()]
    df_titles = gen_titles(brand, base, kws, rules, limit_chars, limit_bytes, n=5)
    st.dataframe(df_titles, use_container_width=True, hide_index=True)

st.caption("© ENVY v21 — Classic UI + 요구 반영")

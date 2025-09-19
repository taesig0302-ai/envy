# ---- Compact table CSS (safe with st.dataframe) ----
st.markdown("""
<style>
.dataframe tbody tr td, .dataframe thead tr th {
  padding-top: 4px !important; padding-bottom: 4px !important;
  font-size: 12px !important;
}
.stDataFrame { border-radius: 8px; }
.section-title { font-size: 1.15rem; font-weight: 700; margin: 6px 0 8px; }
.badge { display:inline-block; padding:3px 8px; border-radius:6px; font-size:12px; margin-left:6px; }
.badge.ok { background:#e6ffcc; border:1px solid #b6f3a4; color:#0b2e13; }
.badge.warn { background:#fff7d6; border:1px solid #f1d27a; color:#4a3b07; }
.badge.err { background:#ffe6e6; border:1px solid #ffb3b3; color:#5a0a0a; }
</style>
""", unsafe_allow_html=True)
# =========================
# Part 2 — 데이터랩 (수정 안정화판)
# =========================
DATALAB_API = "https://datalab.naver.com/shoppingInsight/getCategoryKeywordRank.naver"

@st.cache_data(ttl=300)
def datalab_fetch(cid: str, start_date: str, end_date: str, count: int = 20) -> pd.DataFrame:
    params = {
        "cid": cid, "timeUnit": "date",
        "startDate": start_date, "endDate": end_date,
        "page": 1, "count": count
    }
    r = requests.get(DATALAB_API, params=params, timeout=10)
    r.raise_for_status()
    try:
        data = r.json()
        rows = data.get("ranks") or data.get("data") or data.get("result") or []
        if isinstance(rows, dict): rows = rows.get("ranks", [])
        out=[]
        for i, it in enumerate(rows[:count], start=1):
            kw = (it.get("keyword") or it.get("name") or "").strip()
            score = it.get("ratio") or it.get("value") or it.get("score")
            out.append({"rank": i, "keyword": kw, "score": score})
        df = pd.DataFrame(out)
    except json.JSONDecodeError:
        # HTML fallback
        soup = BeautifulSoup(r.text, "html.parser")
        words=[]
        for el in soup.select("a, span, li"):
            t = (el.get_text(" ", strip=True) or "").strip()
            if 1 < len(t) <= 40: words.append(t)
            if len(words) >= count: break
        if not words: words = ["데이터 없음"]*count
        df = pd.DataFrame([{"rank":i+1,"keyword":w} for i, w in enumerate(words)])
    if df.empty: return df
    if "score" not in df.columns or df["score"].isna().all():
        n = len(df); df["score"] = [max(1,int(100 - i*(100/max(1,n-1)))) for i in range(n)]
    return df

def render_datalab_block():
    st.markdown('<div class="section-title">데이터랩<span class="badge ok">대분류 12종</span></div>', unsafe_allow_html=True)
    # 카테고리 → 실제 cid 매핑(대분류 12종)
    CID_MAP = {
        "패션의류": "50000000","패션잡화":"50000001","화장품/미용":"50000002","디지털/가전":"50000003",
        "가구/인테리어":"50000004","출산/육아":"50000005","식품":"50000006","스포츠/레저":"50000007",
        "생활/건강":"50000008","여가/생활편의":"50000009","면세점":"50000010","도서":"50005542"
    }
    c1, c2, c3 = st.columns([1,1,1])
    with c1:
        cat_label = st.selectbox("카테고리", list(CID_MAP.keys()), index=3, key="dl_cat_v11")
        cid = CID_MAP[cat_label]
        st.caption(f"선택 카테고리: **{cat_label}** (cid={cid})")
    with c2:
        today = pd.Timestamp.today().normalize()
        start = st.date_input("시작일", today - pd.Timedelta(days=30), key="dl_start_v11")
    with c3:
        end   = st.date_input("종료일", today, key="dl_end_v11")

    # 갱신 버튼
    if st.button("시동", key="dl_go_v11"): st.cache_data.clear()

    try:
        df = datalab_fetch(str(cid), str(start), str(end), count=20)
        st.dataframe(df[["rank","keyword","score"]], use_container_width=True, hide_index=True)
        chart_df = df[["rank","score"]].set_index("rank").sort_index()
        st.line_chart(chart_df, height=180)
    except Exception as e:
        st.error(f"DataLab 호출 실패: {type(e).__name__}: {e}")
# =========================
# Part 6 — AI 키워드 레이더 (Rakuten) 안정화
# =========================
RAKUTEN_APP_ID = "1043271015809337425"

SAFE_GENRES = {
    "전체(샘플)":"100283","여성패션":"100371","남성패션":"551169","뷰티/코스메틱":"100939",
    "식품/식료품":"100316","도서":"101266","음반/CD":"101240","영화/DVD·BD":"101251",
    "취미/게임/완구":"101205","스포츠/레저":"101070","자동차/바이크":"558929",
    "베이비/키즈":"100533","반려동물":"101213"
}
DEFAULT_GENRE = SAFE_GENRES["전체(샘플)"]

def _rk_url(params: dict) -> str:
    endpoint = "https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20170628"
    qs = urllib.parse.urlencode(params, safe="")
    url = f"{endpoint}?{qs}"
    return f"{PROXY_URL}/fetch?target={urllib.parse.quote(url, safe='')}" if has_proxy() else url

@st.cache_data(ttl=600)
def rakuten_fetch_ranking(genre_id: str, rows: int = 50) -> pd.DataFrame:
    params={"applicationId":RAKUTEN_APP_ID,"format":"json","formatVersion":2,"genreId":genre_id}
    try:
        resp = requests.get(_rk_url(params), headers=MOBILE_HEADERS, timeout=12)
        if resp.status_code==400: raise ValueError("400 Bad Request (장르)")
        resp.raise_for_status()
        data = resp.json()
        items = data.get("Items", [])[:rows]
        out=[]
        for i, it in enumerate(items, start=1):
            obj = it if "itemName" in it else (it.get("Item") or {})
            name = obj.get("itemName","").strip()
            if name: out.append({"rank":i,"keyword":name,"source":"Rakuten JP"})
        if not out: raise ValueError("응답 파싱 결과 비어 있음")
        return pd.DataFrame(out)
    except Exception:
        if genre_id!=DEFAULT_GENRE:
            fb = rakuten_fetch_ranking.__wrapped__(DEFAULT_GENRE, rows)
            fb["note"]="fallback: genreId 자동 대체"
            return fb
        return pd.DataFrame([{"rank":1,"keyword":"(Rakuten) 데이터 없음","source":"DEMO"}])

def render_rakuten_block():
    st.markdown('<div class="section-title">AI 캠프 랩 (Rakuten)</div>', unsafe_allow_html=True)
    # 국내/글로벌 토글(현재 표시는 동일, 토글 UI 유지)
    st.radio("모드", ["국내","글로벌"], horizontal=True, key="rk_mode_v11")
    c1,c2,c3 = st.columns([1.1,1,1.3])
    with c1:
        cat = st.selectbox("라쿠텐 카테고리", list(SAFE_GENRES.keys()), index=0, key="rk_cat_v11")
    with c2:
        preset = SAFE_GENRES[cat]
        genre_id = st.text_input("장르ID(직접입력)", value=preset, key="rk_gid_v11")
    with c3:
        st.caption(f"앱 ID: **{RAKUTEN_APP_ID}**")
        st.caption("400/파싱 실패 → '전체(샘플)' 자동 폴백")

    df = rakuten_fetch_ranking(genre_id, rows=50)
    # 표: classes 제거 / 글자 크기 소형화는 전역 CSS로 처리됨
    st.dataframe(df, use_container_width=True, hide_index=True)
# =========================
# Part 6.5 — 구글 번역 (텍스트 입력/출력 + 한국어 확인)
# =========================
LANG_LABELS = {
    "auto":"자동 감지","ko":"한국어","en":"영어","ja":"일본어","zh-cn":"중국어(간체)",
    "zh-tw":"중국어(번체)","vi":"베트남어","th":"태국어","id":"인도네시아어",
    "de":"독일어","fr":"프랑스어","es":"스페인어","ru":"러시아어"
}

def translate_text(q: str, src: str, tgt: str) -> str:
    # 의존성 없는 경량 엔드포인트(스트리밍 환경에서 불가시 빈 문자열)
    try:
        from deep_translator import GoogleTranslator
        return GoogleTranslator(source=src, target=tgt).translate(q) or ""
    except Exception:
        return ""  # 실패 시 빈 문자열

def render_translator_block():
    st.markdown('<div class="section-title">구글 번역 (텍스트 입력/출력 + 한국어 확인)</div>', unsafe_allow_html=True)
    c1,c2 = st.columns([1,1])
    with c1:
        src = st.selectbox("원문 언어", list(LANG_LABELS.values()),
                           index=list(LANG_LABELS.keys()).index("auto"),
                           key="tr_src_label_v11")
    with c2:
        tgt = st.selectbox("번역 언어", list(LANG_LABELS.values()),
                           index=list(LANG_LABELS.keys()).index("en"),
                           key="tr_tgt_label_v11")

    # 코드 ↔ 한글라벨 매핑
    inv = {v:k for k,v in LANG_LABELS.items()}
    src_code = inv[src]; tgt_code = inv[tgt]

    text = st.text_area("원문 입력", "", height=120, key="tr_in_v11")
    if st.button("번역", key="tr_go_v11"):
        out = translate_text(text, src_code, tgt_code)
        # 타깃이 한국어가 아닐 때, 한국어 재번역 붙임
        if tgt_code != "ko" and out:
            ko = translate_text(out, tgt_code, "ko")
            st.text_area("번역 결과", f"{out} ({ko})", height=120, key="tr_out_v11")
        else:
            st.text_area("번역 결과", out, height=120, key="tr_out_v11")
export default {
  async fetch(req) {
    const url = new URL(req.url);
    const target = url.searchParams.get("target");
    if (!target) return new Response("Missing target", { status: 400 });

    const r = await fetch(target, {
      headers: {
        "user-agent":
          "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome Safari Mobile",
        "accept-language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
      }
    });

    // HTML 배너 제거 (간단 문자열 치환)
    let body = await r.text();
    body = body
      .replace(/앱에서.*?혜택.*?받기/g, "")
      .replace(/<header[^>]*>.*?<\/header>/gs, ""); // 과하게 지우면 화면 깨질 수 있으니 보수적으로

    return new Response(body, {
      headers: {
        "content-type": r.headers.get("content-type") || "text/html; charset=utf-8",
        // X-Frame-Allow
        "x-frame-options": "ALLOWALL",
        "content-security-policy": "frame-ancestors *"
      }
    });
  }
}
def state_badge(ok="ok"):  # "ok" | "warn" | "err"
    label = {"ok":"🟢 정상","warn":"🟡 폴백","err":"🔴 실패"}[ok]
    cls   = {"ok":"ok","warn":"warn","err":"err"}[ok]
    st.markdown(f'<span class="badge {cls}">{label}</span>', unsafe_allow_html=True)

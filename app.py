# -*- coding: utf-8 -*-
# ENVY — Season 1 (Dual Proxy Edition, Radar tabs=국내/해외, Naver detailed error, Rakuten genre AUTO-MAP)

import base64, time, re, math
from pathlib import Path
from urllib.parse import quote
import hashlib, hmac, base64 as b64
import pandas as pd
import streamlit as st

try:
    import requests
except Exception:
    requests = None

try:
    from deep_translator import GoogleTranslator
except Exception:
    GoogleTranslator = None

st.set_page_config(page_title="ENVY — Season 1 (Dual Proxy Edition)", layout="wide")

# ─────────────────────────────────────────────────────────────────────────────
# PROXIES & KEYS (secrets 우선, 없으면 기본값 사용)
# ─────────────────────────────────────────────────────────────────────────────
NAVER_PROXY      = "https://envy-proxy.taesig0302.workers.dev"
ELEVENST_PROXY   = "https://worker-11stjs.taesig0302.workers.dev"
ITEMSCOUT_PROXY  = "https://worker-itemscoutjs.taesig0302.workers.dev"
SELLERLIFE_PROXY = "https://worker-sellerlifejs.taesig0302.workers.dev"

# Rakuten
RAKUTEN_APP_ID_DEFAULT       = st.secrets.get("RAKUTEN_APP_ID",       "1043271015809337425").strip()
RAKUTEN_AFFILIATE_ID_DEFAULT = st.secrets.get("RAKUTEN_AFFILIATE_ID", "4c723498.cbfeca46.4c723499.1deb6f77").strip()

# Naver Developers (정보표시용)
NAVER_CLIENT_ID_DEFAULT     = st.secrets.get("NAVER_CLIENT_ID",     "h4mklM2hNLct04BD7sC0").strip()
NAVER_CLIENT_SECRET_DEFAULT = st.secrets.get("NAVER_CLIENT_SECRET", "ltoxUNyKxi").strip()

# Naver Ads / 검색광고 API (실사용)
NAVER_API_KEY_DEFAULT     = st.secrets.get("NAVER_API_KEY",     "0100000000785cf1d8f039b13a5d3c3d1262b84e9ad4a046637e8887bbd003051b0d2a5cdf").strip()
NAVER_SECRET_KEY_DEFAULT  = st.secrets.get("NAVER_SECRET_KEY",  "AQAAAAB4XPHY8DmxOl08PRJiuE6ao1LN3lh0kF9rOJ4m5b8O5g==").strip()
NAVER_CUSTOMER_ID_DEFAULT = st.secrets.get("NAVER_CUSTOMER_ID", "2274338").strip()

# ─────────────────────────────────────────────────────────────────────────────
# UI defaults & CSS
# ─────────────────────────────────────────────────────────────────────────────
SHOW_ADMIN_BOX = False

CURRENCIES = {
    "USD":{"kr":"미국 달러","symbol":"$","unit":"USD"},
    "EUR":{"kr":"유로","symbol":"€","unit":"EUR"},
    "JPY":{"kr":"일본 엔","symbol":"¥","unit":"JPY"},
    "CNY":{"kr":"중국 위안","symbol":"元","unit":"CNY"},
}
FX_DEFAULT = {"USD":1400.0,"EUR":1500.0,"JPY":10.0,"CNY":200.0}

def _ensure_session_defaults():
    ss = st.session_state
    ss.setdefault("theme","light")
    ss.setdefault("fx_base","USD")
    ss.setdefault("sale_foreign",1.00)
    ss.setdefault("m_base","USD")
    ss.setdefault("purchase_foreign",0.00)
    ss.setdefault("card_fee_pct",4.00)
    ss.setdefault("market_fee_pct",14.00)
    ss.setdefault("shipping_won",0.0)
    ss.setdefault("margin_mode","퍼센트")
    ss.setdefault("margin_pct",10.00)
    ss.setdefault("margin_won",10000.0)

    # Rakuten genre map (초기 임시 → 첫 로드시 자동 매핑으로 갱신)
    ss.setdefault("rk_genre_map", {
        "전체(샘플)": "100283",
        "뷰티/코스메틱": "100283",
        "의류/패션":   "100283",
        "가전/디지털": "100283",
        "가구/인테리어":"100283",
        "식품":        "100283",
        "생활/건강":   "100283",
        "스포츠/레저": "100283",
        "문구/취미":   "100283",
    })
    ss.setdefault("rk_automap_done", False)
    ss.setdefault("naver_err", "")  # 국내 API 오류 메시지 저장

def _toggle_theme():
    st.session_state["theme"] = "dark" if st.session_state.get("theme","light")=="light" else "light"

def _inject_css():
    theme = st.session_state.get("theme","light")
    bg, fg = ("#0e1117","#e6edf3") if theme=="dark" else ("#ffffff","#111111")
    st.markdown(f"""
    <style>
      .block-container{{max-width:3800px!important;padding-top:.55rem!important;padding-bottom:1rem!important}}
      html,body,[data-testid="stAppViewContainer"]{{background:{bg}!important;color:{fg}!important}}
      .pill{{border-radius:9999px;padding:.40rem .9rem;font-weight:800;display:inline-block;margin:.10rem 0!important}}
      .pill-green{{background:#b8f06c;border:1px solid #76c02a;color:#083500}}
      .pill-blue{{background:#dbe6ff;border:1px solid #88a8ff;color:#09245e}}
      .pill-yellow{{background:#ffe29b;border:1px solid #d2a12c;color:#3e2a00}}
      .card{{border:1px solid rgba(0,0,0,.06);border-radius:14px;padding:.85rem;background:#fff;box-shadow:0 1px 6px rgba(0,0,0,.05)}}
      .card-title{{font-size:1.18rem;font-weight:900;margin:.1rem 0 .55rem 0}}
      .logo-circle{{width:72px;height:72px;border-radius:50%;overflow:hidden;margin:.2rem auto .4rem auto;
                   box-shadow:0 2px 8px rgba(0,0,0,.12);border:1px solid rgba(0,0,0,.06)}}
      .logo-circle img{{width:100%;height:100%;object-fit:cover}}
    </style>
    """, unsafe_allow_html=True)

def _inject_alert_center():
    st.markdown("""
    <div id="envy-alert-root" style="position:fixed;top:16px;right:16px;z-index:999999;pointer-events:none;"></div>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Responsive
# ─────────────────────────────────────────────────────────────────────────────
def _responsive_probe():
    html = """
    <script>
    (function(){
      const bps=[900,1280,1600];
      const w=Math.max(document.documentElement.clientWidth||0, window.innerWidth||0);
      let bin=0; for(let i=0;i<bps.length;i++) if(w>=bps[i]) bin=i+1;
      const url=new URL(window.location); const curr=url.searchParams.get('vwbin');
      if(curr!==String(bin)){ url.searchParams.set('vwbin', String(bin)); window.location.replace(url.toString()); }
    })();
    </script>
    """
    st.components.v1.html(html, height=0, scrolling=False)

def _get_view_bin():
    try:
        raw = st.query_params.get("vwbin", "3")
    except Exception:
        raw = (st.experimental_get_query_params().get("vwbin", ["3"])[0])
    try:
        return max(0, min(3, int(raw)))
    except:
        return 3

# ─────────────────────────────────────────────────────────────────────────────
# Proxy iframes
# ─────────────────────────────────────────────────────────────────────────────
def _proxy_iframe(proxy_base: str, target_url: str, height: int = 860, scroll=True, key=None):
    proxy = (proxy_base or "").strip().rstrip("/")
    url   = f"{proxy}/?url={quote(target_url, safe=':/?&=%')}"
    h     = int(height)
    try:
        st.iframe(url, height=h); return
    except Exception:
        pass
    try:
        st.components.v1.iframe(url, height=h, scrolling=bool(scroll)); return
    except Exception:
        pass
    st.markdown(f'<iframe src="{url}" style="width:100%;height:{h}px;border:0;border-radius:10px;"></iframe>',
                unsafe_allow_html=True)

def _proxy_iframe_with_title(proxy_base: str, target_url: str, height: int = 860, key: str = "naver_home"):
    proxy = (proxy_base or "").strip().rstrip("/")
    url   = f"{proxy}/?url={quote(target_url, safe=':/?&=%')}"
    h     = int(height)
    html  = f'''
<div id="{key}-wrap" style="width:100%;overflow:hidden;">
  <div id="{key}-title" style="display:inline-block;border-radius:9999px;padding:.40rem .9rem;
    font-weight:800;background:#dbe6ff;border:1px solid #88a8ff;color:#09245e;margin:0 0 .5rem 0;">DataLab</div>
  <iframe src="{url}" style="width:100%;height:{h}px;border:0;border-radius:10px;"></iframe>
</div>
'''
    st.components.v1.html(html, height=h+56, scrolling=False)

# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────
def _sidebar():
    _ensure_session_defaults(); _inject_css(); _inject_alert_center()
    with st.sidebar:
        lp = Path(__file__).parent / "logo.png"
        if lp.exists():
            b64img = base64.b64encode(lp.read_bytes()).decode("ascii")
            st.markdown(f'<div class="logo-circle"><img src="data:image/png;base64,{b64img}"></div>', unsafe_allow_html=True)
        st.toggle("🌓 다크 모드", value=(st.session_state.get("theme","light")=="dark"),
                  on_change=_toggle_theme, key="__theme_toggle")

        st.markdown("### ① 환율 계산기")
        base = st.selectbox("기준 통화", list(CURRENCIES.keys()),
                            index=list(CURRENCRIES.keys()).index(st.session_state["fx_base"]) if "CURRENCRIES" in globals() else list(CURRENCIES.keys()).index(st.session_state["fx_base"]),
                            key="fx_base")
        sale_foreign = st.number_input("판매금액 (외화)", value=float(st.session_state["sale_foreign"]),
                                       step=0.01, format="%.2f", key="sale_foreign")
        won = FX_DEFAULT[base] * sale_foreign
        st.markdown(f'<div class="pill pill-green">환산 금액: <b>{won:,.2f} 원</b></div>', unsafe_allow_html=True)

        st.markdown("### ② 마진 계산기")
        m_base = st.selectbox("매입 통화", list(CURRENCIES.keys()),
                              index=list(CURRENCIES.keys()).index(st.session_state["m_base"]), key="m_base")
        purchase_foreign = st.number_input("매입금액 (외화)", value=float(st.session_state["purchase_foreign"]),
                                           step=0.01, format="%.2f", key="purchase_foreign")
        base_cost_won = FX_DEFAULT[m_base]*purchase_foreign if purchase_foreign>0 else won
        st.markdown(f'<div class="pill pill-blue">원가(₩): <b>{base_cost_won:,.2f} 원</b></div>', unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            card_fee = st.number_input("카드수수료(%)", value=float(st.session_state["card_fee_pct"]),
                                       step=0.01, format="%.2f", key="card_fee_pct")
        with c2:
            market_fee = st.number_input("마켓수수료(%)", value=float(st.session_state["market_fee_pct"]),
                                         step=0.01, format="%.2f", key="market_fee_pct")
        shipping_won = st.number_input("배송비(₩)", value=float(st.session_state["shipping_won"]),
                                       step=100.0, format="%.0f", key="shipping_won")

        mode = st.radio("마진 방식", ["퍼센트","플러스"], horizontal=True, key="margin_mode")
        if mode=="퍼센트":
            margin_pct=st.number_input("마진율 (%)", value=float(st.session_state["margin_pct"]),
                                       step=0.01, format="%.2f", key="margin_pct")
            target_price = base_cost_won*(1+card_fee/100)*(1+market_fee/100)*(1+margin_pct/100)+shipping_won
            margin_value = target_price - base_cost_won
        else:
            margin_won=st.number_input("마진액 (₩)", value=float(st.session_state["margin_won"]),
                                       step=100.0, format="%.0f", key="margin_won")
            target_price=base_cost_won*(1+card_fee/100)*(1+market_fee/100)+margin_won+shipping_won
            margin_value=margin_won
        st.markdown(f'<div class="pill pill-yellow">판매가: <b>{target_price:,.2f} 원</b> / 순이익: <b>{margin_value:,.2f} 원</b></div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Rakuten (AUTO GENRE MAP)
# ─────────────────────────────────────────────────────────────────────────────
def _rakuten_keys():
    return RAKUTEN_APP_ID_DEFAULT, RAKUTEN_AFFILIATE_ID_DEFAULT

def _retry_backoff(fn, tries=3, base=0.8, factor=2.0):
    last=None
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            last=e; time.sleep(base*(factor**i))
    raise last

@st.cache_data(ttl=1800, show_spinner=False)
def _rk_fetch_top_genres() -> list[dict]:
    app_id, _ = _rakuten_keys()
    if not (requests and app_id): return []
    api = "https://app.rakuten.co.jp/services/api/IchibaGenre/Search/20140222"
    r = requests.get(api, params={"applicationId": app_id, "genreId": 0}, timeout=10)
    r.raise_for_status()
    return r.json().get("children", [])

RAKUTEN_JP_MATCH = {
    "뷰티/코스메틱": ["美容・コスメ・香水","コスメ","美容"],
    "의류/패션":     ["レディースファッション","メンズファッション","バッグ・小物・ブランド雑貨","靴"],
    "가전/디지털":   ["家電","テレビ・オーディオ・カメラ","パソコン・周辺機器","スマートフォン・タブレット"],
    "가구/인테리어": ["インテリア・寝具・収納"],
    "식품":         ["食品","スイーツ・お菓子","水・ソフトドリンク","日本酒・焼酎","ビール・洋酒"],
    "생활/건강":     ["日用品雑貨・文房具・手芸","ダイエット・健康","医薬品・コンタクト・介護"],
    "스포츠/레저":   ["スポーツ・アウトドア"],
    "문구/취미":     ["ホビー","おもちゃ・ゲーム","楽器・音響機器","CD・DVD"],
}

def _rk_try_automap():
    if not requests: return False
    try:
        top = _rk_fetch_top_genres()
        if not top: return False
        name_id = {}
        for ch in top:
            g = ch.get("child", {})
            name = g.get("genreName","").strip()
            gid  = str(g.get("genreId","")).strip()
            if name and gid: name_id[name] = gid
        changed = False
        m = dict(st.session_state["rk_genre_map"])
        for ko, jp_list in RAKUTEN_JP_MATCH.items():
            for jp in jp_list:
                if jp in name_id:
                    gid = name_id[jp]
                    if m.get(ko) != gid:
                        m[ko] = gid; changed = True
                    break
        if changed: st.session_state["rk_genre_map"].update(m)
        return changed
    except Exception:
        return False

@st.cache_data(ttl=900, show_spinner=False)
def _rk_fetch_rank_cached(genre_id: str, topn: int = 20, strip_emoji: bool=True) -> pd.DataFrame:
    app_id, affiliate = _rakuten_keys()
    def _clean(s: str) -> str:
        if not strip_emoji: return s
        return re.sub(r"[\U00010000-\U0010ffff]", "", s or "")
    if not (requests and app_id):
        return pd.DataFrame([{"rank":i+1,"keyword":_clean(f"[샘플] 키워드 {i+1}"),"shop":"샘플","url":"https://example.com"} for i in range(topn)])
    def _do():
        api = "https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20170628"
        params = {"applicationId": app_id, "genreId": str(genre_id).strip(), "hits": topn}
        if affiliate: params["affiliateId"] = affiliate
        r = requests.get(api, params=params, timeout=12)
        r.raise_for_status()
        items = r.json().get("Items", [])[:topn]
        rows=[]
        for it in items:
            node = it.get("Item", {})
            rows.append({
                "rank": node.get("rank"),
                "keyword": _clean(node.get("itemName","")),
                "shop": node.get("shopName",""),
                "url": node.get("itemUrl",""),
            })
        return pd.DataFrame(rows)
    try:
        return _retry_backoff(_do)
    except Exception:
        return pd.DataFrame([{"rank":i+1,"keyword":_clean(f"[샘플] 키워드 {i+1}"),"shop":"샘플","url":"https://example.com"} for i in range(topn)])

def section_rakuten_ui():
    st.markdown('<div id="rk-card">', unsafe_allow_html=True)
    if not st.session_state.get("rk_automap_done", False):
        if _rk_try_automap(): st.success("라쿠텐 장르 자동 매핑 완료")
        st.session_state["rk_automap_done"] = True
    c1, c2, c3, c4 = st.columns([2,1,1,1])
    with c1:
        cat = st.selectbox("라쿠텐 카테고리",
            ["전체(샘플)","뷰티/코스메틱","의류/패션","가전/디지털","가구/인테리어","식품","생활/건강","스포츠/레저","문구/취미"],
            key="rk_cat")
    with c2: sample_only = st.checkbox("샘플 보기", value=False, key="rk_sample")
    with c3: strip_emoji  = st.toggle("이모지 제거", value=True, key="rk_strip_emoji")
    with c4:
        if st.button("자동 매핑(권장)"):
            ok = _rk_try_automap()
            st.success("자동 매핑 완료") if ok else st.info("이미 최신 매핑입니다.")
    genre_id = (st.session_state.get("rk_genre_map", {}).get(cat) or "").strip() or "100283"
    st.caption(f"장르 ID: **{genre_id}**")
    with st.spinner("라쿠텐 랭킹 불러오는 중…"):
        df = (pd.DataFrame([{"rank":i+1,"keyword":f"[샘플] 키워드 {i+1}","shop":"샘플","url":"https://example.com"} for i in range(20)])
              if sample_only else _rk_fetch_rank_cached(genre_id, topn=20, strip_emoji=strip_emoji))
    colcfg = {
        "rank": st.column_config.NumberColumn("rank", width="small"),
        "keyword": st.column_config.TextColumn("keyword", width="medium"),
        "shop": st.column_config.TextColumn("shop", width="small"),
        "url": st.column_config.LinkColumn("url", display_text="열기", width="small"),
    }
    st.dataframe(df[["rank","keyword","shop","url"]], hide_index=True, use_container_width=True, height=430, column_config=colcfg)
    st.download_button("표 CSV 다운로드", data=df.to_csv(index=False).encode("utf-8-sig"),
                       file_name="rakuten_ranking.csv", mime="text/csv")
    with st.expander("🔧 장르 매핑 편집"):
        cats = ["뷰티/코스메틱","의류/패션","가전/디지털","가구/인테리어","식품","생활/건강","스포츠/레저","문구/취미"]
        g_left, g_right = st.columns(2)
        new_map = dict(st.session_state["rk_genre_map"])
        for i, name in enumerate(cats):
            col = g_left if i < len(cats)//2 else g_right
            with col:
                val = st.text_input(name, value=new_map.get(name,"100283"), key=f"rk_map_{name}")
                new_map[name] = (val or "").strip()
        if st.button("장르 매핑 저장"): st.session_state["rk_genre_map"].update(new_map); st.success("저장 완료")

# ─────────────────────────────────────────────────────────────────────────────
# Korea Radar (Naver Ads Keyword Tool) — with detailed error
# ─────────────────────────────────────────────────────────────────────────────
def _naver_signature(ts: str, method: str, uri: str, secret: str) -> str:
    msg = f"{ts}.{method}.{uri}"
    digest = hmac.new(bytes(secret, "utf-8"), bytes(msg, "utf-8"), hashlib.sha256).digest()
    return b64.b64encode(digest).decode("utf-8")

def _naver_keys_from_defaults():
    return NAVER_API_KEY_DEFAULT, NAVER_SECRET_KEY_DEFAULT, NAVER_CUSTOMER_ID_DEFAULT

def _naver_keywordstool(hint_keywords: list[str]) -> pd.DataFrame:
    """실패 시 st.session_state['naver_err'] 에 상세 오류 저장 + 빈 DF 반환"""
    st.session_state["naver_err"] = ""
    api_key, sec_key, customer_id = _naver_keys_from_defaults()
    if not (requests and api_key and sec_key and customer_id and hint_keywords):
        st.session_state["naver_err"] = "필수 키 또는 키워드 누락"
        return pd.DataFrame()

    # 안전하게 최대 5개까지만 전달
    hints = [k for k in hint_keywords if k]
    if len(hints) > 5:
        hints = hints[:5]

    base_url="https://api.naver.com"
    uri="/keywordstool"
    ts = str(round(time.time()*1000))
    headers = {
        "X-API-KEY": api_key,
        "X-Signature": _naver_signature(ts, "GET", uri, sec_key),
        "X-Timestamp": ts,
        "X-Customer": customer_id,
    }
    params={ "hintKeywords": ",".join(hints),
             "includeHintKeywords": "0", "showDetail": "1" }
    try:
        r = requests.get(base_url+uri, headers=headers, params=params, timeout=12)
    except Exception as e:
        st.session_state["naver_err"] = f"요청 실패: {e}"
        return pd.DataFrame()

    if r.status_code != 200:
        # 응답 본문 앞부분만 저장(너무 길면 잘림)
        body = r.text[:700] if r.text else ""
        st.session_state["naver_err"] = f"HTTP {r.status_code} — {body}"
        return pd.DataFrame()

    try:
        data = r.json().get("keywordList", [])
        if not data:
            st.session_state["naver_err"] = "keywordList 비어있음(권한/쿼터/키워드 확인)"
            return pd.DataFrame()
        df = pd.DataFrame(data).rename(columns={
            "relKeyword":"키워드",
            "monthlyPcQcCnt":"PC월간검색수",
            "monthlyMobileQcCnt":"Mobile월간검색수",
            "monthlyAvePcClkCnt":"PC월평균클릭수",
            "monthlyAveMobileClkCnt":"Mobile월평균클릭수",
            "monthlyAvePcCtr":"PC월평균클릭률",
            "monthlyAveMobileCtr":"Mobile월평균클릭률",
            "plAvgDepth":"월평균노출광고수",
            "compIdx":"광고경쟁정도",
        }).drop_duplicates(["키워드"]).set_index("키워드").reset_index()
        for c in ["PC월간검색수","Mobile월간검색수","PC월평균클릭수","Mobile월평균클릭수","PC월평균클릭률","Mobile월평균클릭률","월평균노출광고수"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        return df
    except Exception as e:
        st.session_state["naver_err"] = f"JSON 파싱 오류: {e}"
        return pd.DataFrame()

def _count_product_from_shopping(keyword: str) -> int|None:
    if not requests: return None
    try:
        url=f"https://search.shopping.naver.com/search/all?where=all&frm=NVSCTAB&query={quote(keyword)}"
        r=requests.get(url, timeout=10); r.raise_for_status()
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.select("a.subFilter_filter__3Y-uy"):
            if "전체" in a.text:
                span=a.find("span")
                if span:
                    txt=span.get_text().replace(",","").strip()
                    return int(re.sub(r"[^0-9]","",txt) or "0")
        return None
    except Exception:
        return None

def section_korea_ui():
    st.caption("※ 검색지표는 네이버 검색광고 API(키워드도구), 상품수는 네이버쇼핑 ‘전체’ 탭 기준입니다.")
    c1, c2, c3 = st.columns([1,1,1])
    with c1: months = st.slider("분석기간(개월, 표시용)", 1, 6, 3)
    with c2: device = st.selectbox("디바이스", ["all","pc","mo"], index=0)
    with c3: src    = st.selectbox("키워드 소스", ["직접 입력"], index=0)

    keywords_txt = st.text_area("키워드(콤마로 구분)", "핸드메이드코트, 남자코트, 여자코트", height=96)
    kw_list = [k.strip() for k in (keywords_txt or "").split(",") if k.strip()]

    opt1, opt2 = st.columns([1,1])
    with opt1: add_product = st.toggle("네이버쇼핑 ‘전체’ 상품수 수집(느림)", value=False)
    with opt2: table_mode  = st.radio("표 모드", ["A(검색지표)","B(검색+순위)","C(검색+상품수+스코어)"], horizontal=True)

    if st.button("레이더 업데이트", use_container_width=False):
        with st.spinner("네이버 키워드도구 조회 중…"):
            df = _naver_keywordstool(kw_list)

        if df.empty:
            err = st.session_state.get("naver_err","")
            st.error("데이터가 없습니다. (API/계정/권한/쿼터 또는 키워드 확인)")
            if err:
                st.code(err, language="text")
            return

        if table_mode.startswith("A"):
            st.dataframe(df, use_container_width=True, height=430)
            st.download_button("CSV 다운로드", df.to_csv(index=False).encode("utf-8-sig"),
                               file_name="korea_keyword_A.csv", mime="text/csv")
            return

        df2 = df.copy()
        df2["검색합계"] = (pd.to_numeric(df2["PC월간검색수"], errors="coerce").fillna(0) +
                           pd.to_numeric(df2["Mobile월간검색수"], errors="coerce").fillna(0))
        df2["검색순위"] = df2["검색합계"].rank(ascending=False, method="min")

        if table_mode.startswith("B"):
            out = df2.sort_values("검색순위")
            st.dataframe(out, use_container_width=True, height=430)
            st.download_button("CSV 다운로드", out.to_csv(index=False).encode("utf-8-sig"),
                               file_name="korea_keyword_B.csv", mime="text/csv")
            return

        if add_product:
            with st.spinner("네이버쇼핑 상품수 수집 중…(키워드 수에 따라 수 분 소요)"):
                df2["판매상품수"] = [(_count_product_from_shopping(k) or math.nan) for k in df2["키워드"]]
        else:
            df2["판매상품수"] = math.nan

        df2["상품수순위"]  = df2["판매상품수"].rank(na_option="bottom", method="min")
        df2["상품발굴대상"] = (df2["검색순위"] + df2["상품수순위"]).rank(na_option="bottom", method="min")

        cols = ["키워드","PC월간검색수","Mobile월간검색수","판매상품수",
                "PC월평균클릭수","Mobile월평균클릭수","PC월평균클릭률","Mobile월평균클릭률",
                "월평균노출광고수","광고경쟁정도","검색순위","상품수순위","상품발굴대상"]
        out = df2[cols].sort_values("상품발굴대상")
        st.dataframe(out, use_container_width=True, height=430)
        st.download_button("CSV 다운로드", out.to_csv(index=False).encode("utf-8-sig"),
                           file_name="korea_keyword_C.csv", mime="text/csv")

# ─────────────────────────────────────────────────────────────────────────────
# Radar Card
# ─────────────────────────────────────────────────────────────────────────────
def section_radar():
    st.markdown('<div class="card"><div class="card-title">AI 키워드 레이더</div>', unsafe_allow_html=True)
    tab_domestic, tab_overseas = st.tabs(["국내", "해외"])
    with tab_domestic: section_korea_ui()
    with tab_overseas: section_rakuten_ui()
    st.markdown('</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Other cards
# ─────────────────────────────────────────────────────────────────────────────
def section_datalab_home():
    st.markdown('<div class="card"><div class="card-title">데이터랩</div>', unsafe_allow_html=True)
    _proxy_iframe_with_title(NAVER_PROXY, "https://datalab.naver.com/", height=860, key="naver_home")
    st.markdown('</div>', unsafe_allow_html=True)

def _11st_abest_url():
    return ("https://m.11st.co.kr/page/main/abest?tabId=ABEST&pageId=AMOBEST&ctgr1No=166160&_ts=%d" % int(time.time()))

def section_11st():
    st.markdown('<div class="card"><div class="card-title">11번가 (모바일) — 아마존 베스트</div>', unsafe_allow_html=True)
    _proxy_iframe(ELEVENST_PROXY, _11st_abest_url(), height=900, scroll=True, key="abest")
    st.markdown('</div>', unsafe_allow_html=True)

LANG_LABELS = {"auto":"자동 감지","ko":"한국어","en":"영어","ja":"일본어","zh-CN":"중국어(간체)","zh-TW":"중국어(번체)","vi":"베트남어","th":"태국어","id":"인도네시아어","de":"독일어","fr":"프랑스어","es":"스페인어","it":"이탈리아어","pt":"포르투갈어"}
def _code(x): return {v:k for k,v in LANG_LABELS.items()}.get(x, x)

def section_translator():
    st.markdown('<div class="card"><div class="card-title">구글 번역기</div>', unsafe_allow_html=True)
    c1, c2 = st.columns([1,1])
    with c1:
        src = st.selectbox("원문", list(LANG_LABELS.values()), index=list(LANG_LABELS.keys()).index("auto"))
        text_in = st.text_area("입력", height=180)
    with c2:
        tgt = st.selectbox("번역", list(LANG_LABELS.values()), index=list(LANG_LABELS.keys()).index("en"))
        if st.button("번역", use_container_width=False):
            if not GoogleTranslator:
                st.warning("deep-translator 설치/런타임 문제")
            else:
                out = GoogleTranslator(source=_code(src), target=_code(tgt)).translate(text_in or "")
                if _code(tgt) != "ko" and out.strip():
                    try:
                        ko_hint = GoogleTranslator(source=_code(tgt), target="ko").translate(out)
                        st.text_area("번역 결과", value=f"{out}\n{ko_hint}", height=180)
                    except Exception:
                        st.text_area("번역 결과", value=out, height=180)
                else:
                    st.text_area("번역 결과", value=out, height=180)
    st.markdown('</div>', unsafe_allow_html=True)

def section_title_generator():
    st.markdown('<div class="card"><div class="card-title">상품명 생성기 (규칙 기반)</div>', unsafe_allow_html=True)
    with st.container():
        cA, cB = st.columns([1,2])
        with cA:
            brand = st.text_input("브랜드", placeholder="예: Apple / 샤오미 / 무지")
            attrs = st.text_input("속성(콤마, 선택)", placeholder="예: 공식, 정품, 한정판")
        with cB:
            kws = st.text_input("키워드(콤마)", placeholder="예: 노트북 스탠드, 접이식, 알루미늄")
        a, b, c = st.columns([1,1,1])
        with a: max_len = st.slider("최대 글자수", 20, 80, 50, 1)
        with b: joiner  = st.selectbox("구분자", [" ", " | ", " · ", " - "], index=0)
        with c: order   = st.selectbox("순서", ["브랜드-키워드-속성", "키워드-브랜드-속성", "브랜드-속성-키워드"], index=0)
        if st.button("상품명 생성"):
            kw_list = [k.strip() for k in (kws or "").split(",") if k.strip()]
            at_list = [a.strip() for a in (attrs or "").split(",") if a.strip()]
            if not kw_list:
                st.warning("키워드가 비었습니다.")
            else:
                titles=[]
                for k in kw_list:
                    if order=="브랜드-키워드-속성": seq=[brand, k]+at_list
                    elif order=="키워드-브랜드-속성": seq=[k,brand]+at_list
                    else: seq=[brand]+at_list+[k]
                    title = (" ".join if joiner==" " else lambda xs: joiner.join(xs))([p for p in seq if p])
                    if len(title)>max_len: title = title[:max_len-1]+"…"
                    titles.append(title)
                st.success(f"총 {len(titles)}건"); st.write("\n".join(titles))
    st.markdown('</div>', unsafe_allow_html=True)

def section_itemscout_placeholder():
    st.markdown('<div class="card"><div class="card-title">아이템스카우트</div>', unsafe_allow_html=True)
    st.info("임베드 보류 중입니다. 아래 버튼으로 원본 페이지를 새 탭에서 여세요.")
    st.link_button("아이템스카우트 직접 열기(새 탭)", "https://app.itemscout.io/market/keyword")
    st.markdown('</div>', unsafe_allow_html=True)

def section_sellerlife_placeholder():
    st.markdown('<div class="card"><div class="card-title">셀러라이프</div>', unsafe_allow_html=True)
    st.info("임베드 보류 중입니다. 아래 버튼으로 원본 페이지를 새 탭에서 여세요.")
    st.link_button("직접 열기(새 탭)", "https://sellochomes.co.kr/sellerlife/")
    st.markdown('</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Layout — row1 ratio 5:7
# ─────────────────────────────────────────────────────────────────────────────
_ = _sidebar()
_responsive_probe()
st.title("ENVY — Season 1 (Dual Proxy Edition)")

row1_l, row1_r = st.columns([5,7], gap="medium")
with row1_l: section_radar()
with row1_r: section_datalab_home()

st.markdown('<div class="row-gap"></div>', unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns([3,3,3,3], gap="medium")
with c1: section_11st()
with c2:
    section_translator()
    st.markdown('<div class="row-gap"></div>', unsafe_allow_html=True)
    section_title_generator()
with c3: section_itemscout_placeholder()
with c4: section_sellerlife_placeholder()

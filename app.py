# -*- coding: utf-8 -*-
# ENVY — Season 1 (Dual Proxy Edition, Final + Naver Keyword Radar)
# 유지/적용된 패치 요약:
# - 사이드바: 입력박스/출력박스 상하 여백 축소, 환산 금액의 (한국어 통화명) 제거(기호만 표시)
# - 데이터랩: 외부(큰) 스크롤 제거, 탭 제목 브릿지 유지
# - 11번가: 섹션카드 높이를 표 최대 높이와 동일하게 조정
# - 라쿠텐: rank 칸 2단계 축소(강제 px), 가로 스크롤 제거, GenreID 입력 숨김(자동 매핑)
# - 번역기/상품명 생성기/기타 설정은 전부 기존 유지
# - NEW: 네이버 데이터랩 Open API 기반 한국 키워드 레이더 섹션 추가

import base64, time, math
from pathlib import Path
from urllib.parse import quote
from datetime import date, timedelta

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

# =========================
# 0) GLOBALS
# =========================
SHOW_ADMIN_BOX = False

# Proxies (배포한 워커 주소)
NAVER_PROXY      = "https://envy-proxy.taesig0302.workers.dev"
ELEVENST_PROXY   = "https://worker-11stjs.taesig0302.workers.dev"
ITEMSCOUT_PROXY  = "https://worker-itemscoutjs.taesig0302.workers.dev"
SELLERLIFE_PROXY = "https://worker-sellerlifejs.taesig0302.workers.dev"

# Rakuten (실키/샘플)
RAKUTEN_APP_ID_DEFAULT       = "1043271015809337425"
RAKUTEN_AFFILIATE_ID_DEFAULT = "4c723498.cbfeca46.4c723499.1deb6f77"

# Sidebar 환율/마진
CURRENCIES = {
    "USD":{"kr":"미국 달러","symbol":"$","unit":"USD"},
    "EUR":{"kr":"유로","symbol":"€","unit":"EUR"},
    "JPY":{"kr":"일본 엔","symbol":"¥","unit":"JPY"},
    "CNY":{"kr":"중국 위안","symbol":"元","unit":"CNY"},
}
FX_DEFAULT = {"USD":1400.0,"EUR":1500.0,"JPY":10.0,"CNY":200.0}

# =========================
# 1) UI 기본값 & CSS
# =========================
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
    # 테이블 공통 표시 옵션
    ss.setdefault("df_height", 520)     # 표 최대 높이
    ss.setdefault("df_font_px", 12)
    ss.setdefault("df_compact", True)
    # 라쿠텐 카테고리 → genreID 매핑(초기값: 숨김/자동)
    ss.setdefault("rk_genre_map", {
        "전체(샘플)": "100283",
        "뷰티/코스메틱": "100283",
        "의류/패션": "100283",
        "가전/디지털": "100283",
        "가구/인테리어": "100283",
        "식품": "100283",
        "생활/건강": "100283",
        "스포츠/레저": "100283",
        "문구/취미": "100283",
    })

def _toggle_theme():
    st.session_state["theme"]="dark" if st.session_state.get("theme","light")=="light" else "light"

def _inject_css():
    theme = st.session_state.get("theme","light")
    bg, fg = ("#0e1117","#e6edf3") if theme=="dark" else ("#ffffff","#111111")
    compact = st.session_state.get("df_compact", True)
    font_px = int(st.session_state.get("df_font_px", 12))

    st.markdown(f"""
    <style>
      .block-container{{max-width:3800px!important;padding-top:.55rem!important;padding-bottom:1rem!important}}
      html,body,[data-testid="stAppViewContainer"]{{background:{bg}!important;color:{fg}!important}}
      h2,h3{{margin-top:.3rem!important}}

      /* Sidebar lock + tighter vertical gap */
      [data-testid="stSidebar"],[data-testid="stSidebar"]>div:first-child,[data-testid="stSidebar"] section{{
        height:100vh!important;overflow:hidden!important;padding:.15rem .25rem!important}}
      [data-testid="stSidebar"] section{{overflow-y:auto!important}}
      [data-testid="stSidebar"] ::-webkit-scrollbar{{display:none!important}}
      [data-testid="stSidebar"] .stSelectbox,
      [data-testid="stSidebar"] .stNumberInput,
      [data-testid="stSidebar"] .stRadio,
      [data-testid="stSidebar"] .stMarkdown,
      [data-testid="stSidebar"] .stTextInput,
      [data-testid="stSidebar"] .stButton{{margin:.06rem 0!important}}

      [data-baseweb="input"] input,.stNumberInput input,[data-baseweb="select"] div[role="combobox"]{{
        height:1.55rem!important;padding:.12rem .6rem!important;font-size:.96rem!important;border-radius:12px!important}}

      /* 로고 72px (기존 사이즈 복원) */
      .logo-circle{{width:72px;height:72px;border-radius:50%;overflow:hidden;margin:.2rem auto .4rem auto;
                   box-shadow:0 2px 8px rgba(0,0,0,.12);border:1px solid rgba(0,0,0,.06)}}
      .logo-circle img{{width:100%;height:100%;object-fit:cover}}

      /* Darker Pills */
      .pill{{border-radius:9999px;padding:.40rem .9rem;font-weight:800;display:inline-block;margin:.10rem 0!important}}
      .pill-green{{background:#b8f06c;border:1px solid #76c02a;color:#083500}}
      .pill-blue{{background:#dbe6ff;border:1px solid #88a8ff;color:#09245e}}
      .pill-yellow{{background:#ffe29b;border:1px solid #d2a12c;color:#3e2a00}}

      .card{{border:1px solid rgba(0,0,0,.06);border-radius:14px;padding:.85rem;background:#fff;box-shadow:0 1px 6px rgba(0,0,0,.05)}}
      .card-title{{font-size:1.18rem;font-weight:900;margin:.1rem 0 .55rem 0}}
      .card iframe{{border:0;width:100%;border-radius:10px}}
      .row-gap{{height:16px}}

      /* DataFrame Compact Mode */
      {"".join([
      f'''
      [data-testid="stDataFrame"] table{{font-size:{font_px}px}}
      [data-testid="stDataFrame"] [role="columnheader"],
      [data-testid="stDataFrame"] [role="gridcell"]{{padding:2px 6px}}
      [data-testid="stDataFrame"] thead tr th{{position:sticky; top:0; z-index:1}}
      '''
      ]) if compact else ""}

      /* 라쿠텐 카드: 가로 스크롤 제거 + rank 칼럼 2단계 축소(강제 px) */
      #rk-card [data-testid="stDataFrame"] div[role='grid']{{ overflow-x: hidden !important; }}
      #rk-card table thead th:nth-child(1),
      #rk-card table tbody td:nth-child(1){{ width:54px!important; min-width:54px!important; max-width:54px!important; text-align:center; }}

      /* 한국 레이더 카드도 가로 스크롤 제거 */
      #kr-card [data-testid="stDataFrame"] div[role='grid']{{ overflow-x: hidden !important; }}
    </style>
    """, unsafe_allow_html=True)

def _inject_alert_center():
    st.markdown("""
    <div id="envy-alert-root" style="position:fixed;top:16px;right:16px;z-index:999999;pointer-events:none;"></div>
    <style>
      .envy-toast{min-width:220px;max-width:420px;margin:8px 0;padding:.7rem 1rem;border-radius:12px;
        color:#fff;font-weight:700;box-shadow:0 8px 24px rgba(0,0,0,.25);opacity:0;transform:translateY(-6px);
        transition:opacity .2s ease, transform .2s ease;}
      .envy-toast.show{opacity:1;transform:translateY(0)}
      .envy-info{background:#2563eb}.envy-warn{background:#d97706}.envy-error{background:#dc2626}
    </style>
    <script>
      (function(){
        const root = document.getElementById('envy-alert-root');
        function toast(level, text){
          const el = document.createElement('div');
          el.className='envy-toast envy-'+(level||'info'); el.textContent=text||'알림';
          el.style.pointerEvents='auto'; root.appendChild(el);
          requestAnimationFrame(()=>el.classList.add('show'));
          setTimeout(()=>{el.classList.remove('show'); setTimeout(()=>el.remove(), 300);}, 5000);
        }
        window.addEventListener('message',(e)=>{ const d=e.data||{}; if(d.__envy && d.kind==='alert'){toast(d.level,d.msg);} },false);
        let heard=false; window.addEventListener('message',(e)=>{ const d=e.data||{}; if(d.__envy && d.kind==='title'){heard=true;}},false);
        setTimeout(()=>{ if(!heard){ toast('warn','데이터랩 연결이 지연되고 있어요.'); } },8000);
      })();
    </script>
    """, unsafe_allow_html=True)

# =========================
# 2) 반응형(필요 시)
# =========================
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

# =========================
# 3) 공용 임베드
# =========================
def _proxy_iframe(proxy_base: str, target_url: str, height: int = 860, scroll=True, key=None):
    proxy = (proxy_base or "").strip().rstrip("/")
    url   = f"{proxy}/?url={quote(target_url, safe=':/?&=%')}"
    h     = int(height) if isinstance(height, (int, float, str)) else 860
    try:
        st.iframe(url, height=h); return
    except Exception:
        pass
    try:
        st.components.v1.iframe(url, height=h, scrolling=bool(scroll)); return
    except Exception:
        pass
    st.markdown(f'<iframe src="{url}" style="width:100%;height:{h}px;border:0;border-radius:10px;"></iframe>', unsafe_allow_html=True)

def _proxy_iframe_with_title(proxy_base: str, target_url: str, height: int = 860, key: str = "naver_home"):
    proxy = (proxy_base or "").strip().rstrip("/")
    url   = f"{proxy}/?url={quote(target_url, safe=':/?&=%')}"
    h     = int(height) if isinstance(height, (int, float, str)) else 860
    html = f"""
    <div id="{key}-wrap" style="width:100%;overflow:hidden;">
      <div id="{key}-title"
           style="display:inline-block;border-radius:9999px;padding:.40rem .9rem;
                  font-weight:800;background:#dbe6ff;border:1px solid #88a8ff;color:#09245e;margin:0 0 .5rem 0;">
        DataLab
      </div>
      <iframe src="{url}" style="width:100%;height:{h}px;border:0;border-radius:10px;"></iframe>
    </div>
    <script>
      (function(){{
        const titleEl=document.getElementById("{key}-title");
        window.addEventListener("message",function(e){{
          const d=e.data||{{}}; try{{ if(d.__envy && d.kind==="title" && d.title) titleEl.textContent=d.title; }}catch(_){{
          }}
        }},false);
      }})();
    </script>
    """
    st.components.v1.html(html, height=h+56, scrolling=False)

# =========================
# 4) 섹션들
# =========================
def _sidebar():
    _ensure_session_defaults(); _inject_css(); _inject_alert_center()
    with st.sidebar:
        lp = Path(__file__).parent / "logo.png"
        if lp.exists():
            b64 = base64.b64encode(lp.read_bytes()).decode("ascii")
            st.markdown(f'<div class="logo-circle"><img src="data:image/png;base64,{b64}"></div>', unsafe_allow_html=True)
        st.toggle("🌓 다크 모드", value=(st.session_state.get("theme","light")=="dark"),
                  on_change=_toggle_theme, key="__theme_toggle")

        st.markdown("### ① 환율 계산기")
        base = st.selectbox("기준 통화", list(CURRENCIES.keys()),
                            index=list(CURRENCIES.keys()).index(st.session_state["fx_base"]), key="fx_base")
        sale_foreign = st.number_input("판매금액 (외화)", value=float(st.session_state["sale_foreign"]),
                                       step=0.01, format="%.2f", key="sale_foreign")
        won = FX_DEFAULT[base] * sale_foreign
        # (한국어 통화명 제거, 심볼만 남김)
        st.markdown(
            f'<div class="pill pill-green">환산 금액: <b>{won:,.2f} 원</b>'
            f'<span style="opacity:.75;font-weight:700"> ({CURRENCIES[base]["symbol"]})</span></div>',
            unsafe_allow_html=True
        )
        st.caption(f"환율 기준: {FX_DEFAULT[base]:,.2f} ₩/{CURRENCIES[base]['unit']}")

        st.markdown("### ② 마진 계산기")
        m_base = st.selectbox("매입 통화", list(CURRENCIES.keys()),
                              index=list(CURRENCIES.keys()).index(st.session_state["m_base"]), key="m_base")
        purchase_foreign = st.number_input("매입금액 (외화)", value=float(st.session_state["purchase_foreign"]),
                                           step=0.01, format="%.2f", key="purchase_foreign")
        base_cost_won = FX_DEFAULT[m_base]*purchase_foreign if purchase_foreign>0 else won
        st.markdown(f'<div class="pill pill-green">원가(₩): <b>{base_cost_won:,.2f} 원</b></div>', unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            card_fee = st.number_input("카드수수료(%)", value=float(st.session_state["card_fee_pct"]),
                                       step=0.01, format="%.2f", key="card_fee_pct")
        with col2:
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
            desc = f"{margin_pct:.2f}%"
        else:
            margin_won=st.number_input("마진액 (₩)", value=float(st.session_state["margin_won"]),
                                       step=100.0, format="%.0f", key="margin_won")
            target_price=base_cost_won*(1+card_fee/100)*(1+market_fee/100)+margin_won+shipping_won
            margin_value=margin_won; desc=f"+{margin_won:,.0f}"
        st.markdown(f'<div class="pill pill-blue">판매가: <b>{target_price:,.2f} 원</b></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="pill pill-yellow">순이익(마진): <b>{margin_value:,.2f} 원</b> — {desc}</div>', unsafe_allow_html=True)

        if SHOW_ADMIN_BOX:
            st.divider()
            st.text_input("PROXY_URL(디버그)", key="PROXY_URL", help="Cloudflare Worker 주소 (옵션)")

def section_datalab_home():
    st.markdown('<div class="card"><div class="card-title">데이터랩</div>', unsafe_allow_html=True)
    # 외부 큰 스크롤 제거(components.html, scrolling=False)
    _proxy_iframe_with_title(NAVER_PROXY, "https://datalab.naver.com/", height=860, key="naver_home")
    st.markdown('</div>', unsafe_allow_html=True)

def section_itemscout_placeholder():
    st.markdown('<div class="card"><div class="card-title">아이템스카우트</div>', unsafe_allow_html=True)
    st.info("임베드 보류 중입니다. 아래 버튼으로 원본 페이지를 새 탭에서 여세요.")
    st.link_button("아이템스카우트 열기(새 탭)", "https://app.itemscout.io/market/keyword")
    st.markdown('</div>', unsafe_allow_html=True)

def section_sellerlife_placeholder():
    st.markdown('<div class="card"><div class="card-title">셀러라이프</div>', unsafe_allow_html=True)
    st.info("임베드 보류 중입니다. 아래 버튼으로 원본 페이지를 새 탭에서 여세요.")
    st.link_button("셀러라이프 열기(새 탭)", "https://sellochomes.co.kr/sellerlife/")
    st.markdown('</div>', unsafe_allow_html=True)

def _11st_abest_url():
    return ("https://m.11st.co.kr/page/main/abest?tabId=ABEST&pageId=AMOBEST&ctgr1No=166160&_ts=%d" % int(time.time()))

def section_11st():
    st.markdown('<div class="card"><div class="card-title">11번가 (모바일) — 아마존 베스트</div>', unsafe_allow_html=True)
    # 표 최대 높이와 동일하게 맞춤
    h = int(st.session_state.get("df_height", 520))
    _proxy_iframe(ELEVENST_PROXY, _11st_abest_url(), height=h, scroll=True, key="abest")
    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# 5) 라쿠텐 (cache + retry + no-HScroll + rank 폭 축소 + GenreID 숨김)
# =========================
def _rakuten_keys():
    app_id = (st.secrets.get("RAKUTEN_APP_ID", "")
              or st.secrets.get("RAKUTEN_APPLICATION_ID", "")
              or RAKUTEN_APP_ID_DEFAULT).strip()
    affiliate = (st.secrets.get("RAKUTEN_AFFILIATE_ID", "")
                 or st.secrets.get("RAKUTEN_AFFILIATE", "")
                 or RAKUTEN_AFFILIATE_ID_DEFAULT).strip()
    return app_id, affiliate

RK_JP_KEYWORDS = {
    "뷰티/코스메틱": "コスメ",
    "의류/패션": "ファッション",
    "가전/디지털": "家電",
    "가구/인테리어": "インテリア",
    "식품": "食品",
    "생활/건강": "日用品",
    "스포츠/레저": "スポーツ",
    "문구/취미": "ホビー",
}

def _rk_guess_genre_by_keyword(jp_keyword: str, hits: int = 30) -> str | None:
    app_id, _ = _rakuten_keys()
    if not (requests and app_id and jp_keyword):
        return None
    try:
        r = requests.get(
            "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20170706",
            params={"applicationId": app_id, "keyword": jp_keyword, "hits": hits, "imageFlag": 0},
            timeout=10
        )
        r.raise_for_status()
        items = [it.get("Item", {}) for it in r.json().get("Items", [])]
        freq={}
        for it in items:
            gid = str(it.get("genreId") or "")
            if gid: freq[gid]=freq.get(gid,0)+1
        if not freq: return None
        return max(freq.items(), key=lambda kv: kv[1])[0]
    except Exception:
        return None

def _retry_backoff(fn, tries=3, base=0.8, factor=2.0):
    last=None
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            last=e
            time.sleep(base*(factor**i))
    raise last

@st.cache_data(ttl=900, show_spinner=False)
def _rk_fetch_rank_cached(genre_id: str, topn: int = 20) -> pd.DataFrame:
    app_id, affiliate = _rakuten_keys()
    if not (requests and app_id):
        return pd.DataFrame([{"rank":i+1,"keyword":f"[샘플] 키워드 {i+1} ハロウィン 秋 🍂","shop":"샘플","url":"https://example.com"} for i in range(topn)])

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
                "keyword": node.get("itemName",""),
                "shop": node.get("shopName",""),
                "url": node.get("itemUrl",""),
            })
        return pd.DataFrame(rows)

    try:
        return _retry_backoff(_do)
    except Exception:
        return pd.DataFrame([{"rank":i+1,"keyword":f"[샘플] 키워드 {i+1} ハロウィン 秋 🍂","shop":"샘플","url":"https://example.com"} for i in range(topn)])

def section_rakuten():
    st.markdown('<div id="rk-card" class="card"><div class="card-title">AI 키워드 레이더 (Rakuten)</div>', unsafe_allow_html=True)
    colA, colB, colC = st.columns([1, 1, 1])
    with colA:
        scope = st.radio("범위", ["국내","글로벌"], horizontal=True, key="rk_scope")
    with colB:
        cat = st.selectbox(
            "라쿠텐 카테고리",
            ["전체(샘플)","뷰티/코스메틱","의류/패션","가전/디지털","가구/인테리어","식품","생활/건강","스포츠/레저","문구/취미"],
            key="rk_cat"
        )
    with colC:
        sample_only = st.checkbox("샘플 보기", value=False, key="rk_sample")

    # GenreID는 입력칸 숨기고 자동 추정(초기값 100283)
    genre_map = st.session_state.get("rk_genre_map", {})
    genre_id = (genre_map.get(cat) or "").strip()
    need_auto = (not genre_id) or (genre_id == "100283" and cat != "전체(샘플)")
    if need_auto and cat in RK_JP_KEYWORDS:
        guessed = _rk_guess_genre_by_keyword(RK_JP_KEYWORDS[cat])
        if guessed:
            genre_id = guessed
            st.session_state["rk_genre_map"][cat] = genre_id
            st.markdown("<script>window.postMessage({__envy:true,kind:'alert',level:'info',msg:'카테고리에 맞춰 장르를 자동 지정했어요.'},'*');</script>", unsafe_allow_html=True)
    if not genre_id:
        genre_id = "100283"

    with st.spinner("라쿠텐 랭킹 불러오는 중…"):
        df = pd.DataFrame([{"rank":i+1,"keyword":f"[샘플] 키워드 {i+1}","shop":"샘플","url":"https://example.com"} for i in range(20)]) if sample_only \
             else _rk_fetch_rank_cached(genre_id, topn=20)

    colcfg = {
        "rank": st.column_config.NumberColumn("rank", width="small"),
        "keyword": st.column_config.TextColumn("keyword", width="medium"),
        "shop": st.column_config.TextColumn("shop", width="small"),
        "url": st.column_config.LinkColumn("url", display_text="열기", width="small"),
    }
    h = int(st.session_state.get("df_height", 520))
    st.dataframe(df[["rank","keyword","shop","url"]], hide_index=True, use_container_width=True, height=h, column_config=colcfg)
    st.download_button("표 CSV 다운로드", data=df.to_csv(index=False).encode("utf-8-sig"),
                       file_name="rakuten_ranking.csv", mime="text/csv")
    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# 6) 네이버 데이터랩 Open API — 한국 키워드 레이더
# =========================
NAVER_DATALAB_API = "https://openapi.naver.com/v1/datalab/search"

def _naver_keys():
    cid = (st.secrets.get("NAVER_CLIENT_ID","") or "").strip()
    csc = (st.secrets.get("NAVER_CLIENT_SECRET","") or "").strip()
    if not cid or not csc:
        raise RuntimeError("NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 누락")
    return cid, csc

def _daterange(months=3):
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=int(30*months))
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

@st.cache_data(ttl=600, show_spinner=False)
def naver_trend_for_keywords(keywords:list[str], months:int=3, device:str="all"):
    """
    네이버 데이터랩 검색트렌드 (주차별 상대지수) 수집 + 성장지표 계산
    반환: (랭킹 DF, 원시 시계열 DF)
    """
    if not keywords:
        return pd.DataFrame(), pd.DataFrame()
    if requests is None:
        raise RuntimeError("requests 모듈이 없음 (requirements에 requests 추가 필요)")

    start, end = _daterange(months)
    cid, csc = _naver_keys()

    def chunk(xs, n):
        for i in range(0, len(xs), n): 
            yield xs[i:i+n]

    frames=[]
    headers = {
        "X-Naver-Client-Id": cid,
        "X-Naver-Client-Secret": csc,
        "Content-Type": "application/json"
    }
    for part in chunk(keywords, 5):  # API가 5개씩 그룹 처리
        body = {
          "startDate": start, "endDate": end,
          "timeUnit": "week",
          "keywordGroups": [{"groupName": k, "keywords": [k]} for k in part],
          "device": device,  # all | pc | mo
          "ages": [], "gender": ""
        }
        r = requests.post(NAVER_DATALAB_API, headers=headers, json=body, timeout=12)
        r.raise_for_status()
        data = r.json().get("results", [])
        for res in data:
            name = res.get("title")
            for row in (res.get("data") or []):
                frames.append({"keyword": name, "date": row["period"], "ratio": float(row["ratio"])})

        time.sleep(0.12)  # 과호출 방지

    raw = pd.DataFrame(frames)
    if raw.empty:
        return pd.DataFrame(), pd.DataFrame()

    # 성장점수: 최근 2주 평균 / 그 전 2주 평균 (+1 스무딩)
    def growth_score(x: pd.DataFrame) -> float:
        x = x.sort_values("date")
        if len(x) < 4:
            return 1.0
        recent = x["ratio"].tail(2).mean()
        prev   = x["ratio"].tail(4).head(2).mean()
        return (recent + 1.0) / (prev + 1.0)

    agg = (raw.groupby("keyword").apply(growth_score).reset_index(name="growth"))
    last4 = (raw.sort_values("date").groupby("keyword").tail(4).groupby("keyword")["ratio"].mean().reset_index(name="last4_avg"))
    rank = (agg.merge(last4, on="keyword", how="left").sort_values(["growth","last4_avg"], ascending=[False, False]))
    return rank, raw

def section_keyword_radar_kr():
    st.markdown('<div id="kr-card" class="card"><div class="card-title">AI 키워드 레이더 (Korea)</div>', unsafe_allow_html=True)
    colA, colB, colC = st.columns([1,1,1])
    with colA:
        months = st.slider("분석기간(개월)", 1, 6, 3)
    with colB:
        device = st.selectbox("디바이스", ["all","pc","mo"], index=0)
    with colC:
        src = st.selectbox("키워드 소스", ["라쿠텐 상위20 사용","직접 입력"], index=0)

    if src == "직접 입력":
        seed = st.text_area("키워드(콤마로 구분)", "원피스, 블라우스, 바람막이, 트위드자켓")
        kw_list = [k.strip() for k in (seed or "").split(",") if k.strip()]
    else:
        # 라쿠텐 표 상위 20개를 시드로 사용(없으면 샘플)
        try:
            genre_map = st.session_state.get("rk_genre_map", {})
            cat = st.session_state.get("rk_cat", "의류/패션")
            gid = (genre_map.get(cat) or "100283")
            df_rk = _rk_fetch_rank_cached(gid, topn=20)
            kw_list = [k.strip() for k in df_rk["keyword"].tolist() if k.strip()]
        except Exception:
            kw_list = ["원피스","블라우스","바람막이","셔츠","골프웨어","슬랙스","롱스커트","플리츠"]

    h = int(st.session_state.get("df_height", 520))
    if st.button("레이더 업데이트", use_container_width=True):
        try:
            with st.spinner("네이버 트렌드 불러오는 중…"):
                rank_df, raw_df = naver_trend_for_keywords(kw_list, months=months, device=device)
            if rank_df.empty:
                st.warning("데이터가 없습니다. 키워드/기간을 조정하세요.")
            else:
                rank_df = rank_df.reset_index(drop=True)
                rank_df["rank"] = range(1, len(rank_df)+1)
                colcfg = {
                    "rank": st.column_config.NumberColumn("rank", width="small"),
                    "keyword": st.column_config.TextColumn("keyword", width="large"),
                    "growth": st.column_config.NumberColumn("growth(↑)", format="%.2f", width="small"),
                    "last4_avg": st.column_config.NumberColumn("최근4주 평균", format="%.1f", width="small"),
                }
                st.dataframe(rank_df[["rank","keyword","growth","last4_avg"]],
                             hide_index=True, use_container_width=True, height=h, column_config=colcfg)
                st.download_button("CSV 다운로드",
                    rank_df.to_csv(index=False).encode("utf-8-sig"),
                    file_name="keyword_radar_kr.csv", mime="text/csv")

                with st.expander("원시 시계열 보기"):
                    st.dataframe(raw_df, hide_index=True, use_container_width=True, height=320)
        except Exception as e:
            st.error(f"실패: {e}")
    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# 7) 번역기(유지)
# =========================
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

# =========================
# 8) 상품명 생성기(유지)
# =========================
def section_title_generator():
    st.markdown('<div class="card"><div class="card-title">상품명 생성기 (규칙 기반)</div>', unsafe_allow_html=True)
    with st.container():
        colA, colB = st.columns([1,2])
        with colA:
            brand = st.text_input("브랜드", placeholder="예: Apple / 샤오미 / 무지")
            attrs = st.text_input("속성(콤마, 선택)", placeholder="예: 공식, 정품, 한정판")
        with colB:
            kws = st.text_input("키워드(콤마)", placeholder="예: 노트북 스탠드, 접이식, 알루미늄")
        col1, col2, col3 = st.columns([1,1,1])
        with col1:
            max_len = st.slider("최대 글자수", 20, 80, 50, 1)
        with col2:
            joiner = st.selectbox("구분자", [" ", " | ", " · ", " - "], index=0)
        with col3:
            order = st.selectbox("순서", ["브랜드-키워드-속성", "키워드-브랜드-속성", "브랜드-속성-키워드"], index=0)

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
                    title = joiner.join([p for p in seq if p])
                    if len(title)>max_len:
                        title = title[:max_len-1]+"…"
                    titles.append(title)
                st.success(f"총 {len(titles)}건")
                st.write("\n".join(titles))
    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# 9) Layout
# =========================
_ = _sidebar()
st.title("ENVY — Season 1 (Dual Proxy Edition)")

# 1줄: 데이터랩 / 아이템스카우트 / 셀러라이프
top1, top2, top3 = st.columns([3,3,3], gap="medium")
with top1: section_datalab_home()
with top2: section_itemscout_placeholder()
with top3: section_sellerlife_placeholder()

st.markdown('<div class="row-gap"></div>', unsafe_allow_html=True)

# 2줄: 11번가 / 라쿠텐 / (한국 레이더) / 번역 / 생성기
b1, b2, b3, b4 = st.columns([3,3,3,3], gap="medium")
with b1: section_11st()
with b2: section_rakuten()
with b3: section_keyword_radar_kr()
with b4: section_translator()

st.markdown('<div class="row-gap"></div>', unsafe_allow_html=True)
# 3줄(선택): 생성기
c1, = st.columns([3])
with c1: section_title_generator()

# -*- coding: utf-8 -*-
# ENVY — Season 1 (Dual Proxy Edition, Responsive + Alerts, Darker Pills)
# - 반응형 카드 레이아웃
# - 전역 알림 팝업(토스트)
# - 데이터랩 탭 제목 표시 + 2중 스크롤 제거
# - 라쿠텐 rank 2단계 축소 + 가로 스크롤 억제(폰트 1단계 축소)
import os, base64
from pathlib import Path
from urllib.parse import quote
import streamlit as st
import pandas as pd

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
# 0. GLOBAL SETTINGS
# =========================
SHOW_ADMIN_BOX = False

# Proxies (배포한 워커 주소)
NAVER_PROXY      = "https://envy-proxy.taesig0302.workers.dev"          # ※ 워커는 TitleReporter 주입 버전이어야 탭제목 표시됨
ELEVENST_PROXY   = "https://worker-11stjs.taesig0302.workers.dev"
ITEMSCOUT_PROXY  = "https://worker-itemscoutjs.taesig0302.workers.dev"
SELLERLIFE_PROXY = "https://worker-sellerlifejs.taesig0302.workers.dev"

# Rakuten (실키/샘플)
RAKUTEN_APP_ID_DEFAULT       = "1043271015809337425"
RAKUTEN_AFFILIATE_ID_DEFAULT = "4c723498.cbfeca46.4c723499.1deb6f77"

# =========================
# 1. Sidebar (계산기 + 테마)
# =========================
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
    # 라쿠텐: 카테고리→GenreID 매핑(초기값 100283, 화면 비노출)
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

      /* 사이드바 입력/출력 상하 여백 축소 */
      [data-testid="stSidebar"] .stSelectbox,
      [data-testid="stSidebar"] .stNumberInput,
      [data-testid="stSidebar"] .stRadio,
      [data-testid="stSidebar"] .stMarkdown,
      [data-testid="stSidebar"] .stTextInput,
      [data-testid="stSidebar"] .stButton{{margin:.06rem 0!important}}

      [data-baseweb="input"] input,.stNumberInput input,[data-baseweb="select"] div[role="combobox"]{{
        height:1.55rem!important;padding:.12rem .6rem!important;font-size:.96rem!important;border-radius:12px!important}}

      /* Pills */
      .pill{{border-radius:9999px;padding:.40rem .9rem;font-weight:800;display:inline-block;margin:.10rem 0!important}}
      .pill-green{{background:#b8f06c;border:1px solid #76c02a;color:#083500}}
      .pill-blue{{background:#dbe6ff;border:1px solid #88a8ff;color:#09245e}}
      .pill-yellow{{background:#ffe29b;border:1px solid #d2a12c;color:#3e2a00}}

      /* Cards */
      .card{{border:1px solid rgba(0,0,0,.06);border-radius:14px;padding:.85rem;background:#fff;box-shadow:0 1px 6px rgba(0,0,0,.05)}}
      .card-title{{font-size:1.18rem;font-weight:900;margin:.1rem 0 .55rem 0}}
      .card iframe{{border:0;width:100%;border-radius:10px}}
      .row-gap{{height:16px}}

      .logo-circle{{width:95px;height:95px;border-radius:50%;overflow:hidden;margin:.2rem auto .5rem auto;
                   box-shadow:0 2px 8px rgba(0,0,0,.12);border:1px solid rgba(0,0,0,.06)}}
      .logo-circle img{{width:100%;height:100%;object-fit:cover}}
    </style>
    """, unsafe_allow_html=True)

# ---------- 전역 알림 센터(토스트) ----------
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
          const div = document.createElement('div');
          div.className = 'envy-toast envy-'+(level||'info');
          div.textContent = text||'알림';
          div.style.pointerEvents='auto';
          root.appendChild(div);
          requestAnimationFrame(()=>div.classList.add('show'));
          setTimeout(()=>{ div.classList.remove('show'); setTimeout(()=>div.remove(), 300); }, 5000);
        }
        // 모든 iframe에서 오는 메시지 수신
        window.addEventListener('message', (e)=>{
          const d = e.data || {};
          if(d.__envy && d.kind === 'alert'){
            toast(d.level||'info', d.msg||'알림');
          }
        }, false);
        // 데이터랩 타이틀 수신 체크(지연 시 경고)
        let heard = false;
        window.addEventListener('message', (e)=>{
          const d=e.data||{}; if(d.__envy && d.kind==='title'){ heard=true; }
        }, false);
        setTimeout(()=>{ if(!heard){ toast('warn','데이터랩 연결이 지연되고 있어요. 네트워크를 확인하세요.'); } }, 8000);
      })();
    </script>
    """, unsafe_allow_html=True)

# -------- 반응형: 뷰포트 버킷(0~3) 계산용 프루브 --------
def _responsive_probe():
    html = """
    <script>
    (function(){
      const bps = [900, 1280, 1600];
      const w = Math.max(document.documentElement.clientWidth || 0, window.innerWidth || 0);
      let bin = 0; for (let i=0;i<bps.length;i++) if (w>=bps[i]) bin=i+1;
      const url = new URL(window.location);
      const curr = url.searchParams.get('vwbin');
      if (curr !== String(bin)) {
        url.searchParams.set('vwbin', String(bin));
        window.location.replace(url.toString());
      }
    })();
    </script>
    """
    st.components.v1.html(html, height=0, scrolling=False)

def _get_view_bin():
    # 0: <900, 1: >=900, 2: >=1280, 3: >=1600
    try:
        qp = st.query_params
        raw = qp.get("vwbin", "3")
    except Exception:
        qp = st.experimental_get_query_params()
        raw = (qp.get("vwbin", ["3"])[0])
    try:
        return max(0, min(3, int(raw)))
    except:
        return 3

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
        # '(미국 달러)' 같은 한글 텍스트 제거 → 통화 기호만 표기
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
        st.markdown(f'<div class="pill pill-yellow">순이익(마진): <b>{margin_value:,.2f} 원</b> — {desc}</div>',
                    unsafe_allow_html=True)

        if SHOW_ADMIN_BOX:
            st.divider()
            st.text_input("PROXY_URL(디버그)", key="PROXY_URL", help="Cloudflare Worker 주소 (옵션)")

# =========================
# 2. Embeds (프록시/데이터랩)
# =========================
def _proxy_iframe(proxy_base: str, target_url: str, height: int = 860, scroll=True, key=None):
    proxy = (proxy_base or "").strip().rstrip("/")
    url   = f"{proxy}/?url={quote(target_url, safe=':/?&=%')}"
    h     = int(height) if isinstance(height, (int, float, str)) else 860
    try:
        st.iframe(url, height=h); return
    except Exception: pass
    try:
        st.components.v1.iframe(url, height=h, scrolling=bool(scroll)); return
    except Exception: pass
    st.markdown(
        f'<iframe src="{url}" style="width:100%;height:{h}px;border:0;border-radius:10px;" '
        f'allow="clipboard-read; clipboard-write"></iframe>', unsafe_allow_html=True)

# DataLab: 탭 제목 + 2중 스크롤 방지(컴포넌트 래퍼 scrolling=False)
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
        const titleEl = document.getElementById("{key}-title");
        window.addEventListener("message", function(e){{
          const d = e.data || {{}};
          try {{
            if (d.__envy && d.kind === "title" && d.title) titleEl.textContent = d.title;
          }} catch(_){{
          }}
        }}, false);
      }})();
    </script>
    """
    st.components.v1.html(html, height=h+56, scrolling=False)

def _11st_abest_url():
    import time
    return ("https://m.11st.co.kr/page/main/abest"
            f"?tabId=ABEST&pageId=AMOBEST&ctgr1No=166160&_ts={int(time.time())}")

def section_datalab_home():
    st.markdown('<div class="card"><div class="card-title">데이터랩</div>', unsafe_allow_html=True)
    _proxy_iframe_with_title(NAVER_PROXY, "https://datalab.naver.com/", height=860, key="naver_home")
    st.markdown('</div>', unsafe_allow_html=True)

def section_itemscout():
    st.markdown('<div class="card"><div class="card-title">아이템스카우트</div>', unsafe_allow_html=True)
    _proxy_iframe(ITEMSCOUT_PROXY, "https://app.itemscout.io/market/keyword", height=760, scroll=True, key="itemscout")
    st.markdown('</div>', unsafe_allow_html=True)

def section_sellerlife():
    st.markdown('<div class="card"><div class="card-title">셀러라이프</div>', unsafe_allow_html=True)
    _proxy_iframe(SELLERLIFE_PROXY, "https://sellerlife.co.kr/dashboard", height=760, scroll=True, key="sellerlife")
    st.markdown('</div>', unsafe_allow_html=True)

def section_11st():
    st.markdown('<div class="card"><div class="card-title">11번가 (모바일) — 아마존 베스트</div>', unsafe_allow_html=True)
    _proxy_iframe(ELEVENST_PROXY, _11st_abest_url(), height=900, scroll=True, key="abest")
    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# 3. AI 키워드 레이더 (Rakuten)
# =========================
def _rakuten_keys():
    app_id = (st.secrets.get("RAKUTEN_APP_ID", "")
              or st.secrets.get("RAKUTEN_APPLICATION_ID", "")
              or RAKUTEN_APP_ID_DEFAULT).strip()
    affiliate = (st.secrets.get("RAKUTEN_AFFILIATE_ID", "")
                 or st.secrets.get("RAKUTEN_AFFILIATE", "")
                 or RAKUTEN_AFFILIATE_ID_DEFAULT).strip()
    return app_id, affiliate

def _rk_fetch_rank(genre_id: str, topn: int = 20) -> pd.DataFrame:
    app_id, affiliate = _rakuten_keys()
    rows=[]
    if requests and app_id:
      try:
        api = "https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20170628"
        params = {"applicationId": app_id, "genreId": str(genre_id).strip()}
        if affiliate: params["affiliateId"] = affiliate
        r = requests.get(api, params=params, timeout=12)
        r.raise_for_status()
        items = r.json().get("Items", [])[:topn]
        for it in items:
          node = it.get("Item", {})
          rows.append({
            "rank": node.get("rank"),
            "keyword": node.get("itemName",""),
            "shop": node.get("shopName",""),
            "url": node.get("itemUrl",""),
          })
      except Exception:
        pass
    if not rows:
      rows=[{"rank":i+1,"keyword":f"[샘플] 키워드 {i+1} ハロウィン 秋 🍂","shop":"샘플","url":"https://example.com"} for i in range(topn)]
    return pd.DataFrame(rows)

def section_rakuten():
    # 표 가로 스크롤 최소화를 위해 카드 범위에서만 폰트 1단계 축소
    st.markdown("""
    <style>
      #rk-card [data-testid="stDataFrame"] * { font-size: 0.92rem !important; }
    </style>
    """, unsafe_allow_html=True)

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

    # 카테고리→GenreID 매핑 (세션 저장, 기본 100283) — 화면엔 ID 미노출
    genre_map = st.session_state.get("rk_genre_map", {})
    genre_id = (genre_map.get(cat) or "100283").strip()

    # 매핑 편집(필요시만 열기)
    with st.expander("🔧 장르 매핑 편집 (GenreID는 여기서만 관리 — 화면에는 숨김)", expanded=False):
        new_map = {}
        cols = st.columns(3)
        cats = ["전체(샘플)","뷰티/코스메틱","의류/패션","가전/디지털","가구/인테리어","식품","생활/건강","스포츠/레저","문구/취미"]
        for i, c in enumerate(cats):
            with cols[i % 3]:
                val = st.text_input(f"{c} → GenreID", value=genre_map.get(c, "100283"), key=f"rk_map_{c}")
                new_map[c] = val.strip()
        if st.button("매핑 저장", use_container_width=False, key="rk_save_map"):
            st.session_state["rk_genre_map"] = new_map
            st.success("장르 매핑을 저장했습니다.")

    # 데이터 로드
    if sample_only:
        df = pd.DataFrame(
            [{"rank": i+1, "keyword": f"[샘플] 키워드 {i+1}", "shop": "샘플샵", "url": "https://example.com"} for i in range(20)]
        )
    else:
        df = _rk_fetch_rank(genre_id or "100283", topn=20)

    # 랭크 칼럼 2단계 축소 유지
    colcfg = {
        "rank": st.column_config.NumberColumn("rank", width="small"),
        "keyword": st.column_config.TextColumn("keyword", width="large"),
        "shop": st.column_config.TextColumn("shop", width="medium"),
        "url": st.column_config.LinkColumn("url", display_text="열기", width="small"),
    }
    st.dataframe(
        df[["rank","keyword","shop","url"]],
        hide_index=True,
        use_container_width=True,
        height=420,
        column_config=colcfg
    )

    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# 4. 번역기
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
# 5. 상품명 생성기 (규칙)
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
                    title = " ".join([p for p in seq if p]) if joiner==" " else joiner.join([p for p in seq if p])
                    if len(title)>max_len:
                        title = title[:max_len-1]+"…"
                    titles.append(title)
                st.success(f"총 {len(titles)}건")
                st.write("\n".join(titles))
    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# 6. Layout (반응형)
# =========================
_ = _sidebar()
# 뷰포트 버킷 주입(브레이크포인트 변경 시 URL 갱신 → 리렌더)
_responsive_probe()
vwbin = _get_view_bin()  # 0:<900, 1:≥900, 2:≥1280, 3:≥1600

st.title("ENVY — Season 1 (Dual Proxy Edition)")

# 1줄: 데이터랩 / 아이템스카우트 / 셀러라이프
if vwbin >= 3:  # ≥1600px (기존 그대로)
    top1, top2, top3 = st.columns([5,2,2], gap="medium")
    with top1: section_datalab_home()
    with top2: section_itemscout()
    with top3: section_sellerlife()
elif vwbin == 2:  # 1280~1599px (살짝 균등화)
    top1, top2, top3 = st.columns([4,3,3], gap="small")
    with top1: section_datalab_home()
    with top2: section_itemscout()
    with top3: section_sellerlife()
else:  # <1280px (스택)
    section_datalab_home()
    st.markdown('<div class="row-gap"></div>', unsafe_allow_html=True)
    section_itemscout()
    st.markdown('<div class="row-gap"></div>', unsafe_allow_html=True)
    section_sellerlife()

st.markdown('<div class="row-gap"></div>', unsafe_allow_html=True)

# 2줄: 11번가 / 레이더 / 번역 / 생성기
if vwbin >= 3:
    b1, b2, b3, b4 = st.columns([3,3,3,3], gap="medium")
    with b1: section_11st()
    with b2: section_rakuten()
    with b3: section_translator()
    with b4: section_title_generator()
elif vwbin == 2:
    # 2열로 재배치: 좌(11번가+라쿠텐) / 우(번역+생성기)
    colL, colR = st.columns([1,1], gap="small")
    with colL:
        section_11st()
        st.markdown('<div class="row-gap"></div>', unsafe_allow_html=True)
        section_rakuten()
    with colR:
        section_translator()
        st.markdown('<div class="row-gap"></div>', unsafe_allow_html=True)
        section_title_generator()
else:
    # 단일 스택
    section_11st()
    st.markdown('<div class="row-gap"></div>', unsafe_allow_html=True)
    section_rakuten()
    st.markdown('<div class="row-gap"></div>', unsafe_allow_html=True)
    section_translator()
    st.markdown('<div class="row-gap"></div>', unsafe_allow_html=True)
    section_title_generator()

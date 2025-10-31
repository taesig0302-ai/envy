# part_crawler.py
# ENVY — Season 1 add-on section (본 섹션만 추가/교체, 기존 사이드바·레이아웃·환율/마진 계산기·PROXY_URL 블록은 절대 수정하지 않음)
import os, time, json, random, traceback
from typing import List
import streamlit as st

# ── ENVY 고정 공지(프록시 관련) ─────────────────────────────────────
# 이 크롤러 파트는 프록시 불필요. 다만 ENVY 전반 운영 규칙상 11번가(모바일) 임베드는 항상 프록시 경유가 필수.
# 기본 프록시 주소: https://envy-proxy.taesig0302.workers.dev/  (앱에서는 PROXY_URL만 사용)
PROXY_INFO = "⚠️ 11번가(모바일) 임베드는 항상 프록시 경유: https://envy-proxy.taesig0302.workers.dev/ (앱은 PROXY_URL 환경만 참조)"

# ── 크롤러 코어 로드 ────────────────────────────────────────────────
try:
    import crawler_core as core
except Exception as e:
    core = None

def _ensure_core_ready():
    if core is None:
        st.error("crawler_core.py 모듈을 찾을 수 없습니다. 현재 사용 중인 단독 스크립트를 같은 폴더에 `crawler_core.py`로 저장하세요.")
        st.stop()

# ── UI 섹션 렌더 ────────────────────────────────────────────────────
def render_crawler_section():
    st.markdown("## 🧲 네이버 스마트스토어 크롤러")
    st.caption("URL 입력 → 상품명/가격/이미지 수집 → 엑셀/이미지 폴더 저장. 동작 중 페이지 전환/새로고침 금지.")
    st.info(PROXY_INFO, icon="🔐")

    _ensure_core_ready()

    with st.expander("옵션", expanded=True):
        urls_text = st.text_area(
            "크롤링할 스마트스토어 카테고리/검색 URL (줄바꿈으로 여러 개)",
            value="\n".join(core.MARKETS) if hasattr(core, "MARKETS") else "",
            height=120,
            help="예) https://smartstore.naver.com/스토어ID/category/...&page=1&size=60"
        )
        download_images = st.checkbox("이미지 저장(DOWNLOAD_IMAGES)", value=getattr(core, "DOWNLOAD_IMAGES", True))
        headless = st.checkbox("헤드리스(브라우저 창 숨김)", value=True)
        autosave_every = st.number_input("자동 저장 간격(AUTOSAVE_EVERY)", min_value=1, max_value=100, value=getattr(core, "AUTOSAVE_EVERY", 10), step=1)
        wait_sec = st.number_input("대기시간(초)", min_value=3, max_value=60, value=getattr(core, "WAIT_SEC", 12), step=1)
        pageload_timeout = st.number_input("페이지로드 타임아웃(초)", min_value=10, max_value=120, value=getattr(core, "PAGELOAD_TIMEOUT", 25), step=1)

        base_dir = st.text_input("BASE_DIR", value=getattr(core, "BASE_DIR", r"C:\singlefiless"))
        excel_path = st.text_input("엑셀 경로", value=getattr(core, "EXCEL_PATH", os.path.join(base_dir, "네이버_상품정보_수집_확장.xlsx")))

    urls: List[str] = [u.strip() for u in urls_text.splitlines() if u.strip()]
    log_box = st.empty()
    prog = st.progress(0, text="대기 중…")
    run = st.button("🚀 크롤링 시작", type="primary", use_container_width=True)

    if run:
        core.BASE_DIR = base_dir
        core.EXCEL_PATH = excel_path
        core.DOWNLOAD_IMAGES = bool(download_images)
        core.AUTOSAVE_EVERY = int(autosave_every)
        core.WAIT_SEC = int(wait_sec)
        core.PAGELOAD_TIMEOUT = int(pageload_timeout)

        from selenium.webdriver.chrome.options import Options
        def _make_driver_with_headless():
            d, w = core.make_driver()
            if headless:
                try:
                    d.quit()
                except: pass
                opts = Options()
                opts.add_argument("--disable-blink-features=AutomationControlled")
                opts.add_argument("--lang=ko-KR")
                opts.add_argument("start-maximized")
                opts.add_argument(f"user-agent={core.UA}")
                opts.add_argument("--headless=new")
                try:
                    d = core.webdriver.Chrome(options=opts)
                except:
                    from selenium.webdriver.chrome.service import Service
                    d = core.webdriver.Chrome(service=Service(core.CHROMEDRIVER_PATH), options=opts)
                d.set_page_load_timeout(core.PAGELOAD_TIMEOUT)
                d.execute_cdp_cmd(
                    "Page.addScriptToEvaluateOnNewDocument",
                    {"source": "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"}
                )
                w = core.WebDriverWait(d, core.WAIT_SEC)
            return d, w

        try:
            driver, wait = _make_driver_with_headless()
        except Exception as e:
            st.error(f"웹드라이버 생성 실패: {e}")
            st.stop()

        done = 0
        total = max(len(urls), 1)
        start_time = time.time()

        try:
            for u in urls:
                prog.progress(done / total, text=f"로딩 중… ({done}/{total})")
                log_box.write(f"### ▶ {u}")
                try:
                    core.collect_one_market(driver, wait, u)
                except Exception as e:
                    log_box.error(f"[에러] {u}\n{e}\n{traceback.format_exc()}")
                done += 1
                prog.progress(done / total, text=f"진행 {done}/{total}")
                time.sleep(random.uniform(0.3, 0.8))

            try:
                core.safe_save_workbook(core.wb, core.EXCEL_PATH)
            except Exception as e:
                log_box.warning(f"[저장 경고] 최종 저장 재시도 중: {e}")

            dur = time.time() - start_time
            st.success(f"완료. {done}/{total} URL 처리, 소요 {dur:0.1f}s")
            if os.path.exists(core.EXCEL_PATH):
                st.link_button("엑셀 열기", url=f"file:///{core.EXCEL_PATH}".replace("\\", "/"), use_container_width=True)
            st.caption(f"엑셀: {core.EXCEL_PATH}")
            img_root = getattr(core, "IMG_ROOT", os.path.join(core.BASE_DIR, "images"))
            st.caption(f"이미지 저장 루트: {img_root}")
        finally:
            try:
                driver.quit()
            except:
                pass

if __name__ == "__main__":
    st.set_page_config(page_title="ENVY — SmartStore Crawler", layout="wide")
    render_crawler_section()

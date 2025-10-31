# app_test_envy_crawler.py
import time, builtins
from typing import List
import streamlit as st
import crawler_core as core

st.set_page_config(page_title="ENVY — 크롤러 테스트", layout="wide")
st.title("ENVY — 스마트스토어 카테고리 크롤러 · 테스트")

# ── 옵션 입력
colA, colB = st.columns(2)
with colA:
    chromedriver = st.text_input("ChromeDriver 경로", value=getattr(core, "CHROMEDRIVER_PATH", r"C:/PATH/to/chromedriver.exe"))
    base_dir = st.text_input("BASE_DIR", value=getattr(core, "BASE_DIR", r"C:\singlefiless"))
with colB:
    excel_path = st.text_input("EXCEL_PATH", value=getattr(core, "EXCEL_PATH", r"C:\singlefiless\네이버_상품정보_수집_확장.xlsx"))
    wait_sec = st.number_input("WAIT_SEC", min_value=3, max_value=60, value=int(getattr(core, "WAIT_SEC", 12)))

urls_text = st.text_area(
    "카테고리 URL 목록 (줄바꿈으로 여러 개)",
    value="\n".join(getattr(core, "MARKETS", [])),
    height=120
)
urls: List[str] = [u.strip() for u in urls_text.splitlines() if u.strip()]

headless = st.toggle("헤드리스(창 숨김)", value=False, help="캡차가 나오면 헤드리스 OFF로 두고 직접 해결하세요.")
run = st.button("🚀 실행")

# ── 캡차 대기용 버튼/상태
if "captcha_wait" not in st.session_state:
    st.session_state["captcha_wait"] = False

def _streamlit_input(prompt: str = "") -> str:
    st.session_state["captcha_wait"] = True
    st.info(prompt + " — 아래 '✅ 캡차 해결, 계속 진행' 버튼을 누르세요.")
    while st.session_state.get("captcha_wait", False):
        time.sleep(0.3)
    return ""

def _driver_factory():
    # core.make_driver를 대체하여 headless 옵션 반영
    from selenium.webdriver.chrome.options import Options as _Options
    from selenium.webdriver.chrome.service import Service as _Service
    import selenium.webdriver as _wd
    opts = _Options()
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--lang=ko-KR")
    opts.add_argument("start-maximized")
    opts.add_argument(f"user-agent={core.UA}")
    if headless:
        opts.add_argument("--headless=new")
    d = _wd.Chrome(service=_Service(chromedriver), options=opts)
    d.set_page_load_timeout(core.PAGELOAD_TIMEOUT)
    d.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"}
    )
    from selenium.webdriver.support.ui import WebDriverWait as _Wait
    return d, _Wait(d, core.WAIT_SEC)

st.divider()
if st.session_state.get("captcha_wait"):
    c1, c2 = st.columns([1,3])
    with c1:
        if st.button("✅ 캡차 해결, 계속 진행"):
            st.session_state["captcha_wait"] = False
    with c2:
        st.info("브라우저에서 캡차를 해결한 뒤 '계속'을 눌러주세요. (헤드리스 OFF 권장)")

log = st.empty()
prog = st.progress(0.0, text="대기 중…")

if run:
    # 코어 파라미터 반영
    core.CHROMEDRIVER_PATH = chromedriver
    core.BASE_DIR = base_dir
    core.EXCEL_PATH = excel_path
    core.WAIT_SEC = int(wait_sec)

    # make_driver 교체, input 교체
    core.make_driver = _driver_factory
    builtins.input = _streamlit_input

    try:
        driver, wait = core.make_driver()
    except Exception as e:
        st.error(f"드라이버 생성 실패: {e}")
        st.stop()

    total = max(1, len(urls))
    done = 0
    try:
        for u in urls:
            prog.progress(done/total, text=f"로딩: {done}/{total}")
            log.write(f"### ▶ {u}")
            try:
                core.collect_one_market(driver, wait, u)
            except Exception as e:
                log.error(f"[에러] {e}")
            done += 1
            prog.progress(done/total, text=f"진행: {done}/{total}")
        try:
            core.safe_save_workbook(core.wb, core.EXCEL_PATH)
        except Exception as e:
            log.warning(f"엑셀 저장 재시도 필요: {e}")
        st.success("완료되었습니다.")
        st.code(f"엑셀: {core.EXCEL_PATH}\n이미지: {core.IMG_ROOT}", language="bash")
    finally:
        try:
            driver.quit()
        except:
            pass

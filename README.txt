ENVY — 카테고리 크롤러 테스트(MVP)
-------------------------------------
1) 필요한 패키지 설치
   pip install streamlit selenium requests openpyxl

2) 실행
   streamlit run app_test_envy_crawler.py

3) 사용법
   - ChromeDriver 경로/BASE_DIR/EXCEL_PATH 설정
   - 헤드리스 OFF 권장(캡차 해결 필요)
   - 카테고리 URL을 넣고 [실행] 클릭
   - 크롤링 중 캡차가 나오면 브라우저에서 해결 후
     화면의 [✅ 캡차 해결, 계속 진행] 버튼을 눌러 다음 단계로 넘어갑니다.

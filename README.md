# ENVY v9 (Streamlit)

변경 사항
- **CID 매핑 강화**: 검색/URL에서 자동 추출, 매핑 드롭다운, 최근 사용 cid 기록
- **DataLab 안정 패치**: Referer/Cookie 입력 지원, JSON 스니핑(스크립트 내 객체 파싱)

## 실행
```bash
python -m venv .venv && source .venv/bin/activate  # (Windows: .venv\Scripts\activate)
pip install -r requirements.txt
streamlit run app.py
```

## 팁
- 브라우저 네트워크 탭에서 복사한 **Cookie**를 사이드바 > 고급 설정에 붙여넣으면 성공률이 올라갑니다.
- 네이버 카테고리 URL/텍스트를 상단 입력칸에 붙여넣으면 `cid`를 자동 추출합니다.

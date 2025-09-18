# ENVY v9.8 — 안정 패치

## 변경점
- 11번가 프록시 워커가 앱 유도 스크립트/배너를 제거하여 iFrame 표시 안정화
- Rakuten 랭킹: 프록시 미사용(직접 호출)로 403 회피
- DataLab 섹션 제목을 markdown 헤딩으로 렌더 → 잘림 방지
- ItemScout/SellerLife 위젯에 고유 key 부여 → DuplicateWidgetID 해결
- 섹션명 정리: "AI 키워드 레이더 (Rakuten)"
- 상품명 생성기 유지

## 실행
```bash
python -m venv .venv && source .venv/bin/activate   # (Windows: .venv\Scripts\activate)
pip install -r requirements.txt
streamlit run app.py
```

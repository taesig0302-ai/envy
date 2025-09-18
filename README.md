# ENVY v10 — 안정화 완전체

## 포함
- `app.py` (DataLab 대분류 랭킹/트렌드 + REAL/FALLBACK 배지, 11번가 높이 슬라이더, 제목 잘림 해소)
- `worker.js` (모든 호스트 허용, 프레임 차단 헤더 제거, 11번가 앱유도 제거, 번역 iFrame 지원)
- `requirements.txt`
- `.gitignore`

## 실행
```bash
python -m venv .venv && source .venv/bin/activate   # (Windows: .venv\Scripts\activate)
pip install -r requirements.txt
streamlit run app.py
```

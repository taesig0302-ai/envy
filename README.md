# ENVY v9.4 — Full Pack
- Rank(대분류 12종) + Trend(기간 프리셋/단위/기기별, GET→POST→fallback)
- 11번가 프록시 임베드 (Cloudflare Worker 포함)
- Rakuten 키워드 레이더, 상품명 생성기 포함
- Sidebar 하단 마지막 버튼 숨김

## 실행
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py

## 11번가 프록시
1) Cloudflare → Workers → 새 Worker 생성 → 아래 worker.js 전체 복붙 → Deploy
2) 발급 주소를 app.py 상단 `PROXY_URL`에 입력
3) 테스트: https://YOUR-WORKER.workers.dev/iframe?target=https%3A%2F%2Fm.11st.co.kr%2Fbrowsing%2FbestSellers.mall


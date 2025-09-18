# ENVY v9.5 — Full Pack

## 포함 기능
- **DataLab Rank** (대분류 12종) + **Trend** (기간 프리셋/단위/기기별, GET→POST 폴백, 강한 폴백 시계열)
- Sidebar: 환율/마진 계산기, 테마 토글, Referer/Cookie 입력
- 11번가 프록시 임베드 (Cloudflare Worker 등) — `PROXY_URL` 설정 시 작동
- Rakuten 랭킹 뷰 + 상품명 생성기

## 설치/실행
```bash
python -m venv .venv && source .venv/bin/activate   # (Windows: .venv\Scripts\activate)
pip install -r requirements.txt
streamlit run app.py
```

## 팁
- DataLab은 Referer/Cookie를 붙이면 성공률이 높습니다. (사이드바 > 고급 설정)
- 11번가는 원사이트가 X-Frame-Options로 막으므로 **프록시 URL**을 넣어야 iframe 통과가 안정적입니다.

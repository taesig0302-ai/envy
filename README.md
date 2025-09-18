# ENVY v9.7 — Full Pack + Google Translate (iFrame)

## 포함
- DataLab Rank/Trend, Rakuten, 11번가(프록시), ItemScout/SellerLife 카드, 상품명 생성기
- **Google Translate 사이트 임베드** (iFrame) — 프록시 경유

## 실행
```bash
python -m venv .venv && source .venv/bin/activate   # (Windows: .venv\Scripts\activate)
pip install -r requirements.txt
streamlit run app.py
```

## 주의
- iFrame 차단 사이트는 Cloudflare Worker 프록시가 필요합니다. 이 패키지는 PROXY_URL이 이미 설정되어 있습니다.

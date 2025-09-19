
# ENVY v11.1 (UI = v10.5-style)

## 실행
```bash
pip install -r requirements.txt
streamlit run app.py
```

## 11번가 프록시
- Cloudflare Workers에 worker.js 배포 후 사이드바에 PROXY_URL 입력
- 사용 경로: https://<worker>/iframe?target=<ENCODED_URL>

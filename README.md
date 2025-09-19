
# ENVY v11.0 (Cloud Patched)

## Cloud/Local 공통 실행
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Cloud 필수
- runtime.txt → `3.11`
- .streamlit/config.toml → `showErrorDetails=true`
- 레포 루트에 `app.py`/`requirements.txt`/`runtime.txt`/`.streamlit/config.toml`

## 11번가 프록시
- worker.js 를 Cloudflare Workers에 배포 → 사이드바 `PROXY_URL` 입력
- iFrame 경로: `https://<worker>/iframe?target=<ENCODED_URL>`

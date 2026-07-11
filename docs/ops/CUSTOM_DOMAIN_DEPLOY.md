# 내 도메인으로 로드로그 배포 (공식 사이트)

Streamlit(`*.streamlit.app`)은 **관리·데모용**입니다.  
일반 사용자용 공식 사이트는 **`server.py` + `web/` (FastAPI SPA)** 를 별도 호스팅하고 **내 도메인**을 붙입니다.

---

## 전체 그림

```
사용자 브라우저
    │
    ▼
https://roadlog.내도메인.com   ← 내가 산 도메인 (DNS)
    │
    ▼
호스팅 (Railway / Render / VPS 등)
    │
    ▼
uvicorn server:app   ← FastAPI + web/ 정적 파일
```

| 구분 | 주소 예 | 용도 |
|------|---------|------|
| Streamlit (지금) | `xxx.streamlit.app` | 관리·내부 테스트 |
| **공식 사이트** | `roadlog.com` 또는 `app.roadlog.com` | 로그인·일지·PWA 메인 |

---

## 1. 도메인 준비

1. 도메인 구매 (가비아, 호스팅케이알, Cloudflare, Namecheap 등)
2. 사용할 주소 결정  
   - 루트: `https://roadlog.kr도메인.com`  
   - 또는 서브: `https://app.내도메인.com`

---

## 2. 호스팅 선택 (추천 순)

### A) Railway / Render (초보 추천)

- GitHub `corelabsstudio/RoadLog` 연결
- **Start command:**
  ```bash
  uvicorn server:app --host 0.0.0.0 --port $PORT
  ```
- **Root directory:** 저장소 루트 (app.py 아님)
- Python, `requirements.txt` 자동 인식

### B) VPS (더 자유로움)

- Ubuntu + nginx + HTTPS (Let's Encrypt)
- systemd 로 uvicorn 상시 실행
- 아래에 nginx 예시 참고

### C) 비추천 (메인 제품용)

- Streamlit Cloud만으로 공식 사이트 → PWA·퀵스탬프·SPA 기능 제한

---

## 3. 환경변수 (호스팅 Secrets / Variables)

운영에서는 반드시 설정:

```env
APP_ENV=production
APP_SECRET=긴-난수-32자이상
ADMIN_USERNAME=관리자_ID
ADMIN_PASSWORD=강한비밀번호
ADMIN_EMAIL=you@company.com
ALLOW_DEMO_BILLING_UPGRADE=false
ALLOWED_ORIGINS=https://roadlog.내도메인.com
OPENAI_API_KEY=sk-...
PRO_PAYMENT_URL=https://결제링크
ENTERPRISE_PAYMENT_URL=https://결제링크
CONTACT_EMAIL=corelabs.studio@gmail.com
```

`APP_SECRET` 생성:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

배포 전 점검:

```powershell
cd C:\Users\hysoo\projects\RoadLog
# 로컬에서 production 가정 테스트 시 .env 에 APP_ENV=production 후
python scripts\check_security.py
```

---

## 4. 실행 명령 (공통)

```bash
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port $PORT
```

- 헬스 체크: `GET /api/health` → `ok: true`
- 메인 페이지: `GET /` → SPA (`web/index.html`)

---

## 5. 도메인 연결 (DNS)

호스팅이 알려 주는 **CNAME 또는 A 레코드**를 도메인 DNS에 등록합니다.

### 예: Railway / Render 서브도메인

| 타입 | 이름 | 값 |
|------|------|-----|
| CNAME | `app` 또는 `@` (안내대로) | `xxx.up.railway.app` 등 |

### 예: VPS IP

| 타입 | 이름 | 값 |
|------|------|-----|
| A | `@` 또는 `app` | `서버공인IP` |

DNS 반영 5분~48시간. HTTPS는 호스팅 자동 발급 또는 certbot.

---

## 6. nginx 예시 (VPS)

```nginx
server {
    listen 80;
    server_name roadlog.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name roadlog.example.com;

    # ssl_certificate ... (certbot)

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

앱:

```bash
uvicorn server:app --host 127.0.0.1 --port 8000
```

---

## 7. 배포 후 확인 체크리스트

- [ ] `https://내도메인/api/health` → ok  
- [ ] 메인 화면·로그인·가입  
- [ ] 일지 생성·다운로드  
- [ ] 관리자 로그인  
- [ ] `/api/billing/upgrade` 는 결제 없이 막힘 (403)  
- [ ] HTTPS 자물쇠 표시  
- [ ] (선택) PWA 홈 화면 추가  

---

## 8. Streamlit 과의 관계

| | Streamlit | FastAPI 공식 사이트 |
|--|-----------|---------------------|
| URL | `*.streamlit.app` | **내 도메인** |
| 데이터 | 클라우드 별도 | 호스팅 디스크/DB 별도 |
| 계정 | 서로 **공유 안 됨** | 공식 서비스 계정 |

원하면 나중에 Supabase 등으로 **한 DB** 에 합칠 수 있습니다. 초기에는 공식 사이트만 키워도 됩니다.

---

## 9. 추천 진행 순서 (오늘부터)

1. 도메인 구매  
2. Railway 또는 Render에 GitHub 연결 + uvicorn 실행  
3. 환경변수 입력  
4. 호스팅이 준 URL로 먼저 동작 확인  
5. DNS로 내 도메인 연결 + HTTPS  
6. Streamlit은 관리용으로 유지하거나 나중에 정리  

---

## 관련 문서

- `docs/ops/DEPLOY_SECURITY_CHECKLIST.md` — 보안  
- `docs/ops/STREAMLIT_CLOUD.md` — Streamlit 전용  
- `server.py` — 메인 앱 엔트리  

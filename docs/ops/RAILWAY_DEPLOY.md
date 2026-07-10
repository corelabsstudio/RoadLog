# Railway로 로드로그 공식 사이트 배포

메인 앱: **`server.py`** (FastAPI + `web/` SPA)  
Streamlit 주소와 **별개**입니다.

---

## 0. 준비

- GitHub 저장소: `corelabsstudio/RoadLog` (`main` 최신)
- Railway 계정: https://railway.app (GitHub로 로그인 권장)
- 결제 수단: Railway는 사용량 과금 (무료 크레딧이 있을 수 있음)

로컬 저장소에 이미 포함:

- `Dockerfile` (권장 빌드 — Nixpacks pip 오류 회피)
- `railway.toml` (DOCKERFILE 빌더)
- `Procfile`

---

## 1. 새 프로젝트 만들기 (웹 UI)

1. https://railway.app/new 접속  
2. **Deploy from GitHub repo** 선택  
3. GitHub 권한 허용 후 **`corelabsstudio/RoadLog`** 선택  
4. 배포가 시작되면 잠시 대기 (빌드 로그 확인)

> Main file / Root: 저장소 **루트** (변경 없음)  
> Start Command가 비어 있으면 Variables 또는 Settings에서:  
> `uvicorn server:app --host 0.0.0.0 --port $PORT`

---

## 2. 환경 변수 (Variables)

프로젝트 → 서비스 → **Variables** → Raw Editor 또는 개별 추가:

```env
APP_ENV=production
APP_SECRET=여기_긴_난수_넣기
ADMIN_USERNAME=hhs126
ADMIN_PASSWORD=hh921544hh@1013
ADMIN_EMAIL=hhs126@roadlog.local
ALLOW_DEMO_BILLING_UPGRADE=false
ALLOWED_ORIGINS=*
OPENAI_API_KEY=
CONTACT_EMAIL=corelabs.studio@gmail.com
```

### APP_SECRET 만들기 (로컬 PowerShell)

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

나온 값을 `APP_SECRET`에 넣습니다.

### 중요

| 변수 | 설명 |
|------|------|
| `APP_ENV=production` | 약한 비밀키면 **기동 거부** (보안 가드) |
| `APP_SECRET` | **32자 이상 난수** 필수 |
| `ADMIN_PASSWORD` | 8자 이상, 약한 값 금지 |
| `ALLOWED_ORIGINS` | 처음엔 `*`, 도메인 붙인 뒤 `https://내도메인` 으로 변경 |
| `OPENAI_API_KEY` | 있으면 AI 생성, 없으면 규칙 초안 |

변수 저장 후 자동 **Redeploy** 됩니다.

---

## 3. 공개 URL 받기

1. 서비스 → **Settings** → **Networking**  
2. **Generate Domain** 클릭  
3. 예: `https://roadlog-production-xxxx.up.railway.app`

브라우저에서 확인:

- `https://(railway주소)/api/health` → `"ok": true`  
- `https://(railway주소)/` → 로드로그 웹 화면  

---

## 4. 내 도메인 연결 (도메인 산 뒤)

1. Railway → Settings → Networking → **Custom Domain**  
2. 도메인 입력 (예: `app.roadlog.com` 또는 `roadlog.com`)  
3. 안내하는 **CNAME / A 레코드**를 도메인 DNS에 등록  
4. HTTPS 발급 완료까지 대기  
5. Variables 의 `ALLOWED_ORIGINS` 를  
   `https://app.roadlog.com` (실제 주소) 로 수정  

---

## 5. 배포 후 체크

- [ ] `/api/health` ok  
- [ ] 회원가입 / 로그인  
- [ ] 관리자 `hhs126` 로그인  
- [ ] 일지 생성 · 다운로드  
- [ ] Streamlit 주소와 **회원 DB가 다름** (각자 저장소)  

---

## 6. 자주 나는 문제

| 증상 | 해결 |
|------|------|
| 빌드 후 바로 죽음 | Variables에 `APP_SECRET` 약한 값 / `APP_ENV=production` 가드 → 로그 확인 |
| 502 | Start command·PORT 확인, 로그에 uvicorn 기동 여부 |
| 화면 빈 페이지 | `web/` 가 GitHub에 있는지, `/` 응답 확인 |
| CORS | `ALLOWED_ORIGINS` 에 실제 프론트 도메인 |

로그 위치: Railway 서비스 → **Deployments** → 해당 배포 → **View Logs**

---

## 7. Streamlit 과의 역할

| | Streamlit | Railway (공식) |
|--|-----------|----------------|
| URL | `*.streamlit.app` | `*.up.railway.app` → **내 도메인** |
| 앱 | `app.py` | `server.py` + `web/` |
| 용도 | 관리·테스트 | **사용자용 메인 사이트** |

---

## 다음 단계 (도메인 구매 후)

1. 도메인 구매  
2. Railway Custom Domain 연결  
3. DNS 반영  
4. `ALLOWED_ORIGINS` 갱신  

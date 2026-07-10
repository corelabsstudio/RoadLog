# 로드로그 배포 보안 체크리스트

공개 서버·도메인에 올리기 **전에** 항목을 확인하세요.  
로컬 PC에서만 쓸 때는 `APP_ENV=development` 로 충분합니다.

---

## 1. 배포 직전 자동 점검

```powershell
cd C:\Users\hysoo\projects\RoadLog
.\.venv\Scripts\Activate.ps1
python scripts\check_security.py
```

- **exit 0** · `PASS` → 배포 가능 수준  
- **exit 1** · `FAIL` → 빨간 항목 수정 후 재실행  
- `APP_ENV=production` 이면 약한 비밀키가 있을 때 **서버 기동도 거부**합니다.

---

## 2. 필수 환경변수 (`.env` — Git에 올리지 말 것)

| 변수 | 필수 | 설명 |
|------|------|------|
| `APP_ENV` | 운영 권장 | `production` / `development` |
| `APP_SECRET` | **필수** | 세션용 긴 난수 (32자 이상 권장) |
| `ADMIN_USERNAME` | **필수** | 관리자 ID |
| `ADMIN_PASSWORD` | **필수** | 강한 비밀번호 (기본값·admin123 금지) |
| `ADMIN_EMAIL` | 권장 | 관리자 이메일 |
| `OPENAI_API_KEY` | 권장 | AI 생성 (없으면 규칙 초안) |
| `PRO_PAYMENT_URL` | 유료 시 | 실제 결제 링크 |
| `ENTERPRISE_PAYMENT_URL` | 유료 시 | 기업 결제 링크 |
| `ALLOW_DEMO_BILLING_UPGRADE` | 운영 **false** | `true`면 결제 없이 Pro 가능 (위험) |
| `ALLOWED_ORIGINS` | 운영 권장 | 허용 도메인, 예: `https://roadlog.example.com` |
| `CONTACT_EMAIL` / `CONTACT_FORM_URL` | 권장 | 문의 |
| `SUPABASE_URL` / `SUPABASE_KEY` | 선택 | 미설정 시 로컬 JSON |

### APP_SECRET 생성 예

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### 운영 `.env` 예시 골격

```env
APP_ENV=production
APP_SECRET=여기에_긴_난수
ADMIN_USERNAME=...
ADMIN_PASSWORD=...
ADMIN_EMAIL=you@company.com
ALLOW_DEMO_BILLING_UPGRADE=false
ALLOWED_ORIGINS=https://your-domain.com
OPENAI_API_KEY=sk-...
PRO_PAYMENT_URL=https://...
ENTERPRISE_PAYMENT_URL=https://...
```

---

## 3. 체크리스트 (수동)

### 비밀·계정
- [ ] `.env` 가 GitHub에 없음 (`git ls-files .env` → 비어 있어야 함)
- [ ] 코드/`config.py` 기본 비밀번호에 의존하지 않음
- [ ] 관리자 비밀번호가 로컬 데모 값·유출 가능한 문자열이 아님
- [ ] OpenAI 키를 채팅·스크린샷·커밋에 붙이지 않음
- [ ] 예전에 유출된 키가 있으면 OpenAI에서 **즉시 폐기·재발급**

### 결제·요금
- [ ] `ALLOW_DEMO_BILLING_UPGRADE=false` (또는 미설정)
- [ ] 요금제 버튼이 실제 결제 URL로 연결됨
- [ ] 결제 완료 후 plan 변경은 **관리자 수동** 또는 **웹훅**(추후)만 사용
- [ ] VIP/수동 결제는 관리자만 등록

### 네트워크·HTTPS
- [ ] HTTPS(리버스 프록시·호스팅 TLS) 사용
- [ ] `ALLOWED_ORIGINS` 에 실제 프론트 도메인만 지정 (`*` 지양)
- [ ] 관리자 경로·API를 불필요하게 공개 문서화하지 않음

### 데이터·백업
- [ ] `data/` (users, sessions, payments, styles) 백업 계획
- [ ] 서버 디스크 권한: 앱 실행 계정만 읽기/쓰기
- [ ] 로그에 비밀번호·토큰·API 키가 찍히지 않는지 확인

### 앱 동작 스모크 (배포 후)
- [ ] `GET /api/health` → ok
- [ ] 가입 → 로그인 → 일지 생성 → Excel/PDF/DOCX
- [ ] 비로그인 `/api/generate` → 401
- [ ] 일반 유저 `/api/admin/dashboard` → 403
- [ ] `/api/billing/upgrade` → 403 (데모 플래그 off 시)
- [ ] 관리자 로그인 후 대시보드 접근

### 인프라
- [ ] 프로세스 매니저 (systemd, Docker, Railway, Render 등) + 자동 재시작
- [ ] 의존성: `pip install -r requirements.txt` (프로덕션 venv)
- [ ] 실행: `uvicorn server:app --host 0.0.0.0 --port $PORT` (리버스 프록시 뒤)
- [ ] Streamlit(`app.py`)을 공개할 경우 별도 인증·방화벽 검토 (메인 제품은 SPA+FastAPI)

---

## 4. 올리면 안 되는 것

| 경로 | 이유 |
|------|------|
| `.env` | 키·비밀번호 |
| `data/users.json`, `sessions.json` | 계정·세션 |
| `data/payments.json` | 결제·플랜 기록 |
| `data/styles/`, `user_configs/` | 개인 서식 |
| `.venv/` | 환경 종속 |

`.gitignore` 에 이미 대부분 포함되어 있습니다. 배포 패키지/아티팩트에도 넣지 마세요.

---

## 5. 알려진 제품 보안 정책 (의도)

| 항목 | 정책 |
|------|------|
| 무료 plan 업그레이드 API | 기본 **차단** (`ALLOW_DEMO_BILLING_UPGRADE`) |
| Free 월 생성 한도 | 서버에서 강제 (우회 불가) |
| 관리자 API | `is_admin` 필요 |
| 세션 | Bearer 토큰 + 서버 세션 맵 (디스크 영속) |
| AI 실패 | 규칙 초안 + 사용자 안내 (키/쿼터 등) |

---

## 6. 사고 시 대응

1. **API 키 유출** → OpenAI에서 키 폐기 → `.env` 교체 → 서버 재시작  
2. **관리자 비밀번호 유출** → `.env` 변경 → `ensure_admin_owner` 재기동으로 해시 갱신 → 기존 세션 파일 삭제 검토 (`data/sessions.json`)  
3. **무단 Pro 전환** → `ALLOW_DEMO_BILLING_UPGRADE` 확인 → `data/users.json` / payments 점검 → plan 수동 복구  

---

## 7. 관련 파일

- `modules/config.py` — 환경변수·프로덕션 가드  
- `server.py` — CORS, 기동 시 보안 검사  
- `scripts/check_security.py` — 배포 전 스캔  
- `.env.example` — 변수 목록 (비밀값 없음)  
- `docs/ops/CONTACT_FORM_SETUP.md` — 문의 폼  

체크리스트를 모두 통과한 뒤에만 도메인을 공개하세요.

# 로드로그 정식 런칭 체크리스트

배포 코드 패치(v15)와 함께 **호스팅 환경변수**를 맞춰야 라이브 품질이 확보됩니다.

## 0. 비용 0 운영 (현재 기본)

```env
COST_MODE=free
```

| 쓰는 것 | 안 쓰는 것 (비용) |
|---------|-------------------|
| 규칙/스마트 초안 생성 | OpenAI / xAI API |
| Railway 기본 디스크 | 유료 Volume (선택) |
| 문의 기반 Pro 등록 | 결제 PG |
| local_json 저장 | 유료 Supabase (선택) |

나중에 AI를 켜려면 `COST_MODE=paid` + `OPENAI_API_KEY`(또는 `XAI_API_KEY`) 만 넣으면 됩니다.

## 0b. 로컬에서 비밀값·변수 파일 생성

```powershell
cd C:\Users\hysoo\Projects\RoadLog
.\.venv\Scripts\python.exe scripts\bootstrap_launch.py --rotate-admin
```

- `.launch/railway-variables.env` → Railway Variables Raw Editor 붙여넣기  
- `.launch/SECRETS_README.txt` → 관리자 비밀번호 (gitignore)

## 1. Railway Variables (필수)

| 변수 | 권장 값 | 비고 |
|------|---------|------|
| `APP_ENV` | `production` | 보안 가드·HSTS |
| `APP_SECRET` | 48자+ 난수 | 아래 명령으로 생성 |
| `ADMIN_USERNAME` | 추측 어려운 ID | 소스에 두지 않음 |
| `ADMIN_PASSWORD` | 12자+ 강한 값 | **기존 유출 비번 즉시 교체** |
| `ADMIN_EMAIL` | 실제 관리 메일 | |
| `OPENAI_API_KEY` | 유효 키 | health `openai:true` |
| `ALLOW_DEMO_BILLING_UPGRADE` | `false` | |
| `ALLOWED_ORIGINS` | `https://roadlog.co.kr` | `*` 금지 |
| `CONTACT_EMAIL` | 공개 문의 메일 | |
| `SUPABASE_URL` / `SUPABASE_KEY` | 운영 DB | 없으면 재배포 시 데이터 유실 위험 |
| `PRO_PAYMENT_URL` | 결제 URL 또는 비움 | 비우면 문의 플로우 |
| `BUSINESS_NAME` | 상호 | 푸터 |
| `BUSINESS_OWNER` | 대표자 | 선택 |
| `BUSINESS_REG_NO` | 사업자번호 | 선택·권장 |
| `MAIL_ORDER_REG_NO` | 통신판매 신고번호 | 준비되면 기입 |

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## 1b. Railway Volume (데이터 영속 — 필수)

1. Railway 서비스 → **Settings** → **Volumes** → Add Volume  
2. Mount Path: **`/data`**  
3. Variables 에 `DATA_DIR=/data` (Dockerfile 기본값과 동일)

재배포 후에도 회원·일지·세션이 유지됩니다. Supabase를 쓰면 더욱 안전합니다.

## 2. 배포 후 스모크

```text
GET  /api/health  → production=true, openai=true, storage_persistent=true, launch_ready=true
GET  /api/meta    → payment_ready / business 필드
가입 → 로그인 → 일지 생성 → PDF/Excel
제출 파일 memo에 "규칙 기반" 문구 없음
비로그인 generate → 401
관리자 대시보드 → 관리자만
/api/billing/upgrade → 403 (데모 off)
```

## 3. 보안 (한 번 더)

- [ ] GitHub에 `.env` 없음
- [ ] 문서·커밋에 실비밀번호 없음 (히스토리에 있으면 **비번 교체**)
- [ ] OpenAI 키 한도·결제 확인
- [ ] `python scripts/check_security.py` (로컬은 warn 허용, 운영 변수는 별도)

## 4. 홍보 카피 정합

- Free 월 15회 · Pro 월 2,900원 **초기 런칭가**
- 자동 결제 전이면 **「문의 후 등록」** 표현 유지
- 후기 섹션: **베타 피드백** 톤 유지

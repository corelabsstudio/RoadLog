# RoadLog (로드로그)

회사 제출용 운행·외근 일지를 작성·검증·내보내는 웹 서비스.

- 라이브: https://roadlog.co.kr
- 운영: 코어랩스(CoreLabs) · corelabs.studio@gmail.com

## 스택

| 구성 | 내용 |
|------|------|
| 백엔드 | FastAPI (`server.py`) · 도메인 로직은 `modules/` 재사용 |
| 프론트 | `web/` 정적 SPA (PWA) |
| 저장소 | 로컬 JSON (`DATA_DIR`) · Supabase 연결 시 DB |
| 문서 생성 | Excel · PDF · Word 내보내기 |
| 초안 생성 | OpenAI (키 없거나 한도 초과 시 규칙 기반 초안으로 폴백) |
| 배포 | Dockerfile → Railway |

`app.py` 와 `pages/` 는 초기 Streamlit 버전입니다. 현재 서비스되는 것은 FastAPI + `web/` SPA 쪽입니다.

## 로컬 실행

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
.\.venv\Scripts\python.exe -m uvicorn server:app --host 127.0.0.1 --port 8501
```

| URL | 용도 |
|-----|------|
| http://127.0.0.1:8501/ | 앱 |
| http://127.0.0.1:8501/docs | API 문서 (OpenAPI) |
| http://127.0.0.1:8501/api/health | 헬스체크 (데이터 경로·저장소 상태 포함) |

## 환경 변수

`.env.example` 을 `.env` 로 복사한 뒤 채웁니다. 전체 목록과 설명은 그 파일에 있습니다. 주요 항목:

| 변수 | 설명 |
|------|------|
| `APP_ENV` | `development` / `production` |
| `APP_SECRET` | 세션 시크릿 (운영에서는 반드시 긴 난수) |
| `COST_MODE` | `hybrid` 기본 · `free` 는 LLM 호출 차단 · `paid` 는 경고 강화 |
| `OPENAI_API_KEY` | 없으면 규칙 기반 초안으로 동작 |
| `SUPABASE_URL` · `SUPABASE_KEY` | 선택 — 미설정 시 로컬 JSON |
| `DATA_DIR` | 데이터 저장 경로 (배포 시 영구 볼륨 권장) |
| `ALLOWED_ORIGINS` | CORS 허용 출처 (운영은 실제 도메인만) |
| `ADMIN_USERNAME` · `ADMIN_PASSWORD` | 관리자 계정 |

`.env` 와 토큰류는 커밋하지 않습니다 (`.gitignore` 처리됨).

## 데이터 저장

사용자·일지·설정은 `DATA_DIR` 아래 JSON 으로 저장됩니다 (미설정 시 `./data`).

컨테이너 배포에서는 `DATA_DIR` 을 **영구 볼륨 경로로 지정해야** 재배포 시 데이터가 유실되지 않습니다. Supabase 를 연결한 경우에는 DB 가 정본입니다. `/api/health` 응답의 `storage_persistent` 로 현재 상태를 확인할 수 있습니다.

## 구조

```
server.py          FastAPI 앱 · 라우트
modules/           도메인 로직 (auth · db · generator · validator · export · admin …)
web/               SPA 프론트엔드 · 정적 자산 · 기본 템플릿
scripts/           빌드 번호 · QA · 스모크 · 점검 스크립트
docs/              운영 · 배포 · 마케팅 문서
app.py, pages/     초기 Streamlit 버전
```

## 점검

정적 검사 — 서버 없이 실행합니다.

```powershell
.\.venv\Scripts\python.exe scripts\qa_check.py
.\.venv\Scripts\python.exe scripts\check_security.py
```

HTTP 스모크 — 서버가 떠 있어야 하고, 대상 주소를 인자로 넘깁니다 (생략 시 `http://127.0.0.1:8765`).

```powershell
.\.venv\Scripts\python.exe scripts\smoke_http.py http://127.0.0.1:8501
```

프론트(`web/`) 를 수정했다면 `scripts/bump_build.py` 로 빌드 번호를 올려 서비스 워커·`index.html` 정합을 맞춥니다.

## 배포

`main` 에 push 하면 Railway 가 `Dockerfile` 로 빌드해 자동 배포합니다. 배포 후 `https://roadlog.co.kr/api/health` 로 확인합니다.

배포 절차와 체크리스트는 [`docs/ops/RAILWAY_DEPLOY.md`](docs/ops/RAILWAY_DEPLOY.md) · [`docs/ops/DEPLOY_SECURITY_CHECKLIST.md`](docs/ops/DEPLOY_SECURITY_CHECKLIST.md) 를 따릅니다.

## 문서

| 문서 | 내용 |
|------|------|
| [`AGENTS.md`](AGENTS.md) | 에이전트 작업 지침 · 트리거 |
| [`docs/SAVE_POINT.md`](docs/SAVE_POINT.md) | 제품·배포 현재 상태 |
| [`docs/ops/`](docs/ops) | 배포 · 도메인 · 런칭 체크리스트 |
| [`docs/marketing/`](docs/marketing) | 마케팅 · SEO 파이프라인 |

## 라이선스

코어랩스 사내 프로젝트입니다. © 2026 CoreLabs.

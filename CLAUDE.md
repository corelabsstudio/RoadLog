# RoadLog — Claude Code 안내

이 파일을 읽은 뒤 **현재 디스크·git·라이브**를 재검증하고 작업한다.  
상세 트리거·마케팅 파이프는 **`AGENTS.md`가 정본**이다. 이 파일은 빠른 부트스트랩용.

## 필수 문서 (순서)

1. `AGENTS.md` — 불러오기 트리거·마케팅·ReachKit·배포 습관  
2. `docs/SAVE_POINT.md` (있으면) — 제품·배포 상태  
3. 공통 이관: `../docs/CLAUDE_TO_GROK_HANDOFF.md`  
4. SEO/마케팅 시: `docs/marketing/AGENT_TEAM.md` · `docs/marketing/news_digest/DAILY_SEO_PROMPT.md`  
5. 일일 SEO 스케줄 메모: `../docs/marketing/GROK_SEO_SCHEDULER.md`

## 제품

| 항목 | 값 |
|------|-----|
| 한 줄 | AI 운행·외근 **제출용 일지** (마일리지 정산 앱 아님) |
| 경로 | `C:\Users\hysoo\Projects\RoadLog` |
| 라이브 | https://roadlog.co.kr |
| 원격 | `github.com/corelabsstudio/RoadLog` · 브랜치 `main` |
| 배포 | push → Railway **RoadLog - web** 자동 |
| 로컬 | `.\.venv\Scripts\python.exe -m uvicorn server:app --host 127.0.0.1 --port 8501` |
| 결제 | 스마트스토어 링크 + 주문번호 claim + 관리자 수동 플랜 (데모 업그레이드 프로덕션 금지) |
| 운영 | 코어랩스 · corelabs.studio@gmail.com · 사업자 705-04-02867 |

## 최근 배포 (2026-07-31 · `6694e85`)

- `web/index.html` **`#demo` 앵커** 복구 (app.js 스크롤 타겟)  
- `ExportBody.format` 기본값 (`validate` 재사용)  
- `AGENTS.md` X 일일 팩 트리거 문서화  

## 아키텍처

- `server.py` — FastAPI 앱, 실제 프로덕션 진입점.
- `modules/` — 도메인 로직: `auth`, `db`, `generator`, `validator`, `export`, `admin`, `enterprise`, `notify`, `rate_limit`, `reviews`, `style_learn`, `styles`, `user_config`, `config_manager`.
- `web/` — SPA/PWA 프런트엔드 (실제 서비스 UI).
- `scripts/` — 운영/QA/마케팅 스크립트.
- `docs/` — SAVE_POINT, 마케팅 문서 등.
- ⚠️ **`app.py` / `pages/` 는 레거시 Streamlit 잔재이며 프로덕션에서 쓰이지 않는다.** 신규 작업은 `server.py` + `web/` 쪽에서 할 것 — 실수로 죽은 Streamlit 코드를 고치지 말 것.

## QA / 테스트

```bash
python scripts/qa_check.py          # 정적 QA 체크
python scripts/check_security.py    # 보안 정적 체크 (서버 불필요)
python scripts/smoke_http.py <url>  # HTTP 스모크 테스트
python scripts/_roadlog_suite_test.py         # 로컬 mock 기반 전체 E2E 스위트 (가장 가까운 "테스트" 명령)
python scripts/_roadlog_suite_test.py --live  # 라이브 대상 read-only 프로브
```

단일 테스트만 골라 실행하는 옵션은 없다 (스위트 단위 실행만 가능).

## 환경 설정

`.env.example` → `.env` 복사 후 채울 것. 주요 변수: `APP_SECRET`, `COST_MODE`, `OPENAI_API_KEY`, `SUPABASE_URL`/`SUPABASE_KEY`, `DATA_DIR`, `ADMIN_USERNAME`/`ADMIN_PASSWORD`.

- **`DATA_DIR`는 반드시 영속 볼륨을 가리켜야 한다** — 아니면 재배포 시 데이터가 유실된다.
- 로컬 확인용 엔드포인트: `/api/health`, `/docs` (OpenAPI).

## 작업 방식 (사용자 강제)

1. **말한 것만**  
2. **애매하면 되묻기**  
3. 「완료」 전 핵심 되짚기  
4. 절세 보장·세무사 검증 확정 표현 금지  
5. **WakeAgain·ReachKit과 카피/브랜드 섞지 말 것** (마케팅 파이프)  
6. Review PASS 전 `git push`/배포 금지 (마케팅 하네스)

## 금지

- 사용자 UI에 OpenAI/내부 운영 배너·노트 노출  
- 비관리자 클릭 시 토스트 양산  
- 시크릿·`.env`·ntfy 토픽·Railway 토큰 커밋  
- 삭제된 CoreLabsPromo 복원  
- 외부 SNS **대리 로그인·무인 게시**를 되는 것처럼 포장 (키 없으면 중단·안내)

## 트리거 말 (요약 — 상세는 AGENTS.md)

| 말 | 동작 |
|----|------|
| 로드로그 이어서 / RoadLog 이어서 | SAVE_POINT + 라이브 이어서 |
| 로드로그 SEO / 일일 마케팅 | Research→Writer→Review→Publisher |
| X 마케팅 / 일일 X 팩 | ⚠️ **미구현** — `scripts/x_auto_daily.py` 등 관련 파일 없음, 상세는 `AGENTS.md` 참고 |
| 홍보 이어서 / ReachKit | `tools/community_poster/SAVE_POINT.md` |

## 배포 습관

- 프론트 변경 시 `scripts/bump_build.py` 로 빌드 번호 정합 (관례)  
- `main` push 후 `https://roadlog.co.kr/api/health` 확인  
- Railway 배포는 push 시 자동 트리거되며, CLI로 수동 트리거해야 할 경우 `.launch/railway.token` + GraphQL `serviceInstanceDeployV2` 사용 (`AGENTS.md` 참고)  
- Railway CLI 미로그인 시 GitHub 연동 배포 상태(`gh` commit status)로 확인 가능  

## 언어

사용자와 **한국어**로 소통한다.

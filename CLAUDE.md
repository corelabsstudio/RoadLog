# RoadLog — Claude Code 안내

이 파일을 읽은 뒤 **현재 디스크·git·라이브**를 재검증하고 작업한다.  
상세 트리거·마케팅 파이프는 **`AGENTS.md`가 정본**이다. 이 파일은 빠른 부트스트랩용.

**마지막 문서 갱신:** 2026-08-10 (방문자 실측·공모 제출·히어로 패럴랙스 반영)

## 필수 문서 (순서)

1. `AGENTS.md` — 불러오기 트리거·마케팅·ReachKit·배포 습관  
2. `docs/SAVE_POINT.md` (있으면) — 제품·배포 상태  
3. 공통 이관: `../docs/CLAUDE_TO_GROK_HANDOFF.md`  
4. SEO/마케팅 시: `docs/marketing/AGENT_TEAM.md` · `docs/marketing/news_digest/DAILY_SEO_PROMPT.md`  
5. 일일 SEO 스케줄 메모: `../docs/marketing/GROK_SEO_SCHEDULER.md`  
6. 공모 제출 기록: `../docs` 외 · Grok `workspace/ai-contest-2026-case-submissions.md` · Desktop `공모전_*.png`

## 제품

| 항목 | 값 |
|------|-----|
| 한 줄 | AI 운행·외근 **제출용 일지** (마일리지 정산 앱 아님) |
| 경로 | `C:\Users\hysoo\projects\RoadLog` |
| 라이브 | https://roadlog.co.kr |
| 원격 | `github.com/corelabsstudio/RoadLog` · 브랜치 `main` |
| 배포 | push → Railway **RoadLog - web** 자동 |
| 로컬 | `.\.venv\Scripts\python.exe -m uvicorn server:app --host 127.0.0.1 --port 8501` |
| 결제 | 스마트스토어 링크 + 주문번호 claim + 관리자 수동 플랜 (데모 업그레이드 프로덕션 금지) |
| 운영 | 코어랩스 · corelabs.studio@gmail.com · 사업자 705-04-02867 |

## 최근 배포·변경 (2026-07-31 ~ 2026-08)

### 코드 (git `main`)

| 시점 | 커밋/내용 |
|------|-----------|
| 2026-07-31 `6694e85` | `web/index.html` **`#demo` 앵커** 복구 · `ExportBody.format` 기본값 · `AGENTS.md` X 일일 팩 문서화 |
| 이후 | 사업자 푸터·연락처 TEL/HP · 블로그 SEO 가이드 · 일일 news SEO digest |
| `eb96278` | 랜딩 히어로 **마우스 팔로우 패럴랙스** |
| `05b1636` | 포토 히어로 중앙 컨테이너 폭 복구 |
| `b46f358` | OS 재설치 전 uncommitted 백업 커밋 |

### 방문자·실사용 실측 (2026-08-08 · 운영 메모)

- **방문자 카운터:** 쿠키 `rl_vid`(~400일), 고유 브라우저. localhost / `?nocount=1` / 자동화 제외. 공개 API는 **`total`만**. `GET /api/stats/visitors?hit=0`. Railway 볼륨 `site_visitors.json`
- **관리자:** `/api/admin/usage` (계정별 생성 수), `/api/admin/dashboard` (매출/클레임)
- **실측 total visitors ≈ 43** (누적 고유, DAU 아님). 과거 ~78 수치와 단절 가능 — **현재 프로덕션 total이 정본**, 트렌드 연결 금지
- **실제 사용 계정 2개만:** `hhs126@roadlog.local`(admin), `corelabs.studio@gmail.com`(VIP/Pro). 외부 무료 가입 **0**
- **생성:** 7월 6건(admin+corelabs), 8월 1건(corelabs). 8월 매출 **0**
- **해석:** 방문자 증가 ≠ 실사용. 랜딩 구경 ≠ 가입/일지 생성
- **점검 패턴:** 트래픽=footer/API `total` / 실사용=admin `usage`+회원 목록

### AI 활용 사례 공모 (2026-08-09 · 사용자 제출 확인)

- **대회:** 전국민 AI 경진대회 · AI 활용 사례 공모전  
- **분야:** **업무 생산성**  
- **스토리 축:** 원칙=운행일지 그때그때 작성 · 병목=도착·작업 중 **깜빡임** → **원클릭 위치 스탬프** → 짧은 메모 → AI 초안 → 사람 검증  
- **금지 톤:** 구독/가격 광고 · “퇴근 전 몰아쓰기” 프레임(원칙과 충돌)
- **캡처:** Desktop `공모전_00~03*.png` (홈 위치스탬프 · 퀵 스탬프 · 메모+AI)
- **상세:** Grok memory `workspace/ai-contest-2026-case-submissions.md` · Desktop `공모전_제출기록_2026-08-09.md`

## 아키텍처

- `server.py` — FastAPI 앱, 실제 프로덕션 진입점.
- `modules/` — 도메인 로직: `auth`, `db`, `generator`, `validator`, `export`, `admin`, `enterprise`, `notify`, `rate_limit`, `reviews`, `style_learn`, `styles`, `user_config`, `config_manager`.
- `web/` — SPA/PWA 프런트엔드 (실제 서비스 UI).
- `scripts/` — 운영/QA/마케팅 스크립트.
- `docs/` — SAVE_POINT, 마케팅 문서 등.
- ⚠️ **`app.py` / `pages/` 는 레거시 Streamlit 잔재이며 프로덕션에서 쓰이지 않는다.** 신규 작업은 `server.py` + `web/` 쪽에서 할 것.

## QA / 테스트

```bash
python scripts/qa_check.py
python scripts/check_security.py
python scripts/smoke_http.py <url>
python scripts/_roadlog_suite_test.py
python scripts/_roadlog_suite_test.py --live
```

## 환경 설정

`.env.example` → `.env`. 주요: `APP_SECRET`, `COST_MODE`, `OPENAI_API_KEY`, `SUPABASE_URL`/`SUPABASE_KEY`, `DATA_DIR`, `ADMIN_USERNAME`/`ADMIN_PASSWORD`.

- **`DATA_DIR`는 반드시 영속 볼륨** — 재배포 시 유실 방지.
- 로컬: `/api/health`, `/docs`

## 작업 방식 (사용자 강제)

1. **말한 것만**  
2. **애매하면 되묻기**  
3. 「완료」 전 핵심 되짚기  
4. 절세 보장·세무사 검증 확정 표현 금지  
5. **WakeAgain·ReachKit과 카피/브랜드 섞지 말 것**  
6. Review PASS 전 `git push`/배포 금지 (마케팅 하네스)

## 금지

- 사용자 UI에 OpenAI/내부 운영 배너·노트 노출  
- 비관리자 클릭 시 토스트 양산  
- 시크릿·`.env`·ntfy 토픽·Railway 토큰 커밋  
- 삭제된 CoreLabsPromo 복원  
- 외부 SNS **대리 로그인·무인 게시**를 되는 것처럼 포장  

## 트리거 말 (요약 — 상세는 AGENTS.md)

| 말 | 동작 |
|----|------|
| 로드로그 이어서 / RoadLog 이어서 | SAVE_POINT + 라이브 이어서 |
| 로드로그 SEO / 일일 마케팅 | Research→Writer→Review→Publisher |
| X 마케팅 / 일일 X 팩 | ⚠️ **미구현** — `AGENTS.md` 참고 |
| 홍보 이어서 / ReachKit | `tools/community_poster/SAVE_POINT.md` |

## 배포 습관

- 프론트 변경 시 `scripts/bump_build.py` 로 빌드 번호 정합  
- `main` push 후 `https://roadlog.co.kr/api/health` 확인  
- Railway: push 자동 · 수동 시 `.launch/railway.token` + GraphQL `serviceInstanceDeployV2` (`AGENTS.md`)  
- 셸 빌드 토큰 관례 `YYYYMMDD-*` + deployV2  

## 디자인 토큰 (CSS 짤 때)

- 배경/종이: `--paper` · `--paper-2` · `--card`
- 글자: `--ink` · `--ink-soft` · `--muted`
- 강조(스탬프 레드): `--stamp` · `--stamp-2` · `--stamp-soft`
- 버튼 잉크: `--navy` · 포인트: `--mark`
- 레거시: `--cyan`→stamp, `--bg`→paper, `--text`→ink  
- 정본: `web/styles.css` `:root`

## 언어

사용자와 **한국어**로 소통한다.

## AI 마케팅 팀 관리자 통합 (2026-09-23 Codex)

- 2026-09-23 실제 유료 Gemini 첫 수동 호출: 온해님이 1건 호출을 승인했고 운영 `/admin/`에서 무료 상품 `today`·블로그 초안을 생성했다. 오늘 사용량은 0→1회, 내부 예산 예약은 0→600원이며 콘텐츠 #22가 `REVISION_REQUESTED`로 저장됐다. 실제 API 응답은 받았으나 `factual_claims`가 정본 결과 항목과 정확히 일치하지 않아 검수 BLOCKED, 승인 대기 등록 0건, 외부 게시 0건이다. 키 설정만으로 연결 성공이라고 표시하지 않는 규칙은 유지한다. 재호출 없이 `modules/marketing_gemini.py`의 응답 스키마에서 `factual_claims`를 해당 상품 `confirmed_results` 값으로만 제한하고 정확히 복사하도록 지시했다. 운영 연결 표시는 `실제 AI 응답 확인 · 검수 통과 대기`로 분리한다(`marketing_core/{repository,service}.py`). `scripts/_marketing_os_test.py`에 스키마·상태 표시 회귀를 추가했다. 수정 후 실제 유료 재호출은 아직 하지 않았으므로 운영에서 검수 통과 여부는 미검증이다. 자동 AI 생성은 계속 꺼져 있다.
- 2026-09-23 DEMO 잔존 경로 제거: 온해님은 "데모가 아니라 실 사용가능"을 지시했는데 직전 변경은 수동 1건만 REAL로 만들고 `팀 시작`·11시·채널 묶음은 DEMO로 남겼다. 이는 요청을 축소한 오류였다. 수정 후 `RoadLogDemoProvider`와 DEMO 묶음 저장 경로를 제거하고, DEMO 요청은 거부한다. 팀 시작은 실제 상품 정본 점검만 수행하며 가짜 초안·활동을 만들지 않는다. 수동 REAL 초안이 정본 검수를 통과한 뒤 관리자가 `실제 AI 자동 생성 켜기`를 명시적으로 선택하면, 실행 중인 팀이 매일 11시 실제 Gemini 초안 1건을 생성·검수한다. 채널별 묶음 버튼도 REAL 3회 호출·검수로 바꿨고, 하루 총 5회·내부 예산 예약 3,000원 제한을 공유한다. 키 없음/데이터 미연결 역할은 대기로 남고, 외부 게시·광고·SNS/검색/성과 연동은 여전히 없다. 기존 DEMO 기록은 삭제하지 않고 과거 기록으로 남긴다. 실제 유료 API 호출은 이번 개발 중 실행하지 않았으며 성공 여부는 첫 관리자의 수동 호출 전까지 미검증이다. 내부 예약액은 실제 청구 상한이 아니다. 구현: `modules/marketing_os.py`, `modules/marketing_gemini.py`, `modules/marketing_roadlog.py`, `modules/marketing_core/{service,repository,operations,policy}.py`, `server.py`, `web/admin/index.html`. 모의 공급자 회귀 테스트 `scripts/_marketing_os_test.py`.
- 후속 정리: 과거 DEMO 콘텐츠는 활동·묶음 이력에만 보존하고 현재 승인 대기 조회/승인 API에서 제외했다. 기존 DEMO로 `DONE`이던 담당자 현재 상태는 실제 초안 대기로 이관한다. 이력 삭제는 하지 않는다.

- 2026-09-23 수동 REAL AI 초안 1건 경로: `modules/marketing_gemini.py`가 기존 `GEMINI_API_KEY`/`SAJU_MODEL`을 서버에서 읽어 Gemini 구조화 JSON 초안을 생성한다. 상품 ID·이름·가격·무료 여부·등불/결제 전용·확인된 결과 항목·동기화 시각·출처만 전달한다. 전체 프롬프트나 키는 DB/활동 로그에 저장하지 않는다. `marketing_core/service.py`는 수동 REAL 호출만 허용하고 정본 검수 후 통과본만 승인 대기에 넣는다. `marketing_core/repository.py`는 동시 요청을 `BEGIN IMMEDIATE`로 예산 예약하며 1건당 600원 내부 예약·하루 최대 5건(콘텐츠 작가)을 적용하고 공급자 토큰 사용량을 기록한다. 600원은 **실제 요금 추정이나 청구 상한이 아니다**. 관리자는 버튼을 누른 뒤 과금 안내를 확인해야 실제 호출된다. 키 존재는 연결 성공 검증이 아니므로 화면에 `키 설정됨 · 실제 호출 미검증`으로 표시한다. 자동 시간표는 여전히 결정론적 DEMO이며 자동 REAL 호출·외부 게시·광고는 없다. 실제 키 호출은 이번 구현·검증 중 수행하지 않았다. 검색/성과 API 및 전체 팀 자동화는 미구현이다. 모의 응답·잘못된 JSON·timeout 재시도·거짓 가격·예산 차단 테스트를 `scripts/_marketing_os_test.py`에 추가했다.

- 2026-09-23 팀 시작 즉시 내부 작업 보강: `RUNNING`만 바꾸고 11시까지 8명 전원이 `IDLE`이던 문제를 고쳤다. `kickoff`를 서울 시간 00:00 이후 하루 한 번 예약·중복 방지하고, `팀 시작` API가 곧바로 이를 실행한다. 상품 정본의 확인된 결과로 DEMO 묶음 4건을 생성·검수하고 8개 역할에 실제 내부 결과 또는 `WAITING_DATA`/`WAITING_APPROVAL` 이유를 기록한다. 시장·검색·성과 API 없이 조사를 했다고 표시하지 않으며 REAL AI·게시·광고는 여전히 차단한다. 11시 추가 DEMO와 18시 보고서는 유지한다. 테스트 `scripts/_marketing_os_test.py`에 즉시 생성·8개 역할·재시작 중복·다중 작업자·실패를 포함했다. 구현: `modules/marketing_core/operations.py`, `modules/marketing_os.py`, `web/admin/index.html`(정본 `roadlog-saju/public/admin/index.html`).
- 2026-09-23 내부 예약 자동화: `팀 시작` 상태에서 서울 시간 11:00 상품 정본의 확인된 항목으로 원본·블로그·짧은 영상·카드뉴스 DEMO 묶음을 하루 1회 생성·검수하고, 18:00에는 일일 보고서를 저장한다. 늦게 시작하면 지난 시각의 작업을 그날 한 번만 따라잡는다. SQLite `(tenant_id, run_date, job_key)` 유일 키와 트랜잭션으로 여러 서버 작업자의 중복 실행을 막는다. 정본 오류는 FAILED와 관리자 활동 ERROR로 남기고 자동 재시도하지 않는다. 일시정지·긴급정지 시 다음 작업은 실행되지 않는다. 시장 조사·SEO·재검수는 API 미연결이므로 자동 실행 대상이 아니며 화면에 구분한다. REAL AI·외부 게시·광고·고객 메시지는 여전히 차단된다. 서버 lifespan에서 60초마다 예약 상태를 점검한다. 구현: `modules/marketing_core/operations.py`, `modules/marketing_os.py`, `server.py`, `web/admin/index.html`, `scripts/_marketing_os_test.py`.
- 2026-09-23 영상(`https://youtu.be/NYxE3eJHCSE`) 벤치마킹 후 원본 대본 입력 흐름 추가: 관리자 화면에서 상품·고객 질문·선택적 원본 대본(최대 5,000자)을 받는다. 질문/원본과 상품 정본의 결과 항목이 일치하면 그 항목으로 원본·블로그·짧은 영상 대본·카드뉴스 문안을 구성한다. 원본 대본이 있는데 일치하는 항목이 없으면 생성 차단한다. 원본 문장 자체는 미검증으로 표시하고, 가격·할인·보장 표현을 초안에 복사하지 않는다. 묶음에 입력 원본과 선택된 정본 항목을 tenant별로 보관한다. 이전 묶음은 빈 원본/항목으로 자동 이관한다. 이 단계는 결정론적 DEMO 변환이며 영상의 실제 AI 전사·이미지 제작·자동 게시·성과 최적화를 구현했다는 뜻이 아니다.
- 2026-09-23 영상 벤치마킹 1차 로컬 구현: 관리자 AI 마케팅 팀에 고객 질문(내부 기획 메모)과 상품을 선택해 `원본 → 블로그 → 짧은 영상 대본 → 카드뉴스 문안` DEMO 초안 4건을 묶어 만드는 화면/API를 추가했다. 각 초안은 상품 정본 사실 검수를 거치고, 원본은 승인 대기에서 제외한다. 채널별 검수 실패는 수정 대기로 저장하며 승인 대기에 넣지 않는다. 묶음에 질문·상품 출처 파일·해시·생성 시각을 저장하고, 담당 직원 활동 기록을 남긴다.
- 이 버전은 실제 고객 질문 조사, 질문 내용에 맞춘 AI 생성, 이미지·영상 생성, 외부 게시, 유입 성과 API 연결을 하지 않는다. 질문은 공개 문안이 아닌 내부 메모다. GUI에는 유입·가입·구매 성과를 `연결되지 않음`으로 명시한다. 기존 `DEMO`·`DRY RUN`·REAL 잠금·외부 게시 차단 유지. 구현 파일: `modules/marketing_core/{repository,service,operations}.py`, `modules/marketing_roadlog.py`, `modules/marketing_os.py`, `server.py`, `web/admin/index.html`, `scripts/_marketing_os_test.py`.
- 로컬 검사: 번들 Python으로 `scripts/_marketing_os_test.py` 통과, 변경 Python 파일 `py_compile` 통과, 관리자 HTML의 inline JS 구문 검사 통과, `git diff --check` 통과. 이전 기록의 「기존 `.venv`가 제거된 Python 경로를 가리킨다」는 진단은 **틀렸다**. 샌드박스 안에서 사용자 AppData의 Python 실행이 거부된 것이며, 권한 있는 실행에서는 `RoadLog/.venv/Scripts/python.exe --version`이 Python 3.12.10, FastAPI import가 0.141.1로 성공했다. 같은 오류가 나면 Python 고장이라고 단정하지 말고 샌드박스 권한을 확인하고 허용된 실행으로 재검사한다. 화면 검증과 배포를 권한 오류만으로 미루지 않는다.
- 2026-09-23 배포 확인: `RoadLog`의 이번 기능 파일만 선택 커밋 `b62851c` 후 원격 `main`에 푸시했다. `roadlog-saju/public/admin/index.html` 정본만 선택 커밋 `7adac3c`로 맞췄으며 그 저장소의 다른 진행 중 파일·미추적 영상은 건드리지 않았다. Railway 배포 `3042724e-c79b-4c9d-8464-3e629e9e4403`는 SUCCESS, 라이브 `/admin/` HTTP 200에서 `marketingBundleCreate`와 「원본에서 여러 채널로」 반영, `/api/health` 200, 비로그인 `/api/admin/marketing/bundles` 401을 확인했다. 관리자 로그인 후 실제 클릭 검증은 별도로 필요하다.
- 로그인 후 실제 클릭 시 `/api/admin/marketing/team`이 500 오류: 관리자 화면의 병렬 읽기 요청이 같은 DB의 `bundle_id` 열 추가를 동시에 실행해 충돌했다. `marketing_core/repository.py`의 기존 DB 스키마 이관을 `BEGIN IMMEDIATE` 트랜잭션으로 직렬화했다. 16개 병렬 연결 회귀 테스트를 `scripts/_marketing_os_test.py`에 추가했고 전체 테스트 통과. 배포 후 관리자 실제 화면에서 재확인한다.

- 운영 관리자 `/admin/`에 `AI 마케팅 팀` 탭을 추가했다. 별도 Marketing OS 앱 대신 기존 `_require_admin()` 인증 안에서 동작한다.
- `modules/marketing_os.py`가 `web/admin/marketing-products.json`을 서버 `lamps.py`와 대조하고, 별도 `DATA_DIR/marketing_os.db`에 동기화·초안·검수·승인·사용량 기록을 저장한다.
- 첫 통합판은 `DRY RUN`·`DEMO` 고정이다. Gemini 키 존재 여부만 표시하며 REAL 호출과 자동 호출은 모두 잠겨 있다.
- 거짓 가격, 검증되지 않은 할인, 없는 결과 항목, 보장 표현, 타 브랜드, AI 상투 표현을 승인 전에 차단한다.
- 승인 버튼은 승인 이력만 남기며 외부 SNS 게시·광고·가격 변경·고객 메시지는 실행하지 않는다.
- 테스트: `scripts/_marketing_os_test.py`. 상품 44개 대조, API 키 없음, 사실 검수, REAL 잠금, 승인 후 외부 게시 차단을 검사한다.
- 로컬 확인용 `run_admin_local.ps1`은 전용 `.venv`로 서버를 켜고 `http://127.0.0.1:8501/admin/`을 자동으로 연다. 바탕화면 바로가기 `ROADLOG AI 마케팅 팀.lnk`가 이 파일을 실행한다.
- SaaS 확장을 위해 `modules/marketing_core/`를 브랜드·웹 프레임워크 독립 코어로 분리했다. 포트, 검수 정책, 생성·승인 서비스, 저장소가 이 안에 있다.
- `modules/marketing_roadlog.py`만 `lamps.py`, 상품 JSON, ROADLOG 문구를 안다. `modules/marketing_os.py`는 기존 API를 깨지 않도록 두 계층을 조립하는 얇은 파사드다.
- 네 마케팅 테이블에 `tenant_id`를 추가하고 기존 행은 `roadlog`로 자동 이관한다. 테스트에서 두 테넌트의 승인 목록과 결정 권한이 섞이지 않는 것을 확인한다.
- 2026-09-23 운영 배포: `a35291b`를 `main`에 푸시했고 Railway 배포 `d07f32a8-55a6-4e27-b176-3722cf7b6bc9`가 SUCCESS다. 라이브 `/api/health` 200, `/admin/`의 `AI 마케팅 팀` 탭, 상품 44개, 비로그인 마케팅 API 401을 확인했다.
- 2026-09-23 전체 운영판 보강: `marketing_core/operations.py`에 8개 AI 직원, 팀 시작·일시정지·긴급정지, 작업 시간표, 수동 작업, 활동 로그, 콘텐츠 기록, 일일 보고서를 tenant별로 추가했다. 기존 DRY RUN과 외부 게시 차단은 유지한다.

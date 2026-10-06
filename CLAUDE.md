# RoadLog — Claude Code 안내

## 2026-10-03 · 관리자 회원·비회원 방문 수 (Codex)

- 온해님 요청으로 `modules/stats.py`에 일간 방문 지문별 `visitor_kind`를 기록하고 `member_uv`·`guest_uv`·`unknown_uv`를 오늘/월/날짜별 API 응답에 추가했다. 같은 날 비회원 방문 후 유효한 로그인 요청이 오면 회원으로 바꾸며 기존 UV/PV 수는 늘리지 않는다. 과거 회원 여부 미기록 방문은 `구분 전`으로 남긴다. 기준은 계정 수가 아닌 기존 IP+브라우저+KST 날짜별 방문이며 로그인하지 않은 회원도 비회원 방문으로 센다.
- `server.py` 미들웨어는 서버 `_sessions`에 존재하는 Bearer 세션과 성공 응답으로 회원 여부를 확인한다. 관리자 경로·제외 쿠키·봇은 기존 제외 조건을 유지한다. 확인된 회원 지문은 당일 메모리에 보관해 요청마다 방문 파일을 읽고 쓰지 않는다.
- 화면 정본 `roadlog-saju/public/admin/index.html` 및 `web/admin/index.html`: 오늘 방문자 아래 회원/비회원 수, 유입 탭 선택 기간별 합계, 날짜별 회원/비회원/구분 전 열. `roadlog-saju/main.js`는 최초 로드·로그인·계정 준비·45초 ping에 인증 헤더를 보낸다. 운영 `web/index.html`은 새 `web/assets/main-B15yzTqy.js`를 읽는다. 기존 최적화 WebP 참조를 보존하고 212개 자산 참조 존재를 확인해 변경 산출물만 선택 반영했다.
- 검증: `scripts/test_admin_visit_kinds.py`와 기존 퍼널 테스트 총 7개 통과(중복/로그인 전환/내부 이동/과거 기록/KST/유효·가짜·실패 세션/제외 경로), Python 구문 검사, 제품 `tools/ship.py --check` 34개, Vite 빌드, 관리자 소스/운영 SHA256 일치. 운영 `9848770`을 corelabsstudio/RoadLog main에 푸시했고 Railway 배포 `6e0fdf70-fee6-4a27-9e05-f0aa99687756` ACTIVE / Deployment successful 확인. 배포 중 한 차례 502 후 정상 운영 관리자 화면에서 오늘 방문 및 유입 합계/날짜별 새 열을 확인했다. 실제 신규 손님 방문·로그인으로 0→양수 증가하는 라이브 거래 검증은 하지 않았다.
- 온해님이 보관용 원본 저장소 동기화를 명시적으로 허용하신 뒤 소스 커밋 `57a7182`를 corelabsstudio/roadlog-saju main에 푸시했고 원격 main 커밋을 확인했다. 운영 `9848770`과 원본 동기화 모두 반영됐다. 다른 작업의 .env.example/.gitignore/문서/미추적 DB·영상은 커밋하지 않았다.

## 2026-09-30 · 운영 화면 재로그인 표시 분리 (Codex)

- 손님 화면에서 관리자로 로그인한 뒤 운영으로 갈 때 세션 토큰도 읽도록 `roadlog-saju/public/admin/index.html`과 운영 사본 `web/admin/index.html`을 맞췄다. 통계 API 오류는 로그인 창 대신 재시도 화면으로 보이고, 운영 나가기에서 두 토큰 저장소를 비운다.
- 소스 커밋 `bcb546f`, 운영 커밋 `111172c`를 각각 `main`에 푸시했다. 제품 검사 전체와 Vite 빌드, 로컬 브라우저의 세션 토큰 + 모의 통계 500 화면 확인을 마쳤다. Railway 배포 `b1bafdd6-53ac-45d6-8c4f-652e7146325c`는 설정 변경 없이 `SUCCESS`로 전환됐다(2026-09-30 02:50 KST). 라이브 `/admin/`에서 새 재시도 화면 코드와 HTTP 200을 확인했고, `/api/health`, 관리자 로그인, `/api/admin/stats?days=90`도 모두 HTTP 200이었다.

## 2026-09-30 · 운영 현황 로그인 뒤 통계 500 (Codex)

- 온해님 화면의 `불러오지 못했습니다`는 관리자 비밀번호 오류가 아니다. 운영 `/api/auth/login`은 HTTP 200·관리자 권한이며 `/api/admin/freepass`도 200, `/api/admin/stats?days=90`만 500을 재현했다.
- `modules/stats.py`의 `_visits()`는 방문자 지문 목록을 숫자로 바꿔 반환하는데, 새 `_funnel_sum()`이 그 숫자에 `len()`을 호출했다. 동시에 `_visits()`가 단계별 `fun` 자료를 버리고 있었다. 숫자를 그대로 더하고 `fun`을 전달하도록 고쳤다.
- `scripts/test_admin_stats_funnel.py`는 수정 전 같은 TypeError를 재현했고 수정 후 통과했다. `tools/ship.py --check` 전체 통과. 수정 파일 두 개만 RoadLog 커밋 `5631644`에 담았다.
- 온해님이 2026-09-30 배포를 명시 승인해 커밋 `5631644`를 `RoadLog main`에 푸시했다. Railway 공식 상태 페이지에 API 장애로 일부 배포가 멈춘다는 공지가 있다. 자동 배포는 대기 중 중복 요청으로 `SKIPPED`됐고 중복 요청 둘은 제거했다. 현재 단일 배포 `762d35a0-3774-47e3-aa09-2cd3f5808332`가 같은 커밋으로 `QUEUED`다(2026-09-30 02:03 KST). 아직 `SUCCESS`와 운영 화면 복구를 확인하지 못했다. 다른 진행 중 파일은 커밋하지 않았다.

## 2026-09-29 · 가입 전환 개선 1~8 (Kiro)

- 정본 기록: **`docs/marketing/SIGNUP_FUNNEL_2026-09-29.md`** (고치기 전 실측 · 웹 근거 · 한 일 · 라이브 확인 · 읽는 법). 화면 쪽 규칙은 `roadlog-saju/CLAUDE.md` 맨 위 같은 날짜 항목.
- 서버: `POST /api/funnel` + `_funnel_from()`(가입 때 `signup_email`·`signup_social`), `modules/stats.py` `funnel()`·`_funnel_sum()` → `/api/admin/stats` 의 `funnel`. `?nocount=1` 브라우저와 크롤러는 세지 않는다. `POST /api/saju/taste` 비회원 맛보기(첫 항목 하나 · 새로 쓸 때만 IP 한 시간 4번 · 하루 전체 `TASTE_DAILY_CAP`=300 · 본문 없이 `_saju_veil_blocks`).
- 배포: 1~7 `cbc03e7` (소스 `1cdec0d`) · 8 `8a304aa`→`8e6a215` (소스 `d980f95`→`ff6f2fa`) · 미리보기 줄 버그 `5bd8d3a`·`8ee3c24`.
- 3·4번(로그인 뒤 잠금 상자 · 소셜 복귀)은 온해님 관리자 계정으로 라이브 확인했다. 방법·결과·못 본 것은 정본 문서 6절.
- 🛑 `modules/saju_writer.py` `write_report` 가 `hooking_preview` 를 블록에 안 담아서 2026-09-18(WRITE_VER 4) 뒤 저장본에 미리보기 줄이 없었다. `5bd8d3a` 에서 담게 고쳤다. 옛 저장본은 `_saju_veil_blocks` 가 `lead`·`scene_line` 을 보낸다. WRITE_VER 는 올리지 않는다 — 산 리포트까지 다시 쓴다.
- 이 저장소의 `.env.example`·`.gitignore`·`CLAUDE.md` 수정과 Threads 미추적 파일(`tools/threads_promo.py` 등)은 다른 작업(Codex)의 것이라 커밋하지 않았다.

## 2026-09-29 · Threads API 시작 안내 반영 (Codex)

- 온해님이 Meta Threads API Get Started 안내를 전달했다. 아직 Threads 앱·사용자 토큰·숫자 사용자 ID가 없다. `tools/threads_promo.py status`는 자격 증명 없음, 게시 OFF, 장부 없음으로 나왔고 자동화는 PAUSED다. 실제 API 연결·게시는 하지 않았다.
- `docs/marketing/THREADS_API.md`에 Threads 앱 ID/시크릿 구분, @roadlog_saju Tester 초대와 수락, 글·검색·답글 권한, 단기/장기 토큰 만료, 텍스트 글에는 공개 미디어 서버가 필요하지 않다는 점을 반영했다. 앱 생성과 OAuth 권한 동의는 온해님이 진행하고 토큰은 채팅에 보내지 않는다.
- `tools/threads_promo.py context <글 ID>`로 원글과 대화 답글을 다시 읽을 수 있게 했고, 자동 답글 절차에 게시 직전 맥락 재확인을 명시했다. 모의 테스트 6개·Python 구문 검사 통과. 실제 계정 권한 및 API 응답은 토큰 발급 뒤 검증해야 한다.

## 2026-09-29 · 스레드 자동 홍보 준비 (Codex)

- 온해님이 스레드 글·답글의 자동 공개까지 허용했고 스크린샷으로 계정 **@roadlog_saju**를 지정했다. 이전의 스레드 접속 금지/건별 승인 기록은 이 범위에서 갱신됐다. 2026-10-06 추가 지시: 인스타그램도 API 게시 허용, 인스타·스레드 접근 금지 전부 폐기.
- 공식 API 실행기 `tools/threads_promo.py`, 모의 검증 `scripts/test_threads_promo.py`, 연결 안내 `docs/marketing/THREADS_API.md`를 추가했다. 이 PC에는 아직 Threads 앱·사용자 토큰·ID가 없어서 실제 계정 연결, 게시, 예약 실행은 미검증이다. 매일 11시 Codex 예약은 만들어 두고 앱 연결 전에는 일시정지했다.

## 2026-09-28 · AI 마케팅 팀 제거 및 운영 반영 (Codex)

- 온해님이 자동 실행과 관리자 화면을 모두 제거하기로 선택했다. `server.py`의 마케팅 예약 스레드와 `/api/admin/marketing/*` 관리자 API를 제거했다. 관리자 화면 정본은 `roadlog-saju/public/admin/index.html`이며 빌드 산출물 `web/admin/index.html`을 동기화했다.
- 공개 블로그 및 기존 캠페인 귀속 추적에 필요한 `marketing_os.db`와 마케팅 저장소, 과거 기록은 보존한다. 서버 커밋 `057cf57`을 `corelabsstudio/RoadLog` main에 푸시했다. 라이브 관리자 탭 제거를 눈으로 확인했고 `/api/admin/marketing/team` 404, `/api/health` 200, `/blog/` 200을 확인했다. 기존 미추적 DB는 커밋하지 않았다.

## 2026-09-25 AI 초안 시험 확인창 정리 (Codex)

- 관리자 `AI 초안 1건 만들기` 버튼에만 중복 브라우저 확인창을 제거했다. 수동 버튼, 별도 유료 API 허용 스위치, 원자적 예산·호출 수 제한, 외부 게시 건별 승인 정책은 유지한다. `web/admin/index.html`은 `roadlog-saju/public/admin/index.html`에서 복사한 운영 사본이다.
- `cf25173`을 운영에 푸시했고 Railway 배포 `3192d2de-e25d-45ae-a402-86ca0c3f80fa`가 ACTIVE임을 확인했다. 라이브 관리자에서 `오늘 운세 한 조각` 블로그 초안 버튼을 한 번 눌렀으며 확인창 없이 Gemini HTTP 시도 1회가 진행됐다. 사실 검수 통과 콘텐츠 #25가 승인 대기 1건에 등록됐다. 오늘 유료 HTTP 시도 3→4/20, 내부 예약 108→142/3,000원, 공급자 사용량 기반 누적 예상 비용 36.86→39.09원(실제 청구액 아님), 외부 호출 감사 4→5건. 외부 게시 0건. 테스트 후 유료 API 허용을 OFF로 저장하고 관리자 화면에서 OFF를 재확인했다. 자동운영·이미지·영상·SNS·자동 게시는 계속 OFF다. 이번 시험에서 기존 8명 카드의 `Gemini API 키 미연결` 오래된 상태 문구는 그대로 남아 있다. 이는 별도 표시 문제다.

## 2026-09-25 비용 안전 배포 및 1회 운영 시도 (Codex)

- 온해님 승인 범위에 따라 비용 안전장치와 기존 자동 실행 큐를 `cb06016`으로 `RoadLog/main`에 푸시했다. Railway `web` 배포 `8228598a-91eb-4a5f-b89b-6d1528e71138`가 Active로 표시되고 로그인된 `/admin/`의 새 비용 설정(내부 3,000원/일, 최대 20회/일, 팀원당 5회)이 로드됐다. 관리자 원본은 `roadlog-saju`의 `c39351b`로 동기화했다. 양쪽 저장소의 미추적 영상/DB는 그대로 뒀다.
- 배포 후 관리자 화면에서 자동 운영 OFF, 이미지/영상/SNS/자동 게시 OFF, 유료 API 허용 OFF, 오늘 유료 API 0/20회, 내부 예상 사용액 0/3,000원을 확인했다. Tavily/Gemini 연결 설정은 표시되지만 이번 턴에 실제 호출은 하지 않았다. 별도 `/api/health` 직접 요청은 로컬 네트워크 권한 문제로 확인하지 못했고 관리자 페이지는 열렸다.
- 브라우저 JavaScript 확인창 제어가 멈춰 온해님이 확인창을 직접 눌렀다. 새 탭에서 유료 API ON을 확인한 뒤 `수동 테스트 · 즉시 실행`을 단 한 번 눌렀고, 두 번째 확인창도 온해님이 직접 눌렀다. 이번 캠페인 #3은 실제 상품 `재회 공략집(again)`을 선택해 외부 조사 결과 10건을 저장했고 디렉터가 `RESEARCH`를 선택했다. 따라서 작성/검수/승인 단계는 실행하지 않고 `NO_ACTION`으로 종료, 신규 초안·승인 대기 0건이다. 관리자 장부의 오늘 유료 HTTP 시도는 0→3/20회, 내부 예약 0→108/3,000원, 공급자 사용량 기반 누적 예상 비용은 36.86원(실제 청구액 아님), 외부 호출 감사 누적 1→4건이다. 게시 0건. 끝난 뒤 유료 API 스위치를 OFF로 저장하고 새 탭에서 OFF를 재확인했다. 자동 운영은 계속 OFF다. 남은 작업: 이번 `RESEARCH` 결정 때문에 8명 전체의 제작 루프가 진행되지 않았으므로 그 원인/정책을 별도 점검한다. 이번 승인으로 추가 실행하지 않는다.

## 2026-09-25 마케팅 비용 안전장치 (Codex, 운영 미배포)

- 내부 예약 3,000원은 실제 청구 하드캡이 아니라는 문제를 기준으로 `docs/marketing/COST_SAFETY.md`에 기존 경로·변경·남은 과금 경로를 기록했다. 새 `modules/marketing_cost_guard.py`와 `modules/marketing_safety.py`의 단일 SQLite 감사 장부가 매 Gemini/Tavily HTTP 시도 전에 모델·입력/출력 상한 기반 예상액을 원자적으로 예약한다. 요청당 고정 20원은 기존 `marketing_runs` 보조 장부에만 남고 실제 HTTP 허용 판단에는 사용하지 않는다.
- 새 관리자 유료 API 스위치는 기본 OFF이며 자동운영 스위치와 별도다. 관리자는 내부 예산 ≤3,000원, 하루 호출 ≤20, 팀원별 ≤5를 따로 설정할 수 있다. Gemini/Tavily HTTP 동시 호출 ≤2, Gemini 초기+재시도 총 ≤3, 캠페인 중복 큐는 유지한다. 사용량 누락·급증·연속 실패·가격 미확인 모델은 그날 유료 호출을 차단한다. 공식 청구액은 여전히 공급자 결제 화면에서만 확인 가능하다.
- `scripts/test_marketing_cost_guard.py`의 모의 병렬·예산·재시도·재시작·KST·이상 사용량 테스트와 기존 회귀를 실행한다. 운영 배포·실제 유료 호출·자동운영/유료 스위치 ON은 하지 않는다. 이전 자동화 큐 변경과 이번 비용 변경이 같은 일부 파일에 겹치므로 후속 배포 전 diff를 분리 검토한다.

## AI 마케팅 자동 실행 큐 리팩터링 (2026-09-25 Codex)

- 온해님 지정 하루 내부 예산 3,000원은 기존 `UsagePolicy.daily_cost`/역할별 예약 검사에 이미 설정되어 있음을 확인했다. 요청당 내부 예약액은 10원에서 20원으로 맞췄다. 하루 요청 20건·역할당 5건 제한은 유지한다. 이는 실제 Google/Tavily 청구액의 상한이 아니며, 실제 청구 내역은 공급자 결제 화면에서 별도 확인해야 한다. 이번 변경으로 자동운영 스위치를 켜거나 유료 호출을 실행하지 않는다.

- `modules/marketing_os.py`의 매일 09:00 KST 캠페인 경로를 `modules/marketing_core/job_queue.py`의 SQLite 영속 큐에 연결했다. 브라우저가 열려 있지 않아도 서버 lifespan의 60초 루프가 큐 작업을 집는다. `(tenant, campaign_daily:날짜)` 고유 키와 `BEGIN IMMEDIATE`로 중복 집기를 막는다.
- 자동운영 ON은 기존 수동 검수 성공·서버 `MARKETING_AUTO_TEAM_ENABLED`·Gemini 안전 게이트를 유지하면서 팀 상태를 RUNNING으로 설정한다. 수동 팀 시작 버튼은 별도 즉시 테스트로 유지한다. 자동 게시·SNS·이미지·영상은 켜지지 않는다.
- 큐 상태 `queued/running/waiting_approval/completed/failed`, 실행 횟수와 결과를 관리자 `team` API에 제공한다. `skipped`는 아직 큐 상태로 구현되지 않았다. 호출 전 안전하게 실패한 캠페인만 지수 대기 후 최대 3회 재시도한다. 캠페인이 이미 만들어졌거나 외부 호출 결과가 불확실하거나 작업자가 중단된 경우는 `waiting_approval`로 고정해 자동 유료 재시도를 막는다. 실패는 관리자 화면의 작업 상태에 표시한다. 긴급정지 상태에서는 자동운영 ON을 거부한다.
- 아직 구현 범위 밖: 이미지·영상·SNS 제작/게시 공급자, 개별 8명 역할마다 영속 큐 작업 할당, 독립 알림 채널. 공개 게시는 기존 건별 관리자 확인 원칙을 따른다. 운영 환경에서 실제 자동 호출을 켜기 전 비용 한도와 서버 스위치를 확인해야 한다. 브라우저가 없는 모의 예약·중복 방지 테스트는 통과했으나 실제 다음 예약 시각의 운영 E2E 검증은 미완료다.

## 마케팅 Gemini 수동 연결 준비 (2026-09-24 Codex)

- Railway 운영 `web` 서비스 변수 화면에서 `GEMINI_API_KEY` 등록을 확인했다. 키 값은 열거나 출력하지 않았다. `TAVILY_API_KEY`와 새 마케팅 안전 스위치는 현재 등록되지 않았다.
- `modules/marketing_safety.py`의 릴리스 잠금은 `MARKETING_RELEASE_HOLD`가 정확히 `false`일 때만 풀리도록 변경했다. 기본값은 잠금 유지이며 글로벌·공급자 스위치도 별도로 필요하다. 자동 팀·이미지·영상·SNS는 이번 단계에서 열지 않는다.
- 격리 Python 환경 `.venv-marketing-check`를 만들어 안전·전략·OS 회귀 테스트를 실행했다. 설치된 로컬 Python 3.12 경로가 없어 기존 `.venv`가 깨졌고, 격리 환경에는 `httpx`, `python-dotenv`, `fastapi`, `pillow`, `tzdata`가 필요했다. 격리 환경은 배포하지 않는다.
- 실제 API 호출과 운영 변수 적용·배포 검증은 아래 후속 기록의 결과를 확인할 것. Tavily 키 발급이나 SNS 게시를 이 작업의 묵시적 승인으로 간주하지 않는다.

## 마케팅 외부 호출 안전 배포 (2026-09-24 Codex)

- `modules/marketing_safety.py`의 글로벌/공급자 기본 OFF를 마케팅 HTTP 진입점에 적용했다. 이미지·영상·SNS 외부 호출 상한 0건, Gemini 캠페인별 10건, 검색 5건. 자동 팀은 `MARKETING_AUTO_TEAM_ENABLED=false` 기본값으로 과거 DB 설정과 관계없이 차단한다.
- Railway 관리 API의 변수 확인이 403으로 실패해 이번 코드 자체에 `RELEASE_HOLD=True`를 고정했다. 따라서 운영 변수가 예상과 다르더라도 이 릴리스는 마케팅 외부 HTTP를 호출하지 않는다. 해제는 별도 배포에서만 한다.
- `marketing_campaigns.mode=TEST`는 관리자 DRY RUN 전용. 실제 정본·내부 진단으로 계획/예상 경로만 기록하며 AI 초안·승인·공개·성과 학습은 만들지 않는다. 외부 호출 감사와 관리자 안전 보드를 추가했다.
- `.env.example`과 `docs/marketing/SAFE_DEPLOYMENT.md`에 운영 스위치/단독 API 검증 경계를 기록했다. 실제 Gemini/Tavily/Meta 호출과 공개 게시를 실행하지 않는다. 실제 배포 및 라이브 검증 결과는 아래 후속 기록에서 확인할 것.
- 운영 서버 커밋 `897c3e0`을 `RoadLog/main`에 푸시했다. Railway 관리 API/CLI는 인증 403/Unauthorized였으므로 배포 ID 자체는 확인하지 못했다. 다만 라이브 `/admin/`에서 TEST 캠페인 UI 반영을 확인하고 로그인된 관리자 화면에서 실제 상품 `오늘 운세 한 조각` TEST #1을 실행했다. 분석→진단→조사·디렉터·작가·검수 계획→게시 준비 예상 경로 7건, 실제 외부 호출 신규 감사 0건, 오늘 AI 사용량 0/20건, 기존 승인 대기 1건 그대로 확인했다. 자동 점검 OFF, 전체 외부 API/공급자/자동 게시 OFF 표시.
- 라이브 `/api/health`, `/admin/`, `/blog/`, `/saju/today.html`, `/pay.html`, `/api/auth/social/ready` 모두 HTTP 200. 이 점검은 결제·가입·게시 동작을 수행하지 않았다. 관리자 UI 원본은 `roadlog-saju/main`의 `3245d34`로 동기화했다. `roadlog-saju` 미추적 영상·Blender 파일과 `RoadLog/data/marketing_os.db`는 커밋/삭제/이동하지 않았다.
- 현재 회귀 `_marketing_safety_test.py`, `_marketing_strategy_test.py`, `_marketing_os_test.py` main 통과, `test_marketing_creative.py`/`test_marketing_assets.py` 6건 중 4건 통과·2건 구형 이미지 성공 모의 skip. 전체 37건 구형 테스트는 이번 릴리스의 합격 기준이 아니며 기존 13/37 분류를 `LEGACY_TEST_AUDIT.md`에 유지했다. 다음 단계는 별도 승인 후 Tavily 단독 1건 → Gemini 단독 1건 → 팀 실호출 순서. 이번 릴리스의 `RELEASE_HOLD` 해제는 그때 별도 코드 배포가 필요하다.

## 조사·전략 근거 계층 (2026-09-24 Codex, 로컬 검증)

- `marketing_research.py`에 Tavily Search 기본 검색 어댑터를 추가하고 운영 선택을 Brave에서 Tavily로 바꿨다. Brave 일반 약관은 검색 결과 보관 제한이 있어 기존 Brave 저장 경로를 더 이상 운영에서 사용하지 않는다. `TAVILY_API_KEY`와 `MARKETING_EXTERNAL_RESEARCH_ENABLED=true`를 모두 설정해야 외부 검색을 한다. 실제 키·한국어 결과는 미검증, 유료 호출 0건.
- `marketing_strategy.py`와 저장소에 출처 4종(MEASURED/EXTERNAL_SOURCE/PAST_CAMPAIGN/AI_INFERENCE), 기존 블로그 제목 중복 검사, 실행 가능한 블로그 전략 우선·이미지/영상 후보 차단을 넣었다. 조사→전략 저장→AI 디렉터 순서이며 선택 이유와 링크는 관리자 캠페인 기록에서 확인한다. 외부 검색 실패·미연결이면 내부 자료로 계속한다. 일일 10검색·동일 query 6시간 캐시·결과 최대 5건.
- `scripts/_marketing_strategy_test.py`, 기존 `scripts/_marketing_os_test.py` 모의 회귀 통과. 37개 구형 모음은 13/37을 재현했고 전 항목을 `docs/marketing/LEGACY_TEST_AUDIT.md`에 분류했다. 검사 방법/한계는 `docs/marketing/RESEARCH_STRATEGY.md`.
- `scripts/marketing_learning_probe.py`에 게시 캠페인의 점수표→Learning 확인과 명시적 `--live-ai`일 때만 실제 Gemini 1회 테스트 경로를 만들었다. 이번 작업에서는 유료 호출을 실행하지 않았다.
- 아직 운영 배포·관리자 로그인 화면 클릭·실제 Tavily/Gemini 호출·테스트 캠페인 버튼은 하지 않았다. 이미지·영상·SNS 무인 게시를 추가하지 않았고 실제 공개는 온해님 건별 확인이 필요하다. 이 변경이 완전 자동 리서치를 의미하지 않는다.

## AI 마케팅 상태 한국어 표기 (2026-09-24 Codex)

- 20개 자동화 능력의 사용자용 상태를 `docs/marketing/AUTOMATION_CAPABILITIES.md`에서 `작동/부분 구현/연결 필요/미구현`으로 바꿨다. 관리자 정본 UI `roadlog-saju/public/admin/index.html`은 8명 AI의 개별 상태와 담당 도구 상태까지 같은 방식으로 표시한다. 내부 DB/API 영문 enum은 호환성을 위해 유지한다.

## AI 마케팅 자동 제작 방향 수정 (2026-09-24 Codex)

- 수동 무료 제작물 가져오기는 fallback이다. `modules/marketing_creative.py`에 Gemini 3.1 Flash Image 공식 API Provider를 추가했고 팀 캠페인에서 텍스트 검수 후 실제 이미지 파일을 생성·비공개 저장하는 조건부 경로를 연결했다. 이미지 API는 별도 과금 가능하므로 `MARKETING_IMAGE_GENERATION_ENABLED=false`가 기본값이다. 운영 실호출·시각 검수는 미검증, 저장 상태는 `GENERATED_UNVERIFIED`이며 `READY_TO_PUBLISH`가 아니다.
- `modules/marketing_tools.py`의 tool registry가 외부 조사/검색/내부 집계/글/이미지/AI 영상/게시/성과의 연결 상태를 각각 표시한다. 관리자 화면에도 실제 자동화 능력을 분리 표시한다. `docs/marketing/AUTOMATION_CAPABILITIES.md`에 요청된 능력별 실제 상태와 미완 범위를 기록했다. API 키·Meta 계정·이미지 API 과금 동의·영상 공급자 결정이 없으므로 전체 자동화 완료로 말하지 말 것.
- 무료 웹앱 브라우저 무인 조작은 구현하지 않았다. 이미지 단가·무료 여부는 Google 공식 가격표를 기준으로 확인하고, 실제 이미지 API/Meta/Brave 호출은 실행하지 않았다. 이미지 provider MockTransport 및 로컬 파일 저장 테스트와 기존 팀 회귀 검사를 실행했다.
- 2026-09-24 후속 검증: `scripts/test_marketing_creative.py`·`scripts/test_marketing_assets.py` 총 6건 통과, `scripts/_marketing_os_test.py` 통과, `roadlog-saju` 전체 `ship.py --check`와 Vite 빌드 통과. 서버/관리자 빌드 `2ac91af`를 `RoadLog/main`, UI 원본 `5e7cbce`를 `roadlog-saju/main`에 푸시했다. 라이브 `/admin/` HTTP 200에서 `자동화 능력: 사이트 분석` 표시 반영 확인. 로그인 관리자 클릭·실제 과금 이미지 생성은 미검증.

## AI 마케팅 무료 제작물 가져오기 (2026-09-24 Codex)

- AI 인플루언서 프로젝트의 무료 제작 방식(Gemini 웹 이미지, Clipchamp 편집/음성, 검증된 로컬 FFmpeg·SadTalker)을 ROADLOG에서 쓸 수 있도록 `modules/marketing_assets.py`의 비공개 자산 보관 및 관리자 인증 API, `tools/build_marketing_video.py` 로컬 MP4 제작기를 추가했다. 상세 경로·한계는 `docs/marketing/FREE_CREATIVE.md`.
- 관리자 승인 항목의 이미지 지시안·영상 구성 확인, 실제 JPEG/PNG·MP4 가져오기, 인증된 비공개 미리보기를 추가했다. 파일은 `IMPORTED_UNVERIFIED`이며 자동 생성 완료·READY_TO_PUBLISH·공개 게시로 표시하지 않는다. Railway가 개인 PC의 Gemini/Clipchamp 웹 세션이나 SadTalker를 무인 호출하는 기능은 없다. 기존 Instagram 게시 어댑터는 공개 JPEG URL이 필요하므로 비공개 가져오기 파일을 바로 게시하지 못한다.
- 원본 AI 인플루언서 프로젝트는 읽기만 했다. 로컬 2초 영상 출력 시험은 기존 AI 생성 이미지를 입력으로 사용했고 파일을 확인한 뒤 시험 출력만 제거했다. 배포·운영 GUI 클릭 결과는 검증 후 이 항목에 별도 보충한다.

## AI 마케팅 실측 진단·공개 검색 경로 (2026-09-24 Codex · 로컬 변경)

- `marketing_diagnosis.py`가 검증된 상품 정본과 `stats.overview` 집계로 `SiteMarketingProfile.v1`을 만든다. SQLite `marketing_site_profiles`에 저장하고 팀 실행 전 갱신한다. 상품별 열람은 누적값이며 방문·결제 전환율이 아니므로 `None`으로 둔다. 월간 전체 방문·가입만으로 보수적 진단을 내리고, 기존 날짜 랜덤 상품 선택 대신 최근 14일 중복을 피하며 누적 열람이 적은 검증 상품을 선택한다. 디렉터 AI에게 진단 근거를 전달하고 캠페인 사건으로 기록한다.
- `marketing_research.py`는 공식 Brave Web Search HTTP API 어댑터다. `BRAVE_SEARCH_API_KEY`와 `MARKETING_EXTERNAL_RESEARCH_ENABLED=true`가 모두 있어야 캠페인에서 1회 검색한다. 결과 제목·URL·설명·관찰 시각을 `marketing_research_sources`에 `EXTERNAL_SOURCE`로 보존하고 관리자 화면에 노출한다. 실패·미연결 때는 검색했다고 쓰지 않는다. 실제 Brave 계정 키가 없어 외부 live 호출은 미검증이며 MockTransport만 테스트했다.
- 이 변경은 **실제 블로그 게시, 이미지·영상 생성, 상품별 방문/결제 귀속, 캠페인 결과의 학습 환류를 완성하지 않았다.** 기존 Instagram 수동 게시 경로 역시 Meta 설정이 없어 미검증이다. `AWAITING_APPROVAL`은 `READY_TO_PUBLISH`가 아니다. 사용자 요청의 전체 완료로 보고하지 말 것.
- 배포 전 전체 `ship.py --check` 통과, Python 마케팅 회귀 테스트 통과, Vite 임시 빌드 통과. 요청 범위 서버 파일과 빌드된 관리자 HTML만 `31ff4d2`로 `RoadLog/main`에 푸시했다. 라이브 `/admin/` HTTP 200에서 `marketingDiagnosis` 표시가 존재하고 `/api/health` HTTP 200임을 확인했다. Railway CLI 인증이 없어 배포 ID와 로그인된 관리자 화면 클릭은 확인하지 못했다. 실제 Gemini·Brave·Meta 유료/외부 호출은 이 검증에서 하지 않았다.

## AI 마케팅 폐쇄 루프 1차 확장 (2026-09-24 Codex · 로컬, 미배포)

- 붙여넣은 요청은 `CASE 5 게시`에서 잘려 있었다. 확인 가능한 요구 중 기존 8명 실행을 디렉터 결정 → 시장/검색 가설 → 작가 초안 → AI 검수 → 채널/크리에이티브/성과 순으로 바꾸고, 앞 단계 요약을 작가에게 `AI_INFERENCE` 맥락으로 전달했다. 디렉터의 `NO_ACTION`은 작성·검수 요청을 하지 않는다. 검수 실패는 작성자에게 최대 2회 수정 요청하고 각 초안을 다시 검수한다. 전체 최대 12회 요청/내부 예약 120원이며 실제 청구액 상한은 아니다. 실측 상품 사실과 섞지 않는다.
- `marketing_campaigns`, `marketing_campaign_events`, `marketing_learning`을 기존 `marketing_os.db`에 추가했다. 실행 전 ROADLOG 내부 집계는 `MEASURED` 기초값으로만 저장하며 게시 성과로 오인하지 않는다. 관리자 화면에는 실제 캠페인 사건 순서만 표시한다.
- 기존 자동 설정 API를 매일 09:00 KST 점검에 연결했다. 수동 AI 초안 검수 통과 및 관리자의 명시적 ON이 필요하고, 팀이 `RUNNING`일 때만 실행한다. 같은 날 수동 팀 작업이 있으면 건너뛰며 DB 유일 키로 중복 실행을 막는다. 디렉터의 `NO_ACTION`은 추가 작성 요청 없이 종료한다. 최근 48시간 내 승인 대기 캠페인도 다시 만들지 않는다. 작업자 재시작으로 15분 이상 진행 중인 자동 작업은 `FAILED`로 기록하고 같은 날 유료 자동 재시도하지 않는다.
- 외부 게시 자동화는 구현/허용하지 않았다. (Instagram 건별 확인·Threads 접속 금지는 2026-10-06 온해님 지시로 모두 폐기 — Instagram·Threads API 게시 허용.) 외부 시장·검색량 API와 이미지·영상 생성 공급자 연결은 아직 없으므로 `NOT_CONNECTED`/`NEEDS_CONFIGURATION`으로 표시한다. 학습은 실행 전 집계만 기록하며 실제 게시/캠페인 성과 환류는 아직 아니다.
- 모의 Gemini 회귀 테스트, 관리자 인라인 JS 문법 검사, 임시 출력 폴더 Vite 빌드 통과. **운영 배포·실제 유료 Gemini 호출·실제 GUI 클릭 검증은 아직 하지 않았다.** 남은 일: 외부 조사·검색/크리에이티브 공급자 실제 연결, 게시 후 성과 귀속과 Learning 피드백, 캠페인별 콘텐츠/게시 상태 연결, 운영 UI 클릭 검증.

## Instagram 공식 API 게시 경로 (2026-09-23 Codex)

- `modules/marketing_instagram.py`는 ROADLOG 전용 Instagram Login Graph API 어댑터다. 외부 스크래핑·비공식 로그인 라이브러리를 사용하지 않는다. Meta 토큰은 Railway 환경변수에서만 읽고 DB·로그·응답에 넣지 않는다. 연결 준비 단계는 `docs/marketing/INSTAGRAM_API.md` 참고.
- 관리자 인증 API `/api/admin/marketing/instagram/status`와 `/api/admin/marketing/approvals/{id}/publish-instagram`을 추가했다. `APPROVED`·REAL·채널 `인스타그램` 콘텐츠, ROADLOG HTTPS JPEG, 별도 `INSTAGRAM_PUBLISH_ENABLED=true`, `confirmed=true`가 모두 필요하다. 서버에서 대상 계정이 `@mumung_101`인지 확인한다. AI 팀/스케줄과는 연결하지 않으며 긴급정지 중 수동 게시도 차단한다. 승인 ID별 중복 차단, 결과 불확실 시 `UNCERTAIN`으로 기록·자동 재시도 금지.
- 관리자 화면 정본 `roadlog-saju/public/admin/index.html`과 운영 복사본 `web/admin/index.html`에 인스타 채널·연결 상태·건별 게시 UI를 추가했다. 실제 Meta 앱/프로페셔널 계정/토큰/공개 JPEG가 아직 확인되지 않아 운영 게시 성공을 주장하지 않는다. 현재 Railway에는 Meta/Instagram 변수가 없으므로 버튼은 비활성화된다. 테스트는 MockTransport로만 실행한다.

## AI 마케팅 성과·시장 데이터 연결 (2026-09-23 Codex)

- 2026-09-23 후속 결정: Instagram `@mumung_101` 연결 조사는 허용하지만 외부 게시는 당시 **매 건 온해님 최종 확인** 조건이었으나 2026-10-06 온해님 지시로 폐기됐다(Instagram·Threads API 게시 허용). 기존 관리자 `승인 기록`은 내부 승인일 뿐 게시 허가가 아니다는 구분은 코드 기준으로 유지한다. 온해님도 계정이 프로페셔널/Meta 앱 연결 상태인지는 모른다고 답했다. Railway 운영 서비스 변수 이름에서 Meta/Instagram 관련 항목은 발견되지 않았다(값은 출력하지 않음). 계정 자격·앱·권한·이미지 자산은 아직 확인 전이다.
- ROADLOG 자체 `stats.overview`의 방문·유입·캠페인·상품별 열람·가입·결제·매출 집계만 선별해 `modules/marketing_roadlog.py`에서 AI용 스냅샷으로 만든다. 회원·이메일·원시 거래는 전달하지 않는다. 디렉터·시장 조사원·성과 분석가에만 입력한다. 내부 상품 관심도를 외부 시장 조사로 표현하지 않는다.
- 관리자 인증 아래 `/api/admin/marketing/insights`를 추가하고 AI 마케팅 팀 화면에 접이식 실제 사이트 성과 카드를 둔다. 검색량/Search Console·인스타 게시/성과·외부 시장 데이터는 연결되지 않았다고 명시한다. Gemini 실제 유료 요청이나 외부 게시를 이번 수정 과정에서 실행하지 않는다.
- 과거 인스타·스레드 접속 금지 기록은 당시 기준이다. **인스타·스레드 접근 금지는 2026-10-06 온해님 지시로 전부 폐기됐고, Instagram·Threads API로 글을 게시하는 것은 허용이다.** Meta/Google 권한·인증 자료는 확인 전이므로 연결 완료라고 표시하지 않는다.

## AI 마케팅 팀 8명 독립 요청 (2026-09-23 Codex)

- 관리자 `팀 시작`은 하루 한 번 `team_8` 작업을 등록하고 백그라운드에서 8개 역할 각각 별도 Gemini 요청을 실행한다. 역할별 요청 ID·토큰·내부 예산 예약 10원·JSON 산출물·실패 상태를 `marketing_runs`와 `marketing_agent_outputs`에 기록한다. 화면은 4초 간격으로 작업 중 상태를 갱신한다. 시장/검색/성과 API가 없으므로 해당 역할은 상품 정본 기반 가설과 미연결 항목만 작성한다. 외부 게시·광고는 여전히 막혀 있다.
- 콘텐츠 작가 초안은 먼저 `AWAITING_AI_REVIEW`로 저장되어 승인 목록에 나타나지 않는다. 품질 검수자의 별도 AI 요청과 기존 정본 규칙이 통과한 경우만 `PENDING_APPROVAL`로 전환한다. 검수 실패/작업 중단은 수정 대기다. 팀 일시정지/긴급정지 시 새 요청은 시작하지 않고 승인 등록도 막는다. AI 키가 없으면 8명 `WAITING_AI`, 유료 요청 0건. 각 역할 오류는 다른 역할과 격리한다.
- SaaS 공통 역할 계약 `modules/marketing_core/agents.py` 및 공통 실행/저장 `marketing_core/`; ROADLOG 전용 사실·Gemini 어댑터 `modules/marketing_os.py`, `marketing_gemini.py`. 배포로 유료 호출이 자동 시작되지는 않는다. 관리자가 다음 `팀 시작`을 눌러야 한다. 실제 8회 호출 검증은 유료 실행이므로 이번 작업에서는 Fake Provider 테스트만 수행한다.

## AI 마케팅 내부 예약 단가 (2026-09-23 Codex)

- 온해님 지시에 따라 신규 Gemini 요청의 내부 예산 예약값을 1건당 600원에서 10원으로 변경했다. 이는 실제 Gemini 청구액의 추정·상한이 아니다. 오늘 사용량은 기존 기록의 600원과 변경 후 기록의 10원이 합산될 수 있으며 기존 기록은 소급 변경하지 않는다.
- `modules/marketing_core/service.py`, 모의 검증 `scripts/_marketing_os_test.py`, 관리자 문구 `web/admin/index.html`을 변경했다. 화면 정본은 `roadlog-saju/public/admin/index.html`. 일일 내부 한도 3,000원, 작성자별 5건 및 전체 20건의 요청 한도는 그대로다.

## AI 마케팅 팀 접기·시각 표시 (2026-09-23 Codex)

- 관리자 `web/admin/index.html`에 자료·기록·생성 카드를 기본 접힘으로 변경하고, 카드 제목에 현재 건수를 넣었다. ISO 시각은 화면에서만 한국 시간으로 변환해 날짜/오전·오후 시각을 읽기 쉽게 보여준다. 데이터/API 스키마는 그대로다. 화면 정본은 `roadlog-saju/public/admin/index.html`이다.

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

- 2026-09-23 팀 시작 즉시 실행: `modules/marketing_os.py`의 시작 명령이 상품 정본 점검, 시장·검색 데이터 연결 상태 확인, Gemini 블로그 초안 최대 1건 생성·사실 검수, 일일 보고서 기록을 요청 안에서 바로 실행한다. 새 AI 초안은 서울 날짜 기준 첫 시작에만 예약·호출하며, 같은 날 반복 클릭이나 일시정지 후 재시작은 다시 과금하지 않는다. 한도·검수·외부 게시 차단은 유지한다. `SCHEDULE`의 시각 기반 자동 작업은 전부 껐으며 기존 자동 설정은 시작 시 해제한다. 관리자 화면에서 시간 예약 토글을 제거하고 시작 버튼에 비용 확인을 둔다. 시장·검색·성과 API는 여전히 미연결이므로 해당 직원은 대기 사유를 기록할 뿐 외부 조사나 게시를 했다고 주장하지 않는다. 구현/검증: `modules/marketing_core/operations.py`, `modules/marketing_os.py`, `modules/marketing_core/service.py`, `scripts/_marketing_os_test.py`, `web/admin/index.html`. 모의 공급자 테스트만 사용했으며 실제 유료 호출은 이 변경 검증 중 하지 않는다.

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

## AI 마케팅 게시 준비 게이트 · 2026-09-24 Codex

## AI 마케팅 폐쇄 루프 · 2026-09-24 Codex

- `marketing_blog.py`/`marketing_core.repository`로 승인된 블로그를 영속 게시물에 저장하고 `/blog/ai-{id}.html` 및 블로그 목록에서 제공한다. 관리자 승인 요청 때만 실제 공개한다. 중복 차단, 저장 재조회 후 `PUBLISHED`, 실패 시 `PUBLISH_FAILED`; 운영 시험 게시물은 만들지 않았다.
- `marketing_attribution.py`와 기존 가입(일반·소셜), PortOne 검증 후 충전·프리미엄, 환불 경로를 연결했다. 서명 쿠키·30일 마지막 유효 캠페인 모델이며 매출은 환불 제외. 기존 회원·결제 원장을 바꾸지 않는다. 세부 한계는 `docs/marketing/BLOG_ATTRIBUTION_POLICY.md`.
- 캠페인 누적 방문/순 브라우저/가입/구매/매출 및 비율을 실측 행에서 계산한다. `performance_analyst`는 현재 규칙 기반 해석만 Learning에 기록하며 AI로 분석했다고 주장하지 않는다. 다음 Director 요청에 이전 scorecard/Learning을 실제로 전달하고 동일 상품 재시도 근거를 요구한다. 이미지·영상·외부 검색·SNS API와 유료 호출은 이번 작업에서 사용하지 않았다.
- 로컬 `scripts/_marketing_publication_e2e_test.py`: 임시 DB+가짜 결제, 승인→실제 HTTP 게시 화면→방문 쿠키→가입→가짜 충전→성과→Learning→다음 Director 모의 공급자 컨텍스트까지 통과. `scripts/_marketing_closed_loop_test.py`도 새 실측 정의에 맞춰 통과. `scripts/_roadlog_suite_test.py`는 13/37; 24 실패는 구 운행일지/스타일/결제 업그레이드 API와 제거된 정적 파일 기대(현 ROADLOG SaaS 스펙과 무관한 legacy)이며 이번 변경의 회귀 증거가 아니다. `/app.js` 200은 SPA 폴백이라 진짜 JS 성공으로 읽으면 안 된다. 테스트 파일은 삭제하지 않았다.
- 배포: RoadLog 선택 커밋 `74c4e2e`를 `main`에 푸시했다. 라이브 `/api/health` 200, `/admin/`의 새 블로그 승인 문구 200, `/blog/` 200, 존재하지 않는 동적 `/blog/ai-99999999.html`은 JSON 404, 비로그인 승인 API 401. 실제 블로그 시험 게시/실결제/유료 AI 호출은 하지 않았다. Railway CLI의 이 로컬 폴더는 프로젝트 미연결이라 배포 ID/SUCCESS 상태는 조회하지 못했다.

- 온해님은 Gemini 이미지 API 과금 승인을 보류했다. `marketing_os._run_team`의 자동 이미지 생성 호출을 제거했고 도구 상태를 `과금 승인 보류`로 표시한다. 이미지 Provider 코드는 남기되 실제 유료 이미지 호출·활성화는 금지한다.
- 팀 자동 작성본은 `REVIEWING → FINAL → READY_TO_PUBLISH` 순서로 진행한다. 최종 검수 통과만으로 승인 항목을 만들지 않는다. `marketing_core/repository.py`의 `prepare_publication`이 상품 정본, 문안, CTA, 채널 payload, 필수 자산을 확인하고 게시 준비 기록·고유 추적 URL을 만든 뒤 승인 항목을 넣는다. 블로그 텍스트는 이미지 불필요, 인스타그램은 검증된 JPEG 없으면 `BLOCKED_ASSET_REQUIRED`다. 승인·준비는 실제 게시가 아니다.
- 자동 수정 최대 2회/검수 3회에 대해 원본·수정본 ID, 피드백, 결과를 `marketing_revisions`에 남기고 전부 실패하면 `REQUIRES_HUMAN`으로 표시한다. 캠페인 단계도 DB `stage`로 보존한다.
- UTM/캠페인/게시물 ID를 가진 링크를 생성한다. 기존 `stats.overview`의 UTM 방문 집계만 scorecard에 실측 저장한다. 상위 30개 제한으로 집계에서 밀리면 방문도 미확인으로 표시한다. 캠페인별 CTA 클릭·가입·구매·매출은 현재 귀속 경로가 없어 NULL이다. 사이트 전체 수치를 캠페인 성과로 쓰지 않는다. 이전 캠페인 scorecard를 다음 Director의 metrics에 전달한다.
- 키가 없어도 팀 시작 시 내부 상품·사이트 진단을 갱신한다. AI 작성은 키/자동화 조건 없으면 대기한다. 외부 검색·Search Console·이미지·영상·Meta 게시를 구현/연결했다는 뜻이 아니다. 현재 블로그도 게시 준비/승인까지만 가능하고 내부 블로그 발행기는 없다. 과거 수동 초안/인스타 승인 경로는 새 게시 준비 게이트와 별개인 레거시 경로이므로 완전한 통합을 후속 작업으로 남긴다.
- 테스트: `scripts/_marketing_os_test.py`, `scripts/_marketing_closed_loop_test.py`는 모의 공급자/로컬 SQLite만 사용한다. 실계정·실유료 호출은 하지 않는다.
# 2026-09-24 AI 마케팅 블로그 폐쇄 루프 재검증 (Codex)

- 기존 production 경로는 `READY_TO_PUBLISH` → 관리자 승인 → `BlogPublisher.publish()` → `/blog/ai-{publicationId}.html` 동적 게시, 서명 쿠키 방문 → 가입 → PortOne 검증 결제 귀속 → 실측 scorecard → 규칙 기반 Learning → 다음 Director 입력으로 이어진다. 공개 테스트 글/실제 결제/유료 API 호출은 하지 않았다.
- 다음 Director의 `metrics.previous_campaigns`에 기존 scorecard 외에 실제 선택 전략과 게시 상태/URL을 추가했다. 이전 전략을 확인하지 못하던 빈틈을 E2E의 Campaign A→B 검증으로 재현 후 수정했다.
- 로컬 `scripts/_marketing_publication_e2e_test.py`는 임시 DB·가짜 가입/결제로 실제 FastAPI 게시 라우트, 관리자 캠페인 API, 귀속, Learning, 다음 Director context를 통과했다. 마케팅 모의 회귀 5개 스크립트 통과. 구형 `scripts/_roadlog_suite_test.py`는 UTF-8 출력 설정 후 13/37이며, `docs/marketing/LEGACY_TEST_AUDIT.md` 분류대로 옛 운행일지 API/자산 테스트가 남는다. 삭제하지 않았다.
- 미확인: 운영 실제 공개 게시물과 실고객 전환은 만들지 않았으므로 라이브 퍼널 데이터 검증은 하지 않았다. `performance_analyst` 후속 Learning은 유료 AI가 아닌 규칙 기반 해석이다.
# 2026-09-24 · Marketing Provider Diagnostics

- 관리자 인증 전용 `GET /api/admin/marketing/providers`, `POST /api/admin/marketing/providers/{provider}/test`를 추가했다. 6개 도구의 설정·활성·최근 검사 상태를 읽기 전용으로 보여주며 키 값은 반환하지 않는다.
- 실제 진단 실행은 Tavily만 지원한다. `MARKETING_DIAGNOSTICS_LIVE_ENABLED=true`, 기존 글로벌/Research 안전 스위치, Tavily 키, 명시적 `live=true`, 검증된 상품 선택이 모두 필요하다. 기본은 OFF이고 하루 1회 DB 선점으로 중복을 차단한다. 전체 팀·스케줄러·Gemini·게시를 호출하지 않는다.
- 기존 `TavilyResearchProvider.search`와 외부 호출 감사 로그를 그대로 쓴다. 감사 operation `diagnostic:tavily_search`, 관리자 식별자는 비복원 해시로 남긴다. 결과는 기존 Research 저장소에 `EXTERNAL_SOURCE`/`PROVIDER_DIAGNOSTIC`로 저장 후 재조회한다. 오류 시 재시도하지 않으며 오류 종류만 반환한다.
- 검증: `scripts/_marketing_diagnostics_test.py`의 오프라인 MockTransport 경로 통과. 실제 Tavily 호출 여부와 운영 배포 상태는 별도 확인 기록을 따른다.
# 2026-09-24 · Tavily 운영 단일 진단 및 표시 보완

- `054e1fd`는 이전 캠페인의 scorecard·선택 전략·게시 상태를 다음 Director 입력에 더하는 변경으로 재확인했다. 자동 외부 API/게시 스위치 변경은 없다. `33ea0d8`과 함께 Railway에 배포해 ACTIVE를 확인했다.
- 배포 직후 `/api/health`, `/admin/`, `/blog/`는 HTTP 200, 미인증 진단 GET·POST는 HTTP 401, 기존 관리자 화면과 6개 도구 상태는 표시됨을 확인했다. 외부 호출 감사 기록은 0건이었다.
- 관리자 화면의 Tavily 단일 진단에서 실제 상품 `오늘 운세 한 조각`, 검색어 `오늘 운세 무료 사주 서비스`로 정확히 1회 실행해 결과 5건과 저장/재조회 통과를 확인했다. Gemini·이미지·영상·SNS·블로그 게시는 실행하지 않았다. 전체 팀과 TEST 캠페인도 실행하지 않았다.
- 진단 GET에서 저장된 마지막 검색어·출처 제목/URL/요약·호출 수를 다시 읽어 주도록 보완했다. 관리자 화면도 새로고침 후 결과가 남도록 표시한다. 임시 `MARKETING_DIAGNOSTICS_LIVE_ENABLED`는 검증 후 다시 false로 닫는다.

## 2026-09-29 · 로드로그 블로그와 공개 글 사이트맵 (Codex)

- `web/index.html`에 홈 블로그 카드와 스타일만 선별 추가했다. 기존 홈의 저주 신단 CSS·JS와 인라인 SEO 문구는 유지했다. `web/blog` 9편을 새 BlogPosting/OG 정보로 갱신하고 첫 새 글 `reunion-after-repeat-fight.html`을 배포했다.
- `modules/marketing_blog.py`가 기존 DB 기반 공개 글의 JSON-LD·OG를 기사로 맞추고 정적 사이트맵에 공개된 DB 글 URL을 합친다. `modules/marketing_core/repository.py`는 공개 글 전체를 사이트맵용으로 읽는다. `server.py`의 `/sitemap.xml`은 이를 XML로 응답한다. 제한된 목록 20건과 달리 공개 글 전체를 포함한다.
- `scripts/test_blog_seo.py` 단위 테스트 통과. 소스 `32e10dc`, RoadLog `4111825`를 main에 푸시했다. 운영 `https://roadlog.co.kr/`, `/blog/`, 첫 새 글, `/sitemap.xml`, `/api/health` 모두 200을 확인했고 새 글의 제목·canonical·BlogPosting 및 사이트맵 67 URL 포함을 확인했다.
- 새 원고 자동 발행은 Codex heartbeat `로드로그 블로그 하루 1편`(id 1, ACTIVE, 매일 10:00 한국 시간)이 `roadlog-saju/tools/publish_blog.py --apply`를 사용한다. 유료 AI·Threads 연결은 사용하지 않는다. 검색 결과 게재는 보장되지 않는다.

## 2026-09-25 · AI 팀 시작/종료 지속 운영 (Codex)

- 관리자 `팀 시작`은 Gemini 설정과 비용 한도를 확인하고 유료 호출을 켠 뒤 즉시 첫 8인 팀 작업을 큐에 등록한다. 서버의 60초 루프가 브라우저와 무관하게 2시간 간격으로 다음 작업을 점검한다. 단, 최근 48시간 승인 대기 캠페인, 실행 중 작업, 불확실한 결과, 하루 호출·내부 예산 한도에서는 새 유료 작업을 만들지 않는다. 이는 빈 시간 내내 AI API를 호출한다는 뜻이 아니다.
- `팀 종료`는 지속 운영 상태와 유료 호출 허용을 끄고 대기 작업을 건너뛴다. 이미 공급자에 전송된 HTTP 요청은 취소할 수 없으므로 이전 작업이 실행 중이면 재시작을 막는다. 외부 게시·이미지·영상은 켜지지 않으며 게시마다 관리자 승인이 필요하다. 옛 `매일 09시` 스위치는 새 운영 화면에서 제거하고 활성화 API도 거부한다.
- `marketing_continuous` 상태와 `marketing_job_queue`/`marketing_scheduled_runs`를 SQLite에 보존해 서버 재시작·다중 worker에서도 중복을 막는다. 배포만으로는 시작되지 않도록 새 스위치 기본값은 OFF. 내부 3,000원은 실제 청구액 하드캡이 아니다.
- 모의 공급자 테스트: `scripts/test_marketing_continuous.py`, `scripts/test_marketing_job_queue.py`, `scripts/_marketing_os_test.py`. 실제 유료 호출·외부 게시는 이 변경 검증 중 하지 않는다.

## 2026-10-01 · 관리자 디자인 및 사용성 개선 반영 (Codex)

- 온해님은 관리자 화면에 무냥이 장식 이미지를 넣는 방향을 거절했고 실제 화면을 보기 좋게 고치라고 지시했다. 앞서 만든 무냥이 시안은 사용하지 않았다.
- public/admin/index.html: 밝은 중성 배경, 또렷한 제목과 숫자, 핵심 지표 4칸, 넓은 매출 그래프, 상품 순위/누적 패널로 정리했다. 상단 메뉴와 옅은 사주 배경 문자는 유지했다. 불필요한 작은 그래프와 중첩 카드 장식은 줄였다.
- 회원 이름/이메일 검색, 결제/VIP 필터, 25명 페이지 나누기, 모바일 SVG 실제 폭 계산, 탭 URL/현재 메뉴 접근성, 프롬프트 미저장 경고와 편집기 이름을 추가했다. 오늘 통계는 어제 하루와의 증감 대신 집계 중임을 표시한다. 저장/공유 집계에서 단순 열람을 제외하고 상품명을 한글로 표시한다.
- RoadLog/modules/stats.py: 퍼널 방문 분모를 2026-09-29 수집 시작일 이후로 맞췄고 응답에 funnelSince를 추가했다. scripts/test_admin_stats_funnel.py에 기간 회귀 검증 추가.
- 검증: 회귀 테스트 2개, ship.py --check 필수 검사 34개, Vite 프로덕션 빌드, 변경 코드 diff 검사 통과. ship.py --no-commit의 npx 빌드가 멈춰 종료하고 기존 로컬 Vite로 직접 빌드했다. 빌드된 관리자 HTML만 RoadLog/web/admin/index.html로 반영했다.
- 커밋/푸시: roadlog-saju 18401df, RoadLog be806a3. Railway 배포 d443c664-30ad-410d-9cc5-23a4c940a70e Active / Deployment successful 확인.
- 라이브 /admin/ 새 디자인과 회원 검색 0건 처리, 페이지 나누기 표시, 저장/공유 상품명, 9월29일부터 퍼널 방문 92명 표시를 확인했다. 로컬 예시 데이터에서 모바일 390px 페이지 넘침 없음과 그래프 viewBox 309를 확인했다. 환불/삭제/유료 AI 호출은 검증 대상에서 실행하지 않았다.
- 실물 화면 캡처: C:\Users\hysoo\projects\roadlog-admin-design\admin-live-desktop.jpg. 필수 수정의 남은 작업은 없다. 제품 문서는 기존 변경을 포함하므로 코드 커밋과 분리해 로컬 기록으로 남겼다.

## 2026-10-01 · 관리자 입체 아이콘과 화면 구성 재디자인 (Codex)

- 온해님이 공유한 입체/유리 질감 대시보드 4종을 참고하고 「사진을 쓰라는 것은 기능 아이콘을 실사화하라는 뜻」「알아들었으면 만들어」 지시에 따라 실제 재디자인·배포했다. 관리 화면을 AI로 그려 캡처처럼 사용하지 않았다. 내장 image_gen으로 6종 기능 아이콘 아틀라스를 만들고 실제 코드 UI에서 사용한다.
- public/admin/index.html 및 운영 RoadLog/web/admin/index.html: 생성 아이콘 상단 메뉴, 입체 지표 카드, 매출/운영 업무 바로가기 2열 구성, 순위와 누적 패널, 표/입력/버튼의 공통 스타일. 상단 메뉴와 옅은 사주 문자를 유지한다. 캐릭터 장식은 없다.
- 아이콘 public/admin/assets/operations-icons-v2.png 및 운영 web/admin/assets/operations-icons-v2.png. 유리/금속 재질의 통계·회원·콘텐츠·결제·유입·피드백 6종. 이미지 생성 프롬프트와 도구는 projects/roadlog-admin-design/MATERIAL_ICONS_PROMPT.md에 보관했다.
- 그래프는 눈금·전체 날짜·정확한 최고값/날짜를 표시하고 방문자는 면/선 그래프로 구성했다. 좁은 차트 날짜는 일자만 표시하고 전체 기간을 위에 명시한다. 모바일 긴 그래프는 최신 날짜부터 보여주며 좌우 이동 안내를 제공한다. 방문자의 날짜별 유입 클릭은 유지하고 Enter/Space 키 조작도 추가했다.
- 검증: 최종 빌드 성공, ship.py --check 34개 통과, inline JS 문법·diff 검사 통과, 소스와 운영 관리자 HTML SHA256 일치. 로컬 PC/390px 실물과 바로가기/페이지 넘침 없음을 확인했다. 브라우저 오류 로그 없음.
- source 836fb4f, 운영 fca6149 푸시. Railway 배포 3fc3d79f-6963-4591-83f3-c7fa109f4613 Active / Deployment successful. 실제 roadlog.co.kr/admin 새 아이콘/구성, 방문자 27개 날짜와 26개 양수 값 표시, 09/08 최고 162명, 키보드로 09/08 유입 선택을 확인했다.
- 라이브 캡처 projects/roadlog-admin-design/admin-material-live.jpg 및 admin-material-visits.jpg. 관리자 대시보드 탭을 열어두었다. 환불/회원 변경/유료 AI 호출은 실행하지 않았다. 요청된 디자인 작업의 필수 미완료 항목은 없다. 문서는 기존 변경과 함께 로컬 기록이며 코드만 선택 커밋했다.

## 2026-10-03 · 실사 무냥이 Threads 카드뉴스 한 건 (Codex)

- 온해님 직접 요청으로 Codex 내장 이미지 생성으로 실사 무냥이 카드뉴스 두 장을 만들고 @roadlog_saju에 공식 Threads API로 게시했다. 훅은 「스토리는 보면서 내 톡은 왜 안 읽어?」, 본문은 336자이며 기다린다/먼저 보낸다 선택지와 경험 질문을 넣었다. AI 생성임을 밝혔다.
- 원본·본문·생성 프롬프트 설명·일회 게시 스크립트·영수증·검증 결과·실제 게시 화면: `RoadLog/docs/marketing/threads-2026-10-03/`. 카드 두 장의 공개 호스팅만 `RoadLog/web/assets/social/threads-2026-10-03/`에 선택 반영했다. 운영 커밋 `8a19b7b`, 공개 URL 두 장 HTTP 200 및 원본 바이트 일치 확인. 사이트 코드 변경 없음.
- 게시 ID `18100417907562410`, 링크 https://www.threads.com/@roadlog_saju/post/DeCSepkn4pW . API 재조회로 username=roadlog_saju, media_type=CAROUSEL_ALBUM, 이미지 2개, 원문을 확인했고 실제 브라우저 게시 화면에서도 글과 카드 두 장을 확인했다. `published.jpg`에 화면 저장.
- 기존 `threads_promo.py` 계정 확인·중복 방지 장부를 사용했다. 이번 한 번의 프로세스에서만 공개를 허용했으며 저장된 반복 공개 스위치·예약은 변경하지 않았다. 토큰은 출력·기록하지 않았다. AutoThreads 설치 폴더가 현 환경에 없어 기존 공식 API 도구를 사용했다. 남은 작업 없음.

## 2026-10-03 · 가입 정체 분석 (Codex · 분석만)

- 라이브 운영 화면 23:51 KST 기준 회원 100명. 날짜별 실제 표에서 09-21~10-03 방문 합계 511, 신규 가입 3. 09-29~10-03 방문 합계 177, 가입 0. 방문은 일별 IP+브라우저 중복 제거 합계이며 날짜 사이 재방문이 포함된다.
- 같은 기간 비회원 사주 퍼널: 방문 177 / 상품 5 / 계산 0 / 리포트 0 / 가입창 1 / 이메일 가입 0 / 소셜 가입 0 / 결제 화면 1. 방문은 전체 사이트·회원 방문도 포함, 상품/계산/리포트는 비회원 사주 showProduct 경로만 기록한다. 꿈·반려동물·저주 등의 시작/완료와 실제 진입 페이지는 분리 집계하지 않는다. 단계별 일간 합계이지 동일인의 연속 전환율이 아니다. 177명의 97%가 메인에서 이탈했다고 해석하지 않는다.
- 회원/비회원 구분은 10-03 도입 후 일부만 있음: 오늘 24 방문 중 회원 0 / 비회원 7 / 구분 전 17. 과거 방문 전체를 비회원이라고 단정하지 않는다. 직접·앱 유입은 referrer 미전달을 포함하고 봇/진짜 사람 비율은 현 화면만으로 확인 불가.
- 실제 메인과 배포본을 분리된 로컬 origin에서 비회원으로 검수했다. 390×844에서 프리미엄 51항목 배너 → 저주 → 꿈/관상 → 반려동물 빈 전당 → 고민 카테고리 → 일반 사주 24개. 카테고리 y=1153, 상품 영역 y=1214, 무료 오늘 운세 카드 y=1604. 하단 오늘 운세 바로가기는 있다. 첫 화면의 시작점과 무료 혜택 노출이 약하다는 판단이지 인과 실험으로 확인한 원인은 아니다.
- 비회원 목록에도 등불 58~396개 표시. 가입 선물 무료 이용권 1장·등불 300개는 가입 창 안에서 설명한다. 첫 방문객이 단위와 실제 무료 열람 범위를 이해하기 어렵다는 가설. 무료 오늘 운세 입력은 1/5, 그 사람 속마음은 1/10. 후자의 첫 입력 영역 y=969, 다음 버튼 y=1370. 실제 신규 계정 생성·소셜 콜백·생년월일 제출·AI 생성·결제는 하지 않았다.
- 우선 제안: 첫 화면에 시작 CTA 한 개와 고민별 대표 경로 3개, 무료 체험/이용권 대상 구체화, 부가 기능·전당 아래로, 상세 입력 축소, 진입페이지·기능별 시작/입력시작/완료/가입CTA/소셜성공/오류 집계 보완. 홈페이지·가입폼 코드 변경이나 배포는 하지 않았다.
- 증거: `RoadLog/docs/marketing/conversion-audit-2026-10-03/visible-stats.json`, 비회원 메인/상품 모바일 캡처. `preview_guest.py`는 배포된 static을 로컬 origin에 띄우고 인증 없는 공개 readiness GET만 중계하며 생성/가입/결제 POST는 차단한다. 서버 점검 후 종료.
- 외부 근거를 직접 열어 확인: https://www.nngroup.com/articles/ecommerce-homepages-listing-pages/ 및 https://www.nngroup.com/articles/simplicity-vs-choice/ . 우선순위·상품 차이·선택 부담 설명의 보조 근거이며 로드로그 원인 확정 근거는 아니다.

## 2026-10-04 · 가입 흐름 개선 적용 및 운영 반영 (Codex)

- 온해님이 10-03 가입 정체 분석의 개선을 순차적으로 모두 적용하도록 승인했다. 메인 첫 화면을 무료 오늘 운세 CTA 1개 + 속마음/재회/연락 대표 경로 3개로 바꿨다. 일반 사주 한 편 무료 이용권·등불 300개를 먼저 설명하고 프리미엄/결제 전용 제외·카드 등록 불필요를 명시한다. 기존 24개 일반 상품과 부가 기능은 더 보기로 유지한다.
- 일반 입력 5→3, 두 사람 입력 10→5. 성별과 날짜를 함께 받고 이름·태어난 곳을 선택 항목으로 접었다. 시각·양음력·성별·지역 계산은 유지하며 모바일 다음 버튼을 하단 메뉴 위에 붙였다. 숨은 굴림판이 0 위치를 읽어 날짜를 1900년으로 바꾸던 문제도 보호했다. 1996-03-14/1994-11-02 및 성별·시간 모름을 실제 확인 화면에서 보존 확인.
- 소셜 취소·만료·예상 인증/통신 오류는 가입창으로 돌아가 이메일 대안을 안내한다. 꿈/관상/반려동물 소셜 로그인 뒤 해당 화면으로 복귀한다. 계정 생성·실제 OAuth 동의·결제·유료 AI 호출은 하지 않았다.
- 비회원 메인, 무료/고민 선택, 입력 시작/확인, 가입 CTA, 이메일 제출/오류, 카카오/구글 시작/오류, 꿈/관상/반려동물/저주 진입·완료 집계 추가. 운영 화면에 10-04 이후 이벤트·같은 날 메인 비회원과 가입의 교집합 추가. 기존 퍼널의 이전 항목 대비 % 제거. 개인정보를 분석 본문에 보내지 않고 기존 일별 해시·중복 제거·운영자/봇 제외를 따른다. 소셜 앱/IP 변경 및 날짜가 달라진 가입은 메인 교집합에 연결되지 않을 수 있고 순차 퍼널이 아니다.
- 변경: roadlog-saju/index.html, style.css, main.js, account.js, dream.js, pet.js, curse.js, public/admin/index.html, tools/ship.py, tools/deploy_to_roadlog.py. RoadLog/server.py, modules/stats.py, 회귀 검사 및 web 빌드 산출물. Windows Vite 실행 수정, SNS 공개 assets/social/ 파일을 전체 배포에서 보존한다. 서비스워커는 기존부터 캐시를 저장하지 않는다.
- 검증: 정식 uv run --offline python tools/ship.py --no-commit 필수 34개·빌드·생성기·WebP 통과. 통계/회원 분리/소셜 오류 회귀 검사 12개 통과. 390×844 비회원 분리 origin에서 무료 CTA 첫 화면(y359), 3/5단계, 다음 버튼(y760), 이름 생략, 시간 모름, 혜택 창, 24개 상품 펼치기, 소셜 오류 복귀 확인. 1280×900 데스크톱 확인.
- 소스 로컬 d8f3e9c, 운영 577ab1aee245e5d1cdd357fa1b72c8ba1f1fcaf4. RoadLog origin/main 푸시·Railway SUCCESS. 라이브 HTML·main JS/CSS·browser JS가 Git blob과 바이트 일치(로컬 CRLF는 정규화 필요). health 정상·영속 저장소 유지, 라이브 모바일 무료 입력·회원 혜택 숨김·새 운영 집계·Google/Kakao 취소 콜백 302 확인. 소스 보관 원격은 푸시하지 않았다. 기존 영상·DB·환경 파일·다른 문서 변경은 커밋하지 않았다.
- 기록/증거: RoadLog/docs/marketing/conversion-2026-10-04/IMPLEMENTATION.md, home-guest-mobile.jpg, input-confirm-mobile.jpg, social-error-mobile.jpg, home-live-mobile.jpg, admin-conversion-live.jpg, verify_deployment.py. 회원이 실제 늘었다고 주장하지 않는다. 남은 것은 새로운 동일 기준 집계로 배포 후 충분한 표본의 가입률 효과를 확인하는 일이다. 반복 자동화는 추가하지 않았다.

## 2026-10-04 · Instagram API 게시 가능 여부 읽기 전용 점검 (Codex)

- 온해님 요청은 API 게시 가능 여부 확인이며 게시·권한 확대·자동화 활성화는 실행하지 않았다.
- `modules/marketing_instagram.py`의 현재 대상은 `@mumung_101`이며 단일 공개 JPEG 게시 어댑터만 구현돼 있다. 대상 지정은 실제 계정 인증을 확인했다는 뜻이 아니다. 카드뉴스 캐러셀은 별도 구현이 필요하다.
- `tools/check_instagram_connection.py`로 실제 Railway 서비스 변수를 읽기 전용 확인했다. `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_USER_ID`, `INSTAGRAM_GRAPH_VERSION`, `INSTAGRAM_PUBLISH_ENABLED` 모두 없고 게시 활성화도 false다. 비밀값은 출력하지 않았다. 로컬 설정에도 연결용 값이 없고 예제 항목만 있다.
- 현재 운영 환경에서는 실제 Instagram 계정 유형·게시 권한·토큰 유효성을 검증할 인증 정보가 없어 바로 게시할 수 없다. Meta 공식 Instagram Login은 Business/Creator 계정과 `instagram_business_basic`, `instagram_business_content_publish` 권한을 사용하며 Facebook Page 연결은 필수가 아니다. 근거: https://www.postman.com/meta/instagram/folder/6raa77c/instagram-api-with-instagram-login
- 다음 필요 작업은 사용할 계정 확인, 해당 계정의 공식 Instagram Login 토큰/게시 권한 연결, 계정 신원과 권한 검증이다. 새 Meta 개발자 계정 생성은 온해님 몫이며 토큰은 채팅이나 Git에 넣지 않는다. Threads 연결 성공은 Instagram 연결 성공을 뜻하지 않는다.

## 2026-10-04 · Instagram 두 계정 인증 보관 및 카드뉴스 도구 준비 (Codex)

- 온해님이 제공한 Desktop/roadlog_saju.txt에서 계정별 인증 자료만 읽었다. 두 토큰 원문은 로그·문서·Git·메모리에 기록하지 않는다. 신원 검증 후 Git 제외 경로 `.launch/instagram-roadlog_saju.env`, `.launch/instagram-mumung_fact.env`에 각각 저장했다. 원본 바탕화면 파일은 삭제하거나 수정하지 않았다.
- 실제 API 재조회: @roadlog_saju user_id=17841426618738292, @mumung_fact user_id=17841428103264018. 둘 다 BUSINESS 계정이며 username 일치. v24.0 호출 성공. `content_publishing_limit` 각각 quota_usage=0, quota_total=100, quota_duration=86400 응답 확인.
- `me/permissions` 조회는 HTTP 400/code 100으로 승인 권한 목록을 얻지 못했다. 이는 빈 권한 목록이 확인됐다는 뜻이 아니다. 게시 한도 조회까지 성공했으나 실제 컨테이너 생성·공개 게시 및 토큰 만료 시점은 검증하지 않았다.
- `tools/instagram_accounts.py`: 비밀값 비노출 가져오기/재검증. `tools/instagram_publish.py`: 두 계정 중 명시적으로 하나를 지정, 공개 RoadLog JPEG 1장 또는 2~10장 캐러셀, 기본은 조회만 실행하고 `--publish`가 있을 때 실제 게시. 계정 신원/한도 확인, 계정별 중복 차단, 마지막 게시 호출 직전 UNCERTAIN 기록, 자동 재시도 금지, 반환 media_id/permalink 기록. 게시 이력은 Git 제외 `.launch/instagram-publications.db`에 저장한다. 실제 공개 결과는 첫 요청 시 계정 화면에서도 확인해야 한다.
- `scripts/test_instagram_accounts_publish.py` 3건 통과: 잘못된 계정은 요청 없음, 공개 호출 타임아웃 후 재시도 차단, 두 이미지 순서/상위 캐러셀 게시 확인. 이는 Mock 검증이며 실제 게시 성공 증거는 아니다.
- 이번에는 실제 게시물을 올리거나 무인 게시 스케줄을 추가하지 않았다. Railway 비밀 변수나 기존 관리자 게시 어댑터는 변경하지 않았으며, 기존 관리자 어댑터의 mumung_101 지정은 이 로컬 CLI와 별개다. 로컬 CLI가 이후 온해님 요청 게시 실행 경로다. 계정별 토큰을 섞지 않는다. 토큰 만료/권한은 게시 전에 다시 확인한다.

## 2026-10-04 · 폭스바니 Instagram 공개 콘텐츠 확인 (Codex)

- 온해님이 제공한 검색 화면의 @foxbunny_saju, @foxbunny_saju2를 로그인된 Chrome에서 읽기 전용 확인했다. 좋아요·팔로우·댓글·메시지는 실행하지 않았다.
- 확인 시 메인 계정 게시물61/팔로워1188, 두 번째 계정 게시물42/팔로워1로 표시됐다. 시점 스냅샷이며 성장·매출 증거가 아니다.
- https://www.instagram.com/p/DeCNk2wE_mB/ : 10월4일 띠별 재회운 6장 전체 확인. 표지 호기심 → 12~1위 세 항목씩 총4장 → 관련 상품/무료시작/프로필링크/팔로우 CTA 마지막장. 어두운 배경·한지·동물 이미지·짧은 행동 조언·색과 물건 반복. 확인 시 좋아요 없음 표시.
- https://www.instagram.com/foxbunny_saju/p/Dd3EmLaE8-_/ : 캐릭터 궁합 카드의 표지와 두 번째 장 및 캡션/댓글을 표본 확인. 강한 표지 훅 → 조합별 성격 충돌 설명/이미지 → 본문 궁합사주 링크. 확인 시 좋아요298/댓글3 표시. 해당 반응이 가입·매출을 뜻하지 않으며 게시 경과시간·노출원 차이 때문에 직전 일일운세와 직접 성과 비교하지 않는다.
- 두 번째 계정 피드와 최신 본문 목록 확인: 인물 이미지를 반복하는 재회/애착/출생연도/MBTI 릴스 중심이다. 영상 전체를 재생·분석했다고 주장하지 않는다.
- 로드로그 참고 방향: 무냥이 표정과 구체적 관계 장면, 자기상황 체크/유형 분류, 다음 장에서 얻을 답의 명료함, 해당 고민에 맞는 상품으로 연결. 캐릭터 실사화가 성과 원인이라는 증거는 없다. 기존 문안·타사 이미지 복제가 아니라 로드로그 자체 콘텐츠로 적용한다.

## 2026-10-04 · 폭스바니 구성 참고 Instagram 실사 무냥이 카드뉴스 게시 (Codex)

- 온해님 요청에 따라 공감 훅 → 행동 체크 → 관련 상품의 구성을 참고해 자체 문구·실사 무냥이 이미지 두 장을 Codex 내장 이미지 생성으로 제작했다. 주제는 ‘답장은 오는데 먼저 연락은 없다면?’이며 ‘그 사람 속마음 해독’으로 연결했다. 경쟁 계정 이미지·캐릭터·문구는 복제하지 않았다.
- @roadlog_saju 실제 API 게시 성공: media_id=18176751727598659, https://www.instagram.com/p/DeDcoLbH14w/ . CAROUSEL_ALBUM, children 2장, caption 원문 일치 확인. Chrome 공개 화면에서 작성 계정·첫 카드·다음 클릭 후 두 번째 카드 모두 확인하고 published-slide-1.jpg/2.jpg 저장. mumung_fact에는 게시하지 않았다.
- RoadLog web/assets/social/instagram-2026-10-04/01-hook.jpg 및 02-checklist.jpg(1080×1080) 배포 커밋 0a392cea7b7825e4b5e0b8935a9e75f5c9ab8ee8, Railway SUCCESS. 초기 배포 중 502는 해소됐고 공개 JPEG Content-Type·SHA-256 원본 일치 후 게시했다.
- RoadLog/docs/marketing/instagram-2026-10-04/에 생성 원본·프롬프트·caption.txt·모바일 검수본·README.md·receipt.json·publish_verified.py 보관. tools/instagram_publish.py HTTP 오류에 비밀값 없는 상태/코드/서브코드 진단 추가. scripts/test_instagram_accounts_publish.py 3건 통과. 비밀 토큰은 Git 제외 .launch만 사용.
- 기존 인스타 전달 규칙에 따라 Desktop/무냥이_카드뉴스_먼저연락_20261004_01.jpg 및 _02.jpg 복사, SHA-256 일치 확인. 관련 상품명과 소개 링크의 홈 → ‘그 사람 마음’ 실제 경로 확인. 댓글 선택 질문·사주 참고용·AI 이미지 안내 포함.
- 실제 공개 게시까지 완료. 남은 평가는 이후 유입·가입 집계이며 가입률 상승을 주장하지 않는다. 반복 자동화·관리자 게시 어댑터·프로필 소개는 변경하지 않았다.

## 2026-10-04 · 로드로그 홍보 기본 3채널 규칙 (온해님 직접 지시)

- 온해님이 ‘로드로그 홍보’라고 요청하면 Instagram @roadlog_saju, Instagram @mumung_fact, Threads @roadlog_saju 세 곳 모두에 게시한다. 계정별 API username을 확인한다.
- 세 곳에 각각 다른 주제의 자체 홍보물을 만든다. 같은 카드뉴스·본문 재업로드로 세 곳을 채우지 않는다. 주제·훅·상황·연결 상품을 구분한다.
- Threads는 @foxbunny_saju의 실제 Threads 글을 따로 읽고 채널에 맞는 대화·이야기·연결 글 구성을 참고한다. Instagram의 카드·문구를 그대로 옮기지 않는다. 허위 실제 상담·후기·결과를 만들지 않으며 가상 상황이면 밝힌다.
- 이는 요청 시 실행하는 기본 범위다. 별도 반복 스케줄 생성 지시로 해석하지 않는다. 이미 같은 홍보 작업에서 게시한 계정은 중복 게시하지 않고 나머지 계정을 완성한다.
- 완료 조건: 각 계정의 공개 URL/게시 ID, 본문, 요청 첨부 또는 글 연결을 API와 실제 화면에서 확인하고 보고한다. 토큰 원문은 기록하지 않는다.

## 2026-10-04 · 3채널 홍보 세트 완성 (Codex)

- Instagram @roadlog_saju는 직전 작업의 ‘답장은 오는데 먼저 연락은 없다면?’ 카드 2장 https://www.instagram.com/p/DeDcoLbH14w/ 를 유지했다. 같은 홍보 세트에서 중복 게시하지 않았다.
- Instagram @mumung_fact 신규 ‘또 같은 꿈을 꿨다면?’ 실사 무냥이 카드 2장 게시: https://www.instagram.com/p/DeDeOx_H3et/ , media_id=18113871494048255. API username·CAROUSEL_ALBUM·children 2개·본문 원문 일치. 실제 Chrome 첫/둘째 카드·본문 확인, instagram-published-1.jpg/2.jpg 저장. 바탕화면 무냥이_카드뉴스_같은꿈_20261004_01.jpg 및 _02.jpg 복사 SHA-256 일치.
- Threads @roadlog_saju는 폭스바니 실제 Threads에서 3부 이야기 구조를 따로 읽고 ‘사과를 받았는데 같은 싸움이 반복된다면?’ 가상 대화 3부를 자체 제작했다. https://www.threads.com/@roadlog_saju/post/DeDdq81n1dj (18207238210368313), 2부 DeDdrwwn-JR (18098303177552938), 3부 DeDdtQ8nxlY (18156881131507071). 각각 API username·본문·URL 일치, 실제 화면에서 3개 연결 및 상품 링크 확인. 가상 상황 표시, 실제 후기 사칭 없음. threads-published.jpg 저장.
- 참고 Threads: https://www.threads.com/@foxbunny_saju/post/DeDU1CXEV5u . 경쟁자의 실제 상담·성장 효과는 검증하지 않았다. 스레드는 글 중심 구성으로 인스타 카드 재사용 없이 게시했다.
- RoadLog/docs/marketing/three-channel-2026-10-04/에 원본·프롬프트·카드 검수본·게시 본문·API 영수증·화면 증거·단발 게시 스크립트·README 보관. publish_threads.py는 명시 --publish, 계정 신원 확인, 단계별 UNCERTAIN/중복 차단으로 3부 self-reply 실행. 장부 .launch/threads-story-publications.db는 Git 제외. 계정 토큰은 출력하거나 문서에 넣지 않았다.
- web/assets/social/mumung-dream-2026-10-04/01.jpg·02.jpg만 배포 커밋 ef22359829429065f66577200c84077da58be780, origin/main 푸시·Railway SUCCESS. 공개 JPEG Content-Type·SHA-256 일치 후 Instagram 게시. 390px 검수, 숫자 둥근 장식 제거. Instagram 회귀 검사 3건, 새 스크립트 문법 검사, 윤문 light 의미·수치 보존 게이트 통과.
- 꿈 화면 #dream 및 반복 이별 상품 #p/loop 실물 확인. 미래 예측·가입률 상승 보장 없음. 앞으로 홍보 요청 시 세 계정 서로 다른 주제, Threads 별도 벤치마킹 기준 기록 완료. 반복 스케줄·프로필·관리자 게시 어댑터는 변경하지 않았다. 남은 평가는 이후 실제 유입/가입 집계다.

## 2026-10-04 · 게시 완료 카드뉴스 바탕화면 정리 (Codex)

온해님 삭제 요청에 따라 Desktop의 무냥이_카드뉴스_먼저연락_20261004_01.jpg·02.jpg, 무냥이_카드뉴스_같은꿈_20261004_01.jpg·02.jpg 네 복사본을 삭제하고 파일 부재를 확인했다. 프로젝트 원본·서버 이미지·공개 게시물·인증 파일은 변경하지 않았다.


## 2026-10-04 · 홈페이지 메인 개편 복원 완료 (Codex)

온해님 요청 ‘로드로그 어제 홈페이지 개편한거 되돌려놔’에 따라 메인 구조·디자인을 d8f3e9c 직전으로 복원했다. 원래 상품 배너·홍보 영역·고민별 메뉴·접히지 않은 상품 목록을 복원하고 신규 무료 운세 첫 화면/고민 3개/메인 가입 혜택/상품 접기를 제거했다. 변경 소스는 roadlog-saju/index.html·style.css·main.js·account.js이며 소스 커밋 b3cd817이다. 입력 단계·날짜 굴림판·로그인 오류 복귀·회원 혜택·운영 분석 개선은 유지했다.

정식 tools/ship.py --no-commit의 필수 검사 34개와 빌드가 통과했다. RoadLog 운영 커밋 891964fee70a7eca99cb0a8c478cd55a07e44238을 origin/main에 푸시했고 Railway SUCCESS를 확인했다. 운영 HTML·JS·CSS와 로컬 빌드가 일치하며 배너/상품 존재·신규 메인 제거·최근 Instagram 이미지 4장 해시 보존·health·영속 저장소 검사 모두 true. 실제 운영 브라우저에서 원래 배너와 상품 목록 24개를 확인했다. 로컬 좁은 화면은 실제 CSS 폭 300px에서 가로 넘침 없음을 확인하고 오늘 운세 입력 1/3 진입을 확인했다. 계정·DB·공개 SNS 게시물은 변경하지 않았다.

기록과 확인 자료: RoadLog/docs/marketing/home-rollback-2026-10-04/README.md, restore_home.py, verify_live.py, live-verification.json, home-before.jpg, home-local-mobile.jpg, home-live.jpg. 복원 작업에 남은 배포/검증은 없다.

## 2026-10-04 · 월 변경 뒤 홈 전당 사진 표시 수정 (Codex)

온해님 ‘강아지들 사진 빠졌네’ 확인. 운영 기본 전당 API는 2026-10 items=[]였으며 2026-09 공개 사진 5개와 원본 이미지 경로가 남아 있었다. 사진 삭제나 메인 복원으로 인한 데이터 손실이 아니라 월별 조회만 하던 동작이 원인이다.

RoadLog/modules/pet_hall.py·server.py에 선택적 fallback=true를 추가했다. 월을 명시하지 않고 이번 달 공개 등록이 없을 때 최근 공개 등록 월을 반환한다. 숨긴 등록 제외, 명시 월/기본 월별 조회와 실제 월별 순위 보존. roadlog-saju/pet.js·hall.js의 홈 배너/갤러리에서만 이 조회를 사용한다. 배너는 실제 표시 월을 적고 지난 관상왕을 이번 달 우승자로 소개하지 않는다. 이번 달 등록이 생기면 이번 달 사진으로 돌아온다.

소스 커밋 5c88b66, 운영 커밋 5041c6642811d191634b1a10558fa60b50ab5a81. 월 변경 회귀 검사 7건, Python 문법 검사, 정식 tools/ship.py --no-commit 필수 검사 34개/빌드 통과. 사진·게시물·등록 데이터는 수정하지 않았다. 검사 스크립트 docs/marketing/home-rollback-2026-10-04/check_hall_fallback.py·verify_hall_live.py.

최종 확인: 소스 후속 커밋 1404628은 홈 복귀 캐시 분기 전에 월 안내가 덮이지 않도록 수정했다. 최종 운영 커밋 9d1ccb2fe0b83ff0d56825422633cadcf169b6b7 Railway SUCCESS, 운영 HTML/JS/CSS 일치 및 health/영속 저장소/홍보 이미지 보존 검사 통과. 공개 사진 다섯 장 image/jpeg 정상 응답, 실제 배너 김뭉치·루리·테디·블루/레드·루이 모두 이미지 로드 완료. 블루/레드 상세 창과 9월 갤러리 9개 등록 확인. 지난달 제목/안내 문구 확인, hall-photos-live.jpg에 운영 실물 저장. 전당 UI·import 후속 검사 통과. 남은 배포/수정 없음.

## 2026-10-05 관리자 홍보 제작과 예약 발행 추가 (Codex)

온해님 요청으로 예시 스크린샷 최대3장과 프롬프트를 참고한 홍보 제작을 운영 화면 /admin/?tab=promotion 에 추가했다. Instagram roadlog_saju/mumung_fact 각각 다른 주제 카드2장, Threads roadlog_saju 다른 주제 글을 Gemini API로 서버에서 생성한다. 소스 public/admin/index.html 및 promotion.html은 roadlog-saju, 운영 사본 web/admin/ 및 modules/promotion.py/server.py는 RoadLog. 기존 마케팅 팀은 되살리지 않았다.

하루1~24회와 횟수별 1시간 단위 시각, 월 생성 예약 한도, 미리보기/바로 발행, 계정 확인/게시 영수증 UI. 예약 한 번은 세 계정 게시글3건이다. 한국 시간에 제작을 시작하고 완료 후 발행하며 정확한 초 단위 게시를 보장하지 않는다. 예약 기본OFF, 서버 중단 중 지난 시각 소급 게시 없음. 생성 실패/부분 발행은 자동 예약을 끄고 불확실한 final publish는 재시도하지 않는다. 참고 원본은 인증 조회만 가능, 생성 JPEG만 공개. DATA_DIR/promotion 영속 저장/Git제외. 시도당1000원은 운영 예약액이며 실제 Gemini 청구액이 아니다.

기존 토큰의 정확한 RoadLog Railway 서비스 저장은 자동 검토가 처음 차단했고 온해님이 명시 승인한 뒤 저장했다. Meta 개발자 본인 확인 화면과 두 Instagram의 API access blocked/code200을 확인했고 후속 조회에서 세 계정 신원/발행한도 정상화. 원인이나 사용자 처리 상세를 추정하지 않는다. Gemini 모델 조회 정상, 실제 예시 업로드와 미리보기 f851ad34a678404788440ac9806ec0c1 READY(카드4장+Threads글) 완료. 화면에서 횟수2→4, 09/12/18/21시 선택 및 저장/계정 확인 검증. 예약OFF, 공개 신규 게시 미실행. 발행 코드는 모의 정상/실패 검증이며 이번 변경에서 실제 신규 게시 영수증은 없다.

필수검사34개와 신규7개 회귀검사 통과. 운영최종 eed2def2961a7b2d58bb9c5af0556cc3e122e33e Railway SUCCESS, 소스최종 f9ae7f3. 운영HTML2개 줄바꿈 정규화 일치, 비인증403/401, 배포 후 READY/설정보존 확인. 한글 조판390px 확인. 증거 docs/marketing/admin-promotion-2026-10-05/README.md/live-state.json/admin-promotion-live.png/카드JPEG/typography-390.jpg, scripts/test_promotion.py/verify_promotion_live.py/configure_promotion.py. CLAUDE 기존 미커밋 기록은 보존했다.

견적: builda-makers/soomgo-web-2026-10-04/quote/온해IT_웹사이트개발_견적서_SNS자동화포함_20261005.docx 및 promotion-inclusion.md. 500만원VAT포함 유지, SNS범위추가4페이지 Word렌더 실물검수, 원본견적보존/고객발송없음. 남은 운영선택은 온해님의 신규 게시 실행과 예약 활성화다.

최종 화면 후속: 24회 선택 시 시간칸24개/서로다른시간24개를 실제 UI에서 확인한 뒤4회09/12/18/21시로 되돌리고 저장 성공 메시지를 확인했다. 최신 iframe 높이가 내용에 맞춰2411px로 조절됨을 확인했고 admin-promotion-final.png에 최종 화면을 저장했다. 최종 운영 HTML둘 모두 Windows/Linux 줄바꿈 정규화 후 일치. scripts/verify_promotion_live.py의 줄바꿈 비교 후속수정은 로컬검증용으로 남겨두었다.


## 2026-10-05 홍보 탭 관리자 색상 통일 (Codex)

온해님이 최신 밝은 관리자 스크린샷을 기준으로 색상 통일을 요청했다. public/admin/promotion.html(소스), web/admin/promotion.html(운영 사본)의 CSS만 변경했다. 관리자와 같은 #f7f8fd 배경, 흰 카드, #252541 본문, #626780 설명, #5847c6 버튼/보라 포인트, Pretendard, 입력칸/파일 버튼/시간 선택/제작 내역/포커스 표시 색상을 적용했다. JS·API·예약·발행 동작은 변경하지 않았으며 소스/운영 사본 내용 일치 및 JS 기존 커밋과 동일 확인. 필수 검사34개 통과. 소스240f2ed, 운영5811d5f. 운영 실물 확인은 아래 후속 기록을 따른다.

운영 확인 완료: Railway5811d5f SUCCESS, 운영 관리자 HTML 두 개가 로컬과 일치, API 정상/비인증 차단 및 기존 READY/예약OFF 보존. 실제 데스크톱 홍보 화면의 밝은 배경/흰 카드/보라 버튼 확인, 390px 뷰포트에서 홍보 iframe 본문343px/scrollWidth343px로 가로 넘침 없고 한글 줄바꿈 정상. 증거 RoadLog/docs/marketing/admin-promotion-2026-10-05/admin-promotion-light.png. 색상 변경에 남은 배포/확인 없음.


## 2026-10-05 홍보 예약 화면 간소화 (Codex)

온해님 요청: 프롬프트 없이 홈페이지에 맞는 자동 홍보, 기본 화면은 하루 횟수/시간 설정만, 등록 API 키는 접어서 숨기기. 홍보 화면을 자동 발행 횟수·시간·켜기·예약 저장과 즉시 1회 버튼으로 간소화했다. 원하는 느낌/참고 이미지, API·비용 설정, 제작내역은 기본 접힘. 기존 밝은 관리자 색상 유지. 빈/공백 프롬프트를 허용하고 글/이미지 모두 로드로그 무냥이/확인된 상품/최근 홍보 기준의 AUTO_STYLE로 자동 생성한다. 미입력 API 요청도 지원한다. 비용한도·중복 발행 방지·계정 검증 유지, 예약을 임의로 켜거나 SNS 발행하지 않았다.

변경 소스 public/admin/promotion.html(e593d12); 운영 modules/promotion.py, scripts/test_promotion.py, web/admin/promotion.html(8885db2). 프롬프트 없는 예약/상품정보 기반 자동 프롬프트 포함 서버8검사, 필수34검사, 홍보JS문법 및 소스/배포사본 일치 통과. 운영 확인은 후속 기록 참고.

운영 최종 확인: 8885db2 RailwaySUCCESS, HTML2개 운영/로컬 일치, 기존 READY/계정연결/시각09·12·18·21 보존. 실제 UI에서 프롬프트를 비워 예약 저장 성공 후 재로드/서버 조회로 빈 값 저장 확인했다. 선택적 프롬프트/참고이미지·API/비용·키변경·내역 모두 기본 접힘, 모바일390px에서 iframe343px=scrollWidth343px 및 줄바꿈/시간칸 배치 확인. admin-promotion-simple.png에 최종 데스크톱 실물 저장. 자동발행OFF, 실제 추가 생성/API비용/게시 없음. 기존 참고이미지는 유지했다. 사용자에게 남은 조작은 횟수/시간을 정하고 자동발행켜기→예약저장이다.


## 2026-10-05 가상 사례 없는 홍보 문체 (Codex)

온해님이 홍보 생성문 '(가상 상황: ... B님)'의 현실감 저하를 지적했다. modules/promotion.py 생성 지시에서 가상대화 표기 지시를 제거하고 가상 인물·개인 체험·고객/상담 사례를 지어내는 형식 자체를 금지했다. 대신 직접적인 공감 질문/일상 고민/체크리스트/확인된 상품 설명으로 쓴다. 이전 제작본의 가상 사례 형식도 따라 하지 않도록 명시. 본문·카드에서 가상상황/사례/인물/대화 또는 A님/B님 패턴 검출 시 생성 결과 거절(이미지제작/공개발행 전)한다. 라벨만 삭제해 실제 사례로 포장하지 않는다. 기존 생성/공개 게시물은 변경하지 않았다. 신규생성부터 적용, 서버모의검사9개 통과. 운영커밋b408343, Railway후속확인 아래 기록.

동시에 온해님 '24명 접속이 맞나?' 확인: modules/stats.py LIVE_MIN=2, IP+UA+날짜 지문으로 최근2분 요청 기록을 중복제거한 추정치, 서버재시작시0. server.py 미들웨어는 알려진봇과관리자경로/집계제외쿠키를 제외하지만 Mozilla UA로 위장한자동화/오류응답/API요청도 live_touch 대상일 수 있다. 동일사람의IP/UA변화 또는 공유IP/같은UA로 과대/과소가능. UI툴팁5분/endpoint주석5분은 오래된설명이며 실제2분. screenshot시점24실제사람동시접속 보장 불가, 해당시점개별로그 미보존. 숫자나필터코드 임의수정 없음.

최종 배포확인: b408343 RailwaySUCCESS, 직후잠깐502 이후 health200/관리자live200/홍보API200 정상. live조회 all3/members0/guests3/minutes2였으며 방금배포재시작으로카운터초기화되어사용자스크린샷24와직접비교불가. 공개신규발행은이번수정에서실행하지않았고 사용자가이미실행한작업PUBLISHED와기존READY보존, 예약OFF확인. 요청한가상사례없는신규생성규칙반영완료.

## 2026-10-05 방문부터 가입 완료까지 순서 집계 (Codex)

온해님 요청: 실제 방문 → 상품 클릭 → 가입 화면 열기 → 가입 완료 확인. 관리자 유입 상단에 4단계 인원, 이전 단계 대비 전환율/미진행 인원, 전체 가입 전환율과 가장 많이 멈춘 구간을 추가했다. 기존 방문 차트 날짜/기간 선택과 연동, 모바일 390px 두 열 배치 확인. 밝은 관리자 색상 유지.

소스 roadlog-saju/signup-path.js, account.js, main.js, curse.js, public/admin/index.html 및 tools/check_signup_path.mjs. 운영 RoadLog/modules/stats.py, server.py, scripts/test_admin_stats_funnel.py, scripts/test_signup_path_gate.py와 빌드 웹 사본. 소스686c891, 운영c4fe7cf. 공유 전송 큐로 방문 이벤트를 먼저 보내고 같은 날 IP+UA 지문별로 순서가 맞는 다음 단계만 진행한다. 일반 상품과 꿈/관상/반려동물/저주 진입 및 직접 상품 링크 포함. 로그인 상태는 제외. 가입 화면은 실제 등록 모드 열기이며 로그인 모드와 구별한다. 완료는 이메일/소셜 새 계정을 만든 서버 경로에서만 기록하고 공개 클라이언트의 완료 이벤트는 무시한다.

2026-10-05 배포 이후 새 이벤트부터 집계한다. 과거 기록의 순서는 추정하지 않는다. 같은 날 IP+UA 지문 기반이므로 실제 사람의 완벽한 식별이 아니며 네트워크/브라우저 변경 시 연결이 끊길 수 있다. 필수검사34개, 기존/신규 집계검사11개, 공개 완료 차단 검사1개, JS 전송 순서 검사 통과. Railway SUCCESS, 운영 API signupPath 및 HTML/새 JS 6파일 로컬 일치, 실물 데스크톱/모바일와 날짜 필터 확인. 운영에서 가짜 계정이나 가짜 유입을 생성하지 않았으며 초기 네 단계 0 표시 정상. 관리자 통계는 기존 페이지 로드/새로고침 방식이다. 증거 docs/marketing/signup-path-2026-10-05/live-verification.json 및 admin-signup-path-live.png. 남은 구현/배포 없음; 실제 방문 후 통계가 쌓인다.

## 2026-10-05 사주 상품 운영 생성 점검 (Codex)

온해님 요청: 상품들이 정상적으로 사주가 나오는지 확인. 사업 코드/가격/권한/배포는 변경하지 않고 점검했다. tools/ship.py --check 필수34개 통과(첫 실행 도구 환경 httpx 누락 후 uv 의존성 포함 재실행 성공). 전체 사주상품31개 로컬 렌더 및 다섯 사주 표본 항목 연결 검사 포함. 가상 생년월일1996-03-14 09:30 여자, 이름 점검용, 독립 pair=audit-20261005-19960314-0930로 운영 /api/saju/write force=true 실제 생성: 31/31 응답 정상·빈 본문 없음. 오늘운세3항목 전체, 다른30개 첫항목만 실제 생성하여 모든 항목의 실생성까지 전수검증한 것은 아니다. 기존 관리자 세션으로 결제/계정 생성/무료권 차감 없이 수행했으며 생성 캐시는 별도 시험 키로 남는다. 실제 API 원가는 발생하지만 공급자 청구액은 확인하지 않았다.

운영 /api/saju/taste 비인증 조회도 이미 생성한 시험 캐시로31/31 정상(무료 오늘은본문, 유료는미리보기). 실제 Chrome에서 오늘운세 입력→사주계산→무료로보기→AI해설3항목 표시, 콘솔오류0 확인. 사용자 저장 프로필 변경/저장버튼은 누르지 않았다. 증거 RoadLog/docs/quality/products-2026-10-05/fixtures.json, live-results.json, contract-results.json, today-live.png. 재현 도구 roadlog-saju/tools/audit_product_fixture.mjs 및 위 폴더 verify_products.py, verify_contract.py. 개인 손님 자료를 시험에 쓰지 않았다. 사진관상/꿈/반려동물 생성·결제거래는 이번실호출 대상아님.

발견된 미수정 문제: server.py saju_write가 요청 sections를 [:20]으로 자르는데 main.js paintWriting/paintTaste는 전체항목을 한번 요청하고 응답을 다시 나누어 받지 않는다. 이미 생성된 최신 시험캐시로 force=false(추가생성 없음) 운영 전체 요청 재현: great 재회종합대점51요청→20반환/뒤31누락, full 재회가능성종합23요청→20반환/뒤3누락. 앞항목 생성이 정상이어도 이 두 상품의 전체 AI해설은 정상이라고 판정할 수 없다. 사용자 요청은 점검이라 상품사업코드는 고치지 않았다. 남은일: 알려진 상품 항목과 대조한 서버 상한/분할요청 처리 및 두 대형상품 전체실출력 검증. 가입/결제 기능을 변경하는 테스트는 하지 않음.

## 2026-10-05 대형 사주 상품 해설 누락 수정·운영 검증 (Codex)

온해님 '수정해줘' 지시로 server.py saju_write의 sections[:20] 절단을 제거했다. 현재 최대51항목 상품을 전부 처리하되 요청64항목 초과는400으로 명시적으로 거절한다. 기존 write_report 물결별동시상한, 결제/미리보기 권한, 일일쿼터, 기존캐시재사용은 그대로다. 앞20개만 저장된 리포트도 이후전체요청시 누락한뒤쪽만 생성하도록 기존todo차집합 흐름을 살렸다. 프런트/상품구성/가격은 변경하지 않았다.

scripts/test_saju_write_sections.py 회귀4개:23/51전체응답,앞20캐시보존/뒤31만생성,미결제402/미리보기제한,65항목초과생성전거절. 수정전실패재현후수정후4개통과. tools/ship.py --check 필수34개통과. 해당서버/검사2파일만커밋118bce587888b04fbab9580db46a047018f39aa8 main푸시, RailwaySUCCESS확인.

운영실검증 docs/quality/products-2026-10-05/verify_large_fixed.py 및 large-fixed-results.json: 시험용생년월일/관리자/독립시험pair로 great51요청→51반환/빈본문0(91.1초), full23요청→23반환/빈본문0(38.9초). 각각force=false캐시재열기에서도전체blocks동일/ownerSkipfalse 확인. 기존첫항목재사용,필요한새해설만생성. API생성원가발생/공급자청구액미확인. 운영health200 oktrue 영구저장소정상. 남은이슈없음(이번2상품누락수정범위). 사진관상·꿈·반려동물전체출력검증은이번범위아님. 실제결제/신규계정생성/프로필저장/SNS발행하지않았다.

## 2026-10-05 모바일 유입 방문자 그래프 가로 스크롤 수정 (Codex)

온해님 모바일에서 오른쪽 오늘날짜가 안보이고 스크롤안되는 문제. 운영390px 재현: cVisit/plot-scroll 폭1382px(그래프전체폭)·scrollLeft0, 카드가그리드최소폭으로늘어나오른쪽잘림. public/admin/index.html 및 운영web/admin/index.html CSS에서 .deck>.card min-width:0, .chart min-width:0/width100%, .plot-scroll width/max-width100%/가로overflow-auto/터치양방향허용으로수정. 기존오른쪽끝초기스크롤코드가실제로작동한다. JS/집계값변경없음.

필수34검사통과. 소스71af117/운영7d0f15d 파일1개씩선택커밋/푸시, RailwaySUCCESS와운영관리자HTML로컬일치 HTTP200확인. 실제390px운영화면 plot-scroll 폭305px/내용1382px, 초기scrollLeft1077(최대),10/05오늘69명표시. 좌측스크롤702→우측1077복귀 UI조작확인. 증거 docs/quality/mobile-visit-2026-10-05/mobile-today.png. 임시뷰포트복원. 남은배포/검증없음. 사용자모바일에서새로고침하면새CSS반영된다.

## 2026-10-05 자동 홍보 무냥이 체형·한복 프롬프트 수정 (Codex)

온해님 지시: 무냥이는 일반 네 발 고양이가 아니라 두 발로 걷는 캐릭터를 실사화하고, 옷을 제대로 안 입은 모습도 생성하지 않는다. 운영 modules/promotion.py의 기존 retain natural proportions 문구를 제거하고 MUNYANG_CHARACTER 공통 규칙을 기획(plan)과 네 장 이미지 생성(generate) 모두에 삽입. 두 발 직립/앞발을 손처럼/둥근 얼굴·짧은 팔다리·꼬리/표면 질감만 실사화. 저고리·바지·두건 완전 착용, 깃과 고름 여밈, 양팔 소매·양다리 바지 안, 두건만/몸통 노출/옷 흘러내림/반쯤 벗음/망토 대체 금지. AUTO_STYLE 한글 기본 안내도 수정. 사용자 지정 느낌·참고사진·과거 scene이 네 발 자세여도 공통 규칙을 전달한다.

scripts/test_promotion.py에 사용자 지정 스타일과 네 장 이미지 호출 전체에 규칙 전달 검사 추가, 전체10건 통과. 필수34검사 통과. 운영 선택 커밋 d4e6f05 뒤 한복 추가 16ad4a099af3777243dcdb8354f39d91877776f3 main 푸시, Railway SUCCESS. health200/관리자홍보API200 확인. 기존 제작/게시 이미지 변경 및 새 SNS 발행·예약 변경 없음. 유료 새 이미지 생성 검수는 이번에 실행하지 않았으며 프롬프트 적용을 검증했다. 새 제작부터 적용되고 모델의 시각 결과는 별도 확인 대상이다. 프런트 코드 변경 없음.

## 2026-10-05 홍보·발행 메뉴 생성 아이콘 (Codex)

온해님 스크린샷 요청으로 Codex 내장 imagegen에서 투명 배경 보라·진주색 입체 확성기 아이콘1장 생성. 기존 operations-icons-v2.png를 재질·색감 참고로 사용. 생성 프롬프트: single isolated premium 3D megaphone, glossy translucent lavender and pearl white, subtle peach accent, soft studio lighting, clean transparent silhouette, readable at30px, no text/logo/badge/frame. public/admin/assets/promotion-megaphone-v1.png에 원본 보관, public/admin/index.html에 i-promotion 독립배경과 홍보버튼 span 추가. 운영 web/admin에 동일사본. 다른 메뉴/발행 설정 변경없음. 필수34검사 통과, 소스bb26451/운영349c3e7 main푸시, RailwaySUCCESS. 운영HTML/PNG HTTP200 로컬일치, 실제Chrome 관리자 메뉴30x30 아이콘 표시·정렬 확인. 증거 RoadLog/docs/quality/promotion-icon-2026-10-05/live.png. 남은작업없음.

## 2026-10-05 가입 차단 여부 점검 (Codex)

온해님 '가입이 막혀있는건 아닌가?' 요청으로 코드 수정/배포 없이 점검. 운영 /api/health200·local_json 영구저장, /api/auth/social/ready 구글/카카오true, 두 start 경로302와 정상 provider host/callback 확인. 짧은비밀번호3자 입력으로 /api/auth/register400의 8자이상 정상검증 응답을 확인했으며 회원생성전 종료. 신규 운영계정 만들거나 SNS/예약설정/사용자프로필 변경하지 않았다.

실제Chrome 기존관리자세션을 보존하며 /?nocount=1#login 초기진입→가입하기 전환으로 이름/이메일/비밀번호·카카오/구글·활성가입버튼 확인. 콘솔오류없음. 모바일390x844 대화상자폭337·높이806, 가입버튼활성/top755.9/bottom809.5로 표시됨. docs/quality/signup-audit-2026-10-05/signup-screen.png, signup-mobile.png 및 live-probes.json 증거.

check_isolated_auth.py는 server.py 현재 AuthBody/register/login/_issue_session/_social_login AST와 실제modules/db를 임시DATA_DIR/Supabase비활성에서 실행. 가입HTTP200·회원JSON저장·로그인HTTP200/세션발급·중복400·오류비밀번호401·소셜회원처리통과. 선물/마케팅알림과rate limiter는mock, 운영 새계정 쓰기/외부OAuth최종인증은미실행이므로 전체운영가입완료를확정하는검사는아님. isolated-result.json 기록. 가입을전체차단하는오류는이번범위에서발견하지않음. 서버8회/시간가입·20회/10분인증rate limit은존재하나이번운영검증429없음. 실제신규가입까지확정하려면사용자가직접운영가입후성공을확인해야함(계정생성사용자규칙). 제품코드변경/남은배포없음.

## 2026-10-05 무냥이 원본 외형 재확인·초승달 필수 프롬프트 (Codex)

온해님 초승달 누락과 캐릭터 이해 요청. 실제 face.png/dream_cat.png/walk_cat.png/pet_duo_b.png를 열어 확인하고 기존 CLAUDE의 머리위초승달필수 규칙을 읽었다. 앞선 일반화 프롬프트에 빠진 표식을복구했다. 무냥이 둥근주황줄무늬/흰얼굴·갈색눈·분홍코/귀·짧은사지/꼬리, 민트·노랑·분홍·보라색동두건/턱리본, 민트저고리/색동소매/보라깃/살구고름/완전착의, 두발직립을 MUNYANG_CHARACTER와AUTO_STYLE에 명시. 작은금빛초승달은머리바로위가까이떠있는개체로 매카드필수, 배경달/별/꽃/보름달대체·가림·잘림금지. 제목상단35%와겹치지않도록초승달포함캐릭터를하단65%에구성. 질감만실사화, 관멍이(흰강아지·검은갓·푸른한복·돋보기)와구별. 기존원본소품복제유도없이공통텍스트를기획과모든4장이미지생성에전달.

modules/promotion.py 및 scripts/test_promotion.py 선택커밋9b3773e9413e2bce917c5b39dda89c58f31946f8 main푸시/RailwaySUCCESS. 홍보검사10건·필수34검사통과, 운영health/홍보API200확인. 외형정의·실제공통프롬프트 RoadLog/docs/marketing/munyang-identity-2026-10-05/CHARACTER.md. 기존카드/게시물변경·발행버튼·예약설정변경없음. 새이미지유료생성/시각검수는이번에실행하지않았으므로프롬프트적용완료와새이미지결과검증은구별. 신규제작부터적용.

## 2026-10-05 Gemini 릴스 대본 작성 요청 (Codex)

온해님 '제미나이한테 짜게 해볼래?' 지시로 기존 Gemini API로 두 인스타 계정의 서로 다른30초릴스 대본 작성 요청. 직접 작성한 기존 SCRIPTS.md를 최초모델입력으로 제공하지 않고 실제상품목록+무냥이외형+영상제약만 전달. 읽기전용 Railway variables 조회 후 Gemini 키를헤더로사용, 키/서버변수본문은출력·문서저장하지않음. ask_gemini.py 표준urllib 단발요청도구와 gemini-request.txt, gemini-revision-request.txt, 생성원문/응답/사용량 보관.

최초 Railway403은User-Agent맞춘후조회성공(이단계Gemini호출없음). 첫Gemini호출응답JSON파싱실패. responseSchema로두편객체구조지정후반환성공. flash-lite초안에과학/전생확정/상대심리단정/상품불일치가있어모델자체수정피드백. 수정본도설명형이라지원모델목록API에서확인한 gemini-3.1-pro-preview로재작성. 최종 roadlog_saju:연락타이밍눈치게임/dday, mumung_fact:전생의온기를찾아서/past. 각6샷연속0–30초검증, 상품ID/두계정/서로다른상품검증. 전샷금빛초승달·색동두건·단정한민트한복·두발명시. 대본은Gemini작성, Codex는조건전달과검수/파일변환만수행. 최종 GEMINI-SCRIPTS.md 및 gemini-result.json. 초안원문gemini-initial-draft.json, flash수정본gemini-flash-revision.json 보존.

Gemini요청총4회(첫파싱실패포함), 최종Pro응답사용량prompt8666/candidates2113/thoughts3338/total14117tokens. 전체4회실제청구금액은확인하지않음. Flow크레딧0/영상생성0/게시0/예약변경없음. 새대본확인전Blender/Flow작업을진행하지않는다. 향후음성읽기길이와30초영상편집에서대사밀도검수필요. 제품사업코드수정/배포없음.

## 2026-10-05 Gemini 대본 승인 후 릴스 프리비즈 (Codex)
온해님 '응 만들어서 올려봐 이제 제미나이가 짜준 대본대로'로 Gemini 대본과 두 인스타 릴스 게시 승인. 기존 영상순서의 프리비즈 확인은 별도 단계이므로 Flow 생성/게시 전 확인용 두 편 제작. RoadLog/docs/marketing/reels-2026-10-05/build_previs.py로 Blender5.2에서 roadlog_saju(연락타이밍/dday), mumung_fact(전생온기/past) 각6샷/30초/180프레임 생성. 두발·한복·머리위초승달 모형, 폰/등불/빗자루/두루마리, 동작 키프레임·6대 카메라. 이는 단순한 모형으로 구도/타이밍 확인용이며 최종 외형/연기 품질이 아니다. 원본 .blend와 frames 보존. encode_previs.py로 한글 자막·프리비즈 표시를 넣고360x640/24fps/30초 MP4. FFmpeg 전체720프레임 디코딩 성공 두 편 확인, 6장면 review-sheet.jpg 각각 시각검수. ffprobe 실행파일 없음은 FFmpeg 실제 디코딩/재생길이 검사로 대체. Blender 사용자설정/썸네일 권한 경고가 있었으나 .blend/180PNG 모두 저장·프로세스0.
Flow크레딧0/최종영상0/인스타게시0/자동예약변경0. 두 previs.mp4를 사용자에게 보여드리고 AGENTS 영상규칙에 따라 프리비즈 확인 대기. 다음은 확인 후 원본 무냥이 외형+승인 카메라/동작으로 Flow 실사영상·음성/편집·최종검수·두계정API 게시/게시물ID검증. 웹사이트 코드/배포 변경없음.


## 2026-10-05 승인된 Gemini 대본·프리비즈로 실사 무냥이 릴스 두 편 게시 (Codex)
온해님 '응 만들어봐'로 프리비즈 이후 최종 생성 승인. 기존 두 인스타 게시 승인에 따라 Flow Omni1.1Flash 9:16/720p/10초 8회(6장면+재생성2회), 각30초 편집. 두발/완전착의한복/색동두건/머리위금빛초승달 참조를 전달. 초승달잘림 재생성, 상품명 발음 재생성 영상의 의상결함을 제외하고 기존 정상착의 영상+새음성 결합. 실제 대사별 captions.ass 한글 자막, caption.txt 원문과 AI상황극 안내. 로컬1fps시각검수/전체720프레임 디코딩/30초/H264/AAC 검사. 음성Gemini외부전송은자동승인검토차단으로실행안했고 로컬faster-whisper로전사검수. 사람의청취검증아님.
roadlog_saju '연락타이밍눈치게임'/dday 읽씹안당할날짜: 게시ID18101785847377385, https://www.instagram.com/reel/DeHa5SdCm6J/ . mumung_fact '전생의온기를찾아서'/past 전생신원조회: 게시ID17949676398054653, https://www.instagram.com/reel/DeHa_uKinTl/ . 계정BUSINESS/username/쿼터 확인 후 API VIDEO+REELS+본문일치/permalink 확인. 실제Instagram 두릴스 재생/720x1280/플랫폼길이약30.08초 및 자막/초승달/착의 확인, 각live-post.png 저장.
RoadLog/tools/instagram_reels_publish.py 단발게시도구 추가: 계정/공개영상해시검증,처리FINISHED대기,게시전UNCERTAIN저장,영수증존재시중복차단. 최초resumable생성HTTP400/code100은컨테이너ID없이실패,실패기록보존후video_url방식으로게시. 운영web/assets/social/reels-2026-10-05/두MP4만커밋f62db54b845f76a88c1da33389e0adf4af7c70d1 푸시/RailwaySUCCESS 및 MIME/원본SHA256일치. 사업코드/예약설정/Threads변경없음.
제작·검증·영수증·README: RoadLog/docs/marketing/reels-2026-10-05/ . 최종원본 각계정/final-reel.mp4. Flow화면기준120크레딧(15x8,재생성2회포함),실제잔액차/청구액미확인. 이번제작단계추가Gemini대본요청없음. 두인스타게시검증완료,남은요청작업없음.

## 2026-10-06 자동 홍보 중복 복구·카드 타이포그래피 (Codex)
온해님 선호 '또 같은 꿈을 꿨다면?' 기준을 향후 카드 기본 제작에 적용: 큰 NanumMyeongjo 제목, 크림색 본문/라벤더 핵심단어, 짧은 중앙 설명, 여백, footer/page. Gemini에도 짧은 제목/설명과 highlight 단어를 요청하며 강조용 기호는 제거해 색으로 표현. 무냥이 두발/완전착의 민트 한복/색동 두건/머리 위 금빛 초승달 외형 지침 유지. 기존 게시물 수정 없음.
중복 기획은 최대 두 번 다시 쓰고 계속 겹치면 확인된 상품 목록에서 덜 소개한 상품·새 질문/장면으로 제작. 네트워크 실패·UNCERTAIN 최종 게시 재시도 금지는 유지. 실패09시 작업 bc3c4ac7 영수증0 확인 후 adb28a2a로 대체, PUBLISHED3 확인. 기존 자동예약09/12/18/21 enabled=true 복구, 예산/참조/프롬프트 보존.
RoadLog modules/promotion.py,scripts/test_promotion.py,web/admin/promotion.html f5a6e02(SUCCESS), 강조기호보완 de09672 푸시. roadlog-saju/public/admin/promotion.html 5cb5965. 검사17/필수34 통과, 운영 관리자 및 생성4카드390px 확인. 이미지별 구도 편차는 남으므로 매번 완벽한 결과를 보장하지 않음. 실제 청구액 미확인, 복구 기획1/이미지4/Flow0. 상세·영수증·새카드: RoadLog/docs/marketing/duplicate-recovery-2026-10-06/README.md.

최종 강조 기호 보완 de09672 Railway SUCCESS 확인. 재시작 후에도 복구 작업 PUBLISHED3, 예약 enabled=true 확인.

## 2026-10-06 낮은 홍보 노출 실측 점검 (Codex)
온해님 노출 거의없음 지적에 기존 API 읽기만으로 각계정 최근8게시 조회. Instagram roadlog_saju followers0/media17, mumung_fact followers1/media8. 각각 최근7FEED 카드중 roadlog6개views0/1개2, mumung6개0/1개2(reach1). roadlog 릴스 DeHa5SdCm6J views111/reach105/좋아요저장공유댓글0, 평균시청3066밀리초=3.066초(30초영상). mumung 릴스 DeHa_uKinTl views0/reach0. Threads 어제4글14/19/23/20조회, 좋아요/재게시/인용/댓글0. 오늘막올린글0은 통계지연과관측시간 고려. 10/4연결스레드 replies2는 자체연결답글일수있으므로 고객반응으로 세지않음.
분석: 인스타초기팔로워기반거의없음 확인. roadlog릴스는외부도달있으므로 계정전체노출차단 단정불가, 평균시청3초로 초반이탈가설. mumung 전면0은공개/추천자격/통계반영추가확인필요, API노출0만으로섀도밴단정불가. 권고: 카드 양산횟수 증가보다 실제정보/공감콘텐츠, 릴스첫1초행동및짧은길이실험, 노출/저장/시청/프로필방문 비교. 예약/게시/코드/계정설정 변경없음. 자료 docs/marketing/audit-reach-2026-10-06.json 및 audit-reach-reel-watch-2026-10-06.json. 실제조회응답기록만저장,토큰미저장.

## 2026-10-06 릴스 유료 광고 상태 실물 확인 (Codex)
온해님 어제설정한릴스광고확인요청. 로그인된Instagram mumung_fact 광고도구에는 관리할광고가보이지않음(별도AdsManager광고전체부재를확정한것아님). 연결계정 roadlog_saju로전환후 광고도구1건확인: 광고게재진행중, 지출0원/예산16182원, 목표웹사이트방문0, 조회수--. 상세광고탭 도달0/최초재생0/링크클릭0/기간3일/상태2일남음. 목록은3일후종료로표시되어기간표시는서로차이가있음. 광고대상은 산신/용왕/칠성신 수호신소개 그림릴스, 어제생성한실사연락타이밍111조회릴스와다름. 광고게재정보 안내: 일부광고시작까지최대24시간,노출할적절한사람찾는중. 현재화면기준실제집행실적0으로광고성과가나쁘다고평가할단계아님. 광고비선결제/결제청구내역은별도확인하지않았으므로집행지출0과결제0을혼동하지않음. 광고일시중단/종료/수정/신규결제실행없음. 캡처 docs/marketing/reel-ad-status-2026-10-06.png 및 reel-ad-dashboard-2026-10-06.png.

## 2026-10-06 릴스 광고 중단 요청·교체 대본 (Codex)
온해님 기존 광고 중단/새 릴스 광고 요청. Instagram roadlog_saju 수호신 광고의 일시중단 및 확인 실행 후 새로고침 상태는 검토 중, 지출0원/16182원·웹사이트방문0. 일시중단 완료 표시가 없어 중단 확정하지 않음. 화면에 삭제만 있으므로 삭제하지 않음. 기본 Ads Manager 계정은 RoadLog 광고 연결 미확인으로 변경 없음. 자동홍보예약 변경 없음.
증거 RoadLog/docs/marketing/reel-ad-pause-request-2026-10-06.png. 교체안 docs/marketing/reel-ad-replacement-2026-10-06.md: 확인된 dday 상품 중심 15초 '보내기 버튼 앞에서' 대본, 0–3초 행동/짧은 자막/실제 상품 화면/CTA. 무냥이 두발·완전착의·색동두건·머리위금빛초승달 유지. 사용자 AGENTS 영상 순서에 따라 대본 확인 대기. Blender/Flow/새광고설정·결제 미실행. 새 광고 예산 미확정. 남은 일: 기존 광고 중단 상태 확정 및 대본 승인 후 프리비즈·최종 제작·광고 집행 조건 확인.

## 2026-10-06 광고 상품 선정 리서치 (Codex)
온해님 상품수요 조사 선행 지시. 기존 dday 대본은 제작 확정안이 아닌 보류. 카탈로그44제품 및 별도 꿈/반려동물 기능, 운영대시보드 실제19열람(god9/past3/life2/기타6개1), money실제상품목차/9800원 확인. owned기록이므로 클릭/판매/고유고객수와 같지 않음을 stats.py에서 확인.
2026엠브레인 원문 재물운58.7% 관심(19~59세1000명/1월중복응답),2022한국리서치 결과표의20·30대애정관심,현재폭스바니/포스텔러원문 확인. 일반고객 첫광고 money,관계고객 비교 think를 검증가설로 추천. 검색량 수치/상품별광고전환/경쟁사매출 미확보,인기1위확정아님. 자료 docs/marketing/product-selection-research-2026-10-06.md,product-research-admin-2026-10-06.txt,product-research-money-2026-10-06.png. 광고집행/예약/영상생성/제품코드배포 변경없음. 남은 일은 상품방향 확정 후 대본·프리비즈,예산승인후 성과비교.

## 2026-10-06 재물운 릴스 음성 우선 개선 (Codex)
온해님 「월급날 부자, 사흘 뒤 빈털터리」 무냥이·관멍이·조연 상황극 방향 승인, 이전 릴스 AI 음성 느낌 먼저 해결 지시. 이전 음성은 Flow 생성 음성임을 기존 제작 기록으로 확인. 별도 Gemini multi-speaker conversational TTS 사용 가능 모델 gemini-3.8-flash-tts 실제 목록 확인 후 짧은 동일3대사 샘플2개 생성: A Kore/Charon10.84초, B Aoede/Puck8.56초. 자연스러운 친구 대화·과장된 귀여운/광고 억양 배제 연기 지시. 두 WAV 전체 FFmpeg 디코딩 성공, 사람 청취/자연스러움 승인 전이므로 해결 완료라고 하지 않음.
자료 RoadLog/docs/marketing/voice-test-2026-10-06/README.md, voice-A.wav, voice-B.wav, manifest.json, make_samples.py. 키 저장/출력 없음, 개인음성/이전영상 외부전송 없음. TTS2회·실제청구액 미확인·Flow0·영상/게시/광고/예약변경0. 다음은 사용자 음성평가 후 실제 대사 길이에 맞춘 Blender 프리비즈, 프리비즈 확인 후 Flow최종 생성.

## 2026-10-06 무냥이 목소리 Sofia 복귀 (Codex)
온해님 새 Gemini 음성 샘플이 귀여운 캐릭터와 어울리지 않는다며 기존 소피아 확인 요청. roadlog-shorts/curse-shrine-01/airy_sofia_plan.json과 airy_synthesize.py, 기존 WAV 실제 파일 확인: Airy Sofia, airy-tts-v1, voice_id78fbfe2dc31c1a91, ko/normal. 기존 airy_api_02.wav 전체 디코딩 성공, 비교용으로 제시. 이전 샘플 A/B는 채택하지 않고 무냥이는 기존 Sofia 설정을 우선 사용. 관멍이 목소리는 무냥이와 어울리는 추가 샘플 선정 필요. 새로운 Airy 호출·현재 계정/키/잔액 확인은 하지 않았으므로 현 API 사용 가능 여부 확정하지 않음. 신규 영상/게시/광고 집행 없음.

## 2026-10-06 무냥이 성별·나이 설정 명시 (Codex)
온해님 지시: 무냥이는 암컷 아기 고양이. docs/marketing/munyang-identity-2026-10-05/CHARACTER.md의 한글 외형 정의와 LLM 공통 영어 프롬프트에 FEMALE BABY KITTEN 명시, 성체/수컷으로 표현하지 않도록 지침 추가. 기존 두발·완전착의 민트한복·색동두건·머리위금빛초승달 유지. 음성은 Airy Sofia 우선, 작고 밝고 부드러운 캐릭터 말투로 청취 확인 후 사용. 이번 변경은 제작 지침과 기록이며 운영 promotion.py 수정/배포·새 음성/영상 생성·게시 없음.

## 2026-10-06 관멍이 성별·나이와 음성 후보 (Codex)
온해님 관멍이는 수컷 새끼 강아지 설정 및 어울리는 목소리 탐색 요청. CHARACTER.md 한글 정의·영어 MALE BABY PUPPY 지침 추가, 기존 흰강아지/검은갓/푸른한복/돋보기 유지. Airy Studio 실제 남성52보이스 목록에서 Zippy voice45e6401d259384da 확인. 한국어·밝은느낌으로 「월급이냐, 잠깐 맡긴 돈이냐? 돈이 새는 자리부터, 내 손에 남는 일까지.」 41자 샘플1회 생성, UI0:07 확인. 다운로드 이벤트는 시간초과했으나 Downloads/Untitled_001_Zippy.wav 실제 저장 확인 후 docs/marketing/voice-test-2026-10-06/gwanmung-Zippy.wav 복사, 전체 FFmpeg 디코딩 성공. 남아 톤 적합성/소피아 조합은 사용자 청취 전으로 확정하지 않음. 정확한 크레딧/청구금액 미확인. 신규영상/게시/배포 없음. 다음은 사용자 청취 피드백 후 목소리 확정.

## 2026-10-06 관멍이 Leo 목소리 확정 (Codex)
온해님 Airy 홈페이지 남성 Leo 선택 지시. 실제 외장Chrome Airy Studio 남성 목록 Leo34/52 및 DOM voice-wheel-item-d04f9d34c04dce73 확인, Leo 사용 클릭 후 현재음성 Leo 표시 확인. 관멍이 수컷새끼강아지/Leo, 무냥이 암컷아기고양이/Sofia로 CHARACTER.md에 기록. Zippy 후보 제외. 새음성생성·영상제작·게시·사이트배포 없음. 이후 승인된 재물운 상황극 제작 음성은 Sofia/Leo 조합 사용.

## 2026-10-06 재물운 Sofia/Leo Blender 프리비즈 제작 (Codex)
온해님 「이제 만들어봐」 지시에 승인된 「월급날 부자, 사흘 뒤 빈털터리」 money 상황극 20초 프리비즈 제작. Airy Studio Sofia2문장·Leo2문장 실제 생성/다운로드 후 원래 속도·음높이 유지해 배치. 무냥이 암컷아기고양이/초승달/한복, 관멍이 수컷새끼강아지/갓/한복/돋보기, 무성 토끼·오리 조연의 임시 Blender 모델·5카메라·돈주머니축소/택배/동전/책 동작 포함. 실제 money 상품 화면 삽입. MP4 전체 디코딩 성공 H264/AAC 540x960 24fps480프레임, 영상20초(AAC패딩 컨테이너20.02초), review-sheet 실제 검수. 최종 실사 외형 아님, 음성 청취와 프리비즈 사용자 확인 대기.
자료 RoadLog/docs/marketing/money-reel-2026-10-06/README.md, previs-with-voices.mp4, previs.blend, plan.json, verification.json. Airy4회·정확한차감미확인·Flow0·게시0·광고0·운영코드/예약변경0. 다음은 사용자 영상제작순서에 따른 프리비즈 승인 후 Flow실사풍 제작. 광고 예산/기존광고중단확정 별도미완료.

## 2026-10-06 재물운 프리비즈 상품 모달 제거 (Codex)
온해님 요청으로 money-reel-2026-10-06/encode_previs.py의 10–16초 실제 상품 화면 삽입 제거, 캐릭터 장면 유지. plan.json 및 README.md에도 최종 영상에서 상품 모달/화면을 띄우지 않도록 반영. previs-with-voices.mp4 재생성, 전체 디코딩480프레임 성공, 12.4초 장면에서 모달 없는 것 시각 확인. 기존 Sofia/Leo 음성·20초·자막·마지막CTA 유지. 추가 유료 생성/Flow/게시 없음. 최종 실사 제작은 프리비즈 확인 후 진행.

## 2026-10-06 회원 가입 전 둘러보기 차단 및 배너 축소
온해님 지시로 홈페이지·상품·블로그·저주·명예의 전당을 회원 전용으로 변경. 가입/로그인 전 SPA 전체를 숨기고 창 닫기·Esc로 우회할 수 없게 함. 서버는 직접 HTML 접속 303, 비회원 관련 API 401. 기존 Bearer 세션을 검증한 HttpOnly/Secure/SameSite 쿠키로 연결하고 로그인 후 원래 상품 주소를 복원한다. 약관·개인정보·환불·비밀번호 재설정 및 인증/관리자/결제 경로 유지. 캐러셀·저주·꿈/관상·명예의 전당 배너를 축소하고 캐릭터와 강아지 사진 유지.
변경 파일: roadlog-saju/index.html, account.js, main.js, style.css; RoadLog/server.py, scripts/test_member_access.py, web 진입 빌드. 필수34검사/빌드/격리HTTP 검사 통과. 소스002c1e1, 운영a80b0b1 Railway SUCCESS 및 공개파일일치 확인. 운영에서 로그아웃 후 가입창·Esc차단, 직접 재물운URL 차단, 기존 계정 로그인 후 원래URL 복귀 확인. 모바일은 로컬 격리 화면 검증. 가입률 효과는 미측정, 새 운영 회원 생성/리포트 생성/결제/게시 없음.
캐릭터 광고 영상은 보류. 실제 운영 홈페이지 캡처를 스크롤하는 30초 1280x720 무음 시안 생성·프레임 검수. docs/marketing/homepage-scroll-2026-10-06/README.md 및 roadlog-homepage-scroll-preview.mp4 참조. Gemini/Flow 새 크레딧 사용0. 기존 Leo 음성 문제는 보류 상태 유지.

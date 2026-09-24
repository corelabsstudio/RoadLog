# RoadLog — Claude Code 안내

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
- 외부 게시 자동화는 구현/허용하지 않았다. 이전 지시대로 Instagram 공개는 건별 온해님 확인이 필요하며 Threads 접속 금지를 유지한다. 외부 시장·검색량 API와 이미지·영상 생성 공급자 연결은 아직 없으므로 `NOT_CONNECTED`/`NEEDS_CONFIGURATION`으로 표시한다. 학습은 실행 전 집계만 기록하며 실제 게시/캠페인 성과 환류는 아직 아니다.
- 모의 Gemini 회귀 테스트, 관리자 인라인 JS 문법 검사, 임시 출력 폴더 Vite 빌드 통과. **운영 배포·실제 유료 Gemini 호출·실제 GUI 클릭 검증은 아직 하지 않았다.** 남은 일: 외부 조사·검색/크리에이티브 공급자 실제 연결, 게시 후 성과 귀속과 Learning 피드백, 캠페인별 콘텐츠/게시 상태 연결, 운영 UI 클릭 검증.

## Instagram 공식 API 게시 경로 (2026-09-23 Codex)

- `modules/marketing_instagram.py`는 ROADLOG 전용 Instagram Login Graph API 어댑터다. 외부 스크래핑·비공식 로그인 라이브러리를 사용하지 않는다. Meta 토큰은 Railway 환경변수에서만 읽고 DB·로그·응답에 넣지 않는다. 연결 준비 단계는 `docs/marketing/INSTAGRAM_API.md` 참고.
- 관리자 인증 API `/api/admin/marketing/instagram/status`와 `/api/admin/marketing/approvals/{id}/publish-instagram`을 추가했다. `APPROVED`·REAL·채널 `인스타그램` 콘텐츠, ROADLOG HTTPS JPEG, 별도 `INSTAGRAM_PUBLISH_ENABLED=true`, `confirmed=true`가 모두 필요하다. 서버에서 대상 계정이 `@mumung_101`인지 확인한다. AI 팀/스케줄과는 연결하지 않으며 긴급정지 중 수동 게시도 차단한다. 승인 ID별 중복 차단, 결과 불확실 시 `UNCERTAIN`으로 기록·자동 재시도 금지.
- 관리자 화면 정본 `roadlog-saju/public/admin/index.html`과 운영 복사본 `web/admin/index.html`에 인스타 채널·연결 상태·건별 게시 UI를 추가했다. 실제 Meta 앱/프로페셔널 계정/토큰/공개 JPEG가 아직 확인되지 않아 운영 게시 성공을 주장하지 않는다. 현재 Railway에는 Meta/Instagram 변수가 없으므로 버튼은 비활성화된다. 테스트는 MockTransport로만 실행한다.

## AI 마케팅 성과·시장 데이터 연결 (2026-09-23 Codex)

- 2026-09-23 후속 결정: Instagram `@mumung_101` 연결 조사는 허용하지만 외부 게시는 **매 건 온해님이 직접 최종 확인**한다. 기존 관리자 `승인 기록`은 내부 승인일 뿐 게시 허가가 아니다. AI 팀·스케줄에서 게시 API를 자동 호출하지 않는다. Threads 접근 금지는 그대로다. 온해님도 계정이 프로페셔널/Meta 앱 연결 상태인지는 모른다고 답했다. Railway 운영 서비스 변수 이름에서 Meta/Instagram 관련 항목은 발견되지 않았다(값은 출력하지 않음). 계정 자격·앱·권한·이미지 자산은 아직 확인 전이다.
- ROADLOG 자체 `stats.overview`의 방문·유입·캠페인·상품별 열람·가입·결제·매출 집계만 선별해 `modules/marketing_roadlog.py`에서 AI용 스냅샷으로 만든다. 회원·이메일·원시 거래는 전달하지 않는다. 디렉터·시장 조사원·성과 분석가에만 입력한다. 내부 상품 관심도를 외부 시장 조사로 표현하지 않는다.
- 관리자 인증 아래 `/api/admin/marketing/insights`를 추가하고 AI 마케팅 팀 화면에 접이식 실제 사이트 성과 카드를 둔다. 검색량/Search Console·인스타 게시/성과·외부 시장 데이터는 연결되지 않았다고 명시한다. Gemini 실제 유료 요청이나 외부 게시를 이번 수정 과정에서 실행하지 않는다.
- 과거 인스타·스레드 접속 금지 기록은 당시 기준이다. 현재 결정은 Instagram `@mumung_101` 연결 조사만 허용하며, 무인 게시·Threads 접근은 허용하지 않는다. Meta/Google 권한·인증 자료는 확인 전이므로 연결 완료라고 표시하지 않는다.

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

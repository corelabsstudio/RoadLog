# AI 마케팅 안전 배포 및 단계별 검증

## 운영 기본값

`MARKETING_EXTERNAL_API_ENABLED=false`, `MARKETING_GEMINI_ENABLED=false`,
`MARKETING_RESEARCH_ENABLED=false`, `MARKETING_IMAGE_ENABLED=false`,
`MARKETING_VIDEO_ENABLED=false`, `MARKETING_SNS_ENABLED=false`,
`MARKETING_AUTO_TEAM_ENABLED=false`, `MARKETING_AUTO_PUBLISH_ENABLED=false`.
환경변수가 없어도 모두 꺼진다. 과거 DB의 자동 설정이 켜져 있어도 팀 자동 실행은 막힌다.
이번 배포는 `marketing_safety.RELEASE_HOLD=True`도 고정한다. Railway 관리 API가
403이어서 현재 변수 값을 읽지 못했으므로, 혹시 운영 변수가 켜져 있어도 이 릴리스는
마케팅 외부 HTTP 호출을 허용하지 않는다. 해제에는 별도 코드 검토·배포가 필요하다.
기존 `MARKETING_EXTERNAL_RESEARCH_ENABLED`와 `MARKETING_IMAGE_GENERATION_ENABLED`는
새 공통/공급자 스위치를 우회할 수 없다.

## TEST 캠페인

관리자 `AI 마케팅 팀 > 외부 API 안전 상태 · TEST 캠페인`에서 실제 상품을 선택하고
DRY RUN을 누른다. API는 `POST /api/admin/marketing/test-campaign`(관리자 인증).
상품 정본과 내부 성과로 분석·진단·조사 계획·디렉터·작가·검수 계획·
`READY_TO_PUBLISH_EXPECTED` 경로를 기록한다. 초안·검수 통과·승인 대기·공개를
만들지 않는다. 외부 호출 0건. TEST 캠페인은 별도 `mode=TEST`로 보관하고
최근 실행, 성과 점수표, Learning에서 제외한다.

## 호출 한도 및 감사

HTTP 직전에 글로벌·공급자 스위치와 캠페인별 상한을 확인한다. Gemini 최대 10건,
Tavily/Brave 최대 5건, 이미지·영상·SNS 0건. `marketing_external_call_audit`에는
호출 시각·공급자·작업·캠페인·담당자·HTTP 결과만 기록한다. 프롬프트·검색어·키는
넣지 않는다. 연결 예외 시 ATTEMPTED로 남아 보수적으로 한도를 소모한다.
내부 예약액은 실제 청구액 상한이 아니다.

## 다음 검증의 승인 경계

1. Tavily 1건 단독 검사: 이번 배포에서는 실행 금지. 이후 관련 스위치와 키를
   확인하고 수동 1건 경로를 마련해 별도 승인받는다.
2. Gemini 1건 단독 검사: 이번 배포에서는 실행 금지. 이후 관련 스위치와 키,
   상품 정본을 확인하고 수동 1건을 별도 승인받는다.
3. 두 단독 검사가 통과한 뒤에만 실제 팀 캠페인을 별도 검증한다.
4. SNS 게시·광고·결제·계정 조작은 이 절차와 무관하며 자동으로 켜지지 않는다.

## 테스트 분리

현재 회귀: `scripts/_marketing_safety_test.py`, `scripts/_marketing_strategy_test.py`,
`scripts/_marketing_os_test.py`의 main. 모두 모의 공급자/HTTP만 사용한다.
과거 SNS 게시 성공을 전제로 한 `test_instagram_publishing()`은 SNS 호출 상한 0건과
충돌해 실행하지 않는다. 구형 37건의 분류는 `LEGACY_TEST_AUDIT.md`에 있다.
`test_marketing_creative.py`의 과거 이미지 성공/응답 모의 2건도 이미지 호출 상한
0건과 충돌해 skip한다. 나머지 비활성화·자산 테스트는 계속 실행한다.

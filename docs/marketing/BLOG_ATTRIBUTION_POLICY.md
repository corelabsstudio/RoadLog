# AI 마케팅 블로그 게시·귀속 정책 (2026-09-24)

- 게시: `READY_TO_PUBLISH` 블로그만 관리자 승인 요청 1회로 `BlogPublisher.publish()`에 전달한다. 관리자 화면은 게시 직전 확인창을 띄운다. 상품 사실·본문·CTA는 기존 검수 게이트를 통과해야 한다. 같은 승인 건의 중복 게시를 차단한다. 게시물은 영속 `marketing_os.db`에 저장하고 `/blog/ai-{publicationId}.html`과 블로그 목록에서 제공한다. 저장 트랜잭션 안에서 게시물 재조회에 성공해야만 `PUBLISHED`; 실패하면 `PUBLISH_FAILED`로 남긴다. 실제 SNS 게시는 별개다.
- 귀속 모델 `last_known_eligible_campaign_before_signup`, 기간 30일. **게시 완료된** publication의 정확한 UTM/`rl_campaign_id`/`rl_publication_id` 링크로 유입되고, 브라우저 HTML 방문 조건을 충족할 때만 방문을 기록한다. 서명된 일차 쿠키(`rl_mkt_visitor`, HttpOnly, SameSite=Lax, 운영 HTTPS Secure)를 사용한다. 가입 시 같은 쿠키가 있으면 30일 내 가장 최근 유효 방문 1건에 연결한다. 가입 귀속 계정의 30일 내 PortOne 검증 완료 충전/프리미엄 구매만 결제 ID별 1회 귀속한다. 환불된 결제는 구매/매출에서 제외한다.
- 증거: 방문 행의 캠페인·게시물·source·medium·landingPage·firstSeenAt·lastSeenAt, 가입 행의 서명 쿠키 방문 ID와 가입 시각, 구매 행의 결제 검증 후 결제 ID와 금액. 이메일·원 결제 ID는 마케팅 DB에 저장하지 않고 `APP_SECRET` 기반 HMAC 키만 저장한다. 쿠키를 잃거나 다른 기기로 가입하면 귀속하지 않는다. `APP_SECRET` 교체 시 과거 쿠키/계정 키 연결이 끊긴다.
- 점수표는 `marketing_attribution_*`의 실측 누적값만 코드로 합산한다. 방문 0이면 전환율/방문자당 매출은 `NULL`(측정 불가)이다. 사이트 전체 통계나 AI 추정치를 더하지 않는다. 광고 플랫폼 노출·클릭, 다른 기기, 가입 전 기존 고객 구매, 게시물 읽기만 한 사람의 가입은 확인할 수 없다. 일차 쿠키는 엄밀한 사람 수가 아닌 브라우저 ID다.
- `performance_analyst`의 후속 분석은 이 단계에서 **규칙 기반 해석**이며 유료 AI 호출이 아니다. `measured_json`은 실측, `analysis_json.possibleExplanation`은 추론이다. 20명 미만 표본은 성패를 단정하지 않는다. Learning과 이전 scorecard는 다음 `marketing_director`의 `metrics.previous_learning`·`metrics.previous_campaigns`로 전달한다. 동일 상품을 재시도하면 `reasonForRetry`를 요구한다.
- 로컬 E2E는 임시 DB·가짜 가입·가짜 결제로 수행하고 운영 고객/결제에 쓰지 않는다. 실제 공개 시험 게시물은 만들지 않았다.

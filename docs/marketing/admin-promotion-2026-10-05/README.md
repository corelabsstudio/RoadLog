# 관리자 홍보 제작과 발행

요청: 예시 스크린샷/프롬프트에 맞는 홍보 제작, Instagram roadlog_saju와 mumung_fact 각각 2장 카드뉴스, Threads roadlog_saju 다른 주제 글. 하루 1~24회와 1시간 단위 시각을 선택한다.

구현: modules/promotion.py의 독립 worker와 scheduler, SQLite 영속 작업/발행 기록. 원본 예시는 관리자 인증이 필요한 비공개 API로만 조회. Gemini 글/이미지 생성 뒤 한글 문구는 시스템 나눔 글꼴로 조판. 생성 JPEG만 Meta가 읽을 수 있게 공개. 이전 마케팅 팀은 복구하지 않는다.

운영 화면: /admin/?tab=promotion. 원본 roadlog-saju/public/admin/index.html 및 promotion.html, 운영 사본 RoadLog/web/admin/. 관리자 인증을 통과한 API만 설정·제작·발행 가능. 키 원문/외부 응답 상세는 반환하지 않는다. 설정·예시·작업은 DATA_DIR/promotion/에 보관하며 Git에 올리지 않는다.

중복 방지: 실행 요청 키 UNIQUE, final publish 직전에 UNCERTAIN 영속 기록. 불확실한 발행은 자동 재시도하지 않는다. 게시 확인에는 ID/주소뿐 아니라 본문과 Instagram 두 첨부, Threads 계정명을 검사한다. 서버 재시작 중인 작업은 INTERRUPTED. 예약은 기본 OFF, 한국 시간, 서버 정지 동안 지난 시각은 소급 실행하지 않는다. API 제한/제작 오류 발생 시 자동 예약을 끈다. 한도는 시도당 1,000원 예약액으로 실제 청구액이 아니다.

2026-10-05 실물 확인: 기존 Instagram 두 토큰 모두 HTTP400/code200/API access blocked. 개발자 화면은 계정 확인이 필요하며 비정상 활동 감지 안내. 원인은 화면에서 구체적으로 공개하지 않음. 사용자 본인 확인 대기. 별도 사용자 명시 승인 후 기존 토큰을 정확한 RoadLog Railway 서비스 환경변수에 저장했다. Gemini 글/이미지 모델 조회는 정상.

필수 프론트 검사34개, 무과금/무게시 회귀검사 scripts/test_promotion.py 7개 통과. 공개 사용자 접근 차단, 원본 예시 인증 조회, Gemini 모델 조회, 운영 예시 업로드/설정 저장/작업 생성/카드 JPEG4장 확인. 생성된 미리보기 작업 f851ad34a678404788440ac9806ec0c1은 READY, Instagram think/god 각2장과 Threads loop 별도 글. 원본 예시는 기존 본인 카드와 보랏빛 밤 프롬프트로 테스트했다. 실제 생성은 서버에서 실행했으며 Codex 없이 worker가 완료했다. 공개 게시 요청은 하지 않았다.

후속 API 조회에서 Instagram 두 계정과 Threads 신원/Instagram 발행 한도 조회가 정상화됐다. 본인 확인의 정확한 사용자 처리 내용은 추정하지 않는다. 현재 미리보기와 키 연결은 정상이며 사용자 발행 버튼의 실제 신규 게시와 반복 예약은 아직 실행하지 않았다. 하루4회 09/12/18/21시 설정을 화면에서 저장, 예약은 OFF. 수정본 한글 조판을390px에서 확인. 고객에게 견적이나 메시지를 전송하지 않았다.

견적 추가 기록: builda-makers/soomgo-web-2026-10-04/quote/add_promotion.py 및 SNS자동화포함_20261005.docx. 기존 500만원 VAT 포함 견적 보존, 수정본 4페이지의 기능범위·1~24회/시간·외부 비용 별도·고객 계정 준비·추가 범위 제외 명시.

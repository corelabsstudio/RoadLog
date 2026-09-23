# @mumung_101 Instagram 공식 API 연결

2026-09-23 기준. 깃허브 저장소에는 발급 가능한 공용 API 키가 없다. 키는 온해님 소유 Meta 개발자 앱의 Instagram Login 절차에서 발급·승인해야 한다. 개인 계정은 게시 API 대상이 아니며 Business/Creator 프로페셔널 계정이 필요하다. Facebook Page가 필요한 옛 Facebook Login 샘플과 혼동하지 않는다.

1. 온해님이 Instagram 앱에서 `@mumung_101`의 계정 유형을 확인한다. 개인 계정이면 프로페셔널 전환 여부를 직접 결정한다. 계정 설정 변경은 Codex가 하지 않는다.
2. 온해님이 Meta for Developers에서 앱을 만들거나 기존 앱을 선택하고 **Instagram API with Instagram Login**을 설정한다. 게시 권한은 `instagram_business_basic`, `instagram_business_content_publish`만 요청한다. DM·댓글·광고 권한은 신청하지 않는다.
3. Meta의 로그인·권한 승인 화면은 온해님이 직접 확인한다. 발급된 액세스 토큰은 채팅·Git·DB가 아니라 Railway 서비스 비밀 변수 `INSTAGRAM_ACCESS_TOKEN`에만 저장한다. 같은 서비스에 `INSTAGRAM_USER_ID`, `INSTAGRAM_GRAPH_VERSION`을 설정한다. 계정 ID는 `@mumung_101`의 ID여야 한다.
4. 최초 연결 검증·미디어 준비 시험 뒤 `INSTAGRAM_PUBLISH_ENABLED=true`를 설정한다. 이 값이 비어 있거나 `false`면 공개 API 요청은 거부된다.
5. 관리자의 AI 마케팅 팀에서 채널 `인스타그램`으로 실제 AI 초안 1건을 만들고 상품 사실을 검수한다. 내부 `승인 기록` 후에도 공개되지 않는다. 온해님이 본문과 `https://roadlog.co.kr/...jpg` 공개 JPEG를 직접 확인해 `내용 확인 후 인스타 게시`를 클릭한 **그 한 건에만** Graph API가 호출된다. 같은 승인 ID로 재요청하면 중복 차단한다.
6. 공개 결과가 불확실하면 상태 `UNCERTAIN`으로 저장하며 자동 재시도하지 않는다. 온해님이 Instagram 계정에서 실제 공개 여부를 먼저 확인한다.

긴급정지 중에는 수동 게시 API도 거부된다. 일반 AI 팀 시작/스케줄은 게시 API를 호출하지 않는다.

현재 운영 환경에는 Meta/Instagram 연결 변수가 없어 실제 계정 연결·게시를 검증하지 못했다. 이번 작업의 테스트는 가짜 Meta 응답만 사용한다. 승인 항목의 이미지는 별도 제작·공개 JPEG 호스팅이 필요하다. `image_prompt`는 이미지 파일이 아니다.

근거: [Meta Instagram Login 권한](https://www.postman.com/meta/instagram/folder/6raa77c/instagram-api-with-instagram-login), [Meta 공개 예제의 컨테이너·게시 흐름](https://github.com/fbsamples/reels_publishing_apis/blob/main/insta_reels_publishing_api_sample/README.md).

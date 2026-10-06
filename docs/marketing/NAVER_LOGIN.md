# 네이버 로그인 연결 (2026-10-07 Claude)

코드는 배포됐고, **키를 넣기 전에는 버튼이 안 보인다.** 아래는 온해님이 직접 하실 일이다.

## 1. 네이버 개발자센터에서 앱 만들기 (온해님)
1. https://developers.naver.com → Application → 애플리케이션 등록
2. 사용 API: **네이버 로그인** · 제공 정보: **이메일 주소**(필수), 이름
3. 서비스 URL: `https://roadlog.co.kr`
4. **Callback URL: `https://roadlog.co.kr/api/auth/naver/callback`** (한 글자라도 다르면 실패한다)
5. 등록하면 **Client ID / Client Secret** 이 나온다.

## 2. Railway 환경변수 (온해님)
`NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` 두 개를 넣고 재배포. 둘 다 있어야 `/api/auth/social/ready` 의 `naver` 가 `true` 가 되고 버튼이 나타난다.
🛑 키는 채팅·파일에 붙여 넣지 말 것.

## 3. 검수
네이버는 앱을 **개발 중** 상태로 만들고, 검수를 통과하기 전에는 **멤버로 등록한 계정만** 로그인된다고 알려져 있다(공식 문서를 이 PC에서 열지 못해 **미확인** — 개발자센터 화면에서 확인할 것). 테스트는 본인 계정을 멤버로 넣고 한다.

## 코드 위치
- `server.py` `naver_start` · `naver_callback` · `_naver_callback`, `social_ready`
- 프런트 `roadlog-saju/index.html` `#btnNaver`, `account.js:paintSocial`
- 통계 `modules/stats.py` `social_naver`

## 🛑 계정 연결 규칙
- 프로필 이메일이 **`@naver.com` 일 때만** 같은 이메일의 기존 계정에 잇는다. 네이버는 주소 확인 여부를 알려 주지 않아서, gmail 등 외부 주소를 프로필에 적어 남의 계정으로 들어오는 걸 막으려는 것이다.
- 그 밖의 주소·이메일 동의 안 함 → `naver<고유번호>@naver.local` 새 계정(카카오와 같은 방식). 이 경우 gmail 로 이미 이메일 가입한 같은 사람과 계정이 나뉜다.

## 시험한 것 / 못 한 것
- 한 것: 가짜 응답으로 서버 시험(키 없음→503·버튼 꺼짐, 키 있음→인가 화면으로 이동, 콜백→토큰·계정 생성, 재로그인 중복 없음, 토큰 실패·state 불일치→오류 화면). 버튼 모양.
- 못 한 것: **실제 네이버 인증은 키가 없어 못 해 봤다.** 응답 항목 이름(`response.id`·`email`·`name`)과 주소는 검색 결과로만 확인했다(공식 문서 미열람).

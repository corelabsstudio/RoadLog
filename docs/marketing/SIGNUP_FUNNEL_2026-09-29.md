# 로드로그 가입 전환 점검과 개선 (2026-09-29 · Kiro)

온해님 요청: 방문자는 느는데 가입이 안 되는 까닭을 찾고, 가입·결제를 늘리는 방법을 웹에서 찾아 적용한다.
다음 작업자(Codex 포함)는 이 파일과 `roadlog-saju/CLAUDE.md`·`RoadLog/CLAUDE.md` 맨 위 2026-09-29 항목을 먼저 읽는다.

## 1. 실측 (고치기 전 상태)

비회원 아이폰 13 화면(Playwright)으로 라이브를 따라갔다. 첫 요청에 `?nocount=1` 을 붙여 방문 집계에서 뺐다.
가입·로그인 제출·결제·저주 뽑기(LLM 호출)는 하지 않았다.

| # | 본 것 | 근거 |
|---|---|---|
| 1 | 첫 방문 1.8초 뒤 「무냥이의 마중」 창이 화면 전체를 덮었다. 검색으로 `/#p/today` 에 온 분도 같았다. 아이폰은 「홈 화면에 두고 쓰세요」 막대가 하나 더 떴다 | 캡처 · `main.js` `LAMP_GUIDE_KEY` · `showInstall` |
| 2 | 무료 「오늘 운세」: 입력 5단계(이름 필수) + 계산 약 17초 뒤, 항목마다 「로그인하시면 보여요」와 함께 **계산 문장 30문단이 그대로 보였다**(감춘 문단 0개). 안내 문구는 그림 위에 흐리게 겹쳤다 | 항목 제목(h4)이 `.item-door` 안에 있어 감추는 코드가 그림 안만 훑었다 |
| 3 | 유료 상품 「복채로 열기」·「등불로 열기」는 맛보기 없이 바로 로그인 창 | `unlockReport` → `tryOpen` |
| 4 | 로그인 창은 늘 「로그인」 모드. 「처음이신가요? 가입하기」는 창 바닥(y=645) 아래 y=731 이라 내려야 보였다. 카카오는 이메일 칸 아래. 소셜 안내만 「등불 50개」(서버는 이용권 1장 + 등불 300개) | 캡처 · `lamps.welcome()` |
| 5 | 카카오·구글 로그인 뒤 홈(`/#t=`)으로 돌아가 입력·결과가 사라졌다. 저주 신단만 되돌아갔다 | 코드 확인. 실제 소셜 로그인은 하지 않았다 |
| 6 | 「복채로 열기」로 가입한 새 손님은 곧장 결제 화면. 이용권·등불 300개로 열 수 있는 상품이어도 그랬다 | 코드 확인 (`lamps:retry` → `unlockReport(id,'pay')`) |
| 7 | 같은 「전생 신원조회」 정가가 진열대 5,300원 · 45%, 잠금 상자·추천 카드 9,900원 · 71%. 「🔒 등불로 전체 풀이 열어보기」는 결제로 연결. 「3.1만 명」을 세는 집계 없음. 저주 신단 「오늘만 여는」 | `products.js` `list` 와 `was` 혼용 |
| 8 | 느린 4G + 폰 CPU 4배 느림 흉내: 첫 글자 12초, 전부 53초. 홈 한 번에 약 10MB, 그중 Pretendard 글꼴 파일 5개가 약 3.8MB | 🛑 이번 목록 밖이라 **고치지 않았다** |
| 9 | 퍼널 기록 없음 — 방문·가입·결제만 셌다 | `stats.py` |

공개 API: `/api/gift` 손님 계정 94개(관리자·테스트·무료패스 제외. 9/13 기록 83명) · `/api/auth/social/ready` 카카오·구글 둘 다 켜짐 · `/api/lamps/ready` `sale_until` 비어 있음.
못 본 것: 관리자 통계(로그인 필요 — 비밀번호 입력 안 함), 로그인 뒤 실제 화면(가입 안 함). **늘어난 방문이 어디서 왔는지는 아직 모른다.**

## 2. 웹 근거 (URL을 직접 열어 확인)

- NN/g [Login Walls](https://www.nngroup.com/articles/login-walls/) — 로그인 벽은 비용이 크다. 내용을 먼저 보여 주고 거래 시점에 로그인을 받는 쪽이 더 많은 사람을 끝까지 데려간다.
- NN/g [Popups](https://www.nngroup.com/articles/popups/) — 가치를 주기 전·로그인 직후 팝업 금지, 여러 개 연달아 금지, 앱 설치 권유는 작은 배너로.
- Center Centre(LukeW) [Twitter 점진 참여](https://articles.centercentre.com/twitter_sign_up/) — 단계가 하나 늘었는데도 가입 완료 +29%.
- Baymard [포기 이유](https://baymard.com/lists/cart-abandonment-rate) — 구경한 사람을 빼면 못 믿어서 19%, 계정을 만들라고 해서 18%, 총액을 미리 못 봐서 12%. [계정 권유는 결제 뒤로](https://baymard.com/blog/delayed-account-creation).
- Korea Herald [다크패턴 규제](https://www.koreaherald.com/article/10417265) — 2025-02-14 전자상거래법 시행. 계속 다시 시작되는 할인 마감 같은 가짜 긴급성이 흔한 불만으로 꼽혔다.

## 3. 한 일

| # | 무엇 | 파일 |
|---|---|---|
| 1 | 비회원 계산 문장 감추기 수정. 기준을 제목이 아니라 `.item-door` 밖으로. 안내 문구도 그림 밖으로 | `roadlog-saju/main.js` `paintWriting` |
| 2 | 로그인한 적 없는 브라우저(`localStorage roadlog.hadLogin.v1` 없음)는 「가입하기」로 연다. 상단 「로그인」·하단바 「마이」는 로그인 쪽. 가입·로그인 바꾸기를 맨 위로, 카카오·구글을 이메일 칸 위로. 소셜 안내 「선물도 똑같이 드려요」 | `account.js` `openAuth` · `index.html` `#authDlg` · `style.css` |
| 3 | 카카오·구글 버튼을 누르면 상품·누르던 단추를 `roadlog.socialBack.v1`(20분)에 적는다. 돌아오면 `social:back` → 상품 화면 → 이 브라우저의 입력값으로 다시 계산 → 잠금 상자(무료 상품은 전문) | `account.js` · `main.js` |
| 4 | 로그인 뒤 복채 전용(프리미엄)만 결제로. 나머지는 잠금 상자(이용권·등불·복채)를 보여 주고 그 자리로 내려 준다. 보던 상품은 `auth:in` 한 곳에서만 연다 — 전에는 두 곳에서 열어 미리보기 글을 두 번 부를 수 있었다 | `main.js` `lamps:retry` · `auth:in` · `openReport` 가 Promise 반환 |
| 5 | 「무냥이의 마중」은 비회원이 첫 계산 결과를 본 2.5초 뒤 한 번. 설치 막대는 다른 날 다시 온 분께만(`roadlog.days.v1`). 계정 메뉴 「앱으로 설치하기」는 그대로 | `main.js` |
| 6 | 정가는 `was` 하나만(진열대·추천 카드). 잠금 상자 단추 「🔒 N원 복채로 전체 풀이 열기」. 배지 「🩸 피눈물 흘린 저주」. 저주 신단 「무냥이가 여는 작은 신단」 | `main.js` · `reco.js` · `index.html` · `curse.html` |
| 7 | 퍼널 기록 `POST /api/funnel {step}`. 앞단은 비회원일 때만 `product`·`calc`·`report`·`auth_open`, 결제 화면은 `pay_view`. 서버 가입 때 `signup_email`·`signup_social`. 같은 브라우저는 하루에 단계마다 한 번. `?nocount=1` 브라우저와 크롤러는 뺀다. 관리자 「유입」 탭 맨 아래 「비회원이 가입까지 가는 길」 | `RoadLog/server.py` · `modules/stats.py` · `public/admin/index.html` · `pay.html` |
| 도구 | `tools/ship.py --no-commit` — 검사·빌드·`RoadLog/web` 반영까지만. 두 저장소에 다른 작업의 미추적 파일이 있을 때 `git add -A` 를 피한다 | `roadlog-saju/tools/ship.py` |

## 4. 읽는 법 · 남은 일

- 관리자 「유입」 탭 「비회원이 가입까지 가는 길」은 **2026-09-29 배포 뒤부터** 쌓인다. 그전 날짜는 방문만 있고 나머지는 0이다. 며칠 쌓인 뒤 가장 크게 줄어드는 단계를 다음에 고친다.
- 8번(비회원에게 무냥이 글 맛보기)은 이 파일 아래 5절에 따로 적는다.
- 글꼴 3.8MB는 고치지 않았다. Pretendard 정적 woff 5개를 부분 글꼴(dynamic subset)로 바꾸면 줄어든다.
- 온해님께 받을 것: 관리자 「유입」 탭 최근 14일 캡처 — 늘어난 방문이 어디서 왔는지, 사람인지.

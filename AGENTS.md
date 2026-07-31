# RoadLog (로드로그) — Agent 지침

## 불러오기 트리거

### 로드로그 본체
사용자가 **「로드로그 불러와줘」** / **「RoadLog 이어서」** / **「로드로그 이어서」** 라고 하면:

1. 이 저장소 루트에서 작업한다: `C:\Users\hysoo\Projects\RoadLog`
2. `docs/SAVE_POINT.md` 를 읽고 현재 제품·배포·로컬 도구 상태를 복구한다
3. 라이브·Railway·관련 도구까지 **이어서** 처리한다 (처음부터 설명 요구하지 말 것)

### 홍보 프로그램 (ReachKit)
사용자가 **「홍보 불러와」** / **「홍보 불러와줘」** / **「홍보 이어서」** / **「ReachKit 이어서」** / **「리치킷 이어서」** / **「ReachKit 불러와」** 라고 하면:

1. `C:\Users\hysoo\Projects\RoadLog\tools\community_poster` 로 컨텍스트를 잡는다
2. **`tools/community_poster/SAVE_POINT.md`** 를 최우선으로 읽고 상태 복구 (`PRODUCT.md` · `VALIDATION_WEEK.md` 병행)
3. ReachKit 기능·검증 루틴·구조 파악까지 **이어서** 작업한다 (처음부터 설명하지 말 것)
4. 실행: `ReachKit.bat` · 브랜드 ReachKit · 로드로그 검증 모드 기본

### 로드로그 마케팅 하네스 (사이트 SEO·카피)
사용자가 **「로드로그 마케팅」** / **「로드로그 SEO」** / **「로드로그 일일 마케팅」** 이라고 하면:

1. 이 저장소 루트에서 작업한다
2. **순서대로 읽기:**  
   `docs/marketing/Context/ONE_PAGER.md` → `docs/marketing/AGENT_TEAM.md` → (SEO면) `docs/marketing/news_digest/DAILY_SEO_PROMPT.md`
3. 파이프: **Research → SEO Writer → Review → (승인 후) Publisher**
4. 관련 뉴스 0건이면 `NO_NEWS_TODAY` 로 종료 (억지 양산 금지)
5. Review PASS 전 `git push` / 배포 금지
6. ReachKit·WakeAgain 과 **섞지 말 것**

### X 일일 자동 게시
사용자가 **「X 마케팅」** / **「로드로그 X」** / **「일일 X 팩」** / **「X 자동 게시」** 라고 하면:

1. 읽기: `docs/marketing/x/STRATEGY.md` · `AUTO_POST_SETUP.md`
2. 실행: `scripts/x_auto_daily.py` (키: `.launch/x.env`)
3. **RoadLog 풀** + **WakeAgain 소프트** (결제·성사 보장 금지)
4. 키 없으면 게시 중단 + 세팅 안내 (비밀번호로 대신 로그인 금지)
5. 성공 시 tweet id / META.json 보고

## 제품 요약

- **로드로그 / RoadLog** — AI 운행·외근 일지 SaaS  
- 사이트: https://roadlog.co.kr/  
- 스택: FastAPI + `web/` SPA PWA · Railway 배포 · GitHub `corelabsstudio/RoadLog` `main`
- OpenAI 하이브리드 비용 모드 · Pro는 스마트스토어 결제 링크 + 주문번호 claim + ntfy 관리자 푸시
- 사용자 UI에 OpenAI/운영 배너·내부 노트 노출 금지
- 비관리자: 아무 곳 클릭해도 **토스트 없음** (view-as silent no-op, `body` data-view-as 잔여 제거)

## 로컬 실행

```powershell
cd C:\Users\hysoo\Projects\RoadLog
.\.venv\Scripts\python.exe -m uvicorn server:app --host 127.0.0.1 --port 8501
```

## ReachKit — 홍보 자동화 도우미

- 상세 저장 지점: `tools/community_poster/SAVE_POINT.md`
- 브랜드: **ReachKit** · 실행: `tools/community_poster/ReachKit.bat`
- 구조 파악 · 문구 생성 · 채널/게시판 · 가드레일 · 검증 대시보드
- CAPTCHA·휴대폰 인증은 가입 시 사용자 처리 (자동화 안 함)

## 배포 습관

- 프론트 변경 시 `scripts/bump_build.py` 로 build 올리고 SW/index 정합
- Railway: `.launch/railway.token` + GraphQL `serviceInstanceDeployV2`
- 보안 토큰·비번·ntfy 토픽은 커밋하지 말 것

## 언어

- 사용자와는 **한국어**로 소통

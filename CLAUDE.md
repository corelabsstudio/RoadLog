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

# RoadLog 저장 지점 (Save Point)

> **로드로그 본체:** **「로드로그 불러와줘」** / **「RoadLog 이어서」** → 이 문서 + `AGENTS.md`  
> **홍보 프로그램(ReachKit):** **「홍보 불러와」** / **「ReachKit 이어서」** → `tools/community_poster/SAVE_POINT.md`  
> **마케팅 하네스:** **「로드로그 마케팅」** / **「로드로그 SEO」** → `docs/marketing/AGENT_TEAM.md` (+ Context · DAILY_SEO_PROMPT)

**저장 시각:** 2026-07-28 (마케팅 하네스 추가) · 이전 본문 스냅샷 2026-07-21  
**로컬 경로:** `C:\Users\hysoo\Projects\RoadLog`  
**라이브:** https://roadlog.co.kr/  
**GitHub:** `corelabsstudio/RoadLog` · `main`  
**최근 배포:** `6990a78a` SUCCESS (Volume `/data` 연결 후 재배포, 2026-07-21)  
**프론트 빌드:** `20260712-print-v25` (`web/build.json` · `app.js?v=…`)  
**데이터:** Railway Volume `web-volume` → mount `/data` · `DATA_DIR=/data`  
**AI:** OpenAI 키 유효 확인 (models + chat completions OK, model `gpt-4o-mini`)

---

## 2026-07-21 세션에서 한 일

### 1) Railway 토큰·상태 점검
- `.launch/railway.token` 재등록 (Workspace 스코프 — `me` 실패해도 `projects`/variables OK)
- GitHub·라이브·배포 SUCCESS 확인
- OpenAI live 키: **유효** (chat reply OK)

### 2) AdSense 슬롯 정리
- Railway에 `ADSENSE_CLIENT=ca-pub-xxxxxxxxxxxxxxxx`, `ADSENSE_SLOT=xxxxxxxxxx` 플레이스홀더만 있었음
- **두 변수 삭제** (기본값 xxxx → Streamlit은 데모 박스만, SPA는 AdSense 미사용)
- 실제 광고 켤 때: 진짜 `ca-pub-…` + 숫자 slot 을 Variables에 다시 넣으면 됨

### 3) Railway Volume 연결 (완료)
- Volume 생성: `web-volume` (`2328b382-…`) · instance mount **`/data`** · region sfo
- Variable: `DATA_DIR=/data`
- 재배포 SUCCESS · health: `data_dir=/data`, `storage_persistent=true`, `openai=true`
- 관리자 로그인 OK (env `ADMIN_*` 로 재시드)
- **주의:** Volume 붙이기 전 컨테이너 ephemeral 데이터는 이전되지 않음. 가입 회원은 초기화됐을 수 있음(관리자는 env로 유지)

---

## 2026-07-17 세션에서 한 일

### 1) Railway · live 관리자
- Account API 토큰 재발급 후 `.launch/railway.token` 에 저장 (커밋 금지)
- 프로젝트: RoadLog · env `production` · service `web`
  - projectId: `9d3da15b-b2e6-4790-af3c-b0229e2d1965`
  - environmentId: `367f2cc2-ac64-4daf-b04d-0d28f4ac97c7`
  - serviceId: `ebf3faf1-2f14-425a-acad-9cc2c67fa633`
- live `ADMIN_PASSWORD` 변경 후 `serviceInstanceRedeploy` → 로그인 확인 OK
- **관리자 ID:** `hhs126` (이메일 `hhs126@roadlog.local` 가능)
- **비번:** 로컬 `.env` · Railway Variables · (선택) `railway-variables.env` 와 동일 — **채팅/커밋에 비번 적지 말 것**
- 예전 401 원인: 로컬 `.env` 비번 ≠ live Railway 비번
- 로그인 API: `POST /api/auth/login` · body `{ "email": "hhs126", "password": "…" }`

### 2) 인쇄 미리보기 버그 수정 (live 반영됨)
- **증상:** 인쇄 → 미리보기 누르면 빈 창
- **원인:** `window.open(..., "noopener,noreferrer")` 후 `document.write` 불가
- **수정:** `web/app.js` `openPrint` — HTML Blob + `URL.createObjectURL` 로 새 탭 오픈
- 커밋: `65fb589` · Railway SUCCESS · live에 `createObjectURL` 확인

### 3) 수익화·홍보 방향 (합의)
- **현금화 속도: RoadLog > Trace** (live + 스마트스토어 claim 경로 있음)
- 홍보는 아직 **0** — 제품·로그인·결제 경로 준비 후 단계
- 다음: 지인 DM 3~5명 → 오픈채 1곳 → (여유 시) 블로그 1글
- 문구: `docs/marketing/CONTENT_PACK.md` · 채널: `CHANNELS.md`
- 유료 광고는 초반 비추천

### 4) 토큰 발급 시 주의 (다음에 막히면)
- **Account Tokens:** https://railway.com/account/tokens (또는 railway.app)
- **Create 직후 전체 문자열만** 유효 (목록 `****-xxxx` 는 비밀값 아님)
- Workspace: RoadLog가 있는 쪽 (예: CoreLabs's Projects)
- Project Settings → Tokens 는 별개(계정 인증 필요할 수 있음) — 변수 수정은 Account 토큰으로 가능했음

---

## 불러올 때 할 일 (에이전트)

1. `cd C:\Users\hysoo\Projects\RoadLog`
2. `git status` / `git log -3 --oneline` 확인
3. 필요 시 로컬 서버:  
   `.\.venv\Scripts\python.exe -m uvicorn server:app --host 127.0.0.1 --port 8501`
4. live 변수/배포: `.launch/railway.token` (Account 토큰) + GraphQL
5. 홍보 툴은 별도 트리거 시 `tools/community_poster/SAVE_POINT.md` 우선

---

## 제품 / 서버

- FastAPI + 정적 SPA (`web/`) · PWA · AI 운행·외근 일지
- Free / Pro(스마트스토어) / Enterprise · claim `#pro-claim` · ntfy 푸시
- 관리자 대시보드 · 역할 미리보기(view-as) — **비관리자는 클릭해도 silent**
- 사용자 UI: OpenAI 비용/운영 배너 비노출
- 인쇄: Blob 미리보기 + 프린터 인쇄 (`openPrint`)
- 마케팅 문구: `docs/marketing/CONTENT_PACK.md`, `CHANNELS.md`

### 로컬 실행

```powershell
cd C:\Users\hysoo\Projects\RoadLog
.\.venv\Scripts\python.exe -m uvicorn server:app --host 127.0.0.1 --port 8501
# → http://127.0.0.1:8501/
```

데스크톱(웹앱): `scripts/launch_roadlog.vbs` (포트 8501)

---

## ReachKit (홍보 프로그램) — 상세는 전용 저장 지점

**전용 저장 지점:** `tools/community_poster/SAVE_POINT.md`  
**트리거:** 「홍보 불러와」 / 「ReachKit 이어서」

요약: ReachKit · 구조 파악 · 사이드바 UI · 3채널 검증 · CAPTCHA는 가입 시 사용자

```powershell
C:\Users\hysoo\Projects\RoadLog\tools\community_poster\ReachKit.bat
```

---

## 배포 / 인프라

- Railway web service: `ebf3faf1-2f14-425a-acad-9cc2c67fa633`
- 토큰: `.launch/railway.token` (커밋 금지)
- 변수 백업(로컬 전용): `railway-variables.env` (커밋 금지 · 시크릿)
- ntfy topic: `.launch/ntfy_topic.txt`
- PWA 강제 갱신: https://roadlog.co.kr/update.html · `scripts/bump_build.py`
- 배포: `git push origin main` (GitHub 연동 자동 배포 확인됨)

---

## 다음 우선순위 (제안)

1. **홍보 시작** — 지인 DM 템플릿 C (`CONTENT_PACK`) 3~5명
2. Free 가입·생성 여부 관리자 패널로 확인
3. (선택) Pro 결제 claim 플로우 실사용 1회 점검
4. Trace는 제품 다듬기 병행, 수익 실험은 RoadLog 우선

---

## 의도적 제외 (Git 미포함)

- `.env`, `.launch/*` 시크릿
- `railway-variables.env`
- `data/users.json`, 세션, 사용량, 개인 서식
- `tools/community_poster/data/*.json` (비밀번호 가능)

---

## 복구 확인

```powershell
cd C:\Users\hysoo\Projects\RoadLog
git status
git log -1 --oneline
Test-Path .launch\railway.token
Test-Path tools\community_poster\app.py
# live 인쇄 수정 여부: app.js 에 createObjectURL
```

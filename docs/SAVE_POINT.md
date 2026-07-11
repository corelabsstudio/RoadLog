# RoadLog 저장 지점 (Save Point)

> 다음에 **「로드로그 불러와줘」** / **「RoadLog 이어서」** 라고 하면 이 경로·커밋 기준으로 복구하면 됩니다.

**저장 시각:** 2026-07-12  
**로컬 패치:** 정식 런칭용 (보안·제출물 스크럽·레이트리밋·요금/푸터 UX) — 배포 전 `docs/ops/LAUNCH_CHECKLIST.md` 필수  
**이전 커밋 기준:** `bb0e894` / `44e3b7d` (`main`)  
**라이브:** https://roadlog.co.kr/

## 프로젝트 위치

```
C:\Users\hysoo\projects\RoadLog
```

## 실행 방법 (로컬)

```powershell
cd C:\Users\hysoo\projects\RoadLog
.\.venv\Scripts\python.exe -m uvicorn server:app --host 127.0.0.1 --port 8501
# → http://127.0.0.1:8501/
```

데스크톱 런처: `scripts/launch_roadlog.vbs` (포트 8501)

Streamlit(기업용 좌석·승인 등):

```powershell
streamlit run app.py
```

## 이 저장 지점에 포함된 주요 기능

### 제품 / UI
- FastAPI + 정적 SPA (`web/`) · PWA 설치 · 브랜드 부제 **AI 운행·외근 일지**
- 운행일지 + 외근·출장 일지 모드
- 로그인 / 회원가입 / 로그인 정보 저장
- 퀵 스탬프 · AI 일지 생성 · Excel / PDF / DOCX
- 회사 서식 학습 · 설정 · 요금제 · 문의 · 약관
- 랜딩: B2B 톤 · 후기(Reviews) 섹션
- i18n KO/EN · 스마트 근무시간 라우팅

### 사생활 / 주유
- **점심 장소 기본 비노출** (시간만 운행시간에서 제외)
- 설정: 「점심 장소는 일지에 남기지 않기」
- **주유 여부·금액·(선택) 주유량** 입력
- 회사 서식에 **주유 칸이 있을 때만** UI 표시 + 일지 반영 (`form_has_fuel`)

### 관리자
- 매출 · 사용 횟수 · 요금 · VIP
- 역할 미리보기 (Pro / Enterprise / Free)
- **메인 후기 CRUD** (공개/숨김/수정/삭제) → `/api/reviews`

### PWA / 배포 캐시
- SW 자동 갱신 · `updateViaCache: none` · 앱 셸 no-cache
- 강제 갱신 페이지: https://roadlog.co.kr/update.html  
  (일반 창이 옛 캐시에 묶였을 때 1회 접속)

## 의도적 제외 (로컬 전용 · Git 미포함)

- `.env` (API 키 등)
- `data/users.json`, 세션, 사용량, `data/admin/`, 개인 서식 샘플 등 런타임 데이터

## 배포

- GitHub: `https://github.com/corelabsstudio/RoadLog.git` · 브랜치 `main`
- 도메인: `roadlog.co.kr` → Railway
- 보안 점검: `docs/ops/DEPLOY_SECURITY_CHECKLIST.md` · `python scripts/check_security.py`

## 복구 / 확인

```powershell
cd C:\Users\hysoo\projects\RoadLog
git status
git log -1 --oneline
# 기대: bb0e894 또는 그 이후 main
```

사이트 캐시 문제 시: https://roadlog.co.kr/update.html

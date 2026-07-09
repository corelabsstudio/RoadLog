# RoadLog 저장 지점 (Save Point)

> 다음에 **「로드로그 불러와줘」** / **「RoadLog 이어서」** 라고 하면 이 경로·커밋 기준으로 복구하면 됩니다.

## 프로젝트 위치

```
C:\Users\hysoo\projects\RoadLog
```

## 실행 방법

```powershell
cd C:\Users\hysoo\projects\RoadLog
.\.venv\Scripts\Activate.ps1

# 웹 SPA (메인)
.\.venv\Scripts\python.exe -m uvicorn server:app --host 127.0.0.1 --port 8765
# → http://127.0.0.1:8765

# Streamlit (기업용 좌석·승인 등)
streamlit run app.py
# → http://localhost:8501
```

## 이 저장 지점에 포함된 주요 기능

- FastAPI + 정적 SPA (`web/`) · PWA 설치 · 통합 로고
- 로그인 / 회원가입 / **로그인 정보 저장** 체크박스
- 퀵 스탬프 · AI 일지 생성 · Excel/PDF/DOCX (한글 파일명 헤더 수정 포함)
- 회사 서식 학습 · 설정 · 요금제 · 문의(구글 폼) · 약관
- 관리자: 매출 · VIP · 요금 · **역할 미리보기(Pro/Enterprise/Free)**
- i18n KO/EN · 스마트 근무시간 라우팅 · 퇴근 케어 모달
- Streamlit Enterprise(좌석·팀 승인) 모듈 유지

## 의도적 제외 (로컬 전용)

- `.env` (API 키 등)
- `data/users.json`, 세션, 사용량, 개인 서식 샘플 등 런타임 데이터

## Git

- 브랜치: `master`
- 커밋 메시지: `save: RoadLog SPA + admin view-as + remember login`

복구:

```powershell
cd C:\Users\hysoo\projects\RoadLog
git status
git log -1 --oneline
```

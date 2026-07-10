# Streamlit Community Cloud 배포 가이드

앱 URL 예: `https://xxxx.streamlit.app/`

메인 제품은 FastAPI SPA(`server.py`)이지만, 기업용·관리 UI는 Streamlit(`app.py`)으로 배포할 수 있습니다.

---

## 1. GitHub 연결

1. [share.streamlit.io](https://share.streamlit.io) 로그인  
2. **New app** → 저장소 `corelabsstudio/RoadLog`  
3. Branch: `main`  
4. Main file path: **`app.py`**  
5. Advanced → Python **3.11** 또는 **3.12** 권장 (3.13 회피)

---

## 2. Secrets (필수에 가깝음)

App settings → **Secrets** 에 TOML 형식으로:

```toml
APP_ENV = "production"
APP_SECRET = "여기에-긴-난수"
ADMIN_USERNAME = "your-admin-id"
ADMIN_PASSWORD = "강한-비밀번호"
ADMIN_EMAIL = "you@email.com"
OPENAI_API_KEY = "sk-..."
ALLOW_DEMO_BILLING_UPGRADE = "false"
PRO_PAYMENT_URL = "https://..."
CONTACT_EMAIL = "corelabs.studio@gmail.com"
```

`modules/config.py` 는 환경변수와 Streamlit secrets 를 모두 읽습니다.

> 참고: Streamlit Cloud 에서 `APP_ENV=production` 이면 약한 `APP_SECRET` / 관리자 비번일 때  
> **FastAPI `server.py` 기동은 막히지만**, Streamlit `app.py` 는 secrets 만 제대로 넣으면 동작합니다.  
> secrets 미설정 시 기본 관리자 `admin` / `admin123` 이 쓰이므로 **반드시 변경**하세요.

---

## 3. 배포 후 오류가 날 때

1. 앱 우하단 **Manage app** → **Logs** 에서 traceback 확인  
2. **Reboot app** (GitHub 푸시 반영이 안 됐을 때)  
3. 로컬에서 동일 커밋 검증:
   ```powershell
   cd C:\Users\hysoo\projects\RoadLog
   git pull
   streamlit run app.py
   ```
4. 예전에 제미나이가 망가뜨린 경우: `app.py` 가 한 줄 placeholder 이거나  
   `modules/*.py` 에 `<<<<<<<` 충돌 마커가 있으면 기동 실패합니다.  
   현재 `main` 브랜치는 복구된 상태여야 합니다.

---

## 4. 정상 동작 확인

- 첫 화면: 로그인 / 회원가입  
- 가입 후: 운행 내용 입력 → 일지 생성  
- 사이드바: 설정 · 요금제 · 관리자  
- AI 키/쿼터 없으면 **규칙 초안** + 안내 문구

---

## 5. Streamlit vs FastAPI

| | Streamlit Cloud | FastAPI + SPA |
|--|-----------------|---------------|
| 파일 | `app.py` | `server.py` + `web/` |
| 용도 | 관리·기업 UI, 빠른 배포 | 메인 제품(PWA, 퀵스탬프 등) |
| 호스팅 | share.streamlit.io | Railway, Render, VPS 등 |

메인 사용자용 웹은 FastAPI 배포를 권장합니다.

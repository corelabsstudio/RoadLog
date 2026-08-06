# X 자동 게시 세팅 (1회)

생성만으로는 계정에 글을 올릴 수 없습니다. **당신 X 계정 API 키**가 있어야  
스케줄러/스크립트가 대신 게시합니다.

---

## 1. 개발자 앱 만들기

1. https://developer.x.com/ 로그인  
2. Project + App 생성  
3. App 권한: **Read and Write**  
4. **Keys and tokens**에서 발급:
   - API Key  
   - API Key Secret  
   - Access Token  
   - Access Token Secret  

> Access Token은 **본인 계정**으로 발급 (User context).  
> Free 티어에서도 게시+미디어가 되는 경우가 많으나, X 정책은 수시 변경.

---

## 2. 키 저장 (로컬만)

```powershell
cd C:\Users\hysoo\projects\RoadLog
copy .launch\x.env.example .launch\x.env
notepad .launch\x.env
```

값을 채운 뒤 저장. **git 커밋 금지** (`.launch/` 는 보통 ignore).

---

## 3. 의존성

```powershell
.\.venv\Scripts\pip.exe install requests requests-oauthlib
```

---

## 4. 테스트

```powershell
# 게시 없이 캡션/이미지 확인
.\.venv\Scripts\python.exe scripts\x_auto_daily.py --dry-run

# 실제 게시 (로드로그만)
.\.venv\Scripts\python.exe scripts\x_auto_daily.py --roadlog-only

# 둘 다
.\.venv\Scripts\python.exe scripts\x_auto_daily.py
```

성공 시 `docs/marketing/x/packs/YYYY-MM-DD/META.json` 에 tweet id 기록.

---

## 5. 매일 자동

- Grok 스케줄: **일일 X 자동 게시** 태스크가  
  `x_auto_daily.py` 실행 (키 없으면 키 요청 알림만)
- Windows 보조 (PC 켜져 있을 때):

```powershell
# 관리자 불필요 · 현재 사용자 작업 스케줄러 예
schtasks /Create /TN "CoreLabsXDaily" /SC DAILY /ST 09:30 /TR "C:\Users\hysoo\projects\RoadLog\.venv\Scripts\python.exe C:\Users\hysoo\projects\RoadLog\scripts\x_auto_daily.py" /F
```

---

## 정책

| 제품 | 자동 게시 |
|------|-----------|
| RoadLog | ON (`X_POST_ROADLOG=1`) |
| WakeAgain | 소프트 캡션만 ON (`X_POST_WAKEAGAIN_SOFT=1`) · 결제 CTA 없음 |

끄기: `x.env` 에서 `X_POST_WAKEAGAIN_SOFT=0`

---

## 키 없이 가능한가?

**불가능.** Grok Build는 당신 X 비밀번호로 대신 로그인할 수 없고,  
플랫폼 API 키 없이는 공식 게시가 안 됩니다.  
키를 `.launch/x.env` 에 넣는 순간부터 매일 자동 게시가 동작합니다.

# Railway에 내 도메인 연결

현재 공식 사이트(임시 주소):

```
https://web-production-e4153e.up.railway.app
```

목표: `https://roadlog.내도메인.com` 또는 `https://내도메인.com` 으로 접속.

---

## 1. 도메인 구매

다음 중 편한 곳에서 구매합니다.

| 업체 | 특징 |
|------|------|
| [Cloudflare Registrar](https://www.cloudflare.com/products/registrar/) | 수수료 적고 DNS 관리 편함 |
| [가비아](https://www.gabia.com/) | 국내 결제·지원 |
| [호스팅케이알](https://www.hosting.kr) | 국내 |
| Namecheap / Google Domains 이전처 | 해외 |

### 이름 예시
- `roadlog.kr도메인.com` / `.kr` / `.co.kr`
- 또는 이미 있는 도메인의 서브: `app.회사도메인.com`

구매 후 **DNS 관리 화면**을 열 수 있으면 됩니다.

---

## 2. Railway에 커스텀 도메인 추가

1. [Railway 대시보드](https://railway.app/dashboard) 접속  
2. **로드로그 프로젝트** → 서비스 **web** 클릭  
3. **Settings** → **Networking** (또는 **Public Networking**)  
4. **Custom Domain** / **+ Custom Domain** 클릭  
5. 사용할 주소 입력  
   - 예: `app.roadlog.com`  
   - 또는 `roadlog.com` (루트 도메인)  
6. Railway가 안내하는 **DNS 레코드**를 복사  

보통 아래 중 하나입니다.

### 서브도메인 (`app.xxx.com`) — 가장 쉬움

| 타입 | 이름(호스트) | 값 |
|------|--------------|-----|
| **CNAME** | `app` | Railway가 준 값  
  (예: `xxxx.up.railway.app` 또는 `xxxx.railway.app`) |

### 루트 도메인 (`xxx.com`)

| 타입 | 이름 | 값 |
|------|------|-----|
| **CNAME** (flatten) 또는 **A** | `@` | Railway 안내에 따름 |

> Cloudflare 사용 시: 레코드 추가 후 프록시는 처음엔 **DNS only (회색 구름)** 으로 두는 편이 안전합니다. 연결 확인 후 주황 구름(프록시) 켜도 됩니다.

---

## 3. DNS 반영 기다리기

- 보통 **5분 ~ 2시간**, 길면 하루  
- Railway 화면에서 도메인 상태가 **Active / Certificate issued** 가 되면 HTTPS 준비 완료  

확인:

```
https://내가연결한도메인/healthz
```

→ `ok` 가 보이면 성공.

---

## 4. 환경 변수 갱신 (중요)

Railway → **Variables** 에서:

```env
ALLOWED_ORIGINS=https://내가연결한도메인
```

예:

```env
ALLOWED_ORIGINS=https://app.roadlog.com
```

여러 개면 쉼표:

```env
ALLOWED_ORIGINS=https://app.roadlog.com,https://roadlog.com
```

저장 후 자동 재배포되면 됩니다.

(선택) 운영 강화:

```env
APP_ENV=production
APP_SECRET=긴-난수
ADMIN_USERNAME=관리자_ID
ADMIN_PASSWORD=강한_비밀번호
ALLOW_DEMO_BILLING_UPGRADE=false
```

---

## 5. 체크리스트

- [ ] `https://내도메인/healthz` → ok  
- [ ] `https://내도메인/` → 로드로그 화면  
- [ ] 회원가입 / 로그인  
- [ ] 일지 생성 · 다운로드  
- [ ] 브라우저 자물쇠(HTTPS) 표시  
- [ ] 예전 `*.up.railway.app` 주소도 당분간 열림 (원하면 나중에 정리)

---

## 6. 자주 하는 실수

| 문제 | 해결 |
|------|------|
| DNS 안 맞음 | Railway가 준 **값 그대로** CNAME 복사 |
| Cloudflare 주황 구름 | 우선 **DNS only** 로 테스트 |
| 아직 반영 전 | 30분 후 다시 `/healthz` |
| Mixed content | 반드시 `https://` 로 접속 |
| CORS 오류 | `ALLOWED_ORIGINS` 에 새 도메인 추가 |

---

## 7. Streamlit 과의 관계

| | Streamlit | Railway + 내 도메인 |
|--|-----------|---------------------|
| 주소 | `*.streamlit.app` | **내 도메인** |
| 용도 | 관리/테스트 | **공식 사용자 사이트** |
| 회원 | 별도 | 별도 |

공식 서비스는 **내 도메인 + Railway** 를 메인으로 쓰면 됩니다.

---

## 요약 순서

1. 도메인 구매  
2. Railway → Custom Domain 추가  
3. DNS에 CNAME/A 등록  
4. Active 될 때까지 대기  
5. `ALLOWED_ORIGINS` 갱신  
6. `https://내도메인/healthz` 확인  

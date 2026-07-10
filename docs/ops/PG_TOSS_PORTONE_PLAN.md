# 로드로그 정식 결제 연동 설계 (토스페이먼츠 / 포트원)

**선택:** 사이다페이 반자동이 아닌 **온라인 PG 정식 연동 (2번)**  
**서비스 URL:** `https://roadlog.co.kr`  
**현재:** 결제 없이 plan 변경 차단됨. 관리자 수동 plan 변경·결제 링크만 가능.

---

## 1. PG 추천

| | **토스페이먼츠 (1순위 추천)** | 포트원 |
|--|------------------------------|--------|
| 특징 | 결제창·문서·한국 SaaS 연동 사례 많음 | 여러 PG를 한 API로 |
| 개발 | REST + 결제위젯/결제창 | SDK + 하위 PG |
| 웹훅 | 지원 | 지원 |
| 적합 | 로드로그처럼 **단일 서비스 구독** | 나중에 PG 갈아타기 쉬움 |

**로드로그 1차: 토스페이먼츠** 로 신청·연동하는 것을 권장합니다.  
(포트원은 토스 심사가 막히거나, 여러 PG를 한꺼번에 쓰고 싶을 때.)

---

## 2. 사업자 쪽 준비 (코딩 전)

사업자: **있음 (컴퓨터 수리점)**  
통신판매업: **없음 → 보완 권장**

| 순서 | 할 일 | 비고 |
|------|--------|------|
| 1 | **통신판매업 신고** | 정부24 등. 온라인 결제 심사에 유리 |
| 2 | 업종에 전자상거래/소프트웨어 등 **추가 가능 여부** 세무사·관할 문의 | 수리만이면 보완 요청 가능 |
| 3 | 정산 통장 = **사업자 명의** | |
| 4 | 사이트 푸터에 사업자·통신판매 신고번호·연락처 | `roadlog.co.kr` |
| 5 | 이용약관·개인정보처리방침 URL | 이미 있으면 링크만 정리 |

사이다페이는 **수리 현장/링크 결제용**으로 유지하고,  
**웹 구독은 토스 가맹**으로 분리하는 구성을 권장합니다.

---

## 3. 토스페이먼츠 신청 시 적을 내용 (예시)

| 항목 | 예시 |
|------|------|
| 서비스명 | 로드로그 (RoadLog) |
| URL | https://roadlog.co.kr |
| 판매 품목 | AI 운행일지 SaaS / 월 구독 소프트웨어 |
| 가격 | Free 0원 / Pro 월 약 9,900원 / Enterprise 별도 |
| 결제 방식 | 정기·단건(1차는 **월 단위 단건 결제** 권장) |
| 정산 | 사업자 계좌 |

**1차 제품 범위 (단순하게)**  
- Pro **월 1회 결제** (자동 정기결제 2차)  
- Enterprise는 **문의 후 수동/별도 견적** 유지 가능  

---

## 4. 로드로그 기술 설계

### 4.1 현재 코드와의 관계

| 기존 | 역할 |
|------|------|
| `POST /api/billing/upgrade` | 데모용, **운영 기본 차단** 유지 |
| 관리자 plan 변경 | 비상·B2B·입금 확인용 **유지** |
| `PRO_PAYMENT_URL` | 임시 외부 링크 → 결제 API로 대체 |
| `db.upgrade_to_pro` / `record_payment` | 웹훅 성공 시 호출 |

### 4.2 결제 흐름 (1차: 단건 결제 → Pro 30일 또는 해당 월)

```
[웹] 로그인 사용자 → 요금제 → "Pro 결제하기"
        ↓
[API] POST /api/billing/checkout  { plan: "pro" }
        ↓
[서버] 주문 생성 (orderId, amount, email, plan)
        ↓
[토스] 결제창/리다이렉트 (amount, orderId, successUrl, failUrl)
        ↓
[웹] successUrl?paymentKey&orderId&amount
        ↓
[API] POST /api/billing/confirm  { paymentKey, orderId, amount }
        ↓
[서버] 토스 결제 승인 API 호출 → 성공 시
        db.upgrade_to_pro(email) + payments 기록
        ↓
[웹] 성공 화면 + /api/me 로 plan=pro 반영
```

**웹훅 (권장 병행)**  
`POST /api/billing/webhook/toss`  
- 토스에서 결제 상태 이벤트 수신  
- confirm 누락·새로고침 대비 **이중 안전장치**  
- 서명 검증 필수  

### 4.3 새 API (추가 예정)

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/billing/checkout` | 로그인 필수. 주문 생성 + 토스용 payload 반환 |
| POST | `/api/billing/confirm` | 결제 승인 + plan 반영 |
| POST | `/api/billing/webhook/toss` | 토스 웹훅 (공개, 서명 검증) |
| GET | `/api/billing/orders/{orderId}` | 주문 상태 조회 (선택) |

### 4.4 데이터 (로컬 JSON 또는 추후 DB)

`data/orders.json` (또는 Supabase `orders`)

```json
{
  "order_id": "rl_20260710_xxxx",
  "email": "user@example.com",
  "plan": "pro",
  "amount": 9900,
  "status": "pending|paid|failed|cancelled",
  "payment_key": null,
  "created_at": "...",
  "paid_at": null
}
```

`status=paid` 인 주문만 plan 변경. **동일 paymentKey 중복 처리 방지.**

### 4.5 프론트 (`web/app.js`)

- `btnUpgradePro`: 데모 upgrade 대신 **`/api/billing/checkout`**  
- 토스 결제창 SDK 또는 리다이렉트  
- success / fail 페이지(해시 라우트 `#billing-success` 등)  
- Enterprise: 당분간 **문의(구글폼/메일)** 유지 가능  

### 4.6 환경 변수 (Railway)

```env
TOSS_CLIENT_KEY=test_ck_...
TOSS_SECRET_KEY=test_sk_...
TOSS_WEBHOOK_SECRET=...   # 있으면
BILLING_SUCCESS_URL=https://roadlog.co.kr/#billing-success
BILLING_FAIL_URL=https://roadlog.co.kr/#billing-fail
# 운영 전환 시 live 키로 교체
```

**시크릿 키는 GitHub·프론트에 넣지 않음.** confirm·웹훅만 서버에서 사용.

### 4.7 보안

| 항목 | 내용 |
|------|------|
| 금액 검증 | 클라이언트 amount 신뢰 금지. 서버 주문 amount 와 토스 승인 amount 일치 |
| 로그인 | checkout/confirm 은 Bearer 토큰 필수 |
| 웹훅 | 토스 서명/IP 정책 준수 |
| 데모 upgrade | `ALLOW_DEMO_BILLING_UPGRADE=false` 유지 |
| HTTPS | `roadlog.co.kr` 만 운영 키 사용 |

---

## 5. 구현 단계 (개발)

| 단계 | 내용 | 의존 |
|------|------|------|
| **P0** | 통신판매업 신고 + 토스 가맹 신청 | 사업자 |
| **P1** | `orders` 저장 + checkout/confirm API (테스트 키) | P0 키 발급 |
| **P2** | 웹 요금제 버튼 → 결제창 연결 | P1 |
| **P3** | 웹훅 + 중복 결제 방지 | P1 |
| **P4** | 라이브 키 + Railway 환경변수 + 실결제 1건 테스트 | 심사 통과 |
| **P5** (선택) | 정기결제(빌링키) | 안정화 후 |

---

## 6. 사용자에게 보이는 UX

1. 로그인 필수 (비로그인 → 로그인 모달)  
2. Pro 카드 → **「카드로 결제하기」**  
3. 토스 결제창  
4. 성공 → “Pro가 활성화되었습니다” + 사용량 무제한 표시  
5. 실패 → “결제가 취소되었습니다. 다시 시도해 주세요”  

관리자 대시보드: 기존 결제 목록 + 주문 목록(선택).

---

## 7. 사이다페이와의 역할 분리

| | 사이다페이 | 토스페이먼츠 |
|--|------------|--------------|
| 용도 | 수리점 현장·원격 카드 | **roadlog.co.kr 구독** |
| 정산 | 기존 계약 | 온라인 가맹 정산 |
| 로드로그 연동 | 수동 Pro (비상) | **자동 Pro** |

---

## 8. 지금 당장 할 일 (코드 전)

1. [ ] 통신판매업 신고 진행  
2. [ ] [토스페이먼츠](https://www.tosspayments.com/) 회원가입·가맹 신청  
3. [ ] 서비스 URL `https://roadlog.co.kr` 등록  
4. [ ] 테스트 키 발급되면 개발 시작 가능  
5. [ ] Railway Variables 에 키 넣을 준비  

---

## 9. 다음 메시지에서 진행할 개발 (키 나온 뒤)

- `modules/billing_toss.py` (또는 `billing.py`)  
- `server.py` checkout / confirm / webhook  
- `web/app.js` 결제 버튼  
- `data/orders.json` 스키마  

테스트 키(`test_ck_`, `test_sk_`)가 준비되면 **P1 구현**으로 바로 들어가면 됩니다.

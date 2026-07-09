# 문의 폼 연결 가이드 (Google Form / Tally)

로드로그 웹의 **「서비스 피드백 및 문의하기」** 버튼은 환경변수 `CONTACT_FORM_URL`을 사용합니다.

## 1. 빠른 연결

프로젝트 루트 `.env`에 추가:

```env
CONTACT_EMAIL=corelabs.studio@gmail.com
CONTACT_FORM_URL=https://docs.google.com/forms/d/e/1FAIpQLScl9ZJD_crv1d6JPDzdNaYTDzUQXKkLNx_X6pmyEwsg_1DnGg/viewform?usp=sf_link
```

기본값은 위 구글 폼으로 설정되어 있습니다.  
`.env`의 `CONTACT_FORM_URL`로 덮어쓸 수 있으며, 서버 재시작 후 `/api/meta` → 웹 문의 버튼에 반영됩니다.

## 2. 권장 폼 문항

| 문항 | 유형 | 비고 |
|------|------|------|
| 문의 유형 | 객관식 | 버그 / 기능 요청 / 단순 문의 |
| 이메일 | 단답 | 필수 |
| 이름·회사 | 단답 | 선택 |
| 제목 | 단답 | 필수 |
| 상세 내용 | 장문 | 필수 |
| 재현 단계 | 장문 | 버그 시 |
| 첨부 | 파일 | 선택 |
| 긴급도 | 객관식 | 낮음/보통/높음 |

## 3. 접수 후 처리

1. 폼/메일 수신  
2. `docs/ops/AI_CUSTOMER_SUPPORT_MANUAL.md` 기준으로 AI 초안 생성  
3. 대표(호현수) 검토  
4. 공식 회신  

---

*CoreLabs 내부 운영 문서*

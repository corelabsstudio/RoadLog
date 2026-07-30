# RoadLog 일일 SEO — 3단 에이전트 프롬프트 (Trigger)

이 프롬프트를 **매일 1회(목표: 한국시간 오전 9시 전후)** 또는  
사용자가 **「로드로그 SEO」/「로드로그 일일 마케팅」** 이라고 할 때 실행한다.

**선행 컨텍스트 (필수 읽기)**  
1. `docs/marketing/Context/ONE_PAGER.md`  
2. `docs/marketing/AGENT_TEAM.md`  
3. 이 파일  

## 제품 범위 (2026-07-31 개정)

- 이 파일은 **RoadLog 파이프**다. 로드로그 글·배포는 여기 규칙을 따른다.
- 사용자가 **「뉴스 올려」/ 둘 다 / 로드로그+웨이크어게인** 이라고 하면  
  **같은 세션에서 WakeAgain SEO도 이어서 실행해도 된다** (한 제품 제한 폐지).
- 단, **한 페이지·한 카피 안에 RoadLog와 WakeAgain 브랜드를 섞지 않는다.**  
  제품별로 조사→작성→배포를 **순서대로** 끝낸다.
- WakeAgain만 하면 될 때는 WA 쪽 `DAILY_SEO_PROMPT.md`만 쓰면 된다.

---


## 역할 분담 (한 세션에서 순서대로)

| 단계 | 역할 | 종료 조건 |
|------|------|-----------|
| **1** | Research | 이슈 목록 확정 또는 `NO_NEWS_TODAY` |
| **2** | SEO Writer | 브리핑±풀글 초안 + index/sitemap 패치 |
| **3** | Review | PASS 또는 FAIL(사유) · FAIL 시 Writer 1회 수정 후 재검수 |
| **4** | Publisher | Review PASS 후에만 커밋/배포 (사람 승인 권장) |

---

## 절대 규칙 (전 역할 공통)

1. 뉴스 **전문 복제 금지**. 3~4줄 자체 요약 + 원문 링크.
2. 「세무사 검증」「절세 보장」「세금 폭탄 확정」 단정 금지. 리스크는 “불리해질 수 있다/소명 부담” 수준.
3. 한도 금액(예: 1500만원)은 확정 수치처럼 단정하지 말 것. 최신 규정·전문가 확인 유도.
4. 이미 `docs/marketing/news_digest/items.json` 에 있는 `source_url` / 유사 slug 는 스킵.
5. 관련 뉴스가 **0건**이면 억지 양산하지 말고 `NO_NEWS_TODAY` 로 보고 종료.
6. 관련 뉴스가 있으면 **지갑 직결 건은 브리핑으로 최대한 반영**, 그중 1건은 **풀 SEO 포스팅**.
7. 배포(push)는 Review PASS 전 금지.

## 롱테일 키워드 (풀 포스팅 시 제목+본문에 주제에 맞게 선택)

- 법인차 국세청 운행록 양식
- 업무용 차량 비용 인정
- 개인사업자 차량유류비 증빙
- 출퇴근 기록 엑셀 자동화

---

## 1) Research

웹 검색으로 한국어 최신 이슈 수집 (예):

- 법인차 운행기록부 국세청
- 업무용 승용차 비용 인정
- 법인차 연두색 번호판
- 개인사업자 차량 유류비 운행일지
- 세무조사 법인차량

**필터**  
- 포함: 세금, 비용 인정, 운행기록부, 규제, 벌금, 보험 요건, 세무조사  
- 제외: 신차 출시, 연비, 단순 교통사고, 무관한 자동차 뉴스  

**출력**

```
RESEARCH_OUT:
- count: N
- items: [{title, source_url, why_wallet, proposed_slug}]
- flagship_candidate: slug or none
- or: NO_NEWS_TODAY
```

`NO_NEWS_TODAY` 이면 **여기서 전체 파이프 종료** (Writer/Publisher 생략).

---

## 2) SEO Writer

### A. 브리핑 등록

채택 뉴스마다 `docs/marketing/news_digest/items.json` 에 추가:

```json
{
  "slug": "YYYY-MM-DD-짧은영문",
  "date": "YYYY-MM-DD",
  "title": "...",
  "tags": ["..."],
  "wallet": "세금·규제 등",
  "source_name": "...",
  "source_url": "https://...",
  "summary": ["줄1", "줄2", "줄3"],
  "pitch": "로드로그 해결책 2~4문장 (스탬프·Excel/PDF/DOCX, 세무 보장 없음)"
}
```

```
python scripts/make_news_digest.py
```

### B. 풀 SEO 포스팅 (하루 1편, 가장 임팩트 큰 이슈)

`web/blog/<slug>.html` 생성. 구조: `docs/marketing/Templates/blog.md`  
참고 HTML: `web/blog/corporate-vehicle-log.html`

필수 섹션:

1. 제목 (키워드 + 클릭 유도)
2. 뉴스 요약 3줄 + 출처 링크
3. 리스크 분석 (법인/개인사업자 세무·시간) — 단정 금지
4. 해결책 + CTA → https://roadlog.co.kr  
   취지: 현장 스마트폰 스탬프 → 제출용 정리, Free 체험
5. 면책 문단
6. `web/sitemap.xml` · `web/blog/index.html` 목록 상단에 카드 추가

### C. Writer 자체 점검 (Review 전)

- ONE_PAGER 금지 메시지 없음
- slug 중복 없음

---

## 3) Review

`AGENT_TEAM.md` Review 체크리스트 전부 통과해야 PASS.

```
REVIEW_OUT:
- status: PASS | FAIL
- fails: [ ... ]
- fix_instructions: (FAIL일 때만, Writer용 1회 수정 지시)
```

FAIL → Writer 1회 수정 → Review 재실행.  
2회 연속 FAIL이면 사람에게 에스컬레이션하고 배포 중단.

---

## 4) Publisher (Review PASS 후)

사람 승인 권장. 승인 후:

```
git add docs/marketing/news_digest web/blog web/sitemap.xml
git commit -m "content: daily RoadLog news SEO digest YYYY-MM-DD"
git push origin main
python scripts/_deploy_latest.py
```

### 티스토리 (토큰 있을 때만)

- 블로그: https://onhae126.tistory.com/ (`TISTORY_BLOG_NAME=onhae126`)
- 설정: `RoadLog/.launch/tistory.env` (없으면 스킵)

```
python tools/tistory_publish/publish.py --file web/blog/<flagship>.html --title "글제목" --tags "로드로그,운행일지,법인차"
```

---

## 프로젝트 경로

`C:\Users\hysoo\Projects\RoadLog` (또는 `projects\RoadLog`)

## 완료 보고 포맷

```
PRODUCT: RoadLog
DATE: ...
PIPE: daily-seo
RESEARCH: n | NO_NEWS_TODAY
BRIEFINGS: n
FLAGSHIP: url or none
REVIEW: PASS | FAIL
PUBLISH: pending | done | skipped
TISTORY: url or SKIP_NO_TOKEN
LIVE: ok/fail
NOTES: ...
```

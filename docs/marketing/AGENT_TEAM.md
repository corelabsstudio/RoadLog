# RoadLog 마케팅 에이전트 팀 (Harness)

> 빌더 조쉬형 구조: **Context → Template → SOP → 역할 분리 → 사람 승인 후 발행**  
> 세팅이 품질을 결정한다. **한 글 = 한 브랜드** (로드로그 페이지에 WA 금지).  
> **한 요청 = 한 제품 제한은 폐지** — 사용자가 둘 다 / 뉴스 올리면 제품별 파이프를 순서 실행.

---

## 불러오기 / 실행 트리거

사용자가 아래처럼 말하면 이 하네스를 실행한다.

- **「로드로그 마케팅」** / **「로드로그 SEO」** / **「로드로그 일일 마케팅」**
- **「뉴스 올려」** (제품 미지정) → RoadLog 파이프 후 **WakeAgain SEO도 이어서** (별도 레포)
- 스케줄: `news_digest/DAILY_SEO_PROMPT.md` 일일 발화


### 시작 시 읽을 파일 (순서)

1. `docs/marketing/Context/ONE_PAGER.md`
2. 이 파일 (`AGENT_TEAM.md`)
3. `docs/marketing/news_digest/DAILY_SEO_PROMPT.md` (일일 SEO 시)
4. 필요 시 `CONTENT_PACK.md` · `CHANNELS.md`

---

## 역할 (Sub-agents)

| 역할 | 책임 | 산출 | 안 함 |
|------|------|------|--------|
| **Research** | 지갑 직결 뉴스·키워드 선별 | 이슈 목록 or `NO_NEWS_TODAY` | 본문 작성, CTA 단정 |
| **SEO Writer** | 브리핑 + 풀 포스팅 1편 | `items.json` 패치, `web/blog/*.html`, index/sitemap 초안 | 금지 문구, 배포 push |
| **Asset** (선택) | OG·카드 브리프 | `Templates/og-brief.md` 형식 | 로고 임의 변형 |
| **Review** | 브랜드·법무 톤·중복 검사 | PASS / FAIL + 수정 지시 | 새 주장 추가 |
| **Publisher** | 커밋·배포·티스토리 | 라이브 URL | **Review PASS 전 배포 금지** |

오케스트레이터(메인 에이전트)는 **라우팅만** 하고, 글을 쓰기 전에 Research → Writer → Review 순서를 지킨다.

---

## 라우팅 규칙

| 사용자/스케줄 의도 | 파이프 |
|--------------------|--------|
| 일일 SEO / 뉴스 | Research → SEO Writer → Review → (승인) Publisher |
| 짧은 홍보 문구 3종 | Writer(카피) → Review → 사람에게 복붙용 출력 (자동 게시 안 함) |
| 무료 서식 홍보 | CONTENT_PACK + resources CTA · 커뮤니티 장문 도배 금지 |
| **X 일일 팩** | `docs/marketing/x/DAILY_X_PROMPT.md` — 생성만 · 이미지 포함 · 자동 게시 없음 |
| ReachKit / 홍보 툴 | **이 팀 밖** → `tools/community_poster` 트리거로 분리 |
| WakeAgain SEO/풀홍보 | 사이트 SEO는 WA 하네스 · **X는 소프트만** (`x/STRATEGY.md`) |

---

## 일일 SEO 파이프 (기본)

```text
1 Research
   - DAILY_SEO_PROMPT 필터
   - 0건 → NO_NEWS_TODAY 보고 후 종료 (억지 양산 금지)
2 SEO Writer
   - 관련 건 브리핑 → items.json + make_news_digest.py
   - 임팩트 1건 → web/blog/<slug>.html (Templates/blog.md 구조)
   - blog/index.html · sitemap.xml 상단 반영
3 Review
   - ONE_PAGER 금지 메시지
   - slug/제목 중복
   - 출처 링크·면책 문단 존재
   - FAIL 시 Writer 1회만 수정 후 재검수
4 Publisher (사람 승인 권장)
   - git commit/push main
   - scripts/_deploy_latest.py (또는 기존 배포 습관)
   - 티스토리: 토큰 있을 때만
```

상세 절차·완료 보고 포맷: [`news_digest/DAILY_SEO_PROMPT.md`](./news_digest/DAILY_SEO_PROMPT.md)

---

## Review 체크리스트 (필수)

- [ ] 절세 보장·세무사 검증·세금 폭탄 확정 표현 없음
- [ ] 금액 한도를 확정 사실처럼 쓰지 않음
- [ ] CTA가 roadlog.co.kr 또는 /resources/ 등 허용 링크
- [ ] WakeAgain·ReachKit 혼입 없음
- [ ] 뉴스 전문 복제 없음 (요약 + 원문 링크)
- [ ] slug·canonical 중복 없음
- [ ] 면책(세무 조언 아님) 문단 있음 (풀 포스팅)

---

## 채널 우선순위 (발행 자동화 범위)

| 순위 | 채널 | 자동화 |
|------|------|--------|
| 1 | 사이트 블로그 + sitemap | **기본 파이프** |
| 2 | 무료 서식 랜딩 CTA | 글·카피에 링크 |
| 3 | 지인 DM / 오픈챗 짧은 글 | **초안만** (사람 복붙) |
| 4 | 링크드인·X | 주 2~3 · 초안만 |
| — | 카페 도배·Buffer 대량 | **안 함** |

---

## 완료 보고 포맷

```
PRODUCT: RoadLog
DATE: YYYY-MM-DD
PIPE: daily-seo | promo-copy | other
RESEARCH: n issues | NO_NEWS_TODAY
BRIEFINGS: n
FLAGSHIP: url or none
REVIEW: PASS | FAIL (reason)
PUBLISH: pending | done | skipped
LIVE: ok/fail/n-a
NOTES: ...
```

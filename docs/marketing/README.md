# RoadLog 마케팅 키트

사이트: https://roadlog.co.kr

## 에이전트 하네스 (실행 진입점)

| 파일 | 역할 |
|------|------|
| **[AGENT_TEAM.md](./AGENT_TEAM.md)** | 역할·라우팅·Review·완료 보고 (**팀 운영 SOP**) |
| **[Context/ONE_PAGER.md](./Context/ONE_PAGER.md)** | 브랜드·금지 문구·CTA·키워드 |
| **[Templates/](./Templates/)** | 블로그·소셜·OG 골격 |
| **[news_digest/DAILY_SEO_PROMPT.md](./news_digest/DAILY_SEO_PROMPT.md)** | 일일 SEO 3단 실행 프롬프트 |

### 트리거 문구

- `로드로그 마케팅` · `로드로그 SEO` · `로드로그 일일 마케팅`
- **X:** `X 마케팅` · `로드로그 X` · `일일 X 팩` → [`x/README.md`](./x/README.md)

### 일일 파이프 (요약)

```text
Research → SEO Writer → Review → (승인) Publisher
```

관련 뉴스 0건이면 `NO_NEWS_TODAY` 종료 (억지 양산 금지).

---

## 기존 자산

| 파일 | 내용 |
|------|------|
| [CONTENT_PACK.md](./CONTENT_PACK.md) | 복붙용 문구 (카톡·블로그·X) |
| [CHANNELS.md](./CHANNELS.md) | 채널 우선순위·게시 팁 |
| [free_templates/](./free_templates/) | 무료 서식 팩·공유 카피 |
| [promo/](./promo/) | 홍보 이미지·POST_COPY |
| [news_digest/](./news_digest/) | 뉴스 브리핑 items + 빌드 |
| [smartstore/](./smartstore/) | 스마트스토어 상세 에셋 |

## 자동 리마인드 (Grok Tasks)

- 이름: `roadlog-promo-copy` (있는 경우)
- 주기: 매일 10:00 (Asia/Seoul) — 홍보 문구 3종 생성 후 알림
- SEO: `DAILY_SEO_PROMPT` 오전 9시 전후

## 사이트 SEO

- OG: `/icons/og-image.jpg`
- sitemap: https://roadlog.co.kr/sitemap.xml
- robots: https://roadlog.co.kr/robots.txt
- 블로그: https://roadlog.co.kr/blog/
- 뉴스: https://roadlog.co.kr/blog/news/
- 무료 서식: https://roadlog.co.kr/resources/

## 범위 밖

- **ReachKit** (`tools/community_poster`) — 별도 트리거
- **WakeAgain** — `WakeAgain/docs/marketing/AGENT_TEAM.md`

# RoadLog 풀 SEO 블로그 템플릿 (구조 스펙)

> 실제 파일: `web/blog/<slug>.html`  
> 스타일: 기존 `corporate-vehicle-log.html` · `blog.css` 재사용  
> 이 MD는 에이전트용 **골격**이다. HTML 마크업은 기존 글 복사 후 본문만 교체.

---

## 메타

- `lang=ko`
- `title`: `{키워드 포함 제목} | 로드로그 가이드`
- `description`: 150자 내 · 세무 단정 금지
- `canonical`: `https://roadlog.co.kr/blog/<slug>` (확장자 없이 기존 관례 따름)
- `og:image`: `https://roadlog.co.kr/icons/og-image.jpg` (기본)
- JSON-LD `Article` · author/publisher CoreLabs

## 본문 필수 섹션 순서

1. **Kicker** (선택): 예) 법인차 · 운행기록 · 실무
2. **H1** — 키워드 + 클릭 유도 (클릭베이트·보장 금지)
3. **리드** — 누구를 위한 글인지 2~3문장
4. **뉴스/이슈 요약** — 3줄 + **출처명 + 원문 링크**
5. **리스크·실무 부담** — 법인/개인사업자 관점 (단정 아닌 “부담·소명” 톤)
6. **실무 팁** — 기록 습관, 제출용 정리 (로드로그 없이도 쓸 수 있는 팁 포함)
7. **해결책 + CTA**
   - 취지: 현장 스마트폰 스탬프 → 제출용 정리, Free 체험
   - 링크: https://roadlog.co.kr
   - 선택: 무료 서식 https://roadlog.co.kr/resources/
8. **면책** — 세무·법률 자문 아님, 최신 규정·전문가 확인 유도

## 키워드

- 롱테일 3개 내외를 제목+본문에 자연스럽게 (키워드 스터핑 금지)
- ONE_PAGER SEO 목록 참고

## 배포 전 Writer가 같이 손댈 파일

- `web/blog/index.html` — 카드 상단 추가
- `web/sitemap.xml` — URL 추가
- 뉴스 브리핑이면 `docs/marketing/news_digest/items.json` + `python scripts/make_news_digest.py`

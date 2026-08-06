# RoadLog 홍보 이미지 (오픈 초기 톤)

톤: **광고·세일즈 아님** · 1인 개발 사연 + “한번 써 보고 피드백 부탁”  
바탕화면 복사: `로드로그_홍보이미지\`

## 메인 (긴 스크롤)

| 파일 | 규격 | 용도 |
|------|------|------|
| **`roadlog_promo_long_story.png`** | 1080×~10000 | **카톡·커뮤니티·블로그 본문 첨부 (권장)** |
| `roadlog_promo_long_story.jpg` | 동일 (용량↓) | 메신저 전송용 |

포함: 사연 · 스크린샷 · 기능 · Excel/PDF/DOCX 출력 예시 · B2B 한 줄 ·  
카드 없이 Free 10회 즉시 체험 · roadlog.co.kr  
(선착순 VIP 문구는 제거)

재생성:
```bash
python scripts/_capture_promo_shots.py   # 또는 _recapture_clean_shots.py
python scripts/make_promo_long.py
```

## 짧은 카드 (보조)

| 파일 | 크기 | 용도 |
|------|------|------|
| `roadlog_promo_square_1080.png` | 1080×1080 | 인스타·썸네일 |
| `roadlog_promo_og_1200x630.png` | 1200×630 | 링크 미리보기 |
| `roadlog_promo_story_1080x1920.png` | 1080×1920 | 스토리 |
| `roadlog_promo_kakao_1000x500.png` | 1000×500 | 짧은 카드 |

```bash
python scripts/make_promo_images.py
```

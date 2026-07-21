# 리치킷 — 판매 준비

| 항목 | 값 |
|------|-----|
| **Brand** | **리치킷 (ReachKit)** |
| **버전** | product_config.PRODUCT_VERSION (0.4.0) |
| **아이콘** | `assets/icon.ico` / `assets/icon.png` |
| **실행** | `ReachKit.bat` · 바탕화면 `리치킷.lnk` |
| **단계** | 범용 홍보 툴 · 성과 검증 → 소액 유료 베타 |
| **상태 복구** | `SAVE_POINT.md` · 트리거 **「홍보 불러와」** |

바로가기:

```powershell
powershell -ExecutionPolicy Bypass -File tools\community_poster\make_shortcut.ps1
.\.venv\Scripts\python.exe tools\community_poster\assets\_make_ko_shortcut.py
```

---

## 제품 포지션

| 판다 | 안 판다 |
|------|---------|
| 사이트 분석 → 홍보 문구 | 100개 카페 원클릭 도배 |
| 채널·게시판 추천 | 캡차·가입 자동화 |
| 작성 보조 (등록 기본 끔) | 무조건 등록 성공 보장 |
| 가드레일 · 검증 대시보드 | 플랫폼 규정 우회 |

> 리치킷 — 인공지능으로 분석하고 · 쓰고 · 도달하세요.

**특정 서비스에 종속되지 않습니다.** 사용자가 넣은 제품 URL 기준입니다.

---

## 이번 주 채널 3곳 (성과 검증)

| # | 채널 | 요일 |
|---|------|------|
| 1 | 네이버 블로그 | 월·목 |
| 2 | 카카오 오픈채팅 | 화 |
| 3 | 링크드인 | 수 |

상세: [`VALIDATION_WEEK.md`](VALIDATION_WEEK.md) · 앱 **이번 주 3채널**

목표: 시도 5+ · 성공률 50%+ · 등록 자동 끔

# 리치킷 저장 지점 (홍보 프로그램)

> 다음에 **「홍보 불러와」** / **「홍보 불러와줘」** / **「ReachKit 이어서」** / **「리치킷 이어서」** 라고 하면  
> 이 문서 + `PRODUCT.md` 기준으로 **리치킷부터** 복구한다.

**저장 시각:** 2026-07-13  
**버전:** **0.5.3** (글 미입력 시 성공 처리 버그 수정)  
**경로:** `C:\Users\hysoo\Projects\RoadLog\tools\community_poster\`  
**브랜드:** 리치킷 (ReachKit)  
**태그라인:** `3단계로 홍보 글 올리기` (`product_config.PRODUCT_TAGLINE`)

**중요:** 특정 서비스에 종속되지 않은 **범용 홍보 툴**.  
(저장소 경로에 RoadLog가 있어도 UI·카피에 넣지 말 것. 제품 URL = 사용자 입력.)

---

## 불러올 때 에이전트가 할 일

1. `cd C:\Users\hysoo\Projects\RoadLog\tools\community_poster`
2. **이 파일** · `product_config.py` · `help_text.py` · `app.py` 우선 읽기
3. 실행: `ReachKit.bat` 또는 venv `pythonw app.py`
4. **처음부터 설명하지 말고** 이어서 작업
5. 사용자와 **한국어** 소통
6. 외부 서비스 브랜드를 UI/카피에 넣지 말 것

### 실행

```powershell
C:\Users\hysoo\Projects\RoadLog\tools\community_poster\ReachKit.bat
```

바탕화면: `리치킷.lnk`

---

## 2026-07-13 세션 요약 (여기까지 기억)

### 로드로그 사업 방향 (대화 결론)
- Mark Tilbury 영상 기준: 분석가 기질 → **B2B 도입 패키지 80% + 셀프가입 20%**
- 로드로그는 분석가 성향과 **제품 DNA는 맞음**, 수익 엔진은 당분간 **맞춤 도입(범위 제한)** 이 유리
- 지인 없음 → 블로그·카페·콜드 아웃리치 (링크드인은 보조, 프로필만 세팅 후 보류 가능)
- 링크드인: Industry Software · 헤드라인 RoadLog · 로고/배너는 바탕화면 생성됨  
  - `C:\Users\hysoo\Desktop\코어랩스_링크드인_프로필.png`  
  - `C:\Users\hysoo\Desktop\코어랩스_링크드인_배너.png`  
  - 원본: `docs/marketing/brand/`

### 리치킷 UX (판매 가능하게 단순화)
| 버전 | 내용 |
|------|------|
| 0.4.x | 쉬운 말 전면 개편 (구조 파악→글 쓰는 칸 찾기 등) |
| 0.4.2 | `app_dialogs.py` 테마 팝업 (messagebox 대체) |
| **0.5.0** | **초간단 모드 기본** — 홈 ①②③ |
| 0.5.1 | 팝업 글자 잘림 수정 · 다이얼로그 크기 자동 맞춤 |
| **0.5.2** | **결과 탭 완전 제거** · 가입·문의 기록 UI 삭제 |
| **0.5.3** | 제목·본문 미입력인데「완료」뜨던 버그 수정 · 검색 화면 실패 처리 · 작성 성공 시 브라우저 5분 유지 |

### 현재 UI (필수)
- 사이드바: **홈** / **자세히** 만 (결과 없음)
- **홈:**  
  ① 홍보글 만들기 (사이트 URL)  
  ② 올릴 곳 주소 + 아이디/비번 + 「올릴 곳 고르기」  
  ③ 브라우저에서 글 쓰기 (올리기는 직접)
- **자세히:** 카드 3개로 중복 제거  
  1. 올릴 곳·계정 (칸 찾기 1회만)  
  2. 게시판·입력 보조  
  3. 글 양식·스타일  
  + 하단 실행·저장 1줄
- **어디에 올릴까:** 버튼 3개만 (이 곳으로 정하기 / 닫기 / 목록 새로고침)
- 등록 자동 기본 끔 · 캡차·가입 인증은 사용자 직접

### 핵심 파일
| 파일 | 역할 |
|------|------|
| `app.py` | GUI · 홈/자세히 |
| `app_dialogs.py` | 테마 팝업 show_message / ask_confirm / ask_text |
| `product_config.py` | 버전·문구·가드레일 상수 |
| `help_text.py` | 사용 방법 (3단계) |
| `ui_theme.py` | 배틀넷 톤 다크·시안 |
| `poster.py` · `structure_scan.py` · `guardrails.py` | 작성·칸 찾기·안전 제한 |

### 다음 하면 좋은 것 (미완)
- 카페 실전 1~2회 올리기 (홈 3단계만)
- 필요 시 인스톨러·결제 등 판매 패키징
- VALIDATION_WEEK / 주간 3채널 UI는 코드에 잔존 가능하나 **메뉴에서 안 보임** (결과 탭과 함께 사실상 비활성)

---

## 가드레일 기본값

| 항목 | 값 |
|------|-----|
| 하루 시도 | 5회 |
| 쿨다운 | 성공 후 30분 |
| 동일 본문 | 성공한 직전 글과 동일 시 차단 |
| 등록 자동 | 기본 끔 |

---

## 복구 확인

```powershell
cd C:\Users\hysoo\Projects\RoadLog\tools\community_poster
Test-Path app.py, app_dialogs.py, ReachKit.bat
.\..\..\.venv\Scripts\python.exe -c "from product_config import PRODUCT_VERSION; print(PRODUCT_VERSION)"
# → 0.5.3
```

# 리치킷 (ReachKit) 1.0

**3단계로 홍보 글 올리기** — 사이트 분석 · 문구 · 채널 안내 · 작성 보조 · 가드레일 · 로컬 성과.

특정 SaaS에 종속되지 않습니다. **사용자가 넣은 제품 URL** 기준입니다.

| 항목 | 내용 |
|------|------|
| 버전 | **1.0.0** |
| 제작 | 코어랩스 |
| 문의 | corelabs.studio@gmail.com |
| 플랫폼 | Windows (Python 3.10+) |
| 상태 | Release (판매·양도 가능 패키지) |

---

## 5분 설치

PowerShell에서:

```powershell
cd C:\Users\hysoo\Projects\RoadLog\tools\community_poster
powershell -ExecutionPolicy Bypass -File .\setup_reachkit.ps1
```

설치 후:

- `ReachKit.bat` 더블클릭  
- 또는 바탕화면 **리치킷** 바로가기  

`setup`이 하는 일: 로컬 `.venv` · `requirements.txt` · Playwright Chromium · 환경 점검 · 바로가기.

---

## 초간단 사용 (홈 ①②③)

1. **내 사이트 주소** → 「홍보글 만들기」  
2. **올릴 곳** 주소 + 계정 (또는 「올릴 곳 고르기」)  
3. **브라우저에서 글 쓰기** → 확인 후 **올리기는 직접**

메뉴:

| 탭 | 용도 |
|----|------|
| 홈 | 평소 3단계 |
| 성과 | 시도·성공률·가입/문의 메모 |
| 자세히 | 칸 찾기·게시판 등 고급 |

상단 **환경 점검** / **정보** / **사용 방법** 지원.

---

## 이 제품이 하는 일 / 안 하는 일

| 함 | 안 함 |
|----|--------|
| 사이트 분석 → 홍보 문구 | 100개 카페 원클릭 도배 |
| 채널·게시판 추천 | 캡차·가입 자동화 |
| 작성 보조 (올리기 기본 끔) | 게시 성공 보장 |
| 가드레일 · 로컬 성과 로그 | 플랫폼 규정 우회 |

---

## 양도·배포 패키지

구매자/인수자에게 넘길 때:

1. 이 폴더 전체 복사 (또는 `make_portable.ps1` zip)  
2. 수신 PC에서 `setup_reachkit.ps1` 1회  
3. `ReachKit.bat` 실행 → 환경 점검 전부  

상세: [`PRODUCT.md`](PRODUCT.md) · [`TRANSFER.md`](TRANSFER.md)

---

## 개발 실행 (모노레포)

```powershell
C:\Users\hysoo\Projects\RoadLog\.venv\Scripts\python.exe tools\community_poster\app.py
```

버전 확인:

```powershell
python -c "from product_config import PRODUCT_VERSION; print(PRODUCT_VERSION)"
```

환경 점검:

```powershell
python healthcheck.py
```

# 리치킷 저장 지점 (홍보 프로그램)

> 다음에 **「홍보 불러와」** / **「ReachKit 이어서」** / **「리치킷 이어서」** 라고 하면  
> 이 문서 + `PRODUCT.md` 기준으로 **리치킷부터** 복구한다.

**저장 시각:** 2026-07-30  
**버전:** **1.0.0** (판매·양도 가능 패키지)  
**경로:** `C:\Users\hysoo\Projects\RoadLog\tools\community_poster\`  
**브랜드:** 리치킷 (ReachKit)  
**태그라인:** `3단계로 홍보 글 올리기`

**중요:** 특정 서비스에 종속되지 않은 **범용 홍보 툴**.  
(저장소 경로에 RoadLog가 있어도 UI·카피에 넣지 말 것. 제품 URL = 사용자 입력.)

---

## 1.0에서 한 일

- 버전 1.0.0 release
- 성과 탭 복구 (요약·최근 기록·가입/문의 메모)
- 첫 실행 온보딩
- 환경 점검 UI + `healthcheck.py`
- 제품 정보(About)
- `setup_reachkit.ps1` 원클릭 설치 (로컬 `.venv`)
- `ReachKit.bat` 경로 독립 (로컬 venv → monorepo venv → 시스템)
- README / PRODUCT / TRANSFER / make_portable.ps1

## 실행

```powershell
# 최초 1회
powershell -ExecutionPolicy Bypass -File setup_reachkit.ps1

# 평소
.\ReachKit.bat
```

## 핵심 파일

| 파일 | 역할 |
|------|------|
| `app.py` | GUI · 홈/성과/자세히 |
| `healthcheck.py` | 환경 점검 |
| `setup_reachkit.ps1` | 설치 |
| `product_config.py` | 버전·채널·면책 |
| `validation_log.py` | 성과 로그 |
| `TRANSFER.md` | 양도 가이드 |

## 다음 (선택)

- PyInstaller 단일 exe (선택 패키징)
- 매물용 실 UI 스크린샷 3~5장 교체 (웨이크어게인)
- 카페 실전 검증 주간 수치 채우기

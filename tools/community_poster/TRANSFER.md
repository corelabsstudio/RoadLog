# 리치킷 1.0 — 양도·인수 가이드

구매자 또는 인수자가 **다른 Windows PC**에서 바로 쓰게 하기 위한 문서입니다.

## 넘기는 것

| 포함 | 제외 (선택) |
|------|-------------|
| `community_poster` 폴더 전체 | `__pycache__` |
| `assets/`, `*.py`, `*.bat`, `*.ps1`, `*.md` | `.venv` (수신자가 재설치) |
| `requirements.txt` | `data/last_form.json` 비밀번호 저장분 |
| 이 문서 · README · PRODUCT | 판매자 개인 로그 |

비밀번호가 저장된 경우 `data/last_form.json` 을 비우거나 삭제 후 전달하세요.

## 인수 PC에서 할 일 (1회)

```powershell
cd <리치킷폴더>
powershell -ExecutionPolicy Bypass -File .\setup_reachkit.ps1
.\ReachKit.bat
```

앱 상단 **환경 점검**이 전부 OK인지 확인합니다.

## 동작 확인 (5분)

1. 홈 ① 본인 사이트 URL → 홍보글 만들기  
2. 성과 탭이 열리는지  
3. 사용 방법 · 제품 정보 창  
4. (선택) 브라우저 글 쓰기 1회 — 올리기는 직접  

## 라이선스·한계 (인수 시 고지)

- 캡차·휴대폰 인증·최종 게시는 사용자 책임  
- 커뮤니티 규정 위반·도배는 지원하지 않음  
- LLM/외부 API 키가 필요하면 **구매자 계정** 사용  
- 결과 로그는 **로컬 PC에만** 저장  

## 지원

- 코어랩스 · corelabs.studio@gmail.com  
- 버전: 제품 정보 창 또는 `product_config.PRODUCT_VERSION`

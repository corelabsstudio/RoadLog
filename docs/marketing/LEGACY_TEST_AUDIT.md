# 2026-09-24 기존 37개 테스트 분류

`scripts/_roadlog_suite_test.py`는 현재 사주 사이트 이전의 운행일지·현장일지 웹앱 계약을 검사합니다. 로컬 TestClient로 실행한 결과 13/37 통과이며, 이 숫자를 현 마케팅 폐쇄 루프의 성공률로 사용하면 안 됩니다. 아래는 실행 순서대로 전체 37항목입니다. `CURRENT_VALID`는 현재 의미 있는 검사, `LEGACY_REMOVED_FEATURE`는 더는 제공하지 않는 API/자산, `BROKEN_TEST`는 200만 확인하여 잘못 통과하거나 전제 오류가 있는 검사입니다. 이번 출력에서 `ACTUAL_REGRESSION`으로 확인된 항목은 없습니다.

| # | 검사 | 분류 | 이번 실행 |
|---:|---|---|---|
| 1 | GET / | CURRENT_VALID | 통과 |
| 2 | GET /app.js | BROKEN_TEST | 통과지만 HTML 응답도 통과시킴 |
| 3 | GET /styles.css | LEGACY_REMOVED_FEATURE | 404 |
| 4 | GET /ui-sound.js | LEGACY_REMOVED_FEATURE | 404 |
| 5 | GET /manifest.webmanifest | CURRENT_VALID | 통과 |
| 6 | GET /sw.js | CURRENT_VALID | 통과 |
| 7 | GET /locales/ko.json | LEGACY_REMOVED_FEATURE | 404 |
| 8 | GET /locales/en.json | LEGACY_REMOVED_FEATURE | 404 |
| 9 | GET /assets/legal/terms.md | LEGACY_REMOVED_FEATURE | 404 |
| 10 | GET /assets/templates/manifest.json | LEGACY_REMOVED_FEATURE | 404 |
| 11 | GET /health | CURRENT_VALID | 통과 |
| 12 | GET /api/health | CURRENT_VALID | 통과 |
| 13 | GET /api/meta | LEGACY_REMOVED_FEATURE | 404 |
| 14 | GET /api/reviews | LEGACY_REMOVED_FEATURE | 404 |
| 15 | GET /api/templates/defaults | LEGACY_REMOVED_FEATURE | 404 |
| 16 | health.ok | CURRENT_VALID | 통과 |
| 17 | meta.free_limit | LEGACY_REMOVED_FEATURE | 404에 따른 실패 |
| 18 | register short pw rejected | CURRENT_VALID | 통과 |
| 19 | register | CURRENT_VALID | 통과 |
| 20 | login after register | CURRENT_VALID | 통과 |
| 21 | login wrong password | CURRENT_VALID | 통과 |
| 22 | me without token | CURRENT_VALID | 통과 |
| 23 | me with token | CURRENT_VALID | 통과 |
| 24 | generate without auth | BROKEN_TEST | 대상 POST 라우트 없음(405) |
| 25 | GET settings | LEGACY_REMOVED_FEATURE | 404 |
| 26 | PUT settings | LEGACY_REMOVED_FEATURE | 405 |
| 27 | generate driving | LEGACY_REMOVED_FEATURE | 405 |
| 28 | generate field | LEGACY_REMOVED_FEATURE | 405 |
| 29 | export skipped | BROKEN_TEST | 사라진 운행일지 생성 결과에 연쇄 의존 |
| 30 | list logs | LEGACY_REMOVED_FEATURE | 예전 로그 계약과 불일치 |
| 31 | save log | LEGACY_REMOVED_FEATURE | 예전 로그 계약과 불일치 |
| 32 | get/delete log | BROKEN_TEST | 이전 저장 실패에 연쇄 의존 |
| 33 | GET style | LEGACY_REMOVED_FEATURE | 404 |
| 34 | style paste | LEGACY_REMOVED_FEATURE | 405 |
| 35 | upgrade pro status ok | LEGACY_REMOVED_FEATURE | 405 |
| 36 | billing claim | LEGACY_REMOVED_FEATURE | 405 |
| 37 | generate for limit check | LEGACY_REMOVED_FEATURE | 405 |

현재 마케팅 유효 테스트는 `scripts/_marketing_os_test.py`와 `scripts/_marketing_strategy_test.py`로 분리해 실행합니다. 예전 테스트를 통과시키려고 현 사주 서비스에 운행일지 라우트를 되살리지 않습니다. 기존 사주 기능의 별도 회귀 범위는 이번 표로 대체되지 않습니다.

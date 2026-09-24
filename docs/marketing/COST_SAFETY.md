# AI 마케팅 비용 안전장치 (2026-09-25, 미배포)

이 문서는 ROADLOG 마케팅 외부 호출에만 적용한다. 내부 3,000원은 실제 Google/Tavily 청구액 하드캡이 아니다.

## 기존 경로와 문제

- `modules/marketing_core/service.py:UsagePolicy`: 하루 3,000원·20회·팀원당 5회, 당시 요청당 고정 예약 20원.
- `modules/marketing_os.py:_run_role`: 역할별 20원 예약. `modules/marketing_core/repository.py:reserve_real_run`의 `BEGIN IMMEDIATE`가 `marketing_runs` 행을 원자적으로 만든다.
- 그러나 실제 `modules/marketing_gemini.py`의 최대 3회 HTTP 시도는 역할별 예약 한 행에 묶여 재시도 비용을 반영하지 않았다. 병렬 외부 HTTP 동시 실행 제한도 없었다.
- `marketing_runs`와 외부 감사는 SQLite에 남지만 DB 파일이 영속 볼륨이 아니면 재배포로 사라진다. 날짜 문자열은 서울 시간 생성 경로를 쓰고, 검색 별도 사용량은 기존에 서버 로컬 시간이었다.
- HTTP 실패·타임아웃에도 역할별 20원 예약을 남기지만 실제 공급자 청구액/생각 토큰은 기록하지 않았다.

## 이번 코드의 방어

- `marketing_cost_guard.py`: 허용 모델 `gemini-3.8-flash`의 2026년 말까지 공식 Standard 요금($0.75/$3.75 per million input/output tokens), 요청 JSON UTF-8 길이, `maxOutputTokens`와 보수적인 환산/안전계수로 사전 예약액을 계산한다. 미등록 모델·형식·2027년 이후 요금은 fail closed. 환산 2,000원/USD는 안전 가정이지 실제 환율이 아니다.
- `marketing_safety.before_call`: Gemini/Tavily의 **매 HTTP 시도 직전** 같은 SQLite `BEGIN IMMEDIATE` 안에서 유료 API ON, 오늘 kill, 기존 미가격 호출, 하루 3,000원 예약 합계, 하루 20회, 팀원당 5회, 동시 2회, 캠페인별 상한을 확인하고 감사 행을 예약한다. Tavily basic 검색은 1크레딧에 $0.008로 내부 16원 추정·32원 예약한다. 가격을 모르는 Brave 검색은 차단한다.
- `record_usage`: Gemini 응답의 입력·출력·생각 토큰을 별도 저장하고 가격표로 `actual_cost_estimate_krw`를 계산한다. 이 값은 사용량 기반 **예상 비용**이지 실제 청구액이 아니다. 누락·비정상·사전 예상 폭증은 오늘의 kill을 켠다. HTTP 재시도 각각 새 감사 행과 예약액을 소비한다. Gemini의 루프는 초기 호출+재시도 최대 2회다.
- 관리자는 자동운영 ON/OFF와 별도로 유료 API ON/OFF, 내부 예산(상한 3,000원), 하루 호출(상한 20), 팀원별 호출(상한 5)을 저장한다. 유료 API는 새 DB/기존 DB 모두 기본 OFF다. 이미지·영상·SNS는 기존 호출 상한 0으로 유지한다.
- 3회 연속 외부 API 오류, 비용 산정 실패, 사용량 누락/폭증, 내부 예약액 한도 도달 시 그날의 유료 호출을 막는다. 무료 로컬 진단·화면 조회는 차단하지 않는다.

## 3,000원 이상 실제 청구가 가능한 코드 경로와 남은 한계

1. `marketing_gemini.py:generate/generate_role`: 예상보다 입력·생각/출력 토큰이 많거나 Google 가격·환율이 변할 수 있다. 응답 후 kill은 **이미 발생한 호출**의 청구를 되돌리지 못한다. 타임아웃도 실제 과금 여부가 불명확하다.
2. `marketing_research.py:TavilyResearchProvider.search`: 1 basic 검색=1크레딧으로 예약하지만 Tavily 플랜/무료 잔여량/청구 실액은 즉시 조회하지 않는다. 응답 오류 전에 이미 사용한 크레딧일 수 있다.
3. `marketing_creative.py` 이미지 생성은 현재 호출 상한 0으로 차단된다. 향후 이 상한만 열면 이미지 요금 계산기가 없어 내부 3,000원 경계를 우회할 수 있다. 요금 계산기·동일 원자 가드 없이는 열면 안 된다. 영상 공급자는 현재 미구현, SNS 호출도 0건 차단이다.
4. 같은 `GEMINI_API_KEY`를 쓰는 사이트 본 서비스의 `modules/saju_writer.py:_call`, `modules/gwansang.py`의 사진/질문 생성, `modules/pet.py`의 사진 생성은 **마케팅 비용 가드 밖**이다. 손님 요청과 각 모듈의 재시도는 마케팅 3,000원에 합산되지 않는다. 이는 계정 전체 비용의 하드캡이 아님을 뜻한다.
5. `modules/marketing_safety.py:DB`는 `DATA_DIR/marketing_os.db`의 SQLite다. 운영에서 `DATA_DIR` 영속 볼륨 및 단일 공유 장부가 실제로 유지되는지, 여러 Railway 인스턴스가 별도 DB를 쓰지 않는지 아직 검증하지 않았다. 별도 DB라면 인스턴스마다 3,000원을 각각 쓸 수 있다.
6. Google 청구 집계는 지연될 수 있고 공급자 결제 계정 단위의 외부 호출·다른 프로젝트는 이 앱이 보지 못한다. 진짜 계정 수준 상한은 Google/Tavily 측의 별도 한도·청구 화면 확인이 필요하다.

## 검증과 배포 경계

- `scripts/test_marketing_cost_guard.py`: 모의 호출만으로 예산/병렬/재시도/중복/재시작/KST/사용량 오류/kill/횟수 제한을 검사한다.
- `scripts/_marketing_os_test.py`, `scripts/_marketing_safety_test.py`: 기존 회귀. 유료 HTTP는 실행하지 않는다.
- 이번 코드와 앞선 자동화 큐 리팩터링은 **둘 다 운영 미배포**. 두 변경의 diff를 논리적으로 나눠 검증하고 별도 운영 승인 없이 유료 스위치를 켜지 않는다.

가격 출처: https://ai.google.dev/gemini-api/docs/pricing · https://help.tavily.com/articles/6938147944-basic-vs-advanced-search-what-s-the-difference · https://www.tavily.com/pricing

# 조사·전략 계층 (2026-09-24)

## 현재 상태

외부 검색은 `TAVILY_API_KEY`와 `MARKETING_EXTERNAL_RESEARCH_ENABLED=true`가 둘 다 있을 때만 캠페인당 기본 검색 최대 2회 수행한다. 운영 키·계정이 없어 실제 Tavily 응답과 한국어 결과 품질은 아직 확인하지 않았다. 키가 없어도 내부 분석→블로그 초안→검수→승인 경로는 유지된다. `BraveResearchProvider`는 기존 모의 테스트 호환용으로 남겼지만 운영 선택 경로에서 더는 사용하지 않는다.

검색 결과는 URL·제목·500자 이하 snippet·관찰 시각·query를 `EXTERNAL_SOURCE`로 기록한다. 이것은 해당 페이지가 실제 검색 결과에 있었다는 근거일 뿐, snippet의 주장이 참이라는 검증은 아니다. AI의 해석은 `AI_INFERENCE`, RoadLog 내부 상품 열람/사이트 집계는 `MEASURED`, 실제 게시 후 귀속된 캠페인 성과는 `PAST_CAMPAIGN`으로 분리한다. 외부 링크는 관리자만 볼 수 있으며 제공자가 반환한 http(s) 주소만 표시한다.

현재 Content Gap은 기존 동적 블로그 제목과 정적 블로그 제목의 단어 겹침으로만 판단한다. 본문 의미 분석·검색량·경쟁사 매출·전환율은 측정하지 않는다. 질문은 실제 검색 결과 제목에 물음표 등이 있을 때만 `observedQuestions`로 기록한다. AI가 만든 질문을 실제 검색 질문으로 둔갑시키지 않는다.

전략 후보는 SEO 블로그, FAQ 블로그, 상품 페이지 개선, 이미지 SNS, 숏폼이다. 현재 자동 완성되는 채널은 블로그뿐이므로 이미지/영상/상품페이지 후보는 `BLOCKED_OPPORTUNITY`다. 디렉터가 검색·실측·과거 점수표를 보기 전에 전략을 결정하던 순서를 바꿨다. 후보 우선순위는 규칙 기반이며 AI 디렉터가 후속 `NO_ACTION`을 선택할 수 있다. 미래 최상 성과를 보장하지 않는다.

## 제공자 검토

| 항목 | Tavily Search (선택) | Brave Search (보류) | Google Custom Search JSON |
|---|---|---|---|
| 웹 결과·URL·제목·snippet | 제공 | 제공 | 제공 |
| 한국어 | 언어/한국 부스팅 파라미터; 실측 품질 미확인 | 한국 설정 가능 | 실측 미확인 |
| 무료 | 월 1,000크레딧, 카드 불필요 | 매월 $5 크레딧, 카드 필요 | 신규 고객 접근 제한 |
| 기본 검색 비용 | 1크레딧/건 | $5/1,000건 | 신규 도입 부적합 |
| API 키 | 필요 | 필요 | 필요 |
| 상업적 사용 | 고객 자체 서비스 내부 업무 용도 약관, 제3자 제공 금지 | 계약 범위 확인 필요 | 신규 도입 부적합 |
| 제한 | 개발 키 100 RPM, 운영 키 1,000 RPM (운영 키는 유료 플랜/PAYGO) | 플랜별 | 기존 고객 조건 |
| 저장 조건 | 출력·원문 제3자 권리 확인 필요; 내부 출처 기록만 | 일반 플랜의 검색 결과 보관 금지; 별도 권리 필요 | 별도 약관 확인 필요 |

근거: [Tavily 가격/크레딧](https://docs.tavily.com/documentation/api-credits), [검색 API](https://docs.tavily.com/documentation/api-reference/endpoint/search), [호출 제한](https://docs.tavily.com/documentation/rate-limits), [플랫폼 약관](https://www.tavily.com/terms), [Brave 가격·저장 조건](https://brave.com/search/api/), [Brave 약관](https://api-dashboard.search.brave.com/documentation/resources/terms-of-service). 제공자 약관·가격은 변경될 수 있으므로 실제 계정 연결 전에 다시 확인한다.

RoadLog 자체 설정은 캠페인당 질문/유사 서비스 최대 2검색·query당 결과 최대 5건·일일 기본 10검색(설정 상한 30)·동일 query 6시간 캐시다. API 키는 서버 환경변수에서만 읽고 DB·로그·화면에 쓰지 않는다. 429/네트워크 오류는 검색 실패로 기록하고 내부 데이터 기반 루프를 계속한다. 계정이 PAYGO면 월 1,000크레딧 초과분이 과금될 수 있으므로 무료 플랜으로 유지해야 한다.

## 검증 및 미완

- `scripts/_marketing_strategy_test.py`: 모의 HTTP 응답, 위험 URL 폐기, 캐시·일일 한도, 4종 근거, 도구 미연결 전략 차단, 중복 주제, 오프라인 fallback 통과.
- `scripts/_marketing_os_test.py`: 모의 AI 8명 팀과 블로그 승인 대기 폐쇄 루프 통과. 실제 Gemini·Tavily 호출은 0건.
- 관리자 `왜 이 전략인가`는 저장된 캠페인 전략에서 보인다. 기존 캠페인에는 소급 데이터가 없어 빈 상태다.
- `scripts/marketing_learning_probe.py --campaign-id ID`는 게시·점수표·Learning 존재를 읽기만 하고 기본 Gemini 호출 0건이다. `--live-ai`를 명시하면 실제 Gemini 디렉터 1회 요청 가능하므로 이번 작업에서는 실행하지 않았다.
- 아직 없는 것: 실제 Tavily 키로 한국어 검색 품질 확인, 원문 독립 검증, 상품별 유입·구매 전환, 관리자 전용 테스트 캠페인 버튼, 실제 운영 블로그 1건 미리보기 클릭. 별도 승인 없는 유료 Gemini 시험·공개 게시를 하지 않았다.

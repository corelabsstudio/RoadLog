# AI 마케팅 자동화 능력의 실제 경계

2026-09-24. `AUTO`는 코드가 자동으로 실행될 수 있다는 뜻이며, 공급자 키가 설정됐다는 것만으로 운영 성공을 뜻하지 않는다. 이미지/영상 프롬프트, FFmpeg 정지 화면 변환, 수동 업로드는 생성 완료가 아니다.

| 능력 | 실제 상태 | 근거 및 한계 |
|---|---|---|
| 사이트 자동 분석 | PARTIAL | 내부 집계와 상품 정본으로 전체 사이트 진단. 상품별 방문·구매 귀속 없음 |
| 상품별 마케팅 진단 | PARTIAL | 상품별 누적 열람과 정본 기반, 전환율 미측정 |
| 외부 시장 실제 조사 | CONFIG_REQUIRED | Brave 공식 API 어댑터 있음, 키·활성화 필요 |
| 경쟁 콘텐츠 조사 | CONFIG_REQUIRED | Brave 검색 결과 출처 저장 가능, 운영 키 필요 |
| SEO/검색 기회 조사 | PARTIAL | 검색 가설만 가능, Search Console·검색량 미연결 |
| 전략 후보 생성 | WORKING | 블로그·상세페이지·Instagram 후보와 근거/위험 생성 |
| 전략 자동 선택 | PARTIAL | 진단 기반 선택, 게시/성과 근거의 검증 부족 |
| 블로그 실제 제작 | PARTIAL | Gemini 본문 초안과 정본 검수, 사이트 블로그 게시 경로 없음 |
| SNS 실제 제작 | PARTIAL | 캡션·대본 가능, 게시용 asset package 미완 |
| 이미지 실제 생성 | CONFIG_REQUIRED | Gemini 3.1 Flash Image API 코드와 자동 팀 호출 경로. 기본 OFF, 과금 가능, 실호출 미검증 |
| 영상 실제 생성 | NOT_IMPLEMENTED | AI 영상 공급자 없음. FFmpeg 정지 이미지 변환은 fallback |
| 자동 품질 검수 | PARTIAL | 본문 사실 검수. 이미지 시각 검수 미구현 |
| 자동 수정 | PARTIAL | 본문 최대 2회 수정·재검수, 이미지 수정 없음 |
| READY_TO_PUBLISH | NOT_IMPLEMENTED | asset 검수·채널 payload 결합 전에는 표시하지 않음 |
| 관리자 승인 | WORKING | 기존 초안 승인 기록. 게시용 최종 승인과 구분 필요 |
| 실제 게시 | CONFIG_REQUIRED | Instagram 공식 API 코드 있음, Meta 연결·공개 JPEG·건별 승인 필요. 블로그 게시 없음 |
| 캠페인 추적 | NOT_IMPLEMENTED | 캠페인 실행 기록은 있지만 UTM 귀속 없음 |
| 성과 측정 | PARTIAL | 사이트 전체 내부 집계만 사용. 캠페인 귀속 아님 |
| 결과 학습 | PARTIAL | 실행 전 측정값·기록은 있으나 실제 게시 성과 학습 아님 |
| 다음 전략 반영 | PARTIAL | 이전 기록을 디렉터 입력에 주지만 캠페인 성과 데이터 없음 |
| 반복 자동 운영 | PARTIAL | 일일 캠페인 스케줄은 조건부 실행, 외부 게시·크리에이티브 완성은 미연결 |

## 연결 전 필수 조건

- `GEMINI_API_KEY`가 텍스트 생성용으로 있어도 **이미지 API 과금 동의**가 별도로 필요하다. `MARKETING_IMAGE_GENERATION_ENABLED`를 명시적으로 `true`로 설정하기 전까지 이미지 API 호출은 0회다. 내부 1,000원 예약은 실제 청구액의 상한이 아니다.
- Brave 시장 검색에는 `BRAVE_SEARCH_API_KEY`와 `MARKETING_EXTERNAL_RESEARCH_ENABLED=true`가 필요하다. 검색량·순위는 별도 공급자가 필요하다.
- 실제 AI 영상 생성 공급자와 과금 방식은 아직 선택되지 않았다.
- Meta 계정과 토큰·권한·공개 JPEG 제공이 검증돼야 Instagram 게시가 가능하다. 계정·비밀번호·토큰을 이 저장소/문서에 넣지 않는다.
- 기존 승인 대기는 **초안 승인**이다. 이미지가 생성되더라도 현재 `GENERATED_UNVERIFIED`이고, 게시 payload와 시각 검수가 없으므로 `READY_TO_PUBLISH`로 승격하지 않는다.

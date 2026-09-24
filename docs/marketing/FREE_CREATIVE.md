# AI 마케팅 팀 수동 제작물 가져오기 (fallback)

2026-09-24. 이 경로는 **로컬·사용자 보조 제작**이며 Railway 서버의 무인 이미지·영상 생성 API가 아니다. 정상 자동 제작 경로로 간주하지 않는다. 별도 Gemini 이미지 API 공급자 코드는 `marketing_creative.py`에 있으며 `MARKETING_IMAGE_GENERATION_ENABLED=false`가 기본값이다. 이미지 API는 무료 웹앱과 다르게 과금될 수 있어 계정 소유자의 명시적 허가 전에는 켜지 않는다.

1. 관리자 `승인 대기`의 검수 통과 항목에서 `이미지 지시안·영상 제작안 보기`를 연다. 지시안 자체는 파일이 아니다.
2. Gemini 웹앱의 사용 가능한 무료 범위에서 이미지를 만든다. 로그인·무료 한도·이용 조건은 해당 계정에서 확인한다. 이미지 결과를 JPEG/PNG로 내려받는다. 화면·상품 사실에 맞는지 사람 눈으로 확인한다.
3. 영상이 필요하면 Clipchamp 무료 음성·편집으로 MP4를 만들거나, 기존 이미지와 선택한 음성 파일을 아래 로컬 명령에 넣는다. 이 명령은 `ai-influencer-7day/runtime/bin/ffmpeg.exe`를 **읽기만** 해서 720×1280 H.264 MP4를 만든다. 상품·가격·CTA·자막을 자동으로 합성하지 않으므로 Clipchamp 등에서 편집·검수해야 한다. 말하는 얼굴 영상만 필요한 경우 `ai-influencer-7day/tools/run_avatar.py`의 SadTalker 경로를 별도로 사용할 수 있다. 그 도구는 다른 프로젝트의 출력 경로 제한을 지켜야 한다.

```powershell
cd C:\Users\hysoo\projects\RoadLog
.\.venv\Scripts\python.exe tools\build_marketing_video.py --image "C:\path\to\AI-image.png" --output "C:\path\to\new-promo.mp4" --seconds 8
```

음성이 준비됐으면 `--audio "C:\path\to\voice.wav"`를 추가한다. 기존 출력 파일은 덮어쓰지 않는다.

4. 관리자 화면에 실제 JPEG/PNG(최대 8 MiB) 또는 MP4(최대 16 MiB)를 가져온다. 서버는 파일 형식을 검사하고 비공개 데이터 저장소에 보관한다. 관리자 인증이 있어야 미리보기 할 수 있다. 원산지는 `USER_SUPPLIED_FREE_TOOL`, 상태는 `IMPORTED_UNVERIFIED`로 기록한다. 이미지 지시안을 `GENERATED`로 표시하지 않는다.
5. 이 단계는 **게시 준비 완료가 아니다.** 브랜드·상품·가격·자막·권리·채널 규격은 별도 사람이 검수해야 한다. 현재 Instagram 게시 API는 공개 ROADLOG JPEG URL을 요구하므로, 비공개 가져오기 파일을 그대로 넘길 수 없다. 공개 자산 제공·연결은 후속 작업이다. 외부 게시 자동 실행 없음.

첫 연결 검증: AI 인플루언서 프로젝트에서 실제 AI 생성한 얼굴 이미지 한 장으로 로컬 FFmpeg의 2초 H.264, 720×1280, 25fps MP4를 만들고 첫 프레임·디코딩을 확인했다. 이는 제작 경로의 연기 시험이지 ROADLOG 최종 홍보물 검수가 아니다. 테스트 파일은 확인 후 제거했다.

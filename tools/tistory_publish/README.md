# 티스토리 자동 발행 — onhae126.tistory.com

블로그: https://onhae126.tistory.com/  
블로그 이름(blogName): `onhae126`

## 1) 토큰 발급 (1회)

1. [카카오 개발자](https://developers.kakao.com/) → 내 애플리케이션 → 앱 추가  
2. 플랫폼 / Redirect URI 등록 (티스토리 OAuth 가이드 참고)  
3. [티스토리 오픈 API](https://www.tistory.com/guide/api/manage/register) 에서 앱 연결  
4. OAuth로 **Access Token** 발급  
5. 아래 파일에 **한 줄로만** 저장 (채팅에 붙이지 말 것)

파일: `C:\Users\hysoo\Projects\RoadLog\.launch\tistory.env`

```env
TISTORY_ACCESS_TOKEN=여기에_토큰
TISTORY_BLOG_NAME=onhae126
TISTORY_DEFAULT_VISIBILITY=3
```

- `visibility`: `0` 비공개(임시) · `1` 보호 · `3` 발행(공개)

## 2) 연결 테스트

```bash
cd C:\Users\hysoo\Projects\RoadLog
python tools/tistory_publish/publish.py --ping
```

성공 시 블로그 정보 JSON이 출력됩니다.

## 3) 글 발행

```bash
# HTML 파일 발행
python tools/tistory_publish/publish.py --file path\to\post.html --title "글 제목" --tags "사이드프로젝트,WakeAgain"

# 마크다운/텍스트 stdin
python tools/tistory_publish/publish.py --title "제목" --tags "로드로그,운행일지" < body.html
```

성공 시 `postId` · URL 이 로그에 남고,  
`tools/tistory_publish/publish_log.jsonl` 에 기록됩니다 (중복 방지용).

## 4) 일일 자동화와 연결

Grok 일일 SEO 프롬프트 마지막 단계:

1. 자체 사이트 `/blog` 배포  
2. 같은 본문으로:

```bash
python tools/tistory_publish/publish.py --file <생성한.html> --title "..." --tags "..."
```

토큰 파일이 없으면 스크립트는 **스킵(exit 0 + SKIP_NO_TOKEN)** 하므로  
토큰 준비 전에도 사이트 배포 파이프라인은 깨지지 않습니다.

## 보안

- `.launch/tistory.env` 는 gitignore 대상인지 확인  
- 토큰 유출 시 카카오/티스토리에서 즉시 폐기·재발급  

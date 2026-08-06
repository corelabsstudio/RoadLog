# 일일 X 노출 팩 생성 프롬프트 (Trigger)

**매일 1회** (목표: 한국시간 09:30) 또는  
**「X 마케팅」** / **「로드로그 X」** / **「일일 X 팩」** 발화 시 실행.

선행 읽기:
1. `docs/marketing/x/STRATEGY.md`
2. `docs/marketing/x/AUDIENCE.md`
3. `docs/marketing/x/HUMAN_VOICE.md`
4. RoadLog: `docs/marketing/Context/ONE_PAGER.md`
5. WA 소프트 시: `WakeAgain/docs/marketing/Context/ONE_PAGER.md` + **결제 CTA 금지**

---

## 파이프 (생성만 · 게시 금지)

```text
1 Audience  — 오늘 페르소나 1 (RL) + 1 (WA soft)
2 Research  — X/웹 시의성 키워드 0~3 (없으면 페르소나 기본 고통)
3 Writer    — 사람 말투 카피 (HUMAN_VOICE)
4 Image     — 이미지 생성 1장씩 (RL, WA) → packs/.../images/
5 Review    — 가드레일 PASS 전 완료 표시 안 함
6 Notify    — ready_for_human 보고 (git push·X 게시 하지 않음)
```

---

## 출력 경로

`C:\Users\hysoo\projects\RoadLog\docs\marketing\x\packs\YYYY-MM-DD\`

### ROADLOG.md 템플릿

```markdown
# RoadLog X pack — YYYY-MM-DD
PERSONA: P1|P2|P3|P4 + 한 줄
TREND_HOOK: (있으면) / none
## Hooks (3)
1. ...
2. ...
3. ...
## Caption (게시용 1 · 고른 훅 기반)
...
## Link
https://roadlog.co.kr  or /resources/
## Image
- file: images/roadlog.png
- alt: ...
## Human note
- 추천 게시 시각(KST): ...
- 피하기: ...
REVIEW: PASS|FAIL
```

### WA_SOFT.md 템플릿

```markdown
# WakeAgain SOFT X pack — YYYY-MM-DD
MODE: soft (no payment CTA)
PERSONA: W1|W2|W3
## Hooks (2)
...
## Caption
...
## Link
https://wakeagain.com  or /sell.html or /app/
## Disclaimer line (캡션 말미 선택)
오픈 초기 · 피드백 환영 (결제/사업자 준비 구간이면 과대 약속 금지)
## Image
- file: images/wakeagain_soft.png
REVIEW: PASS|FAIL
```

### META.json

```json
{
  "date": "YYYY-MM-DD",
  "status": "ready_for_human",
  "roadlog": true,
  "wakeagain_soft": true,
  "posted": { "roadlog": false, "wakeagain": false }
}
```

---

## 이미지 스펙

| 제품 | 파일 | 비율 | 톤 |
|------|------|------|-----|
| RoadLog | `images/roadlog.png` | 1:1 (1080) 또는 16:9 | 다크·실무·신뢰. CoreLabs/WA 로고 혼용 금지 |
| WA soft | `images/wakeagain_soft.png` | 1:1 | 다크·퍼플 힌트. 수익 배지·“보장” 문구 금지 |

이미지 안 텍스트: **짧은 한글 헤드라인 1줄** (+ 선택 서브 1줄). 본문 장문 금지.  
브랜드 워드마크는 작게 또는 생략 가능 (텍스트로 RoadLog / WakeAgain).

---

## Review 필수

**RoadLog:** 절세 보장·세금 확정 단정 없음 · AI 티 없음 · CTA 1  
**WA:** 수익/성사/결제 완료 보장 없음 · 소프트 톤 · AI 티 없음  

FAIL 시 Writer 1회 수정.

---

## 완료 보고

```
PIPE: daily-x
DATE: ...
RL_PERSONA: ...
WA_PERSONA: ...
PACK: docs/marketing/x/packs/YYYY-MM-DD/
IMAGES: n
REVIEW: PASS|FAIL
STATUS: ready_for_human
POST: do_not_auto_post
```

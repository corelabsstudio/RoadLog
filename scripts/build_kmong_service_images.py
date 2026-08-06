# -*- coding: utf-8 -*-
"""Kmong service images: main 1 (4:3) + detail 4 (W>=600, H<=3000)."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path.home() / "Desktop" / "kmong" / "service"
OUT.mkdir(parents=True, exist_ok=True)
for p in OUT.glob("*.jpg"):
    p.unlink()

FONT = next(
    p
    for p in [
        Path(r"C:\Users\hysoo\Projects\RoadLog\tools\community_poster\assets\fonts\SCDream6.otf"),
        Path(r"C:\Windows\Fonts\malgunbd.ttf"),
        Path(r"C:\Windows\Fonts\malgun.ttf"),
    ]
    if p.exists()
)

NAVY = (15, 23, 42)
BLUE = (37, 99, 235)
TEAL = (13, 148, 136)
GREEN = (22, 163, 74)
ORANGE = (217, 119, 6)
LIGHT = (248, 250, 252)
MUTED = (100, 116, 139)
DARK = (30, 41, 59)
WHITE = (255, 255, 255)
SOFT = (51, 65, 85)


def fnt(sz: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT), sz)


def th(d: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    b = d.textbbox((0, 0), text, font=font)
    return b[3] - b[1]


def wrap(d: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    lines: list[str] = []
    cur = ""
    for ch in text:
        t = cur + ch
        if d.textbbox((0, 0), t, font=font)[2] <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return lines or [""]


def draw_wrap(
    d: ImageDraw.ImageDraw,
    x: int,
    y: int,
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple,
    max_w: int,
    gap: int = 6,
) -> int:
    for line in wrap(d, text, font, max_w):
        d.text((x, y), line, font=font, fill=fill)
        y += th(d, line, font) + gap
    return y


def save(img: Image.Image, path: Path) -> None:
    img.convert("RGB").save(path, "JPEG", quality=95)
    print(path.name, img.size)


def header(d: ImageDraw.ImageDraw, w: int, title: str, subtitle: str, accent: tuple, page: str) -> int:
    d.rectangle([0, 0, w, 130], fill=NAVY)
    d.rectangle([0, 0, 10, 130], fill=accent)
    d.text((40, 28), "ONHAE  ·  SERVICE", font=fnt(16), fill=(96, 165, 250))
    d.text((40, 58), title, font=fnt(28), fill=WHITE)
    d.text((40, 96), subtitle, font=fnt(16), fill=MUTED)
    d.text((w - 80, 36), page, font=fnt(16), fill=MUTED)
    return 160


def footer(d: ImageDraw.ImageDraw, w: int, y: int, page: str) -> int:
    d.rectangle([0, y, w, y + 56], fill=NAVY)
    d.text((40, y + 16), f"온해  ·  엑셀 업무 자동화  ·  {page}", font=fnt(16), fill=MUTED)
    return y + 56


def crop_save(img: Image.Image, y: int, path: Path, w: int = 800) -> None:
    h = min(max(int(y), 900), 3000)
    out = img.crop((0, 0, w, h))
    assert out.size[0] >= 600 and out.size[1] <= 3000
    save(out, path)


def make_main() -> None:
    w, h = 1200, 900  # 4:3 service main
    img = Image.new("RGB", (w, h), NAVY)
    d = ImageDraw.Draw(img)
    d.ellipse([w - 420, -120, w + 80, 380], fill=(30, 58, 138))
    d.ellipse([-100, h - 280, 320, h + 120], fill=(30, 41, 59))
    d.rectangle([0, 0, 14, h], fill=BLUE)
    d.text((56, 80), "ONHAE", font=fnt(28), fill=(96, 165, 250))
    d.text((56, 140), "엑셀 업무 자동화", font=fnt(64), fill=WHITE)
    d.text((56, 230), "맞춤 제작해 드립니다", font=fnt(42), fill=(226, 232, 240))
    feats = ["시트 병합", "KPI 집계", "데이터 정제", "Python"]
    x = 56
    for t in feats:
        bb = d.textbbox((0, 0), t, font=fnt(22))
        tw = bb[2] - bb[0] + 36
        d.rounded_rectangle([x, 340, x + tw, 390], radius=22, fill=(30, 41, 59))
        d.text((x + 18, 352), t, font=fnt(22), fill=(226, 232, 240))
        x += tw + 14
    cx, cy = 780, 420
    d.rounded_rectangle([cx, cy, cx + 340, cy + 280], radius=18, fill=WHITE)
    d.rectangle([cx, cy, cx + 340, cy + 48], fill=GREEN)
    d.text((cx + 20, cy + 12), "Excel Automation", font=fnt(20), fill=WHITE)
    for i in range(5):
        yy = cy + 70 + i * 38
        d.line([cx + 20, yy, cx + 320, yy], fill=(226, 232, 240), width=2)
        d.rounded_rectangle(
            [cx + 20, yy - 22, cx + 20 + int(80 + i * 30), yy - 6],
            radius=4,
            fill=(219, 234, 254) if i % 2 == 0 else (187, 247, 208),
        )
    d.ellipse([cx + 250, cy + 200, cx + 320, cy + 270], fill=BLUE)
    d.text((cx + 268, cy + 218), ">", font=fnt(28), fill=WHITE)
    d.text((56, 780), "반복 업무를 규칙 기반 스크립트로 줄입니다", font=fnt(24), fill=MUTED)
    save(img, OUT / "서비스_메인.jpg")


def make_detail1() -> None:
    w, hmax = 800, 3000
    img = Image.new("RGB", (w, hmax), LIGHT)
    d = ImageDraw.Draw(img)
    y = header(d, w, "이런 일을 자동화합니다", "시트 병합 · 집계 · 데이터 정제", BLUE, "1/4")
    pad, cw = 40, w - 80
    cards = [
        (BLUE, "01", "시트 병합", "지점·월별 시트를 하나로, 헤더·날짜 형식이 달라도 정규화"),
        (TEAL, "02", "KPI · 집계", "일별/채널/상품 지표, 취소 제외 등 규칙 반영"),
        (ORANGE, "03", "데이터 정제", "금액·상태·날짜 클리닝, 중복 탐지 후 보고용 합계"),
    ]
    for accent, no, title, body in cards:
        d.rounded_rectangle([pad, y, pad + cw, y + 140], radius=14, fill=WHITE)
        d.rounded_rectangle([pad, y, pad + 56, y + 140], radius=14, fill=accent)
        d.rectangle([pad + 28, y, pad + 56, y + 140], fill=accent)
        d.text((pad + 12, y + 55), no, font=fnt(18), fill=WHITE)
        d.text((pad + 76, y + 22), title, font=fnt(24), fill=DARK)
        draw_wrap(d, pad + 76, y + 62, body, fnt(17), MUTED, cw - 100, 5)
        y += 156
    y += 8
    d.text((pad, y), "작업 방식", font=fnt(22), fill=DARK)
    y += 40
    for t in [
        "Python(openpyxl) 기반 맞춤 스크립트 제작",
        "BEFORE/AFTER 엑셀로 결과 검증 후 납품",
        "재실행 가능한 파일 + 사용 방법 안내",
    ]:
        d.ellipse([pad + 4, y + 8, pad + 16, y + 20], fill=BLUE)
        y = draw_wrap(d, pad + 28, y, t, fnt(18), SOFT, cw - 28, 5)
        y += 12
    y += 24
    y = footer(d, w, y, "1/4")
    crop_save(img, y, OUT / "서비스_상세1_소개.jpg", w)


def make_detail2() -> None:
    w, hmax = 800, 3000
    img = Image.new("RGB", (w, hmax), LIGHT)
    d = ImageDraw.Draw(img)
    y = header(d, w, "BEFORE → AFTER", "수작업을 규칙 기반 결과물로", TEAL, "2/4")
    pad, cw = 40, w - 80
    d.rounded_rectangle([pad, y, pad + cw, y + 200], radius=14, fill=(254, 242, 242))
    d.text((pad + 20, y + 16), "BEFORE", font=fnt(18), fill=(185, 28, 28))
    for i, t in enumerate(
        ["시트마다 헤더·날짜 형식이 다름", "매주 복붙·피벗 반복", "취소/중복이 합계에 섞임", "담당자마다 기준이 다름"]
    ):
        d.text((pad + 24, y + 56 + i * 32), f"·  {t}", font=fnt(18), fill=(127, 29, 29))
    y += 220
    d.rounded_rectangle([pad + cw // 2 - 60, y, pad + cw // 2 + 60, y + 36], radius=18, fill=TEAL)
    d.text((pad + cw // 2 - 36, y + 6), "자동화", font=fnt(18), fill=WHITE)
    y += 56
    d.rounded_rectangle([pad, y, pad + cw, y + 200], radius=14, fill=(236, 253, 245))
    d.text((pad + 20, y + 16), "AFTER", font=fnt(18), fill=(21, 128, 61))
    for i, t in enumerate(
        [
            "통합원장·KPI·정제 시트 자동 생성",
            "실행 한 번으로 반복 마감",
            "규칙이 코드로 고정되어 기준 통일",
            "재실행 스크립트로 동일 결과 재현",
        ]
    ):
        d.text((pad + 24, y + 56 + i * 32), f"·  {t}", font=fnt(18), fill=(20, 83, 45))
    y += 230
    d.text((pad, y), "포트폴리오에서 확인 가능한 예시", font=fnt(20), fill=DARK)
    y += 36
    for t in [
        "CASE 01  지점 매출 시트 병합·요약",
        "CASE 02  주문 RAW → 일별 KPI",
        "CASE 03  경비 원장 정제·보고",
    ]:
        d.rounded_rectangle([pad, y, pad + cw, y + 44], radius=10, fill=WHITE)
        d.text((pad + 16, y + 10), t, font=fnt(17), fill=DARK)
        y += 54
    y += 20
    y = footer(d, w, y, "2/4")
    crop_save(img, y, OUT / "서비스_상세2_전후.jpg", w)


def make_detail3() -> None:
    w, hmax = 800, 3000
    img = Image.new("RGB", (w, hmax), LIGHT)
    d = ImageDraw.Draw(img)
    y = header(d, w, "진행 순서", "문의부터 납품까지", BLUE, "3/4")
    pad, cw = 40, w - 80
    steps = [
        ("01", "문의·파일 확인", "현재 엑셀(또는 샘플)과 원하는 결과 형태를 알려주세요."),
        ("02", "규칙 정리", "포함/제외 기준(예: 취소 제외, 승인만 합계)을 맞춥니다."),
        ("03", "제작·검증", "스크립트 제작 후 샘플 데이터로 BEFORE/AFTER를 확인합니다."),
        ("04", "납품", "결과 xlsx + 실행 방법 + 기본 범위 안 수정을 드립니다."),
    ]
    for no, title, body in steps:
        d.rounded_rectangle([pad, y, pad + cw, y + 120], radius=14, fill=WHITE)
        d.ellipse([pad + 18, y + 34, pad + 70, y + 86], fill=BLUE)
        d.text((pad + 30, y + 48), no, font=fnt(18), fill=WHITE)
        d.text((pad + 90, y + 22), title, font=fnt(22), fill=DARK)
        draw_wrap(d, pad + 90, y + 58, body, fnt(16), MUTED, cw - 110, 4)
        y += 136
    y += 8
    d.rounded_rectangle([pad, y, pad + cw, y + 100], radius=12, fill=(239, 246, 255))
    d.text((pad + 18, y + 16), "준비해 주시면 빠른 견적", font=fnt(18), fill=BLUE)
    for i, t in enumerate(["1) 시트 수·대략 행 수", "2) 원하는 결과 형태", "3) 희망 기한"]):
        d.text((pad + 18, y + 48 + i * 16), t, font=fnt(15), fill=DARK)
    y += 120
    y = footer(d, w, y, "3/4")
    crop_save(img, y, OUT / "서비스_상세3_진행순서.jpg", w)


def make_detail4() -> None:
    w, hmax = 800, 3000
    img = Image.new("RGB", (w, hmax), LIGHT)
    d = ImageDraw.Draw(img)
    y = header(d, w, "패키지 · 작업 범위", "스탠다드 / 딜럭스 / 프리미엄", ORANGE, "4/4")
    pad, cw = 40, w - 80
    packages = [
        (
            BLUE,
            "스탠다드",
            "자동화 1종",
            [
                "병합 또는 집계 또는 정제 중 1종",
                "샘플 검증 + 결과 파일",
                "사용 방법 안내",
                "기본 수정 1회",
            ],
        ),
        (
            TEAL,
            "딜럭스",
            "연계 자동화 2종",
            [
                "예: 병합+요약 / RAW+KPI",
                "규칙 문서화",
                "재실행 스크립트",
                "기본 수정 2회",
            ],
        ),
        (
            ORANGE,
            "프리미엄",
            "맞춤 패키지",
            [
                "3종 이상 또는 복잡한 규칙",
                "추가 리포트·차트",
                "우선 응대·상세 가이드",
                "기본 수정 3회",
            ],
        ),
    ]
    for accent, name, sub, items in packages:
        box_h = 56 + len(items) * 28 + 12
        d.rounded_rectangle([pad, y, pad + cw, y + box_h], radius=14, fill=WHITE)
        d.rectangle([pad, y, pad + 8, y + box_h], fill=accent)
        d.text((pad + 24, y + 14), name, font=fnt(22), fill=DARK)
        d.text((pad + 140, y + 18), sub, font=fnt(15), fill=MUTED)
        yy = y + 52
        for it in items:
            d.text((pad + 28, yy), f"·  {it}", font=fnt(16), fill=SOFT)
            yy += 28
        y += box_h + 14

    y += 8
    d.text((pad, y), "이런 분께 맞습니다", font=fnt(20), fill=DARK)
    y += 36
    targets = [
        "매주·매월 같은 엑셀 마감을 반복하는 분",
        "지점/팀 시트를 합치느라 시간이 많이 드는 분",
        "피벗은 가능하지만 반복 실행 프로세스가 필요한 분",
    ]
    for t in targets:
        d.ellipse([pad + 4, y + 8, pad + 16, y + 20], fill=GREEN)
        y = draw_wrap(d, pad + 28, y, t, fnt(17), SOFT, cw - 28, 4)
        y += 10

    y += 16
    d.text((pad, y), "이런 건 어렵습니다", font=fnt(20), fill=DARK)
    y += 36
    for t in [
        "회사 보안 시스템 우회·무단 계정 접속",
        "요구사항 없는 무한 수정형 대형 프로젝트",
        "엑셀이 아닌 대규모 웹·앱 전체 개발 (별도 상담)",
    ]:
        d.ellipse([pad + 4, y + 8, pad + 16, y + 20], fill=(220, 38, 38))
        y = draw_wrap(d, pad + 28, y, t, fnt(17), SOFT, cw - 28, 4)
        y += 10

    y += 24
    y = footer(d, w, y, "4/4")
    crop_save(img, y, OUT / "서비스_상세4_패키지.jpg", w)


def main() -> None:
    make_main()
    make_detail1()
    make_detail2()
    make_detail3()
    make_detail4()
    print("--- done ---")
    for p in sorted(OUT.glob("*.jpg")):
        im = Image.open(p)
        print(p.name, im.size)


if __name__ == "__main__":
    main()

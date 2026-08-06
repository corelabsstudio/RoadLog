"""Knowledge iN short promo — 업무차량 운행일지 context (shorter than long_story)."""
from __future__ import annotations

import math
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "marketing" / "promo"
SHOTS = OUT / "shots"
DESKTOP = Path(r"C:\Users\hysoo\Desktop\로드로그_홍보이미지")
FONT = r"C:\Windows\Fonts\malgun.ttf"
FONT_B = r"C:\Windows\Fonts\malgunbd.ttf"

W = 1080
MARGIN = 56
CONTENT_W = W - MARGIN * 2


def fnt(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(FONT_B if bold else FONT, size)
    except Exception:
        return ImageFont.truetype(FONT, size)


def text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    b = draw.textbbox((0, 0), text, font=font)
    return b[2] - b[0], b[3] - b[1]


def wrap_lines(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_w: int) -> list[str]:
    lines: list[str] = []
    for para in text.split("\n"):
        if not para.strip():
            lines.append("")
            continue
        cur = ""
        for ch in para:
            trial = cur + ch
            tw, _ = text_size(draw, trial, font)
            if tw <= max_w:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                cur = ch
        if cur:
            lines.append(cur)
    return lines


def draw_bg(h: int) -> Image.Image:
    img = Image.new("RGB", (W, h), "#030712")
    px = img.load()
    for y in range(h):
        for x in range(0, W, 3):
            t = y / max(h - 1, 1)
            wave = 0.5 + 0.5 * math.sin((x / W) * 3.1 + t * 4)
            r = int(3 + 10 * (1 - t) * wave)
            g = int(7 + 28 * (1 - t * 0.7) * wave)
            b = int(18 + 40 * (1 - t * 0.5))
            c = (r, g, b)
            px[x, y] = c
            if x + 1 < W:
                px[x + 1, y] = c
            if x + 2 < W:
                px[x + 2, y] = c
    overlay = Image.new("RGBA", (W, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.ellipse([int(W * 0.4), -120, int(W * 1.2), 420], fill=(34, 211, 238, 22))
    od.ellipse([-200, int(h * 0.3), 360, int(h * 0.5)], fill=(8, 145, 178, 16))
    od.ellipse([int(W * 0.5), int(h * 0.7), int(W * 1.15), int(h * 0.95)], fill=(34, 211, 238, 14))
    return Image.alpha_composite(img.convert("RGBA"), overlay)


def rounded_shot(path: Path, max_w: int) -> Image.Image:
    im = Image.open(path).convert("RGBA")
    ratio = max_w / im.width
    nh = int(im.height * ratio)
    im = im.resize((max_w, nh), Image.Resampling.LANCZOS)
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, im.width - 1, im.height - 1], radius=36, fill=255)
    out = Image.new("RGBA", im.size, (0, 0, 0, 0))
    out.paste(im, (0, 0), mask)
    border = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(border).rounded_rectangle(
        [1, 1, im.width - 2, im.height - 2],
        radius=36,
        outline=(34, 211, 238, 110),
        width=3,
    )
    return Image.alpha_composite(out, border)


def draw_logo_mark(base: Image.Image, x: int, y: int, size: int = 72) -> None:
    tile = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    td = ImageDraw.Draw(tile)
    for i in range(size):
        t = i / max(size - 1, 1)
        r = int(103 + (8 - 103) * t)
        g = int(232 + (145 - 232) * t)
        b = int(249 + (178 - 249) * t)
        td.line([(0, i), (size, i)], fill=(r, g, b, 255))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=int(size * 0.22), fill=255)
    tile.putalpha(mask)
    s = size / 64
    td = ImageDraw.Draw(tile)
    td.arc([int(10 * s), int(18 * s), int(52 * s), int(52 * s)], 200, 340, fill=(4, 16, 22, 255), width=max(2, int(4 * s)))
    td.ellipse([int(43 * s), int(18 * s), int(54 * s), int(29 * s)], fill=(4, 16, 22, 255))
    td.ellipse([int(46 * s), int(21 * s), int(51 * s), int(26 * s)], fill=(103, 232, 249, 255))
    td.line([(int(13 * s), int(46 * s)), (int(40 * s), int(46 * s))], fill=(4, 16, 22, 180), width=max(2, int(3 * s)))
    td.ellipse([int(15 * s), int(43 * s), int(22 * s), int(50 * s)], fill=(4, 16, 22, 255))
    td.ellipse([int(34 * s), int(43 * s), int(41 * s), int(50 * s)], fill=(4, 16, 22, 255))
    base.paste(tile, (x, y), tile)


class Builder:
    def __init__(self) -> None:
        self.parts: list[Image.Image] = []

    def canvas(self, height: int) -> tuple[Image.Image, ImageDraw.ImageDraw]:
        img = Image.new("RGBA", (W, height), (0, 0, 0, 0))
        return img, ImageDraw.Draw(img)

    def push(self, img: Image.Image) -> None:
        self.parts.append(img)

    def spacer(self, h: int = 24) -> None:
        self.push(Image.new("RGBA", (W, h), (0, 0, 0, 0)))

    def add_heading(self, eyebrow: str, title: str) -> None:
        h = 130
        img, d = self.canvas(h)
        if eyebrow:
            d.text((MARGIN, 16), eyebrow, font=fnt(22, True), fill=(103, 232, 249, 255))
        d.text((MARGIN, 50), title, font=fnt(36, True), fill=(248, 250, 252, 255))
        self.push(img)

    def add_paragraphs(self, text: str, size: int = 27, color=(203, 213, 225, 255), gap: int = 12) -> None:
        probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
        font = fnt(size)
        lines = wrap_lines(probe, text, font, CONTENT_W)
        line_h = text_size(probe, "가", font)[1] + gap
        height = max(36, len(lines) * line_h + 12)
        img, d = self.canvas(height)
        y = 0
        for line in lines:
            if line == "":
                y += line_h // 2
                continue
            d.text((MARGIN, y), line, font=font, fill=color)
            y += line_h
        self.push(img)

    def add_shot(self, path: Path, caption: str, max_w: int = 700) -> None:
        shot = rounded_shot(path, max_w)
        probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
        cf = fnt(22)
        lines = wrap_lines(probe, caption, cf, max_w)
        cap_h = len(lines) * (text_size(probe, "가", cf)[1] + 8) + 12
        total_h = shot.height + cap_h + 28
        img, d = self.canvas(total_h)
        x = (W - shot.width) // 2
        img.paste(shot, (x, 6), shot)
        y = 16 + shot.height
        for line in lines:
            tw, th = text_size(d, line, cf)
            d.text(((W - tw) // 2, y), line, font=cf, fill=(148, 163, 184, 255))
            y += th + 8
        self.push(img)

    def add_feature_list(self, items: list[tuple[str, str]]) -> None:
        probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
        title_f, body_f = fnt(26, True), fnt(23)
        rows = []
        for title, body in items:
            blines = wrap_lines(probe, body, body_f, CONTENT_W - 80)
            h = 18 + text_size(probe, title, title_f)[1] + 8
            h += len(blines) * (text_size(probe, "가", body_f)[1] + 5) + 20
            rows.append((title, blines, h))
        total = sum(r[2] for r in rows) + 12
        img, d = self.canvas(total)
        y = 0
        for i, (title, blines, h) in enumerate(rows):
            d.ellipse([MARGIN, y + 6, MARGIN + 40, y + 46], fill=(34, 211, 238, 40), outline=(34, 211, 238, 140), width=2)
            num = str(i + 1)
            nw, nh = text_size(d, num, fnt(20, True))
            d.text((MARGIN + (40 - nw) // 2, y + 6 + (40 - nh) // 2 - 2), num, font=fnt(20, True), fill=(103, 232, 249, 255))
            d.text((MARGIN + 56, y + 10), title, font=title_f, fill=(248, 250, 252, 255))
            by = y + 10 + text_size(d, title, title_f)[1] + 8
            for line in blines:
                d.text((MARGIN + 56, by), line, font=body_f, fill=(148, 163, 184, 255))
                by += text_size(d, "가", body_f)[1] + 5
            y += h
        self.push(img)

    def add_highlight_box(self, title: str, lines: list[str]) -> None:
        probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
        tf, bf = fnt(24, True), fnt(26, True)
        wrapped: list[str] = []
        for line in lines:
            wrapped.extend(wrap_lines(probe, line, bf, CONTENT_W - 64))
        h = 36 + text_size(probe, title, tf)[1] + 14
        h += len(wrapped) * (text_size(probe, "가", bf)[1] + 10) + 32
        img = Image.new("RGBA", (W, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle(
            [MARGIN - 4, 6, W - MARGIN + 4, h - 6],
            radius=24,
            fill=(34, 211, 238, 28),
            outline=(34, 211, 238, 150),
            width=2,
        )
        d.text((MARGIN + 22, 24), title, font=tf, fill=(165, 243, 252, 255))
        y = 24 + text_size(d, title, tf)[1] + 14
        for line in wrapped:
            d.text((MARGIN + 22, y), line, font=bf, fill=(248, 250, 252, 255))
            y += text_size(d, "가", bf)[1] + 10
        self.push(img)

    def add_export_samples(self) -> None:
        card_w, card_h = 300, 300
        gap = 24
        total_w = card_w * 3 + gap * 2
        start_x = (W - total_w) // 2
        strip_h = card_h + 70
        img = Image.new("RGBA", (W, strip_h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)

        samples = [
            (
                "Excel",
                "#107C41",
                [
                    ("업무차량 운행일지", True),
                    ("일자  2026-07-11", False),
                    ("차량  12가3456", False),
                    ("구간  본사→강남", False),
                    ("거리  18.4 km", False),
                    ("목적  영업 미팅", False),
                ],
            ),
            (
                "PDF",
                "#E11D48",
                [
                    ("운행 기록 요약", True),
                    ("성명  김현장", False),
                    ("일시  07/11 10:20", False),
                    ("장소  고객사 A", False),
                    ("내용  방문·견적", False),
                    ("확인  ________", False),
                ],
            ),
            (
                "DOCX",
                "#2563EB",
                [
                    ("월간 운행 요약", True),
                    ("기간  이번 달", False),
                    ("총 거리  126 km", False),
                    ("업무 운행  14건", False),
                    ("첨부  바로 제출", False),
                    ("", False),
                ],
            ),
        ]

        for i, (label, accent, rows) in enumerate(samples):
            x = start_x + i * (card_w + gap)
            y0 = 4
            d.rounded_rectangle(
                [x, y0, x + card_w, y0 + card_h],
                radius=16,
                fill=(248, 250, 252, 255),
                outline=(226, 232, 240, 255),
                width=2,
            )
            ar, ag, ab = int(accent[1:3], 16), int(accent[3:5], 16), int(accent[5:7], 16)
            d.rounded_rectangle([x, y0, x + card_w, y0 + 42], radius=16, fill=(ar, ag, ab, 255))
            d.rectangle([x, y0 + 22, x + card_w, y0 + 42], fill=(ar, ag, ab, 255))
            lf = fnt(20, True)
            lw, lh = text_size(d, label, lf)
            d.text((x + (card_w - lw) // 2, y0 + (42 - lh) // 2), label, font=lf, fill=(255, 255, 255, 255))
            yy = y0 + 56
            for text, is_title in rows:
                if not text:
                    continue
                if is_title:
                    d.text((x + 16, yy), text, font=fnt(18, True), fill=(15, 23, 42, 255))
                    yy += 30
                    d.line([(x + 16, yy - 6), (x + card_w - 16, yy - 6)], fill=(226, 232, 240, 255), width=1)
                else:
                    d.text((x + 16, yy), text, font=fnt(15), fill=(51, 65, 85, 255))
                    yy += 26

        cap = "제출·보관용 출력 예시 (Excel · PDF · DOCX)"
        cf = fnt(20)
        cw, _ = text_size(d, cap, cf)
        d.text(((W - cw) // 2, card_h + 24), cap, font=cf, fill=(148, 163, 184, 255))
        self.push(img)

    def build(self) -> Image.Image:
        self.parts.clear()

        # HERO — Kin context hook
        hero_h = 460
        hero, d = self.canvas(hero_h)
        draw_logo_mark(hero, (W - 80) // 2, 28, 80)
        d = ImageDraw.Draw(hero)
        badge = "지식인 · 업무차량 운행일지"
        bf = fnt(22, True)
        bw, bh = text_size(d, badge, bf)
        bx = (W - bw - 32) // 2
        d.rounded_rectangle(
            [bx, 128, bx + bw + 32, 128 + bh + 16],
            radius=18,
            fill=(34, 211, 238, 32),
            outline=(34, 211, 238, 120),
            width=1,
        )
        d.text((bx + 16, 134), badge, font=bf, fill=(165, 243, 252, 255))

        t1 = "개인차 업무용,"
        tw, _ = text_size(d, t1, fnt(40, True))
        d.text(((W - tw) // 2, 188), t1, font=fnt(40, True), fill=(248, 250, 252, 255))
        t2 = "운행일지 어떻게 남기시나요?"
        tw2, _ = text_size(d, t2, fnt(36, True))
        d.text(((W - tw2) // 2, 242), t2, font=fnt(36, True), fill=(248, 250, 252, 255))

        sub = "RoadLog · 스탬프 찍고 메모만 하면 제출용으로 정리"
        tw3, _ = text_size(d, sub, fnt(24))
        d.text(((W - tw3) // 2, 310), sub, font=fnt(24), fill=(148, 163, 184, 255))

        soft = "오픈 초기 · 한번 써 보시고 피드백 주시면 감사해요"
        tw4, _ = text_size(d, soft, fnt(22))
        d.text(((W - tw4) // 2, 360), soft, font=fnt(22), fill=(103, 232, 249, 255))
        self.push(hero)
        self.spacer(8)

        # CONTEXT (Kin-aligned, soft, not legal advice)
        self.add_heading("이런 고민이셨죠", "업무용 개인차 · 기록 남기기")
        self.add_paragraphs(
            "개인차량을 업무로 쓰면 운행 목적·거리·일정이 "
            "나중에 증빙·정리에 필요할 때가 많아요.\n\n"
            "엑셀을 매번 손으로 쓰다 보면 빠뜨리기 쉽고, "
            "월말에 몰아서 쓰려면 더 힘들죠.\n\n"
            "로드로그는 현장에서 위치 스탬프만 찍고 "
            "짧은 메모를 남기면, 회사·본인 보관용 일지 문장으로 "
            "정리해 드리는 AI 운행·외근 일지예요.",
            size=27,
            color=(226, 232, 240, 255),
            gap=11,
        )
        self.spacer(16)

        # HOW
        self.add_heading("어떻게 쓰나요", "3단계면 끝")
        self.add_feature_list(
            [
                (
                    "운행일지 선택",
                    "로그인 후 메인에서 「운행일지」를 고릅니다. 업무 차량 동선 기록에 맞춰 쓰면 됩니다.",
                ),
                (
                    "지금 위치 스탬프",
                    "출발·도착 때 버튼 한 번. 시각·주소가 남고 방문지 입력에 바로 반영됩니다.",
                ),
                (
                    "AI로 제출용 정리",
                    "메모만 보태도 Excel·PDF·DOCX로 받아 결재·메일·보관에 바로 쓸 수 있어요.",
                ),
            ]
        )
        self.spacer(12)

        # SHOTS (2 only — keep short)
        self.add_heading("실제 화면", "스탬프 → 일지 작성")
        self.add_shot(
            SHOTS / "create_stamp.png",
            "현장 도착 시 「지금 위치 스탬프」 → AI로 일지 작성",
            max_w=680,
        )
        self.spacer(6)
        self.add_shot(
            SHOTS / "app_home.png",
            "메인 — 운행/외근 선택 + 큰 스탬프 버튼",
            max_w=680,
        )
        self.spacer(14)

        # EXPORT
        self.add_heading("결과물", "회사·본인 보관 모양이 이렇게")
        self.add_paragraphs(
            "업무차량 운행 기록은 깔끔한 파일이 중요하죠. "
            "생성 결과를 Excel · PDF · DOCX로 받을 수 있습니다.",
            size=25,
            color=(148, 163, 184, 255),
            gap=9,
        )
        self.spacer(6)
        self.add_export_samples()
        self.spacer(16)

        # FREE
        self.add_heading("부담 없이", "카드 없이 Free 10회")
        self.add_highlight_box(
            "오픈 초기 체험",
            [
                "카드 등록 없이 가입 · Free 10회 즉시",
                "월 리셋 없음 · 결제 강요 없이 먼저 써 보세요",
                "광고 같지 않게… 한번만 써 봐 주실래요?",
            ],
        )
        self.spacer(20)

        # CTA
        cta_h = 200
        cta, d = self.canvas(cta_h)
        url = "roadlog.co.kr"
        uf = fnt(44, True)
        uw, uh = text_size(d, url, uf)
        d.rounded_rectangle(
            [(W - uw - 64) // 2, 24, (W + uw + 64) // 2, 24 + uh + 36],
            radius=28,
            fill=(34, 211, 238, 40),
            outline=(34, 211, 238, 160),
            width=2,
        )
        d.text(((W - uw) // 2, 40), url, font=uf, fill=(103, 232, 249, 255))
        foot = "CoreLabs · 오픈 초기 · 피드백 환영"
        fw, _ = text_size(d, foot, fnt(20))
        d.text(((W - fw) // 2, 130), foot, font=fnt(20), fill=(100, 116, 139, 255))
        note = "세무·세법 판단은 전문가 상담을 · 기록·정리 도구로 활용해 주세요"
        nw, _ = text_size(d, note, fnt(17))
        d.text(((W - nw) // 2, 162), note, font=fnt(17), fill=(71, 85, 105, 255))
        self.push(cta)
        self.spacer(28)

        total_h = sum(p.height for p in self.parts)
        bg = draw_bg(total_h)
        y = 0
        for p in self.parts:
            bg.paste(p, (0, y), p)
            y += p.height
        return bg.convert("RGB")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    DESKTOP.mkdir(parents=True, exist_ok=True)
    img = Builder().build()
    png = OUT / "roadlog_promo_kin_short.png"
    jpg = OUT / "roadlog_promo_kin_short.jpg"
    img.save(png, "PNG", optimize=True)
    img.save(jpg, "JPEG", quality=88, optimize=True)
    for dest in (DESKTOP / png.name, DESKTOP / jpg.name):
        shutil.copy2(png if dest.suffix == ".png" else jpg, dest)
    print(f"OK {img.size[0]}x{img.size[1]}")
    print(f"  {png}")
    print(f"  {jpg}")
    print(f"  Desktop: {DESKTOP}")


if __name__ == "__main__":
    main()

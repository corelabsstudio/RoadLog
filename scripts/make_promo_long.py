"""Long scroll promo image for RoadLog open-early story + screenshots + VIP."""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "marketing" / "promo"
SHOTS = OUT / "shots"
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
    """Word/char wrap for Korean paragraphs."""
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
            # subtle vertical gradient + cyan wash
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
    od.ellipse([-200, int(h * 0.35), 360, int(h * 0.55)], fill=(8, 145, 178, 16))
    od.ellipse([int(W * 0.5), int(h * 0.72), int(W * 1.15), int(h * 0.95)], fill=(34, 211, 238, 14))
    return Image.alpha_composite(img.convert("RGBA"), overlay)


def rounded_shot(path: Path, max_w: int, crop_top: int = 0) -> Image.Image:
    im = Image.open(path).convert("RGBA")
    if crop_top > 0 and im.height > crop_top + 100:
        im = im.crop((0, crop_top, im.width, im.height))
    # fit width
    ratio = max_w / im.width
    nh = int(im.height * ratio)
    im = im.resize((max_w, nh), Image.Resampling.LANCZOS)
    # phone-like rounded mask
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, im.width - 1, im.height - 1], radius=36, fill=255)
    out = Image.new("RGBA", im.size, (0, 0, 0, 0))
    out.paste(im, (0, 0), mask)
    # border
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
        self.y = 0

    def canvas(self, height: int) -> tuple[Image.Image, ImageDraw.ImageDraw]:
        # temporary transparent strip; final composite later
        img = Image.new("RGBA", (W, height), (0, 0, 0, 0))
        return img, ImageDraw.Draw(img)

    def push(self, img: Image.Image) -> None:
        self.parts.append(img)
        self.y += img.height

    def spacer(self, h: int = 28) -> None:
        self.push(Image.new("RGBA", (W, h), (0, 0, 0, 0)))

    def section_card(self, height: int) -> tuple[Image.Image, ImageDraw.ImageDraw, int]:
        """Card with padding; returns draw surface and inner top y=0 relative to card content start."""
        pad = 28
        img = Image.new("RGBA", (W, height + pad * 2), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle(
            [MARGIN - 8, 8, W - MARGIN + 8, height + pad * 2 - 8],
            radius=28,
            fill=(8, 14, 28, 220),
            outline=(34, 211, 238, 70),
            width=2,
        )
        return img, d, pad

    def add_heading(self, eyebrow: str, title: str) -> None:
        h = 150
        img, d = self.canvas(h)
        if eyebrow:
            d.text((MARGIN, 20), eyebrow, font=fnt(24, True), fill=(103, 232, 249, 255))
        d.text((MARGIN, 58), title, font=fnt(40, True), fill=(248, 250, 252, 255))
        self.push(img)

    def add_paragraphs(self, text: str, size: int = 28, color=(203, 213, 225, 255), gap: int = 14) -> None:
        probe = Image.new("RGB", (10, 10))
        pd = ImageDraw.Draw(probe)
        font = fnt(size)
        lines = wrap_lines(pd, text, font, CONTENT_W)
        line_h = text_size(pd, "가", font)[1] + gap
        height = max(40, len(lines) * line_h + 20)
        img, d = self.canvas(height)
        y = 0
        for line in lines:
            if line == "":
                y += line_h // 2
                continue
            d.text((MARGIN, y), line, font=font, fill=color)
            y += line_h
        self.push(img)

    def add_centered(self, text: str, size: int = 32, bold: bool = False, color=(248, 250, 252, 255), pad_y: int = 8) -> None:
        font = fnt(size, bold)
        probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
        tw, th = text_size(probe, text, font)
        img, d = self.canvas(th + pad_y * 2)
        d.text(((W - tw) // 2, pad_y), text, font=font, fill=color)
        self.push(img)

    def add_shot(self, path: Path, caption: str, crop_top: int = 0, max_w: int | None = None) -> None:
        max_w = max_w or min(CONTENT_W, 780)
        shot = rounded_shot(path, max_w, crop_top=crop_top)
        # caption height
        probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
        cf = fnt(24)
        lines = wrap_lines(probe, caption, cf, max_w)
        cap_h = len(lines) * (text_size(probe, "가", cf)[1] + 8) + 16
        total_h = shot.height + cap_h + 40
        img, d = self.canvas(total_h)
        x = (W - shot.width) // 2
        img.paste(shot, (x, 10), shot)
        y = 20 + shot.height
        for line in lines:
            tw, th = text_size(d, line, cf)
            d.text(((W - tw) // 2, y), line, font=cf, fill=(148, 163, 184, 255))
            y += th + 8
        self.push(img)

    def add_feature_list(self, items: list[tuple[str, str]]) -> None:
        probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
        title_f, body_f = fnt(28, True), fnt(24)
        rows = []
        for title, body in items:
            blines = wrap_lines(probe, body, body_f, CONTENT_W - 80)
            h = 20 + text_size(probe, title, title_f)[1] + 10
            h += len(blines) * (text_size(probe, "가", body_f)[1] + 6) + 24
            rows.append((title, blines, h))
        total = sum(r[2] for r in rows) + 20
        img, d = self.canvas(total)
        y = 0
        for i, (title, blines, h) in enumerate(rows):
            # number circle
            d.ellipse([MARGIN, y + 8, MARGIN + 44, y + 52], fill=(34, 211, 238, 40), outline=(34, 211, 238, 140), width=2)
            num = str(i + 1)
            nw, nh = text_size(d, num, fnt(22, True))
            d.text((MARGIN + (44 - nw) // 2, y + 8 + (44 - nh) // 2 - 2), num, font=fnt(22, True), fill=(103, 232, 249, 255))
            d.text((MARGIN + 60, y + 12), title, font=title_f, fill=(248, 250, 252, 255))
            by = y + 12 + text_size(d, title, title_f)[1] + 10
            for line in blines:
                d.text((MARGIN + 60, by), line, font=body_f, fill=(148, 163, 184, 255))
                by += text_size(d, "가", body_f)[1] + 6
            y += h
        self.push(img)

    def add_highlight_box(self, title: str, lines: list[str]) -> None:
        probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
        tf, bf = fnt(26, True), fnt(28, True)
        wrapped: list[str] = []
        for line in lines:
            wrapped.extend(wrap_lines(probe, line, bf, CONTENT_W - 64))
        h = 40 + text_size(probe, title, tf)[1] + 18
        h += len(wrapped) * (text_size(probe, "가", bf)[1] + 12) + 40
        img = Image.new("RGBA", (W, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle(
            [MARGIN - 4, 8, W - MARGIN + 4, h - 8],
            radius=28,
            fill=(34, 211, 238, 28),
            outline=(34, 211, 238, 150),
            width=2,
        )
        d.text((MARGIN + 24, 28), title, font=tf, fill=(165, 243, 252, 255))
        y = 28 + text_size(d, title, tf)[1] + 18
        for line in wrapped:
            d.text((MARGIN + 24, y), line, font=bf, fill=(248, 250, 252, 255))
            y += text_size(d, "가", bf)[1] + 12
        self.push(img)

    def add_export_samples(self) -> None:
        """Fake but clean Excel/PDF/DOCX preview cards for trust."""
        card_w, card_h = 300, 360
        gap = 24
        total_w = card_w * 3 + gap * 2
        start_x = (W - total_w) // 2
        strip_h = card_h + 90
        img = Image.new("RGBA", (W, strip_h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)

        samples = [
            (
                "Excel",
                "#107C41",
                [
                    ("운행일지", True),
                    ("일자  2026-07-11", False),
                    ("차량  12가3456", False),
                    ("구간  본사→강남", False),
                    ("거리  18.4 km", False),
                    ("방문  고객사 A", False),
                    ("목적  영업 미팅", False),
                    ("비고  제출용 정리", False),
                ],
            ),
            (
                "PDF",
                "#E11D48",
                [
                    ("외근·출장 일지", True),
                    ("성명  김현장", False),
                    ("일시  07/11 10:20", False),
                    ("장소  판교 B사", False),
                    ("내용  데모·견적", False),
                    ("결과  후속 조율", False),
                    ("확인  ________", False),
                    ("", False),
                ],
            ),
            (
                "DOCX",
                "#2563EB",
                [
                    ("업무 보고 요약", True),
                    ("기간  이번 달", False),
                    ("총 거리  126 km", False),
                    ("외근  8건", False),
                    ("Top1  강남 고객사", False),
                    ("Top2  판교 B사", False),
                    ("첨부  바로 제출", False),
                    ("", False),
                ],
            ),
        ]

        for i, (label, accent, rows) in enumerate(samples):
            x = start_x + i * (card_w + gap)
            y0 = 8
            # paper
            d.rounded_rectangle(
                [x, y0, x + card_w, y0 + card_h],
                radius=18,
                fill=(248, 250, 252, 255),
                outline=(226, 232, 240, 255),
                width=2,
            )
            # top accent bar
            ar = int(accent[1:3], 16)
            ag = int(accent[3:5], 16)
            ab = int(accent[5:7], 16)
            d.rounded_rectangle([x, y0, x + card_w, y0 + 46], radius=18, fill=(ar, ag, ab, 255))
            # fix bottom of accent to square-ish
            d.rectangle([x, y0 + 24, x + card_w, y0 + 46], fill=(ar, ag, ab, 255))
            lf = fnt(22, True)
            lw, lh = text_size(d, label, lf)
            d.text((x + (card_w - lw) // 2, y0 + (46 - lh) // 2), label, font=lf, fill=(255, 255, 255, 255))

            yy = y0 + 62
            for text, is_title in rows:
                if not text:
                    continue
                if is_title:
                    tf = fnt(20, True)
                    d.text((x + 18, yy), text, font=tf, fill=(15, 23, 42, 255))
                    yy += 34
                    d.line([(x + 18, yy - 8), (x + card_w - 18, yy - 8)], fill=(226, 232, 240, 255), width=1)
                else:
                    bf = fnt(16)
                    d.text((x + 18, yy), text, font=bf, fill=(51, 65, 85, 255))
                    yy += 28

            # footer chip
            chip = f"{label} 다운로드"
            cf = fnt(16, True)
            cw, ch = text_size(d, chip, cf)
            cx = x + (card_w - cw - 24) // 2
            cy = y0 + card_h - 42
            d.rounded_rectangle(
                [cx, cy, cx + cw + 24, cy + ch + 14],
                radius=14,
                fill=(ar, ag, ab, 24),
                outline=(ar, ag, ab, 180),
                width=1,
            )
            d.text((cx + 12, cy + 6), chip, font=cf, fill=(ar, ag, ab, 255))

        # caption
        cap = "제출용 출력물 예시 — 그대로 결재판·메일에 첨부"
        cf = fnt(22)
        cw, _ = text_size(d, cap, cf)
        d.text(((W - cw) // 2, card_h + 28), cap, font=cf, fill=(148, 163, 184, 255))
        self.push(img)

    def build(self) -> Image.Image:
        # Estimate total height by building sections
        self.parts.clear()

        # HERO
        hero_h = 420
        hero, d = self.canvas(hero_h)
        draw_logo_mark(hero, (W - 88) // 2, 40, 88)
        d = ImageDraw.Draw(hero)
        badge = "오픈 초기 · 1인 개발"
        bf = fnt(24, True)
        bw, bh = text_size(d, badge, bf)
        bx = (W - bw - 36) // 2
        d.rounded_rectangle([bx, 150, bx + bw + 36, 150 + bh + 18], radius=20, fill=(34, 211, 238, 32), outline=(34, 211, 238, 120), width=1)
        d.text((bx + 18, 158), badge, font=bf, fill=(165, 243, 252, 255))
        t1 = "RoadLog"
        tw, th = text_size(d, t1, fnt(64, True))
        d.text(((W - tw) // 2, 210), t1, font=fnt(64, True), fill=(248, 250, 252, 255))
        t2 = "로드로그 · AI 운행·외근 일지"
        tw2, _ = text_size(d, t2, fnt(28))
        d.text(((W - tw2) // 2, 290), t2, font=fnt(28), fill=(148, 163, 184, 255))
        t3 = "한번 써 보시고, 피드백 주시면 너무 감사하겠습니다."
        tw3, _ = text_size(d, t3, fnt(26))
        # wrap if needed
        lines = wrap_lines(d, t3, fnt(26), CONTENT_W)
        y = 340
        for line in lines:
            twl, thl = text_size(d, line, fnt(26))
            d.text(((W - twl) // 2, y), line, font=fnt(26), fill=(203, 213, 225, 255))
            y += thl + 6
        self.push(hero)
        self.spacer(10)

        # STORY
        self.add_heading("이야기", "왜 만들었는지")
        story = (
            "그동안 여러가지 일을 시도하다가 잘 안되서, "
            "마지막 시도라고 생각하고 1인 개발에 뛰어들었습니다.\n\n"
            "첫 개발이니만큼 사람 모으는 게 쉽지 않네요.\n\n"
            "광고처럼 들리기보다, 정말 한번 써 보시고 "
            "불편한 점·좋은 점 피드백 주시면 너무 감사하겠습니다. "
            "말씀 주신 내용은 바로바로 반영해 볼게요."
        )
        self.add_paragraphs(story, size=29, color=(226, 232, 240, 255), gap=12)
        self.spacer(20)

        # LANDING SHOT
        self.add_heading("사이트 미리보기", "로드로그는 이렇게 생겼어요")
        self.add_shot(
            SHOTS / "landing_mobile.png",
            "메인 화면 — 오늘 현장 기록부터 제출용 문서까지",
            crop_top=0,
            max_w=720,
        )
        self.spacer(8)

        # FEATURES
        self.add_heading("무엇을 할 수 있나요", "핵심 기능")
        self.add_feature_list(
            [
                (
                    "운행일지 / 외근·출장 선택",
                    "로그인하면 메인에서 오늘 쓸 일지 유형을 바로 고를 수 있어요. 스크롤 내릴 필요 없이 바로 시작합니다.",
                ),
                (
                    "지금 위치 스탬프 (GPS)",
                    "현장에 도착하면 큰 스탬프 버튼 한 번. 시간과 주소가 기록되고, 방문지 입력에 자동으로 반영됩니다.",
                ),
                (
                    "AI 일지 작성",
                    "스탬프·짧은 메모만 있어도 회사 제출용 문장으로 정리해 드려요. Excel · PDF · DOCX로 받을 수 있습니다.",
                ),
                (
                    "주간·월간 업무 요약",
                    "총 운행거리, 외근 건수, 방문 Top3를 한눈에 보고 PDF·Excel·이미지로 뽑아 결재판·메일에 붙일 수 있어요.",
                ),
                (
                    "회사 서식 학습",
                    "쓰는 양식 사진·문서를 올려 두면, 그 톤과 칸에 맞춰 AI가 작성하도록 학습시킬 수 있습니다.",
                ),
            ]
        )
        self.spacer(12)

        # APP HOME
        self.add_heading("실제 사용 화면", "로그인 후 메인")
        self.add_paragraphs(
            "로그인하면 랜딩이 아니라 작업 홈이 열립니다. "
            "운행/외근을 고르고, 바로 아래 큰 스탬프 버튼으로 위치를 찍을 수 있어요.",
            size=26,
            color=(148, 163, 184, 255),
            gap=10,
        )
        self.add_shot(
            SHOTS / "app_home.png",
            "메인 — 유형 선택 + 큰 「지금 위치 스탬프」 버튼",
            crop_top=0,
            max_w=720,
        )
        self.spacer(8)

        self.add_heading("현장 기록", "퀵 스탬프")
        self.add_paragraphs(
            "버튼 한 번으로 현재 시각과 GPS 주소를 남깁니다. "
            "오전/오후 방문지에 반영하거나, 외근 모드에서는 방문 내용으로 이어집니다.",
            size=26,
            color=(148, 163, 184, 255),
            gap=10,
        )
        self.add_shot(
            SHOTS / "create_stamp.png",
            "퀵 스탬프 + AI로 일지 작성",
            crop_top=0,
            max_w=720,
        )
        self.spacer(12)

        # EXPORT SAMPLES (trust for managers)
        self.add_heading("보고서 출력", "회사 제출 모양이 이렇게 나옵니다")
        self.add_paragraphs(
            "외근직·관리자가 가장 궁금한 건 결국 “상급자·회사에 낼 파일이 깔끔한가?”일 거예요. "
            "생성 결과를 Excel · PDF · DOCX로 받아 바로 첨부할 수 있게 만들었습니다.",
            size=26,
            color=(148, 163, 184, 255),
            gap=10,
        )
        self.spacer(8)
        self.add_export_samples()
        self.spacer(16)

        # REPORTS + B2B
        self.add_heading("팀장·총무도", "주간·월간 업무 요약")
        self.add_paragraphs(
            "저장된 일지를 모아 주간·월간 실적을 요약합니다. "
            "월말 보고서·결재 첨부용으로 바로 쓰기 좋게 만들었어요.",
            size=26,
            color=(148, 163, 184, 255),
            gap=10,
        )
        self.spacer(6)
        self.add_highlight_box(
            "B2B · 팀 단위",
            [
                "팀원들의 외근 현황도 대시보드로 한눈에 관리하세요.",
                "Enterprise는 팀·좌석 단위로 도입을 문의하실 수 있습니다.",
            ],
        )
        self.spacer(10)
        self.add_shot(
            SHOTS / "reports.png",
            "업무 요약 — km · 외근 · 방문 Top · 내보내기",
            crop_top=0,
            max_w=720,
        )
        self.spacer(16)

        # FREE TRIAL (no VIP, reduce pay-wall anxiety)
        self.add_heading("부담 없이 시작", "카드 없이, 바로 써보기")
        self.add_highlight_box(
            "Free 체험 · 가입 장벽 없음",
            [
                "카드 등록 없이 3초 가입, Free 10회 즉시 제공",
                "월 리셋 없음 · 결제 강요 없이 먼저 써 보세요",
                "더 쓰실 때만 Pro(무제한) · 팀은 Enterprise",
            ],
        )
        self.spacer(12)
        self.add_paragraphs(
            "“몇 번 쓰면 바로 돈 내야 하나?” 걱정하지 않으셔도 됩니다. "
            "먼저 스탬프·일지·출력까지 끝까지 체험해 보시고, 필요하실 때 유료로 이어가시면 돼요.",
            size=26,
            color=(148, 163, 184, 255),
            gap=10,
        )
        self.spacer(24)

        # CTA
        cta_h = 220
        cta, d = self.canvas(cta_h)
        msg = "roadlog.co.kr"
        mf = fnt(44, True)
        mw, mh = text_size(d, msg, mf)
        d.rounded_rectangle(
            [(W - mw) // 2 - 40, 30, (W + mw) // 2 + 40, 30 + mh + 36],
            radius=32,
            fill=(34, 211, 238, 45),
            outline=(34, 211, 238, 160),
            width=2,
        )
        d.text(((W - mw) // 2, 48), msg, font=mf, fill=(103, 232, 249, 255))
        sub = "카드 없이 가입 → Free 10회 → 피드백 환영"
        sw, _ = text_size(d, sub, fnt(26))
        d.text(((W - sw) // 2, 130), sub, font=fnt(26), fill=(203, 213, 225, 255))
        foot = "CoreLabs · 1인 개발 · 오픈 초기"
        fw, _ = text_size(d, foot, fnt(22))
        d.text(((W - fw) // 2, 175), foot, font=fnt(22), fill=(100, 116, 139, 255))
        self.push(cta)
        self.spacer(40)

        total_h = sum(p.height for p in self.parts)
        bg = draw_bg(total_h)
        y = 0
        for part in self.parts:
            bg.paste(part, (0, y), part)
            y += part.height
        return bg.convert("RGB")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    missing = [n for n in ("landing_mobile.png", "app_home.png", "create_stamp.png", "reports.png") if not (SHOTS / n).exists()]
    if missing:
        raise SystemExit(f"missing shots: {missing} — run scripts/_capture_promo_shots.py first")

    img = Builder().build()
    path = OUT / "roadlog_promo_long_story.png"
    img.save(path, "PNG", optimize=True)
    print("saved", path, img.size)

    # also a slightly compressed jpeg for chat share
    jpg = OUT / "roadlog_promo_long_story.jpg"
    img.save(jpg, "JPEG", quality=90, optimize=True)
    print("saved", jpg, jpg.stat().st_size)


if __name__ == "__main__":
    main()

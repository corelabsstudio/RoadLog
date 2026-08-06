"""Generate soft open-early RoadLog promo images (exact Korean text via PIL)."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import math

OUT = Path(__file__).resolve().parents[1] / "docs" / "marketing" / "promo"
FONT = r"C:\Windows\Fonts\malgun.ttf"
FONT_B = r"C:\Windows\Fonts\malgunbd.ttf"


def font(size, bold=False):
    try:
        return ImageFont.truetype(FONT_B if bold else FONT, size)
    except Exception:
        return ImageFont.truetype(FONT, size)


def draw_bg(w, h):
    img = Image.new("RGB", (w, h), "#030712")
    px = img.load()
    cx, cy = w * 0.55, h * 0.35
    for y in range(h):
        for x in range(0, w, 2):
            dx = (x - cx) / w
            dy = (y - cy) / h
            d = math.sqrt(dx * dx + dy * dy)
            t = max(0, 1 - d * 1.35)
            r = int(3 + 12 * t)
            g = int(7 + 40 * t)
            b = int(18 + 55 * t)
            px[x, y] = (r, g, b)
            if x + 1 < w:
                px[x + 1, y] = (r, g, b)
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.ellipse(
        [int(w * 0.55), int(-h * 0.1), int(w * 1.15), int(h * 0.55)],
        fill=(34, 211, 238, 28),
    )
    od.ellipse(
        [int(-w * 0.2), int(h * 0.55), int(w * 0.45), int(h * 1.15)],
        fill=(8, 145, 178, 22),
    )
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def text_w(draw, text, f):
    b = draw.textbbox((0, 0), text, font=f)
    return b[2] - b[0]


def center_text(draw, y, text, f, fill, W):
    tw = text_w(draw, text, f)
    draw.text(((W - tw) // 2, y), text, font=f, fill=fill)
    bb = draw.textbbox((0, 0), text, font=f)
    return y + (bb[3] - bb[1])


def wrap_center(draw, y, text, f, fill, W, max_chars=18, line_gap=10):
    lines, cur = [], ""
    for ch in text:
        cur += ch
        if len(cur) >= max_chars and ch in " ·,./!?":
            lines.append(cur.strip())
            cur = ""
        elif len(cur) >= max_chars + 4:
            lines.append(cur.strip())
            cur = ""
    if cur.strip():
        lines.append(cur.strip())
    if not lines:
        lines = [text]
    for line in lines:
        tw = text_w(draw, line, f)
        draw.text(((W - tw) // 2, y), line, font=f, fill=fill)
        bb = draw.textbbox((0, 0), line, font=f)
        y += (bb[3] - bb[1]) + line_gap
    return y


def draw_logo_mark(base, x, y, size=88):
    tile = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    td = ImageDraw.Draw(tile)
    for i in range(size):
        t = i / max(size - 1, 1)
        r = int(103 + (8 - 103) * t)
        g = int(232 + (145 - 232) * t)
        b = int(249 + (178 - 249) * t)
        td.line([(0, i), (size, i)], fill=(r, g, b, 255))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, size - 1, size - 1], radius=int(size * 0.22), fill=255
    )
    tile.putalpha(mask)
    shine = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(shine).rounded_rectangle(
        [3, 3, size - 4, size // 2], radius=int(size * 0.18), fill=(255, 255, 255, 35)
    )
    tile = Image.alpha_composite(tile, shine)
    td = ImageDraw.Draw(tile)
    s = size / 64
    td.arc(
        [int(10 * s), int(18 * s), int(52 * s), int(52 * s)],
        200,
        340,
        fill=(4, 16, 22, 255),
        width=max(2, int(4 * s)),
    )
    td.ellipse(
        [int(43 * s), int(18 * s), int(54 * s), int(29 * s)], fill=(4, 16, 22, 255)
    )
    td.ellipse(
        [int(46 * s), int(21 * s), int(51 * s), int(26 * s)], fill=(103, 232, 249, 255)
    )
    td.line(
        [(int(13 * s), int(46 * s)), (int(40 * s), int(46 * s))],
        fill=(4, 16, 22, 180),
        width=max(2, int(3 * s)),
    )
    td.ellipse(
        [int(15 * s), int(43 * s), int(22 * s), int(50 * s)], fill=(4, 16, 22, 255)
    )
    td.ellipse(
        [int(34 * s), int(43 * s), int(41 * s), int(50 * s)], fill=(4, 16, 22, 255)
    )
    base.paste(tile, (x, y), tile)


def make_square():
    W, H = 1080, 1080
    img = draw_bg(W, H).convert("RGBA")
    glass = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glass).rounded_rectangle(
        [72, 72, W - 72, H - 72],
        radius=40,
        fill=(8, 14, 28, 210),
        outline=(34, 211, 238, 90),
        width=2,
    )
    img = Image.alpha_composite(img, glass)
    d = ImageDraw.Draw(img)
    badge, fb = "오픈 초기", font(28, True)
    bw = text_w(d, badge, fb) + 36
    bx = (W - bw) // 2
    d.rounded_rectangle(
        [bx, 130, bx + bw, 176],
        radius=23,
        fill=(34, 211, 238, 30),
        outline=(34, 211, 238, 120),
        width=1,
    )
    d.text((bx + 18, 138), badge, font=fb, fill=(165, 243, 252, 255))
    draw_logo_mark(img, (W - 96) // 2, 210, 96)
    d = ImageDraw.Draw(img)
    y = 330
    y = center_text(d, y, "RoadLog", font(64, True), (248, 250, 252, 255), W) + 8
    y = center_text(d, y, "로드로그", font(30), (148, 163, 184, 255), W) + 28
    y = wrap_center(d, y, "광고 같긴 싫어서…", font(36), (203, 213, 225, 255), W, 16, 8)
    y += 6
    y = wrap_center(
        d, y, "한번만 써 봐 주실래요?", font(48, True), (248, 250, 252, 255), W, 14, 10
    )
    y += 18
    y = wrap_center(
        d,
        y,
        "운행·외근 일지, 스탬프 찍고 메모만 하면",
        font(28),
        (148, 163, 184, 255),
        W,
        22,
        8,
    )
    y = wrap_center(
        d, y, "회사 제출용으로 정리해 드려요.", font(28), (148, 163, 184, 255), W, 22, 8
    )
    y += 28
    note, fn = "가입 후 Free 10회 · 부담 없이 시험해 보세요", font(26)
    nw = text_w(d, note, fn) + 40
    nx = (W - nw) // 2
    d.rounded_rectangle(
        [nx, y, nx + nw, y + 52],
        radius=26,
        fill=(15, 23, 42, 230),
        outline=(100, 116, 139, 80),
        width=1,
    )
    d.text((nx + 20, y + 12), note, font=fn, fill=(103, 232, 249, 255))
    y += 80
    y = center_text(d, y, "roadlog.co.kr", font(34, True), (34, 211, 238, 255), W) + 10
    center_text(d, y, "CoreLabs · 오픈 초기 부탁", font(22), (100, 116, 139, 255), W)
    p = OUT / "roadlog_promo_square_1080.png"
    img.convert("RGB").save(p, "PNG", optimize=True)
    print("saved", p)


def make_landscape():
    W, H = 1200, 630
    img = draw_bg(W, H).convert("RGBA")
    glass = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glass).rounded_rectangle(
        [36, 36, W - 36, H - 36],
        radius=32,
        fill=(8, 14, 28, 200),
        outline=(34, 211, 238, 80),
        width=2,
    )
    img = Image.alpha_composite(img, glass)
    d = ImageDraw.Draw(img)
    draw_logo_mark(img, 80, 100, 100)
    d = ImageDraw.Draw(img)
    d.text((210, 105), "RoadLog", font=font(44, True), fill=(248, 250, 252, 255))
    d.text((210, 160), "오픈 초기 · 로드로그", font=font(24), fill=(103, 232, 249, 255))
    d.text((80, 240), "한번만 써 봐 주실래요?", font=font(46, True), fill=(248, 250, 252, 255))
    d.text(
        (80, 310),
        "운행·외근 일지, 스탬프 한 번이면 됩니다.",
        font=font(28),
        fill=(203, 213, 225, 255),
    )
    d.text(
        (80, 355),
        "광고 말고, 그냥 써 보고 피드백 주시면 감사하겠습니다.",
        font=font(24),
        fill=(148, 163, 184, 255),
    )
    d.rounded_rectangle(
        [80, 430, 480, 490],
        radius=28,
        fill=(34, 211, 238, 40),
        outline=(34, 211, 238, 120),
        width=1,
    )
    d.text(
        (110, 445),
        "Free 10회  ·  roadlog.co.kr",
        font=font(26, True),
        fill=(165, 243, 252, 255),
    )
    d.rounded_rectangle(
        [720, 120, 1120, 500],
        radius=24,
        fill=(15, 23, 42, 180),
        outline=(51, 65, 85, 120),
        width=1,
    )
    tips = [("1", "유형 고르기"), ("2", "위치 스탬프"), ("3", "AI 일지 작성")]
    ty = 160
    for n, t in tips:
        d.ellipse(
            [760, ty, 810, ty + 50],
            fill=(34, 211, 238, 50),
            outline=(34, 211, 238, 140),
            width=1,
        )
        tw = text_w(d, n, font(24, True))
        d.text(
            (760 + (50 - tw) // 2, ty + 10),
            n,
            font=font(24, True),
            fill=(103, 232, 249, 255),
        )
        d.text((830, ty + 10), t, font=font(28), fill=(226, 232, 240, 255))
        ty += 90
    d.text((760, 450), "부담 없이 한 번만요", font=font(22), fill=(100, 116, 139, 255))
    p = OUT / "roadlog_promo_og_1200x630.png"
    img.convert("RGB").save(p, "PNG", optimize=True)
    print("saved", p)


def make_story():
    W, H = 1080, 1920
    img = draw_bg(W, H).convert("RGBA")
    glass = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glass).rounded_rectangle(
        [56, 200, W - 56, H - 200],
        radius=44,
        fill=(8, 14, 28, 205),
        outline=(34, 211, 238, 85),
        width=2,
    )
    img = Image.alpha_composite(img, glass)
    d = ImageDraw.Draw(img)
    badge, fb = "오픈 초기 부탁", font(30, True)
    bw = text_w(d, badge, fb) + 40
    bx = (W - bw) // 2
    d.rounded_rectangle(
        [bx, 260, bx + bw, 320],
        radius=30,
        fill=(34, 211, 238, 28),
        outline=(34, 211, 238, 110),
        width=1,
    )
    d.text((bx + 20, 272), badge, font=fb, fill=(165, 243, 252, 255))
    draw_logo_mark(img, (W - 120) // 2, 380, 120)
    d = ImageDraw.Draw(img)
    y = 540
    y = center_text(d, y, "RoadLog", font(72, True), (248, 250, 252, 255), W) + 16
    y = (
        center_text(
            d, y, "로드로그 · AI 운행·외근 일지", font(30), (148, 163, 184, 255), W
        )
        + 50
    )
    y = wrap_center(d, y, "홍보 글 같긴 한데…", font(36), (203, 213, 225, 255), W, 14, 10)
    y += 8
    y = wrap_center(d, y, "진짜로 한번만", font(52, True), (248, 250, 252, 255), W, 12, 12)
    y = wrap_center(d, y, "써 봐 주세요", font(52, True), (103, 232, 249, 255), W, 12, 12)
    y += 30
    y = wrap_center(
        d, y, "스탬프 찍고 메모만 하면", font(30), (148, 163, 184, 255), W, 18, 10
    )
    y = wrap_center(
        d, y, "제출용 일지로 정리해 드려요.", font(30), (148, 163, 184, 255), W, 18, 10
    )
    y += 40
    note, fn = "Free 10회 · 가입 후 바로", font(28, True)
    nw = text_w(d, note, fn) + 48
    nx = (W - nw) // 2
    d.rounded_rectangle(
        [nx, y, nx + nw, y + 58],
        radius=29,
        fill=(15, 23, 42, 240),
        outline=(100, 116, 139, 90),
        width=1,
    )
    d.text((nx + 24, y + 14), note, font=fn, fill=(165, 243, 252, 255))
    y += 100
    y = center_text(d, y, "roadlog.co.kr", font(40, True), (34, 211, 238, 255), W) + 16
    center_text(d, y, "피드백 주시면 바로 반영할게요", font(26), (100, 116, 139, 255), W)
    p = OUT / "roadlog_promo_story_1080x1920.png"
    img.convert("RGB").save(p, "PNG", optimize=True)
    print("saved", p)


def make_kakao():
    W, H = 1000, 500
    img = draw_bg(W, H).convert("RGBA")
    glass = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glass).rounded_rectangle(
        [24, 24, W - 24, H - 24],
        radius=28,
        fill=(8, 14, 28, 210),
        outline=(34, 211, 238, 85),
        width=2,
    )
    img = Image.alpha_composite(img, glass)
    d = ImageDraw.Draw(img)
    draw_logo_mark(img, 56, 70, 84)
    d = ImageDraw.Draw(img)
    d.text((160, 78), "RoadLog · 오픈 초기", font=font(26), fill=(103, 232, 249, 255))
    d.text((160, 120), "한번만 써 봐 주실래요?", font=font(40, True), fill=(248, 250, 252, 255))
    d.text(
        (56, 220),
        "운행·외근 일지 — 스탬프 찍고 메모만 하면 됩니다.",
        font=font(26),
        fill=(203, 213, 225, 255),
    )
    d.text(
        (56, 265),
        "광고 말고, 써 보고 느낌만 알려주셔도 감사해요.",
        font=font(24),
        fill=(148, 163, 184, 255),
    )
    d.rounded_rectangle(
        [56, 340, 520, 410],
        radius=24,
        fill=(34, 211, 238, 35),
        outline=(34, 211, 238, 110),
        width=1,
    )
    d.text(
        (80, 358),
        "Free 10회  ·  roadlog.co.kr",
        font=font(28, True),
        fill=(165, 243, 252, 255),
    )
    d.text((560, 365), "CoreLabs", font=font(22), fill=(100, 116, 139, 255))
    p = OUT / "roadlog_promo_kakao_1000x500.png"
    img.convert("RGB").save(p, "PNG", optimize=True)
    print("saved", p)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    make_square()
    make_landscape()
    make_story()
    make_kakao()
    print("done ->", OUT)


if __name__ == "__main__":
    main()

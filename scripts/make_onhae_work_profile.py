# -*- coding: utf-8 -*-
"""Kmong profile: work-themed (Excel / automation), no brand nickname as hero."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import math

OUT = Path(r"C:\Users\hysoo\Desktop\kmong")
OUT.mkdir(parents=True, exist_ok=True)

FONT_DIR = Path(r"tools\community_poster\assets\fonts")
candidates = [
    FONT_DIR / "SCDream6.otf",
    FONT_DIR / "SCDream5.otf",
    Path(r"C:\Windows\Fonts\malgunbd.ttf"),
    Path(r"C:\Windows\Fonts\malgun.ttf"),
]
font_path = next(p for p in candidates if p.exists())


def font(size):
    return ImageFont.truetype(str(font_path), size=size)


def save(img: Image.Image, stem: str):
    png = OUT / f"{stem}.png"
    jpg = OUT / f"{stem}.jpg"
    img.save(png, "PNG", optimize=True)
    img.convert("RGB").save(jpg, "JPEG", quality=95)
    print("saved", png.name, jpg.name)


def profile_excel_grid():
    """Spreadsheet + automation arrow — icon only, no nickname."""
    size = 1024
    bg = (15, 23, 42)
    img = Image.new("RGB", (size, size), bg)
    d = ImageDraw.Draw(img)

    # circular frame
    m = int(size * 0.07)
    ring = (37, 99, 235)
    d.ellipse([m, m, size - m, size - m], outline=ring, width=max(10, size // 56))
    m2 = m + 14
    d.ellipse([m2, m2, size - m2, size - m2], outline=(30, 58, 120), width=3)

    # spreadsheet card
    card_w, card_h = int(size * 0.48), int(size * 0.38)
    cx, cy = size // 2 - int(size * 0.06), size // 2 - int(size * 0.02)
    x0, y0 = cx - card_w // 2, cy - card_h // 2
    x1, y1 = x0 + card_w, y0 + card_h
    # shadow
    shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle([x0 + 10, y0 + 14, x1 + 10, y1 + 14], radius=18, fill=(0, 0, 0, 90))
    img = Image.alpha_composite(img.convert("RGBA"), shadow).convert("RGB")
    d = ImageDraw.Draw(img)

    # sheet body
    d.rounded_rectangle([x0, y0, x1, y1], radius=18, fill=(248, 250, 252))
    # header green like excel
    header_h = int(card_h * 0.22)
    d.rounded_rectangle([x0, y0, x1, y0 + header_h + 12], radius=18, fill=(22, 163, 74))
    d.rectangle([x0, y0 + header_h - 4, x1, y0 + header_h + 12], fill=(22, 163, 74))
    # header dots
    for i, col in enumerate([(255, 255, 255), (187, 247, 208), (134, 239, 172)]):
        d.ellipse([x0 + 22 + i * 22, y0 + 18, x0 + 36 + i * 22, y0 + 32], fill=col)

    # grid
    rows, cols = 4, 4
    grid_top = y0 + header_h + 8
    cell_w = card_w / cols
    cell_h = (y1 - grid_top) / rows
    grid_color = (203, 213, 225)
    for r in range(rows + 1):
        yy = grid_top + r * cell_h
        d.line([x0 + 8, yy, x1 - 8, yy], fill=grid_color, width=2)
    for c in range(cols + 1):
        xx = x0 + c * cell_w
        d.line([xx, grid_top, xx, y1 - 8], fill=grid_color, width=2)

    # filled cells suggesting data
    fills = [
        (1, 1, (219, 234, 254)),
        (1, 2, (191, 219, 254)),
        (2, 1, (187, 247, 208)),
        (2, 3, (254, 249, 195)),
        (3, 2, (224, 231, 255)),
    ]
    for r, c, col in fills:
        cx0 = x0 + c * cell_w + 3
        cy0 = grid_top + r * cell_h + 3
        d.rectangle([cx0, cy0, cx0 + cell_w - 6, cy0 + cell_h - 6], fill=col)

    # automation arrow / gear-ish circle on right of sheet
    ax = x1 + int(size * 0.02)
    ay = cy
    r = int(size * 0.09)
    d.ellipse([ax - r, ay - r, ax + r, ay + r], fill=(37, 99, 235))
    # play / arrow
    tri = [
        (ax - r // 3, ay - r // 2),
        (ax - r // 3, ay + r // 2),
        (ax + r // 2, ay),
    ]
    d.polygon(tri, fill=(255, 255, 255))

    # small sparkles / process dots
    for i, (dx, dy) in enumerate([(-0.28, 0.28), (-0.22, 0.34), (0.32, -0.28)]):
        px, py = size // 2 + int(size * dx), size // 2 + int(size * dy)
        d.ellipse([px - 6, py - 6, px + 6, py + 6], fill=(56, 189, 248))

    save(img, "profile_work_excel")


def profile_workflow():
    """Three-step workflow icons: table -> gear -> chart."""
    size = 1024
    bg = (15, 23, 42)
    img = Image.new("RGB", (size, size), bg)
    d = ImageDraw.Draw(img)

    m = int(size * 0.07)
    d.ellipse([m, m, size - m, size - m], outline=(37, 99, 235), width=max(10, size // 56))

    def icon_box(cx, cy, s, fill, draw_fn):
        x0, y0 = cx - s // 2, cy - s // 2
        d.rounded_rectangle([x0, y0, x0 + s, y0 + s], radius=s // 5, fill=fill)
        draw_fn(d, cx, cy, s)

    def draw_table(d, cx, cy, s):
        pad = s // 5
        d.rectangle([cx - pad, cy - pad, cx + pad, cy + pad], outline=(255, 255, 255), width=3)
        d.line([cx - pad, cy, cx + pad, cy], fill=(255, 255, 255), width=2)
        d.line([cx, cy - pad, cx, cy + pad], fill=(255, 255, 255), width=2)

    def draw_gear(d, cx, cy, s):
        # simple gear: circle + teeth marks
        r = s // 4
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(255, 255, 255), width=4)
        d.ellipse([cx - r // 2, cy - r // 2, cx + r // 2, cy + r // 2], fill=(255, 255, 255))
        for ang in range(0, 360, 45):
            rad = math.radians(ang)
            x1 = cx + int((r + 8) * math.cos(rad))
            y1 = cy + int((r + 8) * math.sin(rad))
            x2 = cx + int((r + 18) * math.cos(rad))
            y2 = cy + int((r + 18) * math.sin(rad))
            d.line([x1, y1, x2, y2], fill=(255, 255, 255), width=5)

    def draw_chart(d, cx, cy, s):
        pad = s // 4
        base = cy + pad // 2
        bars = [0.35, 0.55, 0.85, 0.65]
        bw = (2 * pad) // len(bars) - 4
        for i, h in enumerate(bars):
            bh = int(pad * 1.6 * h)
            bx = cx - pad + i * (bw + 4)
            d.rectangle([bx, base - bh, bx + bw, base], fill=(255, 255, 255))

    cy = size // 2
    s = int(size * 0.18)
    positions = [
        (size * 0.28, cy, (22, 163, 74), draw_table),
        (size * 0.50, cy, (37, 99, 235), draw_gear),
        (size * 0.72, cy, (14, 165, 233), draw_chart),
    ]
    for i, (x, y, col, fn) in enumerate(positions):
        icon_box(int(x), int(y), s, col, fn)
        if i < 2:
            x1 = int(x) + s // 2 + 8
            x2 = int(positions[i + 1][0]) - s // 2 - 8
            midy = cy
            d.line([x1, midy, x2, midy], fill=(100, 116, 139), width=4)
            # arrow head
            d.polygon([(x2, midy), (x2 - 12, midy - 8), (x2 - 12, midy + 8)], fill=(148, 163, 184))

    # bottom caption - work type not nickname
    f = font(int(size * 0.048))
    text = "엑셀 · 업무 자동화"
    bbox = d.textbbox((0, 0), text, font=f)
    tw = bbox[2] - bbox[0]
    d.text(((size - tw) // 2, int(size * 0.72)), text, font=f, fill=(186, 198, 214))

    save(img, "profile_work_flow")


def profile_python_excel():
    """Code bracket + spreadsheet — technical expert look."""
    size = 1024
    bg = (15, 23, 42)
    img = Image.new("RGB", (size, size), bg)
    d = ImageDraw.Draw(img)

    m = int(size * 0.07)
    d.ellipse([m, m, size - m, size - m], outline=(37, 99, 235), width=max(10, size // 56))

    # left: code braces
    f_big = font(int(size * 0.22))
    d.text((int(size * 0.18), int(size * 0.32)), "{ }", font=f_big, fill=(56, 189, 248))

    # center plus
    f_plus = font(int(size * 0.1))
    d.text((int(size * 0.44), int(size * 0.40)), "+", font=f_plus, fill=(148, 163, 184))

    # right mini excel
    ex0, ey0 = int(size * 0.52), int(size * 0.34)
    ew, eh = int(size * 0.28), int(size * 0.24)
    d.rounded_rectangle([ex0, ey0, ex0 + ew, ey0 + eh], radius=12, fill=(248, 250, 252))
    d.rectangle([ex0, ey0, ex0 + ew, ey0 + int(eh * 0.28)], fill=(22, 163, 74))
    # grid lines
    for i in range(1, 4):
        yy = ey0 + int(eh * 0.28) + i * int(eh * 0.18)
        d.line([ex0 + 8, yy, ex0 + ew - 8, yy], fill=(203, 213, 225), width=2)
    for i in range(1, 3):
        xx = ex0 + i * ew // 3
        d.line([xx, ey0 + int(eh * 0.28), xx, ey0 + eh - 6], fill=(203, 213, 225), width=2)

    f = font(int(size * 0.045))
    lines = ["파이썬 자동화", "시트 합치기 · 요약 · 리포트"]
    y = int(size * 0.66)
    for line in lines:
        bbox = d.textbbox((0, 0), line, font=f)
        tw = bbox[2] - bbox[0]
        color = (226, 232, 240) if line == lines[0] else (148, 163, 184)
        d.text(((size - tw) // 2, y), line, font=f, fill=color)
        y += int(size * 0.06)

    save(img, "profile_work_python")


def profile_clean_icon_only():
    """Pure icon, no text at all — safest small avatar."""
    size = 1024
    bg = (15, 23, 42)
    img = Image.new("RGB", (size, size), bg)
    d = ImageDraw.Draw(img)

    m = int(size * 0.06)
    d.ellipse([m, m, size - m, size - m], outline=(37, 99, 235), width=max(12, size // 50))

    # large sheet centered
    card_w, card_h = int(size * 0.42), int(size * 0.42)
    x0 = (size - card_w) // 2
    y0 = (size - card_h) // 2 - int(size * 0.02)
    x1, y1 = x0 + card_w, y0 + card_h
    d.rounded_rectangle([x0, y0, x1, y1], radius=22, fill=(241, 245, 249))
    hh = int(card_h * 0.2)
    d.rounded_rectangle([x0, y0, x1, y0 + hh + 10], radius=22, fill=(22, 163, 74))
    d.rectangle([x0, y0 + hh - 6, x1, y0 + hh + 10], fill=(22, 163, 74))

    rows, cols = 5, 4
    gt = y0 + hh + 6
    cw, ch = card_w / cols, (y1 - gt) / rows
    for r in range(rows + 1):
        d.line([x0 + 6, gt + r * ch, x1 - 6, gt + r * ch], fill=(203, 213, 225), width=2)
    for c in range(cols + 1):
        d.line([x0 + c * cw, gt, x0 + c * cw, y1 - 6], fill=(203, 213, 225), width=2)

    # highlight column being "processed"
    d.rectangle(
        [x0 + 2 * cw + 2, gt + 2, x0 + 3 * cw - 2, y1 - 8],
        fill=(191, 219, 254),
    )

    # floating auto badge bottom-right of sheet
    bx = x1 - int(size * 0.02)
    by = y1 - int(size * 0.02)
    br = int(size * 0.1)
    d.ellipse([bx - br, by - br, bx + br, by + br], fill=(37, 99, 235))
    # lightning / bolt for automation
    bolt = [
        (bx - 8, by - 28),
        (bx + 12, by - 28),
        (bx + 2, by - 4),
        (bx + 16, by - 4),
        (bx - 10, by + 30),
        (bx + 2, by + 2),
        (bx - 14, by + 2),
    ]
    d.polygon(bolt, fill=(255, 255, 255))

    save(img, "profile_work_icon")


profile_excel_grid()
profile_workflow()
profile_python_excel()
profile_clean_icon_only()

# default upload copies
import shutil
for src, dst in [
    ("profile_work_icon.png", "profile_main.png"),
    ("profile_work_icon.jpg", "profile_main.jpg"),
]:
    shutil.copy(OUT / src, OUT / dst)
    print("default ->", dst)

print("done", OUT)
"""Generate professional CoreLabs logos for LinkedIn profile (circle-safe)."""
from __future__ import annotations

import math
import os

from PIL import Image, ImageDraw, ImageFont

OUT = os.path.dirname(os.path.abspath(__file__))

# Brand palette — professional tech studio
BG = (11, 18, 32)
BG2 = (17, 28, 48)
ACCENT = (0, 163, 255)
ACCENT2 = (56, 189, 248)
WHITE = (248, 250, 252)
MUTED = (148, 163, 184)

SIZE = 1024


def get_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\malgunbd.ttf" if bold else r"C:\Windows\Fonts\malgun.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def draw_bg(draw: ImageDraw.ImageDraw, size: int) -> None:
    cx = cy = size // 2
    for r in range(size // 2, 0, -2):
        t = r / (size / 2)
        col = tuple(
            int(BG[i] * t + BG2[i] * (1 - t) * 0.7 + BG[i] * (1 - t) * 0.3) for i in range(3)
        )
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)


def make_profile_clean() -> str:
    """Primary LinkedIn avatar: big CL, circle-safe, maximum readability."""
    img = Image.new("RGB", (SIZE, SIZE), BG)
    draw = ImageDraw.Draw(img)
    draw_bg(draw, SIZE)
    cx = cy = SIZE // 2

    disc_r = 460
    draw.ellipse(
        [cx - disc_r, cy - disc_r, cx + disc_r, cy + disc_r],
        fill=(13, 22, 38),
    )
    draw.ellipse(
        [cx - disc_r, cy - disc_r, cx + disc_r, cy + disc_r],
        outline=ACCENT,
        width=14,
    )
    draw.ellipse(
        [cx - disc_r + 36, cy - disc_r + 36, cx + disc_r - 36, cy + disc_r - 36],
        outline=(28, 55, 90),
        width=4,
    )

    font = get_font(340, bold=True)
    text = "CL"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = cx - tw // 2 - bbox[0]
    ty = cy - th // 2 - bbox[1] - 36
    draw.text((tx + 4, ty + 6), text, font=font, fill=(0, 0, 0))
    draw.text((tx, ty), text, font=font, fill=WHITE)

    bar_w = 220
    bar_y = cy + 150
    draw.rounded_rectangle(
        [cx - bar_w // 2, bar_y, cx + bar_w // 2, bar_y + 14],
        radius=7,
        fill=ACCENT,
    )

    font_s = get_font(48, bold=True)
    label = "CORELABS"
    bbox = draw.textbbox((0, 0), label, font=font_s)
    lw = bbox[2] - bbox[0]
    draw.text((cx - lw // 2, bar_y + 36), label, font=font_s, fill=MUTED)

    path = os.path.join(OUT, "corelabs_linkedin_profile.png")
    img.save(path, "PNG", optimize=True)
    return path


def make_profile_hex() -> str:
    """Alternate: hex core + CL monogram (lab / network metaphor)."""
    img = Image.new("RGB", (SIZE, SIZE), BG)
    draw = ImageDraw.Draw(img)
    draw_bg(draw, SIZE)
    cx = cy = SIZE // 2

    ring_r = 400
    draw.ellipse(
        [cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r],
        outline=ACCENT,
        width=10,
    )
    draw.ellipse(
        [cx - ring_r + 28, cy - ring_r + 28, cx + ring_r - 28, cy + ring_r - 28],
        outline=(30, 58, 95),
        width=3,
    )

    hex_r = 250
    pts = []
    for i in range(6):
        a = math.radians(-90 + i * 60)
        pts.append((cx + hex_r * math.cos(a), cy + hex_r * math.sin(a)))
    draw.polygon(pts, outline=ACCENT2, width=5)

    pts2 = []
    for i in range(6):
        a = math.radians(-90 + i * 60)
        pts2.append((cx + (hex_r - 24) * math.cos(a), cy + (hex_r - 24) * math.sin(a)))
    draw.polygon(pts2, fill=(14, 24, 42))

    for i in range(6):
        a = math.radians(-90 + i * 60)
        x = cx + 168 * math.cos(a)
        y = cy + 168 * math.sin(a)
        draw.line([cx, cy, x, y], fill=(40, 90, 130), width=2)
        draw.ellipse([x - 8, y - 8, x + 8, y + 8], fill=ACCENT)
    draw.ellipse([cx - 16, cy - 16, cx + 16, cy + 16], fill=ACCENT2)

    font = get_font(200, bold=True)
    text = "CL"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = cx - tw // 2 - bbox[0]
    ty = cy - th // 2 - bbox[1] - 10
    draw.text((tx + 3, ty + 4), text, font=font, fill=(5, 10, 20))
    draw.text((tx, ty), text, font=font, fill=WHITE)

    path = os.path.join(OUT, "corelabs_linkedin_hex.png")
    img.save(path, "PNG", optimize=True)
    return path


def make_wordmark() -> str:
    """Symbol + CoreLabs wordmark (company page / banner companion)."""
    img = Image.new("RGB", (SIZE, SIZE), BG)
    draw = ImageDraw.Draw(img)
    draw_bg(draw, SIZE)
    cx = cy = SIZE // 2

    sy = cy - 130
    r = 150
    draw.ellipse(
        [cx - r - 18, sy - r - 18, cx + r + 18, sy + r + 18],
        outline=ACCENT,
        width=8,
    )
    pts = []
    for i in range(6):
        a = math.radians(-90 + i * 60)
        pts.append((cx + 100 * math.cos(a), sy + 100 * math.sin(a)))
    draw.polygon(pts, outline=ACCENT2, width=4)
    draw.ellipse([cx - 14, sy - 14, cx + 14, sy + 14], fill=ACCENT)

    font = get_font(92, bold=True)
    text = "CoreLabs"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    text_y = cy + 60
    draw.text((cx - tw // 2, text_y), text, font=font, fill=WHITE)

    # Divider fully below the wordmark (avoid crossing glyphs)
    line_y = text_y + th + 28
    draw.line([cx - 72, line_y, cx + 72, line_y], fill=ACCENT, width=3)

    font_s = get_font(34, bold=False)
    sub = "TECHNOLOGY STUDIO"
    bbox = draw.textbbox((0, 0), sub, font=font_s)
    sw = bbox[2] - bbox[0]
    draw.text((cx - sw // 2, line_y + 22), sub, font=font_s, fill=MUTED)

    path = os.path.join(OUT, "corelabs_logo_wordmark.png")
    img.save(path, "PNG", optimize=True)
    return path


def make_transparent_icon() -> str:
    """CL on solid disc with alpha outside (flexible export)."""
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx = cy = SIZE // 2
    disc_r = 460
    draw.ellipse(
        [cx - disc_r, cy - disc_r, cx + disc_r, cy + disc_r],
        fill=(*BG, 255),
    )
    draw.ellipse(
        [cx - disc_r, cy - disc_r, cx + disc_r, cy + disc_r],
        outline=(*ACCENT, 255),
        width=14,
    )

    font = get_font(340, bold=True)
    text = "CL"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = cx - tw // 2 - bbox[0]
    ty = cy - th // 2 - bbox[1] - 20
    draw.text((tx, ty), text, font=font, fill=(*WHITE, 255))

    bar_w = 200
    bar_y = cy + 160
    draw.rounded_rectangle(
        [cx - bar_w // 2, bar_y, cx + bar_w // 2, bar_y + 12],
        radius=6,
        fill=(*ACCENT, 255),
    )

    path = os.path.join(OUT, "corelabs_icon_transparent.png")
    img.save(path, "PNG", optimize=True)
    return path


def main() -> None:
    paths = [
        make_profile_clean(),
        make_profile_hex(),
        make_wordmark(),
        make_transparent_icon(),
    ]
    for p in paths:
        print(p)


if __name__ == "__main__":
    main()

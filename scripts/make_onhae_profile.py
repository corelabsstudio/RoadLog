# -*- coding: utf-8 -*-
"""Generate professional Kmong profile avatars for brand name 온해."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

OUT = Path(r"docs\marketing\brand\kmong")
OUT.mkdir(parents=True, exist_ok=True)

FONT_DIR = Path(r"tools\community_poster\assets\fonts")
# Prefer SCDream for Korean
candidates = [
    FONT_DIR / "SCDream6.otf",
    FONT_DIR / "SCDream5.otf",
    FONT_DIR / "SCDream7.otf",
    Path(r"C:\Windows\Fonts\malgunbd.ttf"),
    Path(r"C:\Windows\Fonts\malgun.ttf"),
]
font_path = next((p for p in candidates if p.exists()), None)
if not font_path:
    raise SystemExit("No Korean font found")
print("font:", font_path)


def load_font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(font_path), size=size)


def rounded_rect(draw, xy, radius, fill):
    draw.rounded_rectangle(xy, radius=radius, fill=fill)


def make_circle_badge(
    path: Path,
    bg: tuple,
    ring: tuple,
    text_color: tuple,
    accent: tuple,
    size: int = 1024,
    subtitle: str | None = "업무 자동화",
):
    img = Image.new("RGB", (size, size), bg)
    draw = ImageDraw.Draw(img)
    cx = cy = size // 2
    # outer ring
    m = int(size * 0.08)
    draw.ellipse([m, m, size - m, size - m], outline=ring, width=max(8, size // 64))
    # inner soft ring
    m2 = m + int(size * 0.03)
    draw.ellipse([m2, m2, size - m2, size - m2], outline=(*ring[:3],), width=max(2, size // 256))

    # Main word 온해
    font_main = load_font(int(size * 0.28))
    text = "온해"
    bbox = draw.textbbox((0, 0), text, font=font_main)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    # slight optical lift
    ty = cy - th // 2 - int(size * 0.04)
    draw.text(((size - tw) // 2, ty), text, font=font_main, fill=text_color)

    # accent line under name
    line_w = int(size * 0.18)
    line_y = ty + th + int(size * 0.06)
    draw.rounded_rectangle(
        [cx - line_w // 2, line_y, cx + line_w // 2, line_y + max(6, size // 80)],
        radius=4,
        fill=accent,
    )

    if subtitle:
        font_sub = load_font(int(size * 0.055))
        sb = draw.textbbox((0, 0), subtitle, font=font_sub)
        sw, sh = sb[2] - sb[0], sb[3] - sb[1]
        draw.text(
            ((size - sw) // 2, line_y + int(size * 0.05)),
            subtitle,
            font=font_sub,
            fill=(160, 175, 195) if sum(bg[:3]) < 400 else (90, 100, 120),
        )

    img.save(path, "PNG", optimize=True)
    img.convert("RGB").save(path.with_suffix(".jpg"), "JPEG", quality=95)
    print("saved", path)


def make_minimal_letter(
    path: Path,
    bg: tuple,
    text_color: tuple,
    accent: tuple,
    size: int = 1024,
):
    """Single-syllable-feel: big 온해 only, ultra clean."""
    img = Image.new("RGB", (size, size), bg)
    draw = ImageDraw.Draw(img)
    # subtle corner marks for tech feel
    pad = int(size * 0.1)
    L = int(size * 0.06)
    w = max(4, size // 128)
    # top-left
    draw.line([(pad, pad + L), (pad, pad), (pad + L, pad)], fill=accent, width=w)
    # bottom-right
    draw.line(
        [(size - pad - L, size - pad), (size - pad, size - pad), (size - pad, size - pad - L)],
        fill=accent,
        width=w,
    )

    font_main = load_font(int(size * 0.32))
    text = "온해"
    bbox = draw.textbbox((0, 0), text, font=font_main)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size - tw) // 2, (size - th) // 2 - int(size * 0.02)), text, font=font_main, fill=text_color)

    img.save(path, "PNG", optimize=True)
    img.convert("RGB").save(path.with_suffix(".jpg"), "JPEG", quality=95)
    print("saved", path)


def make_card_style(
    path: Path,
    size: int = 1024,
):
    """Professional card: dark left accent, name + role."""
    bg = (18, 24, 38)
    img = Image.new("RGB", (size, size), bg)
    draw = ImageDraw.Draw(img)
    # left accent bar
    bar = int(size * 0.04)
    draw.rectangle([0, 0, bar, size], fill=(37, 99, 235))
    # soft circle watermark
    overlay = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    r = int(size * 0.55)
    od.ellipse(
        [size - r - int(size * 0.05), -int(size * 0.1), size + int(size * 0.15), r],
        fill=(37, 99, 235, 28),
    )
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    font_main = load_font(int(size * 0.22))
    font_sub = load_font(int(size * 0.055))
    font_tiny = load_font(int(size * 0.04))

    name = "온해"
    role = "Excel · 업무 자동화"
    tag = "PYTHON  ·  AUTOMATION"

    # vertical center block shifted slightly left of center for balance
    left = int(size * 0.14)
    y = int(size * 0.36)
    draw.text((left, y), name, font=font_main, fill=(255, 255, 255))
    nb = draw.textbbox((left, y), name, font=font_main)
    y2 = nb[3] + int(size * 0.04)
    draw.rectangle([left, y2, left + int(size * 0.12), y2 + max(5, size // 90)], fill=(56, 189, 248))
    y3 = y2 + int(size * 0.05)
    draw.text((left, y3), role, font=font_sub, fill=(180, 195, 215))
    y4 = y3 + int(size * 0.09)
    draw.text((left, y4), tag, font=font_tiny, fill=(100, 120, 150))

    img.save(path, "PNG", optimize=True)
    img.convert("RGB").save(path.with_suffix(".jpg"), "JPEG", quality=95)
    print("saved", path)


# A: Navy circle badge (most "expert / brand") — recommended
make_circle_badge(
    OUT / "onhae_profile_navy.png",
    bg=(15, 23, 42),
    ring=(37, 99, 235),
    text_color=(255, 255, 255),
    accent=(56, 189, 248),
    subtitle="업무 자동화",
)

# B: Clean white professional
make_circle_badge(
    OUT / "onhae_profile_white.png",
    bg=(248, 250, 252),
    ring=(37, 99, 235),
    text_color=(15, 23, 42),
    accent=(37, 99, 235),
    subtitle="업무 자동화",
)

# C: Minimal mark
make_minimal_letter(
    OUT / "onhae_profile_minimal.png",
    bg=(15, 23, 42),
    text_color=(248, 250, 252),
    accent=(56, 189, 248),
)

# D: Card style (looks more "agency expert")
make_card_style(OUT / "onhae_profile_card.png")

print("done")
for p in sorted(OUT.glob("onhae_profile*")):
    print(p.name, p.stat().st_size)

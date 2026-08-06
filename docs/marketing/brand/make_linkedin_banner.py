"""LinkedIn background banner — CoreLabs / RoadLog professional."""
from __future__ import annotations

import math
import os

from PIL import Image, ImageDraw, ImageFont

# LinkedIn recommended banner size
W, H = 1584, 396

BG = (11, 18, 32)
BG2 = (17, 28, 48)
ACCENT = (0, 163, 255)
ACCENT2 = (56, 189, 248)
WHITE = (248, 250, 252)
MUTED = (148, 163, 184)
SOFT = (30, 48, 72)


def get_font(size: int, bold: bool = True) -> ImageFont.ImageFont:
    candidates = [
        r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\malgunbd.ttf" if bold else r"C:\Windows\Fonts\malgun.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def draw_gradient(draw: ImageDraw.ImageDraw) -> None:
    for x in range(W):
        t = x / max(W - 1, 1)
        # left deep navy → slight blue lift on right
        col = tuple(int(BG[i] * (1 - t * 0.35) + BG2[i] * (t * 0.55) + SOFT[i] * (t * 0.2)) for i in range(3))
        draw.line([(x, 0), (x, H)], fill=col)


def draw_grid(draw: ImageDraw.ImageDraw) -> None:
    """Subtle tech grid on the right half."""
    step = 36
    color = (25, 40, 62)
    for x in range(W // 2, W, step):
        draw.line([(x, 0), (x, H)], fill=color, width=1)
    for y in range(0, H, step):
        draw.line([(W // 2, y), (W, y)], fill=color, width=1)


def draw_hex(draw: ImageDraw.ImageDraw, cx: float, cy: float, r: float, outline, width: int = 2) -> None:
    pts = []
    for i in range(6):
        a = math.radians(-90 + i * 60)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    draw.line(pts + [pts[0]], fill=outline, width=width)


def draw_network(draw: ImageDraw.ImageDraw) -> None:
    """Abstract nodes on right — professional, not busy."""
    nodes = [
        (1180, 90),
        (1320, 70),
        (1450, 120),
        (1260, 200),
        (1400, 230),
        (1500, 180),
        (1210, 300),
        (1360, 320),
        (1480, 290),
    ]
    # edges
    edges = [(0, 1), (1, 2), (0, 3), (1, 3), (2, 4), (3, 4), (4, 5), (3, 6), (4, 7), (5, 8), (6, 7), (7, 8)]
    for a, b in edges:
        draw.line([nodes[a], nodes[b]], fill=(35, 70, 110), width=2)
    for i, (x, y) in enumerate(nodes):
        r = 6 if i % 3 else 8
        draw.ellipse([x - r, y - r, x + r, y + r], fill=ACCENT if i % 4 == 0 else ACCENT2)


def make_banner() -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    draw_gradient(draw)
    draw_grid(draw)

    # Mark sits mid-left, above the LinkedIn avatar overlap zone (bottom-left)
    cx, cy = 220, 168
    for r in range(140, 36, -4):
        t = (r - 36) / 104
        col = (
            int(BG[0] + 2 * (1 - t)),
            int(BG[1] + 18 * (1 - t)),
            int(BG[2] + 36 * (1 - t)),
        )
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)

    draw.ellipse([cx - 72, cy - 72, cx + 72, cy + 72], outline=ACCENT, width=4)
    draw.ellipse([cx - 62, cy - 62, cx + 62, cy + 62], outline=(28, 55, 90), width=2)
    draw_hex(draw, cx, cy, 44, ACCENT2, width=3)
    draw.ellipse([cx - 7, cy - 7, cx + 7, cy + 7], fill=ACCENT)

    draw_network(draw)

    draw_hex(draw, 1490, 200, 120, (22, 45, 70), width=2)
    draw_hex(draw, 1490, 200, 90, (28, 55, 88), width=1)

    # Text block to the right of mark (avatar-safe)
    x0 = 340

    font_brand = get_font(56, bold=True)
    brand = "CoreLabs"
    brand_y = 88
    draw.text((x0, brand_y), brand, font=font_brand, fill=WHITE)

    bb = draw.textbbox((x0, brand_y), brand, font=font_brand)
    brand_bottom = bb[3]
    draw.line([(x0, brand_bottom + 8), (x0 + 128, brand_bottom + 8)], fill=ACCENT, width=4)

    font_sub = get_font(28, bold=False)
    draw.text((x0, brand_bottom + 20), "Technology Studio", font=font_sub, fill=MUTED)

    try:
        font_tag_ko = ImageFont.truetype(r"C:\Windows\Fonts\malgunbd.ttf", 28)
    except OSError:
        font_tag_ko = get_font(28, bold=True)
    tag = "RoadLog  |  AI 운행·외근 일지"
    draw.text((x0, brand_bottom + 64), tag, font=font_tag_ko, fill=ACCENT2)

    font_url = get_font(26, bold=True)
    url = "https://roadlog.co.kr"
    draw.text((x0, brand_bottom + 108), url, font=font_url, fill=MUTED)

    font_r = get_font(22, bold=False)
    right = "Field ops logging  |  Team automation"
    rb = draw.textbbox((0, 0), right, font=font_r)
    rw = rb[2] - rb[0]
    draw.text((W - rw - 48, H - 44), right, font=font_r, fill=(100, 120, 145))

    return img


def main() -> None:
    out_brand = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "corelabs_linkedin_banner.png",
    )
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    # Windows may use OneDrive Desktop
    candidates = [
        desktop,
        os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop"),
        r"C:\Users\hysoo\Desktop",
    ]
    desk = next((p for p in candidates if os.path.isdir(p)), desktop)

    img = make_banner()
    img.save(out_brand, "PNG", optimize=True)

    desk_path = os.path.join(desk, "코어랩스_링크드인_배너.png")
    desk_path_en = os.path.join(desk, "corelabs_linkedin_banner.png")
    img.save(desk_path, "PNG", optimize=True)
    img.save(desk_path_en, "PNG", optimize=True)

    # also into logo folder on desktop if exists
    logo_folder = os.path.join(desk, "CoreLabs_Logo")
    if os.path.isdir(logo_folder):
        img.save(os.path.join(logo_folder, "corelabs_linkedin_banner.png"), "PNG", optimize=True)

    print(out_brand)
    print(desk_path)
    print(desk_path_en)
    print(f"{W}x{H}")


if __name__ == "__main__":
    main()

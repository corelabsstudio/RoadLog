# -*- coding: utf-8 -*-
"""Render simple square promo cards for X (exact Korean text via Pillow)."""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FONT_CANDIDATES = [
    Path(r"C:\Windows\Fonts\malgunbd.ttf"),
    Path(r"C:\Windows\Fonts\malgun.ttf"),
    Path(r"C:\Windows\Fonts\arial.ttf"),
]


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    paths = FONT_CANDIDATES if not bold else [
        Path(r"C:\Windows\Fonts\malgunbd.ttf"),
        *FONT_CANDIDATES,
    ]
    for p in paths:
        if p.is_file():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def wrap(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.ImageFont, max_w: int) -> list[str]:
    lines: list[str] = []
    for para in text.split("\n"):
        if not para:
            lines.append("")
            continue
        cur = ""
        for ch in para:
            test = cur + ch
            if draw.textlength(test, font=fnt) <= max_w:
                cur = test
            else:
                if cur:
                    lines.append(cur)
                cur = ch
        if cur:
            lines.append(cur)
    return lines


def render_card(
    out: Path,
    *,
    brand: str,
    headline: str,
    sub: str,
    footer: str,
    theme: str = "roadlog",
) -> Path:
    w = h = 1080
    img = Image.new("RGB", (w, h), "#030712" if theme == "roadlog" else "#0a0612")
    draw = ImageDraw.Draw(img)

    # accent bar
    if theme == "roadlog":
        draw.rectangle([0, 0, w, 12], fill="#22d3ee")
        accent = "#22d3ee"
        muted = "#94a3b8"
    else:
        draw.rectangle([0, 0, w, 12], fill="#a78bfa")
        accent = "#c4b5fd"
        muted = "#a1a1aa"

    # soft panel
    draw.rounded_rectangle([64, 120, w - 64, h - 160], radius=36, fill="#0f172a" if theme == "roadlog" else "#15101f")

    f_brand = font(36, bold=True)
    f_head = font(64, bold=True)
    f_sub = font(40)
    f_foot = font(32)

    draw.text((96, 160), brand, font=f_brand, fill=accent)

    y = 260
    for line in wrap(draw, headline, f_head, w - 220):
        draw.text((96, y), line, font=f_head, fill="#f8fafc")
        y += 78

    y += 24
    for line in wrap(draw, sub, f_sub, w - 220):
        draw.text((96, y), line, font=f_sub, fill=muted)
        y += 52

    draw.text((96, h - 220), footer, font=f_foot, fill=accent)

    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG", optimize=True)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--brand", required=True)
    ap.add_argument("--headline", required=True)
    ap.add_argument("--sub", default="")
    ap.add_argument("--footer", default="")
    ap.add_argument("--theme", choices=["roadlog", "wakeagain"], default="roadlog")
    args = ap.parse_args()
    path = render_card(
        Path(args.out),
        brand=args.brand,
        headline=args.headline,
        sub=args.sub,
        footer=args.footer,
        theme=args.theme,
    )
    print(path)


if __name__ == "__main__":
    main()

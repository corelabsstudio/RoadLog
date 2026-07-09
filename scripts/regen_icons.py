"""Regenerate PWA/favicon PNGs and ICO from logo.svg design (viewBox 64x64)."""
from pathlib import Path
from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / "web" / "icons"


def lerp(a, b, t):
    return a + (b - a) * t


def cubic(p0, p1, p2, p3, t):
    u = 1 - t
    return (
        u * u * u * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t * t * t * p3[0],
        u * u * u * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t * t * t * p3[1],
    )


def sample_cubic(p0, p1, p2, p3, n=64):
    return [cubic(p0, p1, p2, p3, i / n) for i in range(n + 1)]


def rounded_rect_mask(size, rx):
    m = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=rx, fill=255)
    return m


def gradient_bg(size):
    img = Image.new("RGBA", (size, size))
    px = img.load()
    c0 = (0x67, 0xE8, 0xF9)
    c1 = (0x22, 0xD3, 0xEE)
    c2 = (0x08, 0x91, 0xB2)
    x0, y0, x1, y1 = 6 / 64, 4 / 64, 58 / 64, 60 / 64
    dx, dy = x1 - x0, y1 - y0
    denom = dx * dx + dy * dy
    for y in range(size):
        for x in range(size):
            nx, ny = x / size, y / size
            t = ((nx - x0) * dx + (ny - y0) * dy) / denom
            t = max(0.0, min(1.0, t))
            if t < 0.45:
                u = t / 0.45
                r = int(lerp(c0[0], c1[0], u))
                g = int(lerp(c0[1], c1[1], u))
                b = int(lerp(c0[2], c1[2], u))
            else:
                u = (t - 0.45) / 0.55
                r = int(lerp(c1[0], c2[0], u))
                g = int(lerp(c1[1], c2[1], u))
                b = int(lerp(c1[2], c2[2], u))
            px[x, y] = (r, g, b, 255)
    return img


def s(v, size):
    return v / 64.0 * size


def draw_logo(size: int) -> Image.Image:
    ss = 4
    S = size * ss
    base = gradient_bg(S)

    shine = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shine)
    sd.rounded_rectangle(
        [s(3, S), s(3, S), s(3 + 58, S), s(3 + 28, S)],
        radius=max(1, int(s(13, S))),
        fill=(255, 255, 255, int(255 * 0.12)),
    )
    base = Image.alpha_composite(base, shine)

    draw = ImageDraw.Draw(base)
    ink = (0x04, 0x10, 0x16, 255)
    cyan = (0x67, 0xE8, 0xF9, 255)
    cyan_soft = (0x67, 0xE8, 0xF9, int(255 * 0.85))

    # M13 46 c7.5-15 15.5-22.5 26.5-22.5 4.2 0 7.4 1.6 9.5 4.2
    p0 = (13.0, 46.0)
    p1 = (20.5, 31.0)
    p2 = (28.5, 23.5)
    p3 = (39.5, 23.5)
    q0 = p3
    q1 = (43.7, 23.5)
    q2 = (46.9, 25.1)
    q3 = (49.0, 27.7)
    pts = sample_cubic(p0, p1, p2, p3, 80) + sample_cubic(q0, q1, q2, q3, 40)[1:]
    scaled = [(s(x, S), s(y, S)) for x, y in pts]
    sw = max(1, int(s(4.2, S)))
    draw.line(scaled, fill=ink, width=sw, joint="curve")
    r_cap = sw / 2
    for pt in (scaled[0], scaled[-1]):
        draw.ellipse(
            [pt[0] - r_cap, pt[1] - r_cap, pt[0] + r_cap, pt[1] + r_cap],
            fill=ink,
        )

    cx, cy = s(48.5, S), s(25, S)
    r_out = s(5.2, S)
    r_in = s(2.1, S)
    draw.ellipse([cx - r_out, cy - r_out, cx + r_out, cy + r_out], fill=ink)
    draw.ellipse([cx - r_in, cy - r_in, cx + r_in, cy + r_in], fill=cyan)

    yb = s(46, S)
    x0, x1 = s(13, S), s(13 + 28, S)
    swb = max(1, int(s(3.2, S)))
    road = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    rd = ImageDraw.Draw(road)
    ink_a = (0x04, 0x10, 0x16, int(255 * 0.4))
    rd.line([(x0, yb), (x1, yb)], fill=ink_a, width=swb)
    rcb = swb / 2
    for pt in ((x0, yb), (x1, yb)):
        rd.ellipse([pt[0] - rcb, pt[1] - rcb, pt[0] + rcb, pt[1] + rcb], fill=ink_a)
    base = Image.alpha_composite(base, road)
    draw = ImageDraw.Draw(base)

    for wx in (18, 37):
        cxw, cyw = s(wx, S), s(46, S)
        ro = s(3.6, S)
        ri = s(1.3, S)
        draw.ellipse([cxw - ro, cyw - ro, cxw + ro, cyw + ro], fill=ink)
        draw.ellipse([cxw - ri, cyw - ri, cxw + ri, cyw + ri], fill=cyan_soft)

    mask = rounded_rect_mask(S, max(1, int(s(16, S))))
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    out.paste(base, (0, 0), mask)
    return out.resize((size, size), Image.Resampling.LANCZOS)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, sz in [("icon-192.png", 192), ("icon-512.png", 512), ("logo.png", 256)]:
        im = draw_logo(sz)
        path = OUT / name
        im.save(path, "PNG", optimize=True)
        print("wrote", path, im.size, path.stat().st_size)

    ico_sizes = [16, 32, 48, 64, 128, 256]
    icons = [draw_logo(sz) for sz in ico_sizes]
    ico_path = OUT / "roadlog.ico"
    icons[-1].save(ico_path, format="ICO", sizes=[(sz, sz) for sz in ico_sizes])
    print("wrote", ico_path, ico_path.stat().st_size)
    print("done")


if __name__ == "__main__":
    main()

"""
ReachKit UI theme — Blizzard Battle.net launcher aesthetic.

Dimensional chrome · atmospheric gradients · cyan glow · elevated cards.
Uses Pillow for soft gradients / ambient lighting (not flat solid fills).
"""

from __future__ import annotations

import math
import tkinter as tk
from functools import lru_cache
from pathlib import Path
from tkinter import ttk
from typing import Callable

# --- Battle.net-inspired palette (blue-tinted, not pure black) ---
BG = "#07090f"  # deepest app chrome
BG_DEEP = "#05070c"
BG_SURFACE = "#12151d"  # main cards
BG_RAISED = "#1a1e29"  # elevated
BG_INPUT = "#0b0e15"  # fields
BG_HOVER = "#232836"
BG_HEADER = "#0a0c12"
BG_SIDEBAR = "#090b11"
BG_SIDEBAR_EDGE = "#1a2030"
BG_BOTTOM = "#06080d"
BG_HERO = "#0c1018"
BG_CARD_TOP = "#161b26"  # card header strip
BG_SHADOW = "#020308"
FG = "#e8eaed"
FG_MUTED = "#8b929e"
FG_DIM = "#5a6270"
ACCENT = "#00aeff"
ACCENT_HOVER = "#33c0ff"
ACCENT_PRESS = "#0090d4"
ACCENT_SOFT = "#0a2436"
ACCENT_GLOW = "#0078b4"
ACCENT_DIM = "#004d73"
BORDER = "#2a3140"
BORDER_LIGHT = "#3d4658"  # top/left highlight for bevel
BORDER_FOCUS = "#00aeff"
BORDER_SUBTLE = "#1a1f2a"
SUCCESS = "#00c853"
WARNING = "#f0b429"
DANGER = "#e74c3c"
SELECT_BG = "#0078b4"
SELECT_FG = "#ffffff"
CHIP_BG = "#152636"
CHIP_FG = "#7dd3fc"
GOLD = "#f8b700"

# ---------------------------------------------------------------------------
# 에스코어 드림 (S-Core Dream) — 9 weights as separate Windows families
# Bundled under assets/fonts/SCDream1..9.otf  (register via register_app_fonts)
# 가독성: 본문 Medium, 보조 Regular, 제목 Bold/ExtraBold (Thin/Light 지양)
# ---------------------------------------------------------------------------
_FONT_DIR = Path(__file__).resolve().parent / "assets" / "fonts"
_fonts_registered = False
_fonts_cache: dict[str, tuple] | None = None

# weight index → preferred family name candidates (KO first, EN fallback)
_DREAM_WEIGHTS: dict[int, tuple[str, ...]] = {
    1: ("에스코어 드림 1 Thin", "S-Core Dream 1 Thin"),
    2: ("에스코어 드림 2 ExtraLight", "S-Core Dream 2 ExtraLight"),
    3: ("에스코어 드림 3 Light", "S-Core Dream 3 Light"),
    4: ("에스코어 드림 4 Regular", "S-Core Dream 4 Regular"),
    5: ("에스코어 드림 5 Medium", "S-Core Dream 5 Medium"),
    6: ("에스코어 드림 6 Bold", "S-Core Dream 6 Bold"),
    7: ("에스코어 드림 7 ExtraBold", "S-Core Dream 7 ExtraBold"),
    8: ("에스코어 드림 8 Heavy", "S-Core Dream 8 Heavy"),
    9: ("에스코어 드림 9 Black", "S-Core Dream 9 Black"),
}

# Fallback if Dream not available
_FALLBACK = "Malgun Gothic"


def register_app_fonts() -> int:
    """
    Load bundled SCDream*.otf into this process (private, no system install).
    Call once before apply_theme / any Font usage. Returns count loaded.
    """
    global _fonts_registered, _fonts_cache
    if _fonts_registered:
        return 0
    loaded = 0
    try:
        import ctypes
        from ctypes import wintypes

        FR_PRIVATE = 0x10
        add = ctypes.windll.gdi32.AddFontResourceExW
        add.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.LPVOID]
        add.restype = ctypes.c_int
        if _FONT_DIR.is_dir():
            for path in sorted(_FONT_DIR.glob("SCDream*.otf")):
                try:
                    if add(str(path), FR_PRIVATE, None) > 0:
                        loaded += 1
                except Exception:
                    pass
    except Exception:
        pass
    _fonts_registered = True
    _fonts_cache = None  # rebuild after registration
    return loaded


def _resolve_dream_family(weight: int, families: set[str]) -> str | None:
    for name in _DREAM_WEIGHTS.get(weight, ()):
        if name in families:
            return name
    # partial match (some systems strip spaces / use different spacing)
    needle = f"드림 {weight} "
    for fam in families:
        if needle in fam or f"Dream {weight} " in fam:
            return fam
    return None


def _fonts() -> dict[str, tuple]:
    """
    Role → tk font tuple. Dream weights are separate families — do not use
    synthetic 'bold' style (causes wrong faces).
    """
    global _fonts_cache
    if _fonts_cache is not None:
        return _fonts_cache

    register_app_fonts()

    families: set[str] = set()
    try:
        import tkinter.font as tkfont

        families = set(tkfont.families())
    except Exception:
        pass

    def face(weight: int, size: int) -> tuple:
        fam = _resolve_dream_family(weight, families)
        if fam:
            return (fam, size)
        # fallback with synthetic weight
        if weight >= 6:
            return (_FALLBACK, size, "bold")
        return (_FALLBACK, size)

    # Readability map (dark UI):
    #   sub     → Regular 9   (Light는 다크에서 흐림)
    #   ui      → Medium 10   (본문 라벨 가독성)
    #   bold    → Bold 10     (버튼·강조)
    #   section → Bold 10     (카드 제목)
    #   nav     → Medium 11
    #   nav_bold→ Bold 11
    #   title   → Bold 16
    #   hero    → ExtraBold 20
    #   brand   → ExtraBold 17
    #   mono    → Regular 9   (로그도 동일 패밀리)
    #   body    → Medium 10   (긴 본문)
    #   help    → Medium 11
    cache = {
        "sub": face(4, 9),
        "ui": face(5, 10),
        "body": face(5, 10),
        "bold": face(6, 10),
        "section": face(6, 10),
        "nav": face(5, 11),
        "nav_bold": face(6, 11),
        "title": face(6, 16),
        "brand": face(7, 17),
        "hero": face(7, 20),
        "hero_mark": face(6, 14),
        "help": face(5, 11),
        "help_title": face(6, 12),
        "mono": face(4, 9),
        "list": face(5, 10),
        "list_sm": face(4, 9),
    }
    _fonts_cache = cache
    # public aliases for older constants
    global FONT_UI, FONT_UI_BOLD, FONT_TITLE, FONT_HERO, FONT_SUB
    global FONT_SECTION, FONT_NAV, FONT_NAV_BOLD, FONT_MONO
    FONT_UI = cache["ui"]
    FONT_UI_BOLD = cache["bold"]
    FONT_TITLE = cache["title"]
    FONT_HERO = cache["hero"]
    FONT_SUB = cache["sub"]
    FONT_SECTION = cache["section"]
    FONT_NAV = cache["nav"]
    FONT_NAV_BOLD = cache["nav_bold"]
    FONT_MONO = cache["mono"]
    return cache


def fonts() -> dict[str, tuple]:
    """Public accessor for role-based font tuples."""
    return _fonts()


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _mix(c1: tuple[int, int, int], c2: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return (
        int(_lerp(c1[0], c2[0], t)),
        int(_lerp(c1[1], c2[1], t)),
        int(_lerp(c1[2], c2[2], t)),
    )


def _pil_available() -> bool:
    try:
        from PIL import Image  # noqa: F401

        return True
    except Exception:
        return False


@lru_cache(maxsize=48)
def _ambient_png_bytes(w: int, h: int, kind: str = "stage") -> bytes | None:
    """Render ambient art once; cache PNG bytes (Tk-safe across roots)."""
    if w < 8 or h < 8:
        return None
    w = max(8, min(w, 2400))
    h = max(8, min(h, 1800))
    rw, rh = w, h
    if w * h > 1_600_000:
        scale = math.sqrt(1_600_000 / (w * h))
        rw, rh = max(8, int(w * scale)), max(8, int(h * scale))

    if not _pil_available():
        return None

    import io
    import random

    from PIL import Image, ImageDraw, ImageFilter

    base = _hex_to_rgb(BG)
    deep = _hex_to_rgb(BG_DEEP)
    cyan = _hex_to_rgb(ACCENT)
    navy = (12, 28, 48)
    mid = (14, 18, 30)

    img = Image.new("RGB", (rw, rh), base)
    px = img.load()

    for y in range(rh):
        vy = y / max(1, rh - 1)
        for x in range(rw):
            vx = x / max(1, rw - 1)
            t = 0.35 * vx + 0.45 * vy + 0.15 * (vx * vy)
            c = _mix(mid, deep, t)
            c = _mix(c, navy, 0.18 * (1.0 - vy) * (0.4 + 0.6 * vx))
            px[x, y] = c

    draw = ImageDraw.Draw(img, "RGBA")

    def glow(cx: float, cy: float, radius: float, color: tuple[int, int, int], alpha: int) -> None:
        steps = 18
        for i in range(steps, 0, -1):
            t = i / steps
            r = radius * t
            a = int(alpha * (1.0 - t) ** 1.6)
            if a < 1:
                continue
            box = [cx - r, cy - r, cx + r, cy + r]
            draw.ellipse(box, fill=(*color, a))

    if kind == "stage":
        glow(rw * 0.78, rh * 0.18, max(rw, rh) * 0.55, cyan, 38)
        glow(rw * 0.72, rh * 0.22, max(rw, rh) * 0.32, (0, 120, 200), 45)
        glow(rw * 0.12, rh * 0.55, max(rw, rh) * 0.40, (40, 70, 120), 28)
        for y in range(rh):
            vy = y / max(1, rh - 1)
            if vy < 0.55:
                continue
            fade = (vy - 0.55) / 0.45
            a = int(90 * fade * fade)
            draw.line([(0, y), (rw, y)], fill=(*deep, a))
        for y in range(min(48, rh)):
            a = int(35 * (1.0 - y / 48))
            draw.line([(0, y), (rw, y)], fill=(30, 50, 80, a))
    elif kind == "hero":
        # --- Cinematic AI banner (premium, not neon-kitsch) ---
        # Base: deep navy → near-black vertical wash (already painted); refine pixels
        indigo = (18, 28, 55)
        teal = (0, 140, 170)
        soft_cyan = (80, 190, 230)
        for y in range(rh):
            vy = y / max(1, rh - 1)
            for x in range(rw):
                vx = x / max(1, rw - 1)
                # left readable dark zone, right lit “engine” zone
                c = _mix(deep, indigo, 0.35 + 0.25 * (1.0 - vx) * (1.0 - vy * 0.5))
                c = _mix(c, mid, 0.12 * vy)
                # subtle right-side cool lift
                c = _mix(c, (10, 40, 70), 0.22 * vx * (1.0 - vy * 0.3))
                px[x, y] = c

        # Soft layered orbs (low alpha, large — like stage lighting, not stickers)
        glow(rw * 0.88, rh * 0.42, max(rw, rh) * 0.62, cyan, 28)
        glow(rw * 0.78, rh * 0.20, max(rw, rh) * 0.38, soft_cyan, 18)
        glow(rw * 0.92, rh * 0.70, max(rw, rh) * 0.30, teal, 22)
        glow(rw * 0.08, rh * 0.50, max(rw, rh) * 0.28, indigo, 35)

        # Horizontal light streak (cinematic bar under copy)
        streak_y = int(rh * 0.52)
        for dy in range(-10, 11):
            y = streak_y + dy
            if y < 0 or y >= rh:
                continue
            fall = 1.0 - abs(dy) / 10.0
            a = int(28 * fall * fall)
            draw.line([(int(rw * 0.04), y), (int(rw * 0.62), y)], fill=(*soft_cyan, a))

        # Fine tech grid (AI / neural board feel) — very subtle
        grid = Image.new("RGBA", (rw, rh), (0, 0, 0, 0))
        gdraw = ImageDraw.Draw(grid)
        step = max(18, min(rw, rh) // 14)
        for x in range(0, rw, step):
            gdraw.line([(x, 0), (x, rh)], fill=(120, 180, 220, 10))
        for y in range(0, rh, step):
            gdraw.line([(0, y), (rw, y)], fill=(120, 180, 220, 10))
        # diagonal accent lines on right third
        for i in range(6):
            x0 = int(rw * (0.62 + i * 0.05))
            gdraw.line([(x0, 0), (x0 + int(rh * 0.9), rh)], fill=(0, 180, 255, 8 + i))
        img = Image.alpha_composite(img.convert("RGBA"), grid).convert("RGB")
        draw = ImageDraw.Draw(img, "RGBA")
        px = img.load()

        # Soft node constellation (AI network) on the right
        nodes = [
            (0.72, 0.28),
            (0.80, 0.22),
            (0.86, 0.38),
            (0.78, 0.48),
            (0.90, 0.55),
            (0.74, 0.62),
            (0.84, 0.70),
            (0.93, 0.32),
        ]
        pts = [(int(rw * nx), int(rh * ny)) for nx, ny in nodes]
        for i, (x1, y1) in enumerate(pts):
            for j, (x2, y2) in enumerate(pts):
                if j <= i:
                    continue
                dist = math.hypot(x2 - x1, y2 - y1)
                if dist < max(rw, rh) * 0.22:
                    draw.line([(x1, y1), (x2, y2)], fill=(*cyan, 28), width=1)
        for x, y in pts:
            r = 3
            draw.ellipse([x - r, y - r, x + r, y + r], fill=(*soft_cyan, 160))
            draw.ellipse([x - r * 2, y - r * 2, x + r * 2, y + r * 2], outline=(*cyan, 50))

        # Left vignette for text readability
        for x in range(min(int(rw * 0.55), rw)):
            t = 1.0 - x / max(1, rw * 0.55)
            a = int(110 * (t**1.4))
            draw.line([(x, 0), (x, rh)], fill=(*deep, a))
        # bottom edge soft fade
        for y in range(rh):
            vy = y / max(1, rh - 1)
            if vy < 0.70:
                continue
            fade = (vy - 0.70) / 0.30
            draw.line([(0, y), (rw, y)], fill=(*deep, int(70 * fade)))
    elif kind == "sidebar":
        for x in range(rw):
            vx = x / max(1, rw - 1)
            for y in range(rh):
                vy = y / max(1, rh - 1)
                c = _mix(deep, mid, 0.25 + 0.15 * vy)
                c = _mix(c, navy, 0.12 * (1 - vx))
                dist = math.hypot(x - rw * 0.5, y - rh * 0.08) / max(rw, rh)
                g = max(0.0, 1.0 - dist * 3.2)
                c = _mix(c, cyan, 0.08 * g)
                px[x, y] = c
        for x in range(max(0, rw - 6), rw):
            a = int(40 * ((x - (rw - 6)) / 6))
            draw.line([(x, 0), (x, rh)], fill=(*cyan, a))
    elif kind == "header":
        for y in range(rh):
            vy = y / max(1, rh - 1)
            c = _mix((14, 18, 28), deep, vy)
            for x in range(rw):
                px[x, y] = c
        glow(rw * 0.15, rh * 0.5, rw * 0.25, cyan, 22)
        draw.line([(0, rh - 1), (rw, rh - 1)], fill=(*cyan, 60))

    rnd = random.Random(42)
    grain = Image.new("RGBA", (rw, rh), (0, 0, 0, 0))
    gpx = grain.load()
    for _ in range((rw * rh) // 40):
        x, y = rnd.randint(0, rw - 1), rnd.randint(0, rh - 1)
        v = rnd.randint(0, 18)
        gpx[x, y] = (v, v, v, 18)
    img = Image.alpha_composite(img.convert("RGBA"), grain).convert("RGB")
    img = img.filter(ImageFilter.GaussianBlur(radius=0.4))

    if (rw, rh) != (w, h):
        img = img.resize((w, h), Image.Resampling.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def ambient_photo(
    w: int, h: int, kind: str = "stage", master: tk.Misc | None = None
) -> "tk.PhotoImage | None":
    """Build Tk PhotoImage for ambient art (pass master=widget to avoid cross-root errors)."""
    try:
        data = _ambient_png_bytes(int(w), int(h), kind)
        if not data:
            return None
        # PhotoImage must belong to the live Tk interpreter
        kw = {"data": data}
        if master is not None:
            kw["master"] = master
        return tk.PhotoImage(**kw)
    except Exception:
        return None


class AmbientCanvas(tk.Canvas):
    """Canvas that paints a soft Battle.net-style atmospheric background."""

    def __init__(self, parent, kind: str = "stage", **kwargs):
        kwargs.setdefault("highlightthickness", 0)
        kwargs.setdefault("bd", 0)
        kwargs.setdefault("bg", BG)
        super().__init__(parent, **kwargs)
        self._kind = kind
        self._photo: tk.PhotoImage | None = None
        self._img_id: int | None = None
        self.bind("<Configure>", self._on_configure)

    def _on_configure(self, event=None) -> None:
        w = max(self.winfo_width(), 2)
        h = max(self.winfo_height(), 2)
        if w < 4 or h < 4:
            return
        # snap to reduce cache thrash
        sw = max(8, (w // 32) * 32)
        sh = max(8, (h // 32) * 32)
        photo = ambient_photo(sw, sh, self._kind, master=self)
        if photo is None:
            return
        self._photo = photo
        self.delete("bg")
        self._img_id = self.create_image(0, 0, anchor=tk.NW, image=photo, tags="bg")
        if abs(sw - w) > 8 or abs(sh - h) > 8:
            exact = ambient_photo(w, h, self._kind, master=self)
            if exact is not None:
                self._photo = exact
                self.itemconfigure(self._img_id, image=exact)
        self.tag_lower("bg")


class ElevatedPanel(ttk.Frame):
    """
    Dimensional card: outer shadow → bevel border → surface body.
    Self is the content host (children pack into self); geometry methods
    redirect to the outer shell so existing make_card(...).pack() works.
    """

    def __init__(
        self,
        master,
        title: str = "",
        step: str | None = None,
        *,
        hero: bool = False,
        padding: int = 14,
        **kwargs,
    ):
        # Outer shell sits in master
        self._outer = tk.Frame(master, bg=BG, highlightthickness=0, bd=0)

        # Drop shadow (offset layer)
        shadow = tk.Frame(self._outer, bg=BG_SHADOW, highlightthickness=0)
        shadow.pack(fill=tk.BOTH, expand=True, padx=(2, 0), pady=(2, 0))

        # Outer bevel rim (light top/left via nested frames)
        rim = tk.Frame(shadow, bg=BORDER_LIGHT, highlightthickness=0)
        rim.pack(fill=tk.BOTH, expand=True, padx=(0, 2), pady=(0, 2))

        face = tk.Frame(rim, bg=BORDER, highlightthickness=0)
        face.pack(fill=tk.BOTH, expand=True, padx=(1, 0), pady=(1, 0))

        panel_bg = BG_HERO if hero else BG_SURFACE
        panel = tk.Frame(face, bg=panel_bg, highlightthickness=0)
        panel.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        # Top accent hairline (cyan glow strip)
        accent_h = 2 if hero else 1
        tk.Frame(panel, bg=ACCENT if hero else ACCENT_DIM, height=accent_h).pack(fill=tk.X)

        # Title bar
        if title or step:
            title_bg = BG_HERO if hero else BG_CARD_TOP
            tbar = tk.Frame(panel, bg=title_bg, highlightthickness=0)
            tbar.pack(fill=tk.X)
            # left cyan indicator bar
            tk.Frame(tbar, bg=ACCENT, width=3).pack(side=tk.LEFT, fill=tk.Y)
            tinner = tk.Frame(tbar, bg=title_bg)
            tinner.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=12, pady=8)
            fonts = _fonts()
            if step:
                tk.Label(
                    tinner,
                    text=step,
                    bg=ACCENT_SOFT,
                    fg=ACCENT,
                    font=fonts["bold"],
                    padx=8,
                    pady=1,
                ).pack(side=tk.LEFT, padx=(0, 10))
            tk.Label(
                tinner,
                text=title,
                bg=title_bg,
                fg=ACCENT if not hero else FG,
                font=fonts["section"] if not hero else fonts["sub"],
            ).pack(side=tk.LEFT)
            if hero:
                tk.Label(
                    tinner,
                    text="추천",
                    bg=title_bg,
                    fg=GOLD,
                    font=fonts["sub"],
                ).pack(side=tk.RIGHT, padx=4)
            # bottom separator under title
            tk.Frame(panel, bg=BORDER_SUBTLE, height=1).pack(fill=tk.X)

        # Content host (ttk for theme styles)
        content_wrap = tk.Frame(panel, bg=panel_bg, highlightthickness=0)
        content_wrap.pack(fill=tk.BOTH, expand=True)

        # Hero: cinematic AI banner + solid body for controls
        self._hero_canvas: tk.Canvas | None = None
        self._hero_photo: tk.PhotoImage | None = None
        if hero:
            self._hero_canvas = tk.Canvas(
                content_wrap,
                bg=panel_bg,
                highlightthickness=0,
                bd=0,
                height=148,
            )
            self._hero_canvas.pack(fill=tk.X)

            def _hero_cfg(_e=None) -> None:
                if self._hero_canvas is None:
                    return
                cw = max(self._hero_canvas.winfo_width(), 2)
                ch = max(self._hero_canvas.winfo_height(), 2)
                photo = ambient_photo(
                    max(cw, 64), max(ch, 64), "hero", master=self._hero_canvas
                )
                if photo is None:
                    return
                self._hero_photo = photo
                self._hero_canvas.delete("hbg")
                self._hero_canvas.create_image(0, 0, anchor=tk.NW, image=photo, tags="hbg")
                self._hero_canvas.delete("hcopy")
                fonts = _fonts()
                # AI pill badge
                badge_x, badge_y = 28, max(14, ch // 2 - 42)
                self._hero_canvas.create_rectangle(
                    badge_x,
                    badge_y,
                    badge_x + 118,
                    badge_y + 22,
                    fill="#0a2436",
                    outline=ACCENT,
                    width=1,
                    tags="hcopy",
                )
                self._hero_canvas.create_text(
                    badge_x + 10,
                    badge_y + 11,
                    anchor=tk.W,
                    text="✦  인공지능 탑재",
                    fill=ACCENT,
                    font=fonts["bold"],
                    tags="hcopy",
                )
                # headline
                self._hero_canvas.create_text(
                    28,
                    ch // 2 + 2,
                    anchor=tk.W,
                    text="인공지능으로 분석하고 · 쓰고 · 도달하세요",
                    fill=FG,
                    font=fonts["hero"],
                    tags="hcopy",
                )
                self._hero_canvas.create_text(
                    28,
                    ch // 2 + 32,
                    anchor=tk.W,
                    text="사이트 분석 · 홍보 글 만들기 · 글 쓰는 칸 찾기까지 도와줍니다",
                    fill=FG_MUTED,
                    font=fonts["sub"],
                    tags="hcopy",
                )
                # 우측 인공지능 엔진 카드
                rx = cw - 128
                ry = ch // 2 - 30
                self._hero_canvas.create_rectangle(
                    rx,
                    ry,
                    rx + 108,
                    ry + 60,
                    fill="#0a121c",
                    outline="#1a4a66",
                    width=1,
                    tags="hcopy",
                )
                self._hero_canvas.create_text(
                    rx + 54,
                    ry + 20,
                    text="인공지능 엔진",
                    fill=ACCENT,
                    font=fonts["bold"],
                    tags="hcopy",
                )
                self._hero_canvas.create_text(
                    rx + 54,
                    ry + 40,
                    text="분석 · 문구 작성",
                    fill=FG_MUTED,
                    font=fonts["sub"],
                    tags="hcopy",
                )

            self._hero_canvas.bind("<Configure>", _hero_cfg)
            tk.Frame(content_wrap, bg=BORDER_SUBTLE, height=1).pack(fill=tk.X)
            body_parent = content_wrap
            body_style = "Hero.TFrame"
        else:
            body_parent = content_wrap
            body_style = "Card.TFrame"

        super().__init__(body_parent, style=body_style, padding=padding)
        super().pack(fill=tk.BOTH, expand=True, padx=4 if hero else 2, pady=4 if hero else 2)

        self._hero = hero
        self._panel_bg = panel_bg

    # Geometry redirects → outer shell
    def pack(self, **kw):
        return self._outer.pack(**kw)

    def grid(self, **kw):
        return self._outer.grid(**kw)

    def place(self, **kw):
        return self._outer.place(**kw)

    def pack_forget(self):
        return self._outer.pack_forget()

    def grid_forget(self):
        return self._outer.grid_forget()

    def destroy(self):
        try:
            self._outer.destroy()
        except Exception:
            pass
        try:
            super().destroy()
        except Exception:
            pass


def make_card(parent: ttk.Frame, title: str, step: str | None = None) -> ElevatedPanel:
    return ElevatedPanel(parent, title=title, step=step, hero=False, padding=14)


def make_hero(parent: ttk.Frame, title: str = "추천") -> ElevatedPanel:
    """추천 배너 — 앰비언트 글로우 아트."""
    return ElevatedPanel(parent, title=title, step=None, hero=True, padding=20)


def apply_theme(root: tk.Tk) -> ttk.Style:
    register_app_fonts()
    fonts = _fonts()
    root.configure(bg=BG)
    try:
        # Global default → 에스코어 드림 Medium
        fam, sz = fonts["ui"][0], fonts["ui"][1]
        root.option_add("*Font", f"{{{fam}}} {sz}")
        root.option_add("*TCombobox*Listbox.font", fonts["ui"])
        root.option_add("*Text.font", fonts["body"])
        root.option_add("*Listbox.font", fonts["list"])
    except Exception:
        pass

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    style.configure(
        ".",
        background=BG,
        foreground=FG,
        fieldbackground=BG_INPUT,
        bordercolor=BORDER,
        troughcolor=BG,
        focuscolor=BORDER_FOCUS,
    )
    style.configure("TFrame", background=BG_SURFACE)
    style.configure("App.TFrame", background=BG)
    style.configure("Surface.TFrame", background=BG_SURFACE)
    style.configure("Header.TFrame", background=BG_HEADER)
    style.configure("Card.TFrame", background=BG_SURFACE)
    style.configure("Hero.TFrame", background=BG_HERO)
    style.configure("Bottom.TFrame", background=BG_BOTTOM)
    style.configure("Raised.TFrame", background=BG_RAISED)

    style.configure("TLabel", background=BG_SURFACE, foreground=FG, font=fonts["ui"])
    style.configure("App.TLabel", background=BG, foreground=FG, font=fonts["ui"])
    style.configure("Surface.TLabel", background=BG_SURFACE, foreground=FG, font=fonts["ui"])
    style.configure("Header.TLabel", background=BG_HEADER, foreground=FG, font=fonts["ui"])
    style.configure("Muted.TLabel", background=BG, foreground=FG_MUTED, font=fonts["sub"])
    style.configure(
        "SurfaceMuted.TLabel", background=BG_SURFACE, foreground=FG_MUTED, font=fonts["sub"]
    )
    style.configure(
        "HeaderMuted.TLabel", background=BG_HEADER, foreground=FG_MUTED, font=fonts["sub"]
    )
    style.configure("Title.TLabel", background=BG_HEADER, foreground=FG, font=fonts["title"])
    style.configure("Brand.TLabel", background=BG_HEADER, foreground=ACCENT, font=fonts["brand"])
    style.configure(
        "HeroTitle.TLabel",
        background=BG_HERO,
        foreground=FG,
        font=fonts["hero"],
    )
    style.configure(
        "HeroSub.TLabel",
        background=BG_HERO,
        foreground=FG_MUTED,
        font=fonts["ui"],
    )
    style.configure(
        "HeroMuted.TLabel",
        background=BG_HERO,
        foreground=FG_DIM,
        font=fonts["sub"],
    )
    style.configure(
        "Section.TLabel",
        background=BG_SURFACE,
        foreground=ACCENT,
        font=fonts["section"],
    )
    style.configure(
        "Step.TLabel",
        background=ACCENT_SOFT,
        foreground=ACCENT,
        font=fonts["bold"],
        padding=(8, 2),
    )
    style.configure(
        "Chip.TLabel",
        background=CHIP_BG,
        foreground=CHIP_FG,
        font=fonts["sub"],
        padding=(8, 3),
    )
    style.configure(
        "Stat.TLabel",
        background=BG_HEADER,
        foreground=SUCCESS,
        font=fonts["sub"],
    )
    style.configure(
        "Bottom.TLabel",
        background=BG_BOTTOM,
        foreground=FG_MUTED,
        font=fonts["sub"],
    )
    style.configure(
        "BottomBrand.TLabel",
        background=BG_BOTTOM,
        foreground=ACCENT,
        font=fonts["bold"],
    )
    style.configure(
        "Footer.TLabel",
        background=BG_SURFACE,
        foreground=FG_DIM,
        font=fonts["sub"],
    )
    style.configure(
        "Gold.TLabel",
        background=BG_SURFACE,
        foreground=GOLD,
        font=fonts["sub"],
    )

    style.configure(
        "Card.TLabelframe",
        background=BG_SURFACE,
        foreground=FG,
        bordercolor=BORDER,
        relief="solid",
        borderwidth=1,
        padding=14,
    )
    style.configure(
        "Card.TLabelframe.Label",
        background=BG_SURFACE,
        foreground=ACCENT,
        font=fonts["section"],
    )
    style.configure(
        "TLabelframe",
        background=BG_SURFACE,
        foreground=FG,
        bordercolor=BORDER,
        relief="solid",
        borderwidth=1,
    )
    style.configure(
        "TLabelframe.Label",
        background=BG_SURFACE,
        foreground=ACCENT,
        font=fonts["section"],
    )
    style.configure(
        "Hero.TLabelframe",
        background=BG_HERO,
        foreground=FG,
        bordercolor=BORDER_SUBTLE,
        relief="solid",
        borderwidth=1,
        padding=18,
    )
    style.configure(
        "Hero.TLabelframe.Label",
        background=BG_HERO,
        foreground=ACCENT,
        font=fonts["section"],
    )
    style.configure(
        "Bottom.TLabelframe",
        background=BG_BOTTOM,
        foreground=FG_MUTED,
        bordercolor=BORDER_SUBTLE,
        relief="solid",
        borderwidth=1,
        padding=8,
    )
    style.configure(
        "Bottom.TLabelframe.Label",
        background=BG_BOTTOM,
        foreground=ACCENT,
        font=fonts["sub"],
    )

    style.configure(
        "TEntry",
        fieldbackground=BG_INPUT,
        foreground=FG,
        insertcolor=ACCENT,
        bordercolor=BORDER,
        lightcolor=BORDER,
        darkcolor=BORDER,
        padding=8,
        font=fonts["ui"],
    )
    style.map(
        "TEntry",
        fieldbackground=[("readonly", BG_RAISED), ("disabled", BG_RAISED), ("focus", BG_INPUT)],
        bordercolor=[("focus", BORDER_FOCUS)],
        lightcolor=[("focus", BORDER_FOCUS)],
        darkcolor=[("focus", BORDER_FOCUS)],
        foreground=[("disabled", FG_DIM)],
    )

    style.configure(
        "TCombobox",
        fieldbackground=BG_INPUT,
        background=BG_RAISED,
        foreground=FG,
        arrowcolor=ACCENT,
        bordercolor=BORDER,
        lightcolor=BORDER,
        darkcolor=BORDER,
        padding=6,
        font=fonts["ui"],
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", BG_INPUT)],
        selectbackground=[("readonly", SELECT_BG)],
        selectforeground=[("readonly", SELECT_FG)],
        foreground=[("readonly", FG)],
        bordercolor=[("focus", BORDER_FOCUS)],
        arrowcolor=[("active", ACCENT_HOVER)],
    )
    root.option_add("*TCombobox*Listbox.background", BG_INPUT)
    root.option_add("*TCombobox*Listbox.foreground", FG)
    root.option_add("*TCombobox*Listbox.selectBackground", SELECT_BG)
    root.option_add("*TCombobox*Listbox.selectForeground", SELECT_FG)
    root.option_add("*TCombobox*Listbox.font", fonts["ui"])

    style.configure(
        "TCheckbutton",
        background=BG_SURFACE,
        foreground=FG,
        focuscolor=BG_SURFACE,
        indicatorcolor=BG_INPUT,
        padding=4,
        font=fonts["sub"],
    )
    style.map(
        "TCheckbutton",
        background=[("active", BG_SURFACE)],
        foreground=[("active", FG)],
        indicatorcolor=[("selected", ACCENT), ("!selected", BG_INPUT)],
    )

    style.configure(
        "TButton",
        background=BG_RAISED,
        foreground=FG,
        bordercolor=BORDER,
        focuscolor=BG_HOVER,
        lightcolor=BORDER_LIGHT,
        darkcolor=BG_SHADOW,
        padding=(14, 9),
        font=fonts["ui"],
    )
    style.map(
        "TButton",
        background=[("active", BG_HOVER), ("disabled", BG_SURFACE), ("pressed", BG_HOVER)],
        foreground=[("disabled", FG_DIM)],
        bordercolor=[("active", ACCENT_GLOW)],
    )

    # Primary Play button — bright cyan with hard edge
    style.configure(
        "Accent.TButton",
        background=ACCENT,
        foreground="#041018",
        bordercolor=ACCENT_HOVER,
        focuscolor=ACCENT_HOVER,
        lightcolor=ACCENT_HOVER,
        darkcolor=ACCENT_PRESS,
        padding=(20, 12),
        font=fonts["bold"],
    )
    style.map(
        "Accent.TButton",
        background=[("active", ACCENT_HOVER), ("disabled", BG_HOVER), ("pressed", ACCENT_PRESS)],
        foreground=[("disabled", FG_DIM), ("!disabled", "#041018")],
        bordercolor=[("active", "#66d4ff")],
    )

    style.configure(
        "Ghost.TButton",
        background=BG_HEADER,
        foreground=FG_MUTED,
        bordercolor=BORDER,
        lightcolor=BORDER_LIGHT,
        darkcolor=BG_HEADER,
        padding=(12, 8),
        font=fonts["sub"],
    )
    style.map(
        "Ghost.TButton",
        background=[("active", BG_RAISED)],
        foreground=[("active", ACCENT)],
        bordercolor=[("active", ACCENT_GLOW)],
    )
    style.configure(
        "Secondary.TButton",
        background=BG_RAISED,
        foreground=FG,
        bordercolor=BORDER,
        lightcolor=BORDER_LIGHT,
        darkcolor=BG_SHADOW,
        padding=(12, 9),
        font=fonts["ui"],
    )
    style.map(
        "Secondary.TButton",
        background=[("active", BG_HOVER)],
        bordercolor=[("active", ACCENT_GLOW)],
        foreground=[("active", FG)],
    )
    style.configure(
        "Header.TButton",
        background=BG_HEADER,
        foreground=FG_MUTED,
        bordercolor=BG_HEADER,
        lightcolor=BG_HEADER,
        darkcolor=BG_HEADER,
        focuscolor=BG_RAISED,
        padding=(12, 7),
        font=fonts["sub"],
    )
    style.map(
        "Header.TButton",
        background=[("active", BG_RAISED), ("pressed", BG_RAISED)],
        foreground=[("active", ACCENT)],
    )

    style.configure("Sidebar.TFrame", background=BG_SIDEBAR)
    style.configure(
        "Nav.TButton",
        background=BG_SIDEBAR,
        foreground=FG_MUTED,
        bordercolor=BG_SIDEBAR,
        lightcolor=BG_SIDEBAR,
        darkcolor=BG_SIDEBAR,
        focuscolor=BG_RAISED,
        padding=(16, 14),
        font=fonts["nav"],
        anchor="w",
    )
    style.map(
        "Nav.TButton",
        background=[("active", BG_RAISED), ("pressed", BG_RAISED)],
        foreground=[("active", FG)],
    )
    style.configure(
        "NavActive.TButton",
        background=ACCENT_SOFT,
        foreground=ACCENT,
        bordercolor=ACCENT,
        lightcolor=ACCENT_SOFT,
        darkcolor=ACCENT_SOFT,
        focuscolor=ACCENT_SOFT,
        padding=(16, 14),
        font=fonts["nav_bold"],
        anchor="w",
    )
    style.map(
        "NavActive.TButton",
        background=[("active", ACCENT_SOFT), ("pressed", ACCENT_SOFT)],
        foreground=[("active", ACCENT_HOVER)],
    )
    style.configure(
        "SidebarMuted.TLabel",
        background=BG_SIDEBAR,
        foreground=FG_DIM,
        font=fonts["sub"],
    )
    style.configure(
        "SidebarBrand.TLabel",
        background=BG_SIDEBAR,
        foreground=ACCENT,
        font=fonts["section"],
    )
    style.configure(
        "SidebarTitle.TLabel",
        background=BG_SIDEBAR,
        foreground=FG,
        font=fonts["bold"],
    )
    style.configure(
        "SidebarSection.TLabel",
        background=BG_SIDEBAR,
        foreground=FG_DIM,
        font=fonts["sub"],
    )

    style.configure(
        "TScrollbar",
        background=BG_RAISED,
        troughcolor=BG,
        bordercolor=BG,
        arrowcolor=FG_MUTED,
    )
    style.map("TScrollbar", background=[("active", BG_HOVER)], arrowcolor=[("active", ACCENT)])
    style.configure("TSeparator", background=BORDER)

    return style


def style_text_widget(widget: tk.Text) -> None:
    fonts = _fonts()
    widget.configure(
        bg=BG_INPUT,
        fg=FG,
        insertbackground=ACCENT,
        selectbackground=SELECT_BG,
        selectforeground=SELECT_FG,
        relief=tk.FLAT,
        borderwidth=0,
        highlightthickness=1,
        highlightbackground=BORDER,
        highlightcolor=BORDER_FOCUS,
        padx=10,
        pady=10,
        font=fonts["body"],
    )


def style_listbox(widget: tk.Listbox) -> None:
    fonts = _fonts()
    widget.configure(
        bg=BG_INPUT,
        fg=FG,
        selectbackground=SELECT_BG,
        selectforeground=SELECT_FG,
        relief=tk.FLAT,
        borderwidth=0,
        highlightthickness=1,
        highlightbackground=BORDER,
        highlightcolor=BORDER_FOCUS,
        activestyle="none",
        font=fonts["list"],
    )


def style_log_widget(widget: tk.Text) -> None:
    fonts = _fonts()
    widget.configure(
        bg="#04060a",
        fg=SUCCESS,
        insertbackground=SUCCESS,
        selectbackground=SELECT_BG,
        selectforeground=SELECT_FG,
        relief=tk.FLAT,
        borderwidth=0,
        highlightthickness=1,
        highlightbackground=BORDER_SUBTLE,
        highlightcolor=ACCENT,
        padx=10,
        pady=8,
        font=fonts["mono"],
    )


def paint_frame_ambient(frame: tk.Misc, kind: str = "stage") -> Callable[[], None]:
    """
    Attach a background label that repaints ambient art on resize.
    Returns a no-op cleanup for API symmetry.
    """

    host = frame
    bg_label = tk.Label(host, bg=BG, bd=0, highlightthickness=0)
    bg_label.place(x=0, y=0, relwidth=1, relheight=1)
    try:
        bg_label.lower()
    except Exception:
        pass

    state: dict = {"photo": None, "w": 0, "h": 0}

    def repaint(_e=None) -> None:
        try:
            w = max(host.winfo_width(), 2)
            h = max(host.winfo_height(), 2)
        except Exception:
            return
        if w < 16 or h < 16:
            return
        # debounce identical sizes
        sw, sh = (w // 24) * 24, (h // 24) * 24
        if sw == state["w"] and sh == state["h"] and state["photo"] is not None:
            return
        photo = ambient_photo(max(sw, 64), max(sh, 64), kind, master=host)
        if photo is None:
            return
        state["photo"] = photo
        state["w"], state["h"] = sw, sh
        try:
            bg_label.configure(image=photo)
            bg_label.image = photo  # type: ignore[attr-defined]
        except tk.TclError:
            return
        try:
            bg_label.lower()
        except Exception:
            pass

    host.bind("<Configure>", repaint)
    # initial
    try:
        host.after(50, repaint)
    except Exception:
        pass

    return lambda: None

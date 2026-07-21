"""
리치킷 스타일 팝업 · 다이얼로그

Windows 기본 messagebox 대신, 메인 앱과 같은 다크·시안 테마 창을 사용합니다.
모든 알림/확인/입력 창은 내용에 맞춰 크기를 맞추고, 글·버튼이 잘리지 않게 배치합니다.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import scrolledtext, ttk
from typing import Literal

from product_config import ICON_ICO, PRODUCT_DISPLAY_NAME
from ui_theme import (
    ACCENT,
    BG,
    BG_HEADER,
    BORDER,
    DANGER,
    FG,
    FG_MUTED,
    SUCCESS,
    WARNING,
    fonts as theme_fonts,
    paint_frame_ambient,
    style_text_widget,
)

Kind = Literal["info", "warn", "error", "success", "confirm"]

_KIND_META: dict[str, tuple[str, str]] = {
    "info": ("안내", ACCENT),
    "warn": ("주의", WARNING),
    "error": ("오류", DANGER),
    "success": ("완료", SUCCESS),
    "confirm": ("확인", ACCENT),
}

# 본문 배경과 맞는 라벨 스타일 (Surface 는 카드용 — 팝업 App.TFrame 과 어긋남)
_LABEL_STYLE = "App.TLabel"
_MUTED_STYLE = "Muted.TLabel"


def _font_bold() -> tuple:
    try:
        return theme_fonts().get("bold", ("Malgun Gothic", 11, "bold"))
    except Exception:
        return ("Malgun Gothic", 11, "bold")


def _font_sub() -> tuple:
    try:
        return theme_fonts().get("sub", ("Malgun Gothic", 10))
    except Exception:
        return ("Malgun Gothic", 10)


def _font_ui() -> tuple:
    try:
        return theme_fonts().get("ui", ("Malgun Gothic", 11))
    except Exception:
        return ("Malgun Gothic", 11)


def _apply_icon(win: tk.Toplevel | tk.Tk) -> None:
    try:
        if ICON_ICO.is_file():
            win.iconbitmap(default=str(ICON_ICO))
            win.iconbitmap(str(ICON_ICO))
    except Exception:
        pass


def _lift(win: tk.Toplevel) -> None:
    try:
        win.lift()
        win.focus_force()
        win.attributes("-topmost", True)
        win.after(80, lambda: win.attributes("-topmost", False))
    except Exception:
        pass


def style_window(
    win: tk.Toplevel,
    parent: tk.Misc | None,
    *,
    title: str,
    geometry: str = "520x360",
    modal: bool = True,
    minsize: tuple[int, int] | None = (420, 260),
    ambient: bool = False,
) -> ttk.Frame:
    """
    팝업 창에 앱 테마를 입히고, 본문용 Frame을 반환합니다.
    ambient 기본 False — 작은 창에서 배경 이미지가 레이아웃/글자를 가리는 문제 방지.
    """
    win.title(f"{PRODUCT_DISPLAY_NAME} · {title}")
    win.geometry(geometry)
    win.configure(bg=BG)
    try:
        win.resizable(True, True)
    except Exception:
        pass
    if minsize:
        win.minsize(*minsize)
    if parent is not None:
        try:
            win.transient(parent)
        except Exception:
            pass
    _apply_icon(win)
    if modal:
        try:
            win.grab_set()
        except Exception:
            pass

    shell = tk.Frame(win, bg=BG, highlightthickness=0)
    shell.pack(fill=tk.BOTH, expand=True)
    if ambient:
        try:
            paint_frame_ambient(shell, "stage")
        except Exception:
            pass

    tk.Frame(shell, bg=ACCENT, height=2).pack(fill=tk.X)
    tk.Frame(shell, bg="#004d73", height=1).pack(fill=tk.X)

    header = tk.Frame(shell, bg=BG_HEADER, height=48)
    header.pack(fill=tk.X)
    header.pack_propagate(False)
    bold, sub = _font_bold(), _font_sub()
    tk.Label(header, text="◆", bg=BG_HEADER, fg=ACCENT, font=bold).pack(
        side=tk.LEFT, padx=(14, 6), pady=12
    )
    tk.Label(header, text=PRODUCT_DISPLAY_NAME, bg=BG_HEADER, fg=FG, font=bold).pack(
        side=tk.LEFT, pady=12
    )
    tk.Label(
        header,
        text=f"  ·  {title}",
        bg=BG_HEADER,
        fg=FG_MUTED,
        font=sub,
        anchor=tk.W,
    ).pack(side=tk.LEFT, fill=tk.X, expand=True, pady=12, padx=(0, 12))

    tk.Frame(shell, bg=BORDER, height=1).pack(fill=tk.X)

    body = ttk.Frame(shell, style="App.TFrame", padding=(20, 16))
    body.pack(fill=tk.BOTH, expand=True)
    return body


def _center_on_parent(win: tk.Toplevel, parent: tk.Misc | None) -> None:
    win.update_idletasks()
    try:
        ww = max(win.winfo_width(), win.winfo_reqwidth(), 320)
        wh = max(win.winfo_height(), win.winfo_reqheight(), 200)
        if parent is not None:
            try:
                if parent.winfo_viewable():
                    px = parent.winfo_rootx()
                    py = parent.winfo_rooty()
                    pw = max(parent.winfo_width(), 200)
                    ph = max(parent.winfo_height(), 200)
                    x = px + max(0, (pw - ww) // 2)
                    y = py + max(0, (ph - wh) // 2)
                    # 크기 유지 + 위치만 (WxH+X+Y)
                    win.geometry(f"{ww}x{wh}+{x}+{y}")
                    return
            except Exception:
                pass
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        x = max(0, (sw - ww) // 2)
        y = max(0, (sh - wh) // 2)
        win.geometry(f"{ww}x{wh}+{x}+{y}")
    except Exception:
        pass


def _fit_window(
    win: tk.Toplevel,
    *,
    min_w: int = 400,
    min_h: int = 240,
    max_w: int = 720,
    max_h: int = 640,
    pad: int = 24,
) -> None:
    """내용이 잘리지 않게 창 크기를 키웁니다. (이미 큰 창은 줄이지 않음)"""
    win.update_idletasks()
    try:
        req_w = win.winfo_reqwidth() + pad
        req_h = win.winfo_reqheight() + pad
        cur_w = win.winfo_width()
        cur_h = win.winfo_height()
        if cur_w < 2:
            cur_w = 0
        if cur_h < 2:
            cur_h = 0
        # 줄이지 않고 필요한 만큼만 확대
        w = min(max_w, max(min_w, req_w, cur_w))
        h = min(max_h, max(min_h, req_h, cur_h))
        win.geometry(f"{w}x{h}")
        win.update_idletasks()
    except Exception:
        pass


def _message_text_height(message: str) -> int:
    """ScrolledText 줄 수 (너무 작지 않게)."""
    n = message.count("\n") + 1
    # 긴 한 줄도 감안
    n += max(0, len(message) // 42)
    return max(5, min(16, n + 1))


def _est_window_height(text_lines: int, *, base: int = 200) -> int:
    """헤더+배지+버튼+여백 + 텍스트 줄."""
    # header 50 + padding 40 + badge 36 + buttons 50 + text ~20px/line
    return min(640, max(280, base + text_lines * 22))


def show_message(
    parent: tk.Misc | None,
    title: str,
    message: str,
    *,
    kind: Kind = "info",
    ok_text: str = "확인",
    width: int = 500,
) -> None:
    """정보 / 경고 / 오류 / 성공 알림."""
    root = parent.winfo_toplevel() if parent is not None else None
    win = tk.Toplevel(root)
    kind_label, kind_color = _KIND_META.get(kind, _KIND_META["info"])
    message = (message or "").strip() or "(내용 없음)"

    lines = _message_text_height(message)
    h = _est_window_height(lines)
    body = style_window(
        win,
        root,
        title=title or "안내",
        geometry=f"{width}x{h}",
        modal=True,
        minsize=(400, 280),
        ambient=False,
    )

    # 버튼 먼저 하단에 고정
    bf = ttk.Frame(body, style="App.TFrame")
    bf.pack(side=tk.BOTTOM, fill=tk.X, pady=(12, 0))

    def close() -> None:
        try:
            win.grab_release()
        except Exception:
            pass
        win.destroy()

    btn = ttk.Button(bf, text=ok_text, style="Accent.TButton", command=close)
    btn.pack(side=tk.RIGHT)

    # 배지
    badge_row = ttk.Frame(body, style="App.TFrame")
    badge_row.pack(fill=tk.X, pady=(0, 10))
    fg_badge = "#ffffff" if kind == "error" else "#061018"
    tk.Label(
        badge_row,
        text=f"  {kind_label}  ",
        bg=kind_color,
        fg=fg_badge,
        font=_font_bold(),
    ).pack(side=tk.LEFT)

    # 본문 — 읽기 전용 텍스트 (한글·줄바꿈 안정)
    txt = scrolledtext.ScrolledText(
        body,
        wrap=tk.WORD,
        height=lines,
        width=52,
        font=_font_ui(),
    )
    style_text_widget(txt)
    txt.pack(fill=tk.BOTH, expand=True)
    txt.insert("1.0", message)
    txt.configure(state=tk.DISABLED)

    win.bind("<Return>", lambda _e: close())
    win.bind("<Escape>", lambda _e: close())
    win.protocol("WM_DELETE_WINDOW", close)
    _fit_window(win, min_w=width, min_h=280, max_w=720, max_h=640)
    _center_on_parent(win, root)
    _lift(win)
    try:
        btn.focus_set()
    except Exception:
        pass
    win.wait_window()


def ask_confirm(
    parent: tk.Misc | None,
    title: str,
    message: str,
    *,
    ok_text: str = "계속",
    cancel_text: str = "취소",
    kind: Kind = "confirm",
    width: int = 520,
) -> bool:
    """확인/취소. True = 확인."""
    root = parent.winfo_toplevel() if parent is not None else None
    win = tk.Toplevel(root)
    result = {"ok": False}
    kind_label, kind_color = _KIND_META.get(kind, _KIND_META["confirm"])
    message = (message or "").strip() or "(내용 없음)"

    lines = _message_text_height(message)
    h = _est_window_height(lines, base=210)
    body = style_window(
        win,
        root,
        title=title or "확인",
        geometry=f"{width}x{h}",
        modal=True,
        minsize=(420, 300),
        ambient=False,
    )

    bf = ttk.Frame(body, style="App.TFrame")
    bf.pack(side=tk.BOTTOM, fill=tk.X, pady=(12, 0))

    def accept() -> None:
        result["ok"] = True
        try:
            win.grab_release()
        except Exception:
            pass
        win.destroy()

    def cancel() -> None:
        result["ok"] = False
        try:
            win.grab_release()
        except Exception:
            pass
        win.destroy()

    ttk.Button(bf, text=ok_text, style="Accent.TButton", command=accept).pack(side=tk.RIGHT)
    ttk.Button(bf, text=cancel_text, style="Ghost.TButton", command=cancel).pack(
        side=tk.RIGHT, padx=8
    )

    badge_row = ttk.Frame(body, style="App.TFrame")
    badge_row.pack(fill=tk.X, pady=(0, 10))
    tk.Label(
        badge_row,
        text=f"  {kind_label}  ",
        bg=kind_color,
        fg="#061018",
        font=_font_bold(),
    ).pack(side=tk.LEFT)

    txt = scrolledtext.ScrolledText(
        body,
        wrap=tk.WORD,
        height=lines,
        width=54,
        font=_font_ui(),
    )
    style_text_widget(txt)
    txt.pack(fill=tk.BOTH, expand=True)
    txt.insert("1.0", message)
    txt.configure(state=tk.DISABLED)

    win.bind("<Return>", lambda _e: accept())
    win.bind("<Escape>", lambda _e: cancel())
    win.protocol("WM_DELETE_WINDOW", cancel)
    _fit_window(win, min_w=width, min_h=300, max_w=740, max_h=660)
    _center_on_parent(win, root)
    _lift(win)
    win.wait_window()
    return bool(result["ok"])


def ask_text(
    parent: tk.Misc | None,
    title: str,
    prompt: str,
    *,
    ok_text: str = "저장",
    cancel_text: str = "취소",
    width: int = 500,
) -> str | None:
    """한 줄 입력 팝업 — 헤더·안내·입력·버튼이 모두 보이도록 고정 최소 높이."""
    root = parent.winfo_toplevel() if parent is not None else None
    win = tk.Toplevel(root)
    result: dict[str, str | None] = {"value": None}
    prompt = (prompt or "").strip() or "내용을 입력하세요."

    body = style_window(
        win,
        root,
        title=title or "입력",
        geometry=f"{width}x320",
        modal=True,
        minsize=(420, 280),
        ambient=False,
    )

    bf = ttk.Frame(body, style="App.TFrame")
    bf.pack(side=tk.BOTTOM, fill=tk.X, pady=(16, 0))

    def ok() -> None:
        result["value"] = var.get().strip() or None
        try:
            win.grab_release()
        except Exception:
            pass
        win.destroy()

    def cancel() -> None:
        result["value"] = None
        try:
            win.grab_release()
        except Exception:
            pass
        win.destroy()

    ttk.Button(bf, text=ok_text, style="Accent.TButton", command=ok).pack(side=tk.RIGHT)
    ttk.Button(bf, text=cancel_text, style="Ghost.TButton", command=cancel).pack(
        side=tk.RIGHT, padx=8
    )

    ttk.Label(
        body,
        text=prompt,
        wraplength=width - 56,
        style=_MUTED_STYLE,
        font=_font_ui(),
    ).pack(anchor=tk.W, fill=tk.X)

    var = tk.StringVar()
    ent = ttk.Entry(body, textvariable=var, font=_font_ui())
    ent.pack(fill=tk.X, pady=(16, 0), ipady=8)
    try:
        ent.focus_set()
    except Exception:
        pass

    win.bind("<Return>", lambda _e: ok())
    win.bind("<Escape>", lambda _e: cancel())
    win.protocol("WM_DELETE_WINDOW", cancel)
    _fit_window(win, min_w=width, min_h=300, max_w=640, max_h=420)
    _center_on_parent(win, root)
    _lift(win)
    win.wait_window()
    return result["value"]


# messagebox-compatible thin wrappers
def showinfo(title: str, message: str, parent: tk.Misc | None = None, **_kw) -> str:
    show_message(parent, title, message, kind="info")
    return "ok"


def showwarning(title: str, message: str, parent: tk.Misc | None = None, **_kw) -> str:
    show_message(parent, title, message, kind="warn")
    return "ok"


def showerror(title: str, message: str, parent: tk.Misc | None = None, **_kw) -> str:
    show_message(parent, title, message, kind="error")
    return "ok"


def askokcancel(title: str, message: str, parent: tk.Misc | None = None, **_kw) -> bool:
    return ask_confirm(parent, title, message, ok_text="계속", cancel_text="취소")

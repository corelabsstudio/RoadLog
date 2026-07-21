#!/usr/bin/env python3
"""
리치킷 — 범용 커뮤니티 홍보 도우미

1) 사이트 분석 → 홍보 문구
2) 어디에 올리면 좋은지 안내
3) 글 쓰기 보조 (올리기 자동은 기본 끔 · 안전 제한)
4) 브라우저에서 글 쓰기 보조

사용:
  python app.py
  또는 실행.bat
"""

from __future__ import annotations

import json
import sys
import threading
import webbrowser
import tkinter as tk
from pathlib import Path
from tkinter import scrolledtext, ttk

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from guardrails import check_before_post, record_attempt, today_stats  # noqa: E402
from help_text import HELP_BODY, HELP_TITLE  # noqa: E402
from phrase_gen import generate_post, list_styles  # noqa: E402
from poster import (  # noqa: E402
    BoardCandidate,
    PostJob,
    discover_boards,
    load_site_profiles,
    run_post,
    save_site_profile,
)
from product_config import (  # noqa: E402
    DEFAULT_COOLDOWN_MINUTES,
    DEFAULT_MAX_POSTS_PER_DAY,
    DEFAULT_PRODUCT_URL,
    DEFAULT_SUBMIT_ENABLED,
    DISCLAIMER_FULL,
    DISCLAIMER_SHORT,
    ICON_ICO,
    ICON_PNG,
    PRODUCT_DISPLAY_NAME,
    PRODUCT_NAME,
    PRODUCT_TAGLINE,
    PRODUCT_VERSION,
    STRUCTURE_SCAN_HINT,
    WEEKLY_VALIDATION_CHANNELS,
    WEEKLY_VALIDATION_LABEL,
    support_label,
    weekly_plan_text,
)
from structure_scan import StructureScanResult, scan_site_structure  # noqa: E402
from secure_store import decrypt_secret, prepare_password_for_save  # noqa: E402
from site_analyzer import SiteProfile, analyze_site  # noqa: E402
from sites_recommend import (  # noqa: E402
    format_site_line,
    list_categories,
    recommend,
    recommend_top,
)
from templates import get_template, get_template_for_profile, list_template_names  # noqa: E402
from validation_log import log_post_attempt  # noqa: E402

from app_dialogs import (  # noqa: E402
    ask_confirm,
    show_message,
    style_window,
)
from ui_theme import (  # noqa: E402
    ACCENT,
    BG,
    BG_HEADER,
    BG_SIDEBAR,
    BORDER,
    apply_theme,
    fonts as theme_fonts,
    make_card,
    make_hero,
    paint_frame_ambient,
    register_app_fonts,
    style_listbox,
    style_log_widget,
    style_text_widget,
)

PROFILES_PATH = ROOT / "data" / "sites.json"
CREDS_PATH = ROOT / "data" / "last_form.json"
DISCLAIMER_FLAG = ROOT / "data" / ".disclaimer_accepted_v2"


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{PRODUCT_DISPLAY_NAME}  ·  v{PRODUCT_VERSION}")
        self.geometry("1180x900")
        self.minsize(980, 720)
        register_app_fonts()  # 에스코어 드림 번들 로드
        apply_theme(self)
        self._F = theme_fonts()
        self._apply_app_icon()

        self._busy = False
        self._last_boards: list[BoardCandidate] = []
        self._product_profile: SiteProfile | None = None
        self._site_selectors: dict = {}
        self._structure_scan: StructureScanResult | None = None
        self.var_product_url = tk.StringVar(value=DEFAULT_PRODUCT_URL)
        self.var_product_summary = tk.StringVar(
            value="홍보할 사이트 주소를 넣고 「사이트 보고 홍보글 만들기」로 시작하세요."
        )
        self.var_structure_summary = tk.StringVar(
            value="아직 준비 전 · 올릴 곳 주소를 넣고 「글 쓰는 칸 찾기」를 누르세요."
        )
        self.var_board_url = tk.StringVar()
        self.var_board_name = tk.StringVar(value="(아직 없음 · 게시판 찾기로 고르기)")
        self.var_auto_pick = tk.BooleanVar(value=True)
        self.var_validation = tk.BooleanVar(value=False)  # 결과 탭 제거 — 기록 UI 없음
        self.var_max_day = tk.IntVar(value=DEFAULT_MAX_POSTS_PER_DAY)
        self.var_cooldown = tk.IntVar(value=DEFAULT_COOLDOWN_MINUTES)
        self.var_stats_line = tk.StringVar(value="홈에서 ①②③ 만 하면 됩니다")
        self.var_next_hint = tk.StringVar(
            value="다음: ① 홍보할 내 사이트 주소를 넣고 「홍보글 만들기」를 누르세요"
        )
        self._build()
        self._load_last()
        self._refresh_stats_line()
        self._update_next_hint()
        self.after(200, self._maybe_show_disclaimer)
        self._log(f"{PRODUCT_DISPLAY_NAME} 초간단 모드 — 홈에서 ①②③ 만 하면 됩니다.")

    def _apply_app_icon(self) -> None:
        """전문 앱 아이콘 (ico/png) 적용."""
        try:
            if ICON_ICO.is_file():
                self.iconbitmap(default=str(ICON_ICO))
                self.iconbitmap(str(ICON_ICO))
        except Exception:
            pass
        try:
            if ICON_PNG.is_file():
                # PNG는 PhotoImage로 작업표시줄 품질↑ (참조 유지 필요)
                self._icon_img = tk.PhotoImage(file=str(ICON_PNG))
                # 너무 크면 축소
                try:
                    w = self._icon_img.width()
                    if w > 64:
                        factor = max(1, w // 64)
                        self._icon_img = self._icon_img.subsample(factor, factor)
                except Exception:
                    pass
                self.iconphoto(True, self._icon_img)
        except Exception:
            pass


    def _build(self) -> None:
        self._nav_btns: dict[str, ttk.Button] = {}
        self._pages: dict[str, ttk.Frame] = {}
        self._page_canvas: dict[str, tk.Canvas] = {}
        self._current_page = "home"

        # Vars used across pages (must exist before building forms)
        self.var_site = tk.StringVar()
        self.var_login = tk.StringVar()
        self.var_write = tk.StringVar()
        self.var_user = tk.StringVar()
        self.var_pass = tk.StringVar()
        self.var_save_pw = tk.BooleanVar(value=False)
        self.var_submit = tk.BooleanVar(value=DEFAULT_SUBMIT_ENABLED)  # 초간단: 기본 끔 유지
        self.var_template = tk.StringVar(value=list_template_names()[0])
        self.var_phrase_style = tk.StringVar(value=list_styles()[0])

        shell = ttk.Frame(self, style="App.TFrame")
        shell.pack(fill=tk.BOTH, expand=True)

        # ===== TOP BAR — Battle.net chrome (layered depth) =====
        header_shell = tk.Frame(shell, bg=BG_HEADER, highlightthickness=0)
        header_shell.pack(fill=tk.X)
        paint_frame_ambient(header_shell, "header")
        header = ttk.Frame(header_shell, style="Header.TFrame", padding=(18, 12))
        header.pack(fill=tk.X)
        head_left = ttk.Frame(header, style="Header.TFrame")
        head_left.pack(side=tk.LEFT, fill=tk.Y)
        brand_row = ttk.Frame(head_left, style="Header.TFrame")
        brand_row.pack(anchor=tk.W)
        # cyan mark + brand (launcher logo strip)
        tk.Label(
            brand_row,
            text="◆",
            bg=BG_HEADER,
            fg=ACCENT,
            font=self._F["hero_mark"],
        ).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Label(brand_row, text=PRODUCT_DISPLAY_NAME, style="Brand.TLabel").pack(side=tk.LEFT)
        ttk.Label(brand_row, text=f"  v{PRODUCT_VERSION}", style="HeaderMuted.TLabel").pack(
            side=tk.LEFT, padx=(4, 0), pady=(4, 0)
        )
        ttk.Label(brand_row, text="  ·  초간단", style="HeaderMuted.TLabel").pack(
            side=tk.LEFT, padx=(2, 0), pady=(4, 0)
        )

        head_center = ttk.Frame(header, style="Header.TFrame")
        head_center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=24)
        ttk.Label(head_center, textvariable=self.var_stats_line, style="Stat.TLabel").pack(
            anchor=tk.CENTER, pady=6
        )

        head_right = ttk.Frame(header, style="Header.TFrame")
        head_right.pack(side=tk.RIGHT)
        ttk.Button(
            head_right, text="사용 방법", style="Header.TButton", command=self._show_help
        ).pack(side=tk.LEFT, padx=2)
        ttk.Button(
            head_right, text="이용 안내", style="Header.TButton", command=self._show_disclaimer_only
        ).pack(side=tk.LEFT, padx=2)

        # multi-stop accent under top chrome (glow strip)
        glow = tk.Frame(shell, bg=ACCENT, height=2)
        glow.pack(fill=tk.X)
        tk.Frame(shell, bg="#004d73", height=1).pack(fill=tk.X)
        tk.Frame(shell, bg=BG_HEADER, height=1).pack(fill=tk.X)

        # ===== BODY: left game-rail + main stage =====
        body = ttk.Frame(shell, style="App.TFrame")
        body.pack(fill=tk.BOTH, expand=True)

        # --- Left rail (game selector style) with ambient depth ---
        side_shell = tk.Frame(body, bg=BG_SIDEBAR, width=228, highlightthickness=0)
        side_shell.pack(side=tk.LEFT, fill=tk.Y)
        side_shell.pack_propagate(False)
        paint_frame_ambient(side_shell, "sidebar")
        side = ttk.Frame(side_shell, style="Sidebar.TFrame", padding=(0, 0))
        side.pack(fill=tk.BOTH, expand=True)

        side_inner = ttk.Frame(side, style="Sidebar.TFrame", padding=(10, 16))
        side_inner.pack(fill=tk.BOTH, expand=True)

        ttk.Label(side_inner, text="메뉴", style="SidebarSection.TLabel").pack(
            anchor=tk.W, padx=8, pady=(0, 10)
        )

        nav_items = [
            ("home", "◉  홈", "초간단 3단계"),
            ("write", "⚙  자세히", "고급 · 필요할 때만"),
        ]
        for key, title, sub in nav_items:
            btn = ttk.Button(
                side_inner,
                text=title,
                style="Nav.TButton",
                command=lambda k=key: self._show_page(k),
            )
            btn.pack(fill=tk.X, pady=1)
            self._nav_btns[key] = btn
            ttk.Label(side_inner, text=f"    {sub}", style="SidebarMuted.TLabel").pack(
                anchor=tk.W, pady=(0, 8)
            )

        ttk.Separator(side_inner, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        ttk.Label(side_inner, text="도움", style="SidebarSection.TLabel").pack(
            anchor=tk.W, padx=8, pady=(0, 8)
        )
        ttk.Button(
            side_inner,
            text="？  사용 방법",
            style="Nav.TButton",
            command=self._show_help,
        ).pack(fill=tk.X, pady=1)

        ttk.Frame(side_inner, style="Sidebar.TFrame").pack(fill=tk.BOTH, expand=True)

        foot = ttk.Frame(side_inner, style="Sidebar.TFrame")
        foot.pack(fill=tk.X, pady=(8, 0))
        ttk.Label(foot, text=PRODUCT_DISPLAY_NAME, style="SidebarBrand.TLabel").pack(anchor=tk.W)
        ttk.Label(foot, text=PRODUCT_TAGLINE, style="SidebarMuted.TLabel", wraplength=180).pack(
            anchor=tk.W, pady=(4, 0)
        )
        ttk.Label(foot, text="● 이 컴퓨터에서만 동작", style="SidebarMuted.TLabel").pack(
            anchor=tk.W, pady=(6, 0)
        )

        # rail edge glow (cyan depth line like Battle.net game list)
        edge = tk.Frame(body, bg=BG_SIDEBAR, width=3)
        edge.pack(side=tk.LEFT, fill=tk.Y)
        tk.Frame(edge, bg="#0a3048", width=2).pack(side=tk.LEFT, fill=tk.Y)
        tk.Frame(edge, bg=ACCENT, width=1).pack(side=tk.LEFT, fill=tk.Y)

        # --- Main stage (atmospheric background) ---
        main_shell = tk.Frame(body, bg=BG, highlightthickness=0)
        main_shell.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        paint_frame_ambient(main_shell, "stage")
        main = ttk.Frame(main_shell, style="App.TFrame")
        main.pack(fill=tk.BOTH, expand=True)

        pages_host = ttk.Frame(main, style="App.TFrame")
        pages_host.pack(fill=tk.BOTH, expand=True)

        self._pages["home"] = self._build_page_home(pages_host)
        self._pages["write"] = self._build_page_write(pages_host)
        # 하위 호환 별칭
        self._pages["overview"] = self._pages["home"]

        # Bottom status strip (friends bar vibe) + activity log
        tk.Frame(main, bg="#0a3048", height=1).pack(fill=tk.X)
        tk.Frame(main, bg=ACCENT, height=1).pack(fill=tk.X)
        bottom = ttk.Frame(main, style="Bottom.TFrame", padding=(14, 10))
        bottom.pack(fill=tk.X)
        bottom_head = ttk.Frame(bottom, style="Bottom.TFrame")
        bottom_head.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(bottom_head, text="● 진행 기록", style="BottomBrand.TLabel").pack(side=tk.LEFT)
        ttk.Label(
            bottom_head,
            text="  방금 한 일  ·  이 컴퓨터",
            style="Bottom.TLabel",
        ).pack(side=tk.LEFT, pady=(1, 0))
        ttk.Label(
            bottom_head,
            text="준비됨",
            style="Bottom.TLabel",
        ).pack(side=tk.RIGHT)
        self.txt_log = scrolledtext.ScrolledText(bottom, height=2, wrap=tk.WORD)
        style_log_widget(self.txt_log)
        self.txt_log.pack(fill=tk.X, expand=False)

        self._show_page("home")

    def _make_scroll_page(self, parent: ttk.Frame):
        wrap = ttk.Frame(parent, style="App.TFrame")
        canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0, bd=0)
        vsb = ttk.Scrollbar(wrap, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        # tk.Frame so ambient art shows in gaps between elevated cards
        inner = tk.Frame(canvas, bg=BG, highlightthickness=0, bd=0, padx=22, pady=18)
        paint_frame_ambient(inner, "stage")
        win_id = canvas.create_window((0, 0), window=inner, anchor=tk.NW)

        def on_frame_cfg(_e=None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def on_canvas_cfg(e) -> None:
            canvas.itemconfigure(win_id, width=e.width)

        inner.bind("<Configure>", on_frame_cfg)
        canvas.bind("<Configure>", on_canvas_cfg)

        def wheel(e) -> None:
            if canvas.winfo_ismapped():
                canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

        canvas.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", wheel))
        canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))
        return wrap, canvas, inner

    def _show_page(self, key: str) -> None:
        if key == "overview":
            key = "home"
        if key not in self._pages:
            return
        self._current_page = key
        for k, fr in self._pages.items():
            if k == "overview":
                continue  # alias of home
            if k == key:
                fr.pack(fill=tk.BOTH, expand=True)
            else:
                fr.pack_forget()
        for k, btn in self._nav_btns.items():
            btn.configure(style="NavActive.TButton" if k == key else "Nav.TButton")
        if key == "home":
            try:
                self._update_next_hint()
            except Exception:
                pass

    def _build_page_home(self, parent: ttk.Frame) -> ttk.Frame:
        """초간단 홈 — 3단계만 보여 주는 판매용 기본 화면."""
        wrap, _canvas, frm = self._make_scroll_page(parent)  # type: ignore[misc]
        pad = {"padx": 0, "pady": (0, 12)}

        # 다음 할 일 배너
        hint = make_card(frm, "지금 할 일", None)
        hint.pack(fill=tk.X, **pad)
        ttk.Label(
            hint,
            textvariable=self.var_next_hint,
            style="Surface.TLabel",
            wraplength=760,
            font=self._F.get("section", self._F.get("ui")),
        ).pack(anchor=tk.W)
        ttk.Label(
            hint,
            text="평소에는 이 화면만 쓰세요. 어려운 설정은 왼쪽 「자세히」에 있습니다.",
            style="SurfaceMuted.TLabel",
            wraplength=760,
        ).pack(anchor=tk.W, pady=(8, 0))

        # ① 홍보글
        g1 = make_card(frm, "①  홍보글 만들기", "1")
        g1.pack(fill=tk.X, **pad)
        ttk.Label(
            g1,
            text="팔거나 알리고 싶은 사이트 주소 (예: https://roadlog.co.kr)",
            style="SurfaceMuted.TLabel",
            wraplength=720,
        ).pack(anchor=tk.W)
        prow = ttk.Frame(g1)
        prow.pack(fill=tk.X, pady=(10, 6))
        ttk.Entry(prow, textvariable=self.var_product_url).pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )
        self.btn_analyze = ttk.Button(
            prow,
            text="홍보글 만들기",
            style="Accent.TButton",
            command=self._on_analyze_product,
        )
        self.btn_analyze.pack(side=tk.LEFT, padx=(8, 0))
        ttk.Label(
            g1,
            textvariable=self.var_product_summary,
            wraplength=720,
            style="SurfaceMuted.TLabel",
        ).pack(anchor=tk.W, pady=(4, 0))

        ttk.Label(g1, text="제목", style="Surface.TLabel").pack(anchor=tk.W, pady=(12, 4))
        self.ent_title = ttk.Entry(g1)
        self.ent_title.pack(fill=tk.X)
        self.ent_title.bind("<KeyRelease>", lambda _e: self._update_next_hint())

        row_body_h = ttk.Frame(g1)
        row_body_h.pack(fill=tk.X, pady=(12, 4))
        ttk.Label(row_body_h, text="본문", style="Surface.TLabel").pack(side=tk.LEFT)
        ttk.Button(
            row_body_h,
            text="다른 버전 만들기",
            style="Secondary.TButton",
            command=self._generate_free_phrase,
        ).pack(side=tk.RIGHT)
        self.txt_body = scrolledtext.ScrolledText(g1, height=8, wrap=tk.WORD)
        style_text_widget(self.txt_body)
        self.txt_body.pack(fill=tk.BOTH, expand=True)
        self.txt_body.bind("<KeyRelease>", lambda _e: self._update_next_hint())

        # ② 올릴 곳
        g2 = make_card(frm, "②  어디에 올릴까", "2")
        g2.pack(fill=tk.X, **pad)
        ttk.Label(
            g2,
            text="카페·블로그 주소를 넣거나, 「올릴 곳 고르기」로 선택하세요.",
            style="SurfaceMuted.TLabel",
            wraplength=720,
        ).pack(anchor=tk.W)
        r2 = ttk.Frame(g2)
        r2.pack(fill=tk.X, pady=(10, 4))
        ttk.Label(r2, text="올릴 곳 주소", width=12, style="Surface.TLabel").pack(side=tk.LEFT)
        ent_site = ttk.Entry(r2, textvariable=self.var_site)
        ent_site.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        ent_site.bind("<KeyRelease>", lambda _e: self._update_next_hint())
        ttk.Button(
            r2,
            text="올릴 곳 고르기",
            style="Secondary.TButton",
            command=self._open_site_recommend,
        ).pack(side=tk.LEFT)

        r3 = ttk.Frame(g2)
        r3.pack(fill=tk.X, pady=4)
        ttk.Label(r3, text="아이디", width=12, style="Surface.TLabel").pack(side=tk.LEFT)
        ent_user = ttk.Entry(r3, textvariable=self.var_user)
        ent_user.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        ent_user.bind("<KeyRelease>", lambda _e: self._update_next_hint())
        ttk.Label(r3, text="비밀번호", width=10, style="Surface.TLabel").pack(side=tk.LEFT)
        ent_pass = ttk.Entry(r3, textvariable=self.var_pass, show="*")
        ent_pass.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        ent_pass.bind("<KeyRelease>", lambda _e: self._update_next_hint())

        ttk.Label(
            g2,
            text="※ 가입·캡차·휴대폰 인증은 브라우저에서 직접 해 주세요. 올리기 버튼은 직접 누릅니다.",
            style="SurfaceMuted.TLabel",
            wraplength=720,
        ).pack(anchor=tk.W, pady=(8, 0))

        # ③ 올리기
        g3 = make_card(frm, "③  글 올리기", "3")
        g3.pack(fill=tk.X, **pad)
        ttk.Label(
            g3,
            text="버튼을 누르면 브라우저가 열리고 제목·본문을 넣어 줍니다. 마지막 「올리기」는 직접 확인 후 누르세요.",
            style="SurfaceMuted.TLabel",
            wraplength=720,
        ).pack(anchor=tk.W)
        act = ttk.Frame(g3)
        act.pack(fill=tk.X, pady=(14, 0))
        self.btn_run = ttk.Button(
            act,
            text="▶  브라우저에서 글 쓰기",
            style="Accent.TButton",
            command=self._on_run,
        )
        self.btn_run.pack(side=tk.LEFT)
        ttk.Button(
            act,
            text="사용 방법",
            style="Ghost.TButton",
            command=self._show_help,
        ).pack(side=tk.LEFT, padx=10)
        ttk.Button(
            act,
            text="자세히 (고급)",
            style="Ghost.TButton",
            command=lambda: self._show_page("write"),
        ).pack(side=tk.RIGHT)

        return wrap

    def _update_next_hint(self) -> None:
        """홈 상단 ‘지금 할 일’ 한 줄 갱신."""
        try:
            has_title = bool(self.ent_title.get().strip()) if hasattr(self, "ent_title") else False
            has_body = (
                bool(self.txt_body.get("1.0", "end").strip())
                if hasattr(self, "txt_body")
                else False
            )
        except Exception:
            has_title, has_body = False, False
        has_site = bool(self.var_site.get().strip())
        has_user = bool(self.var_user.get().strip() and self.var_pass.get())
        if not (has_title and has_body):
            self.var_next_hint.set(
                "다음: ① 홍보할 사이트 주소를 넣고 「홍보글 만들기」를 누르세요"
            )
        elif not has_site:
            self.var_next_hint.set(
                "다음: ② 올릴 곳 주소를 넣거나 「올릴 곳 고르기」를 누르세요"
            )
        elif not has_user:
            self.var_next_hint.set("다음: ② 아이디와 비밀번호를 입력하세요")
        else:
            self.var_next_hint.set(
                "다음: ③ 「브라우저에서 글 쓰기」→ 내용 확인 후 올리기는 직접"
            )

    def _build_page_write(self, parent: ttk.Frame) -> ttk.Frame:
        """자세히(고급) — 중복 없이 카드 3개 + 하단 액션 1줄."""
        wrap, _canvas, frm = self._make_scroll_page(parent)  # type: ignore[misc]
        pad = {"padx": 0, "pady": (0, 12)}

        # ----- 안내 -----
        note = make_card(frm, "자세히 (고급)", None)
        note.pack(fill=tk.X, **pad)
        ttk.Label(
            note,
            text="평소 홍보는 「홈」3단계만 쓰세요. 여기서는 주소·게시판·칸 찾기를 세밀히 다룹니다.",
            style="SurfaceMuted.TLabel",
            wraplength=720,
        ).pack(anchor=tk.W)
        ttk.Button(
            note,
            text="← 홈으로",
            style="Accent.TButton",
            command=lambda: self._show_page("home"),
        ).pack(anchor=tk.W, pady=(10, 0))

        # ----- 1) 올릴 곳 + 계정 (주소·로그인 한곳에) -----
        g1 = make_card(frm, "1. 올릴 곳 · 계정", "1")
        g1.pack(fill=tk.X, **pad)
        ttk.Label(
            g1,
            text="주소를 직접 넣거나 「올릴 곳 고르기」로 채운 뒤, 필요하면 「글 쓰는 칸 찾기」를 한 번 하세요.",
            style="SurfaceMuted.TLabel",
            wraplength=720,
        ).pack(anchor=tk.W)
        # grid rows for fields
        fields = ttk.Frame(g1)
        fields.pack(fill=tk.X, pady=(8, 0))
        fields.columnconfigure(1, weight=1)
        self._row_url(fields, 0, "올릴 곳 주소 *", self.var_site, width=58)
        self._row_url(fields, 1, "로그인 화면 주소", self.var_login, width=58)
        self._row_url(fields, 2, "글쓰기 화면 주소", self.var_write, width=58)
        self._row(fields, 3, "아이디 *", self.var_user, width=40)
        self._row(fields, 4, "비밀번호 *", self.var_pass, width=40, show="*")

        tools1 = ttk.Frame(g1)
        tools1.pack(fill=tk.X, pady=(12, 0))
        ttk.Button(
            tools1,
            text="올릴 곳 고르기",
            style="Secondary.TButton",
            command=self._open_site_recommend,
        ).pack(side=tk.LEFT)
        self.btn_scan = ttk.Button(
            tools1,
            text="글 쓰는 칸 찾기",
            style="Accent.TButton",
            command=self._on_structure_scan,
        )
        self.btn_scan.pack(side=tk.LEFT, padx=8)
        ttk.Button(
            tools1,
            text="찾은 내용 보기",
            style="Ghost.TButton",
            command=self._show_structure_detail,
        ).pack(side=tk.LEFT)
        ttk.Label(
            g1,
            textvariable=self.var_structure_summary,
            wraplength=720,
            style="SurfaceMuted.TLabel",
        ).pack(anchor=tk.W, pady=(8, 0))

        opt = ttk.Frame(g1)
        opt.pack(fill=tk.X, pady=(8, 0))
        ttk.Checkbutton(
            opt, text="비밀번호 이 컴퓨터에만 저장", variable=self.var_save_pw
        ).pack(side=tk.LEFT, padx=(0, 16))
        ttk.Checkbutton(
            opt, text="올리기 버튼까지 자동 (비추천)", variable=self.var_submit
        ).pack(side=tk.LEFT)

        # ----- 2) 게시판 + 입력 보조 -----
        g2 = make_card(frm, "2. 게시판 · 입력 보조", "2")
        g2.pack(fill=tk.X, **pad)
        ttk.Label(
            g2,
            text="카페 안 게시판을 고르고, 로그인 후 제목·본문 칸에 글을 넣습니다. 올리기는 직접.",
            style="SurfaceMuted.TLabel",
            wraplength=720,
        ).pack(anchor=tk.W)
        br = ttk.Frame(g2)
        br.pack(fill=tk.X, pady=(10, 6))
        ttk.Label(br, text="고른 게시판", width=12, style="Surface.TLabel").pack(side=tk.LEFT)
        ttk.Label(br, textvariable=self.var_board_name, style="SurfaceMuted.TLabel").pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )
        tools2 = ttk.Frame(g2)
        tools2.pack(fill=tk.X, pady=(4, 0))
        self.btn_find_boards = ttk.Button(
            tools2,
            text="게시판 찾기",
            style="Secondary.TButton",
            command=self._on_find_boards_or_picker,
        )
        self.btn_find_boards.pack(side=tk.LEFT)
        ttk.Checkbutton(
            tools2, text="안 고르면 추천 1순위", variable=self.var_auto_pick
        ).pack(side=tk.LEFT, padx=12)
        self.btn_smart = ttk.Button(
            tools2,
            text="▶  로그인 후 글 칸에 넣기",
            style="Accent.TButton",
            command=self._on_smart_post,
        )
        self.btn_smart.pack(side=tk.RIGHT)

        # ----- 3) 글 양식 (홈 제목·본문에 반영) -----
        g3 = make_card(frm, "3. 글 양식 · 스타일", "3")
        g3.pack(fill=tk.X, **pad)
        ttk.Label(
            g3,
            text="제목·본문은 「홈」에서 고칩니다. 양식/스타일만 여기서 바꿉니다.",
            style="SurfaceMuted.TLabel",
            wraplength=720,
        ).pack(anchor=tk.W)
        top = ttk.Frame(g3)
        top.pack(fill=tk.X, pady=(10, 0))
        ttk.Label(top, text="양식", style="Surface.TLabel").pack(side=tk.LEFT)
        cb = ttk.Combobox(
            top,
            textvariable=self.var_template,
            values=list_template_names(),
            state="readonly",
            width=16,
        )
        cb.pack(side=tk.LEFT, padx=8)
        cb.bind("<<ComboboxSelected>>", lambda e: self._apply_template())
        ttk.Label(top, text="스타일", style="Surface.TLabel").pack(side=tk.LEFT, padx=(12, 0))
        cb2 = ttk.Combobox(
            top,
            textvariable=self.var_phrase_style,
            values=list_styles(),
            state="readonly",
            width=14,
        )
        cb2.pack(side=tk.LEFT, padx=8)
        ttk.Button(
            top,
            text="다른 버전 만들기",
            style="Secondary.TButton",
            command=self._generate_free_phrase,
        ).pack(side=tk.LEFT, padx=8)

        # ----- 하단 액션 1줄 (중복 제거) -----
        act = make_card(frm, "실행 · 저장", None)
        act.pack(fill=tk.X, **pad)
        row = ttk.Frame(act)
        row.pack(fill=tk.X)
        ttk.Button(
            row,
            text="▶  브라우저에서 글 쓰기",
            style="Accent.TButton",
            command=self._on_run,
        ).pack(side=tk.LEFT)
        ttk.Button(
            row, text="설정 저장", style="Secondary.TButton", command=self._save_profile
        ).pack(side=tk.LEFT, padx=8)
        ttk.Button(
            row, text="설정 불러오기", style="Ghost.TButton", command=self._load_profile_dialog
        ).pack(side=tk.LEFT)
        ttk.Button(
            row, text="지금 내용 기억", style="Ghost.TButton", command=self._save_last
        ).pack(side=tk.RIGHT)

        return wrap

    def _on_find_boards_or_picker(self) -> None:
        """게시판 찾기 — 이미 목록 있으면 다시 고르기, 없으면 새로 탐색."""
        if self._last_boards:
            self._show_board_picker()
        else:
            self._on_find_boards()

    def _row(self, parent, row, label, var, width=50, show=None) -> None:
        ttk.Label(parent, text=label, width=16, style="Surface.TLabel").grid(
            row=row, column=0, sticky=tk.W, pady=4
        )
        ent = ttk.Entry(parent, textvariable=var, width=width, show=show or "")
        ent.grid(row=row, column=1, sticky=tk.EW, pady=4)
        parent.columnconfigure(1, weight=1)

    def _row_url(self, parent, row, label, var, width=50) -> None:
        """주소 입력 + 열기 버튼."""
        ttk.Label(parent, text=label, width=16, style="Surface.TLabel").grid(
            row=row, column=0, sticky=tk.W, pady=4
        )
        cell = ttk.Frame(parent)
        cell.grid(row=row, column=1, sticky=tk.EW, pady=4)
        parent.columnconfigure(1, weight=1)
        ent = ttk.Entry(cell, textvariable=var, width=width)
        ent.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(
            cell,
            text="열기",
            style="Ghost.TButton",
            width=7,
            command=lambda v=var, lab=label: self._open_url(
                v.get(), label=lab.replace(" *", "").replace(" (선택)", "")
            ),
        ).pack(side=tk.LEFT, padx=(8, 0))

    def _open_url(self, url: str, label: str = "페이지", parent=None) -> bool:
        """브라우저에서 주소 바로 열기. 복사·붙여넣기 없음."""
        url = (url or "").strip()
        if not url:
            show_message(parent or self, "주소 없음", f"{label} 주소가 비어 있습니다.\n추천 사이트에서 적용하거나 주소를 입력하세요.", kind="info")
            return False
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        try:
            webbrowser.open(url)
            self._log(f"{label} 바로 연결: {url}")
            return True
        except Exception as e:
            show_message(parent or self, "연결 실패", str(e), kind="error")
            return False

    def _log(self, msg: str) -> None:
        def append() -> None:
            if not hasattr(self, "txt_log") or self.txt_log is None:
                return
            try:
                self.txt_log.insert(tk.END, msg + "\n")
                self.txt_log.see(tk.END)
            except Exception:
                pass

        self.after(0, append)

    def _apply_template(self) -> None:
        name = self.var_template.get()
        if self._product_profile and self._product_profile.ok:
            title, body = get_template_for_profile(name, self._product_profile)
            self._log(f"템플릿 적용 (내 사이트 기준): {name}")
        else:
            title, body = get_template(name)
            self._log(f"템플릿 적용 (기본 문구): {name} — 내 사이트를 먼저 분석하면 제품에 맞게 바뀝니다")
        self.ent_title.delete(0, tk.END)
        self.ent_title.insert(0, title)
        self.txt_body.delete("1.0", tk.END)
        self.txt_body.insert("1.0", body)

    def _apply_recommended_site(self, site: dict) -> None:
        """추천 사이트 URL·로그인·글쓰기 필드를 폼에 채움."""
        self.var_site.set(site.get("site_url") or "")
        self.var_login.set(site.get("login_url") or "")
        self.var_write.set(site.get("write_url") or "")
        name = site.get("name", "")
        self._log(f"추천 사이트 적용: {name} → {site.get('site_url', '')}")
        if site.get("tip"):
            self._log(f"  팁: {site['tip']}")
        if site.get("caution"):
            self._log(f"  주의: {site['caution']}")

    @staticmethod
    def _site_login_url(site: dict) -> str:
        """로그인 URL (없으면 사이트 URL로 대체)."""
        return (site.get("login_url") or site.get("site_url") or "").strip()

    def _open_site_recommend(self) -> None:
        """올릴 곳 고르기 — 목록 선택 후 「이 곳으로 정하기」만 (버튼 최소화)."""
        win = tk.Toplevel(self)
        frm = style_window(
            win,
            self,
            title="어디에 올릴까",
            geometry="640x520",
            modal=True,
            minsize=(480, 400),
            ambient=False,
        )

        ttk.Label(
            frm,
            text="목록에서 고른 뒤 「이 곳으로 정하기」만 누르면 됩니다. (더블클릭도 동일)",
            wraplength=600,
            style="Muted.TLabel",
        ).pack(anchor=tk.W, pady=(0, 8))

        filters = ttk.Frame(frm, style="App.TFrame")
        filters.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(filters, text="종류", style="App.TLabel").pack(side=tk.LEFT)
        var_cat = tk.StringVar(value="전체")
        cb_cat = ttk.Combobox(
            filters,
            textvariable=var_cat,
            values=list_categories(),
            state="readonly",
            width=16,
        )
        cb_cat.pack(side=tk.LEFT, padx=6)

        state: dict = {"sites": [], "current": None}

        mid = ttk.Frame(frm, style="App.TFrame")
        mid.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(mid, style="App.TFrame")
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        lb = tk.Listbox(left, font=self._F["list"], height=14)
        style_listbox(lb)
        lb.pack(fill=tk.BOTH, expand=True)

        right = ttk.Frame(mid, style="App.TFrame")
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))
        ttk.Label(right, text="설명", style="App.TLabel").pack(anchor=tk.W)
        txt = scrolledtext.ScrolledText(
            right, height=12, wrap=tk.WORD, font=self._F["list_sm"], width=36
        )
        style_text_widget(txt)
        txt.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        txt.configure(state=tk.DISABLED)

        def selected_site() -> dict | None:
            sel = lb.curselection()
            if not sel:
                return state.get("current")
            idx = int(sel[0])
            if 0 <= idx < len(state["sites"]):
                return state["sites"][idx]
            return None

        def show_detail(site: dict | None) -> None:
            state["current"] = site
            txt.configure(state=tk.NORMAL)
            txt.delete("1.0", tk.END)
            if not site:
                txt.insert("1.0", "왼쪽 목록에서 고르세요.")
            else:
                score = site.get("recommend_score") or site.get("score", 0)
                lines = [
                    f"【{site.get('name', '')}】",
                    f"점수 {score} · {site.get('category', '')}",
                    "",
                    f"누구: {site.get('audience', '-')}",
                    f"왜: {site.get('why', '-')}",
                    "",
                    f"팁: {site.get('tip', '-')}",
                    f"주의: {site.get('caution', '-')}",
                ]
                txt.insert("1.0", "\n".join(lines))
            txt.configure(state=tk.DISABLED)
            has = site is not None
            btn_pick.configure(state=tk.NORMAL if has else tk.DISABLED)

        def refresh(_event=None) -> None:
            cat = var_cat.get()
            if cat == "전체":
                sites = recommend_top(n=10)
            else:
                sites = recommend(
                    n=12,
                    category=cat,
                    shuffle=True,
                    exclude_low=True,
                    min_score=65,
                )
            state["sites"] = sites
            lb.delete(0, tk.END)
            for s in sites:
                lb.insert(tk.END, format_site_line(s))
            if sites:
                lb.selection_set(0)
                show_detail(sites[0])
            else:
                show_detail(None)

        def on_select(_event=None) -> None:
            site = selected_site()
            if site is not None:
                show_detail(site)

        def pick_here() -> None:
            """홈 ②에 주소 넣고 창 닫기 — 메인 동작 하나."""
            site = selected_site()
            if not site:
                show_message(win, "선택", "목록에서 올릴 곳을 골라 주세요.", kind="info")
                return
            self._apply_recommended_site(site)
            win.destroy()
            self._show_page("home")
            self._update_next_hint()
            show_message(
                self,
                "② 올릴 곳 정함",
                f"「{site.get('name')}」을 넣었습니다.\n\n"
                "아이디·비밀번호 입력 후\n"
                "③ 「브라우저에서 글 쓰기」를 누르세요.",
                kind="success",
            )

        cb_cat.bind("<<ComboboxSelected>>", refresh)
        lb.bind("<<ListboxSelect>>", on_select)
        lb.bind("<Double-Button-1>", lambda _e: pick_here())

        # 버튼 3개만: 정하기 / 닫기 (+ 목록 새로고침은 보조)
        btns = ttk.Frame(frm, style="App.TFrame")
        btns.pack(fill=tk.X, pady=(12, 0))
        ttk.Button(btns, text="목록 새로고침", style="Ghost.TButton", command=refresh).pack(
            side=tk.LEFT
        )
        ttk.Button(btns, text="닫기", style="Ghost.TButton", command=win.destroy).pack(
            side=tk.RIGHT
        )
        btn_pick = ttk.Button(
            btns, text="이 곳으로 정하기", style="Accent.TButton", command=pick_here
        )
        btn_pick.pack(side=tk.RIGHT, padx=8)

        refresh()
        self._log("어디에 올릴까 창을 열었습니다.")

    def _generate_free_phrase(self) -> None:
        """API 없이 로컬 블록 조합으로 제목·본문 생성 (분석된 내 사이트 우선)."""
        style = self.var_phrase_style.get() or "랜덤"
        profile = self._product_profile
        if profile is None and self.var_product_url.get().strip():
            # 분석 전이면 빠른 분석 시도
            try:
                profile = analyze_site(self.var_product_url.get().strip())
                self._product_profile = profile
                self.var_product_summary.set(profile.summary_text().replace("\n", "  |  "))
            except Exception as e:
                self._log(f"빠른 분석 실패: {e}")
        title, body = generate_post(style, profile=profile)
        self.ent_title.delete(0, tk.END)
        self.ent_title.insert(0, title)
        self.txt_body.delete("1.0", tk.END)
        self.txt_body.insert("1.0", body)
        who = (profile.brand if profile and getattr(profile, "brand", None) else "기본(분석 전)")
        self._log(f"문구 생성 완료 (대상: {who}, 스타일: {style})")
        self._update_next_hint()

    def _form_data(self) -> dict:
        return {
            "product_url": self.var_product_url.get().strip(),
            "product_profile": self._product_profile.to_dict() if self._product_profile else None,
            "site_url": self.var_site.get().strip(),
            "login_url": self.var_login.get().strip(),
            "write_url": self.var_write.get().strip(),
            "board_url": self.var_board_url.get().strip(),
            "board_name": self.var_board_name.get().strip(),
            "username": self.var_user.get().strip(),
            "password": self.var_pass.get() if self.var_save_pw.get() else "",
            "save_password": self.var_save_pw.get(),
            "submit": self.var_submit.get(),
            "auto_pick_board": self.var_auto_pick.get(),
            "validation_mode": self.var_validation.get(),
            "template": self.var_template.get(),
            "phrase_style": self.var_phrase_style.get(),
            "title": self.ent_title.get().strip(),
            "body": self.txt_body.get("1.0", tk.END).rstrip(),
            "selectors": dict(self._site_selectors or {}),
            "structure_scan": self._structure_scan.to_dict() if self._structure_scan else None,
        }

    def _apply_data(self, data: dict) -> None:
        if data.get("product_url"):
            self.var_product_url.set(data["product_url"])
        if data.get("product_profile"):
            try:
                self._product_profile = SiteProfile.from_dict(data["product_profile"])
                if self._product_profile and self._product_profile.ok:
                    self.var_product_summary.set(
                        self._product_profile.summary_text().replace("\n", "  |  ")
                    )
            except Exception:
                self._product_profile = None
        self.var_site.set(data.get("site_url", ""))
        self.var_login.set(data.get("login_url", ""))
        self.var_write.set(data.get("write_url", ""))
        self.var_board_url.set(data.get("board_url", ""))
        if data.get("board_name"):
            self.var_board_name.set(data["board_name"])
        elif data.get("board_url"):
            self.var_board_name.set(data["board_url"][:60])
        self.var_user.set(data.get("username", ""))
        if data.get("password"):
            self.var_pass.set(decrypt_secret(data["password"]))
            self.var_save_pw.set(True)
        self.var_submit.set(bool(data.get("submit", DEFAULT_SUBMIT_ENABLED)))
        if "auto_pick_board" in data:
            self.var_auto_pick.set(bool(data.get("auto_pick_board")))
        if "validation_mode" in data:
            self.var_validation.set(bool(data.get("validation_mode")))
        if data.get("template") in list_template_names():
            self.var_template.set(data["template"])
        if data.get("phrase_style") in list_styles():
            self.var_phrase_style.set(data["phrase_style"])
        if data.get("title"):
            self.ent_title.delete(0, tk.END)
            self.ent_title.insert(0, data["title"])
        if data.get("body"):
            self.txt_body.delete("1.0", tk.END)
            self.txt_body.insert("1.0", data["body"])
        if data.get("selectors"):
            self._site_selectors = dict(data["selectors"] or {})
        if data.get("structure_scan"):
            try:
                self._structure_scan = StructureScanResult.from_dict(data["structure_scan"])
                if self._structure_scan and self._structure_scan.confidence:
                    self.var_structure_summary.set(
                        f"신뢰도 {self._structure_scan.confidence}%  ·  "
                        f"선택자 {len(self._structure_scan.selectors)}개  ·  "
                        f"{self._structure_scan.message}"
                    )
                    if self._structure_scan.selectors:
                        self._site_selectors = dict(self._structure_scan.selectors)
            except Exception:
                pass
        try:
            self._update_next_hint()
        except Exception:
            pass

    def _apply_board(self, board: BoardCandidate) -> None:
        self.var_board_url.set(board.url)
        self.var_board_name.set(f"[{board.score}] {board.name}")
        # 글쓰기 URL이 추정되면 폼에도 채움
        if board.write_url:
            self.var_write.set(board.write_url)
        # 사이트 주소가 비어 있으면 게시판 도메인으로
        if not self.var_site.get().strip() and board.url:
            self.var_site.set(board.url)
        self._log(f"게시판 선택: [{board.score}] {board.name}")
        self._log(f"  목록: {board.url}")
        if board.write_url:
            self._log(f"  글쓰기 추정: {board.write_url}")
        self._log(f"  이유: {board.reason}")

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        state = tk.DISABLED if busy else tk.NORMAL
        for btn in (
            self.btn_run,
            self.btn_find_boards,
            self.btn_smart,
            getattr(self, "btn_analyze", None),
            getattr(self, "btn_scan", None),
        ):
            if btn is None:
                continue
            try:
                btn.configure(state=state)
            except Exception:
                pass

    def _show_help(self) -> None:
        win = tk.Toplevel(self)
        frm = style_window(
            win,
            self,
            title="사용 방법",
            geometry="640x620",
            modal=True,
            minsize=(480, 400),
        )
        ttk.Label(frm, text=HELP_TITLE, style="App.TLabel").pack(
            anchor=tk.W, pady=(0, 8)
        )
        txt = scrolledtext.ScrolledText(
            frm, wrap=tk.WORD, font=self._F["help"], height=28
        )
        style_text_widget(txt)
        txt.pack(fill=tk.BOTH, expand=True)
        txt.insert("1.0", HELP_BODY)
        txt.configure(state=tk.DISABLED)
        bf = ttk.Frame(frm)
        bf.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(
            bf,
            text="시작하기: 내 사이트부터",
            style="Accent.TButton",
            command=lambda: (win.destroy(), self._show_page("home"), self.btn_analyze.focus_set()),
        ).pack(side=tk.LEFT)
        ttk.Button(bf, text="닫기", command=win.destroy).pack(side=tk.RIGHT)

    def _maybe_show_disclaimer(self) -> None:
        if DISCLAIMER_FLAG.exists():
            return
        self._show_disclaimer_only(force_accept=True)

    def _show_disclaimer_only(self, force_accept: bool = False) -> None:
        win = tk.Toplevel(self)
        frm = style_window(
            win,
            self,
            title="이용 안내",
            geometry="560x480",
            modal=True,
            minsize=(420, 360),
        )
        txt = scrolledtext.ScrolledText(frm, wrap=tk.WORD, font=self._F["body"], height=20)
        style_text_widget(txt)
        txt.pack(fill=tk.BOTH, expand=True)
        txt.insert("1.0", DISCLAIMER_FULL)
        txt.configure(state=tk.DISABLED)

        def accept() -> None:
            try:
                DISCLAIMER_FLAG.parent.mkdir(parents=True, exist_ok=True)
                DISCLAIMER_FLAG.write_text(PRODUCT_VERSION, encoding="utf-8")
            except Exception:
                pass
            win.destroy()

        bf = ttk.Frame(frm)
        bf.pack(fill=tk.X, pady=(10, 0))
        if force_accept:
            ttk.Button(bf, text="동의하고 시작", style="Accent.TButton", command=accept).pack(
                side=tk.RIGHT
            )
        else:
            ttk.Button(bf, text="닫기", command=win.destroy).pack(side=tk.RIGHT)

    def _refresh_stats_line(self) -> None:
        g = today_stats()
        self.var_stats_line.set(
            f"오늘 시도 {g.get('attempts', 0)}/{g.get('max_per_day', 5)}번"
            f"  ·  v{PRODUCT_VERSION}"
        )

    def _apply_weekly_channel(self, ch: dict, *, make_phrase: bool = True) -> None:
        """이번 주 검증 채널 1곳을 폼에 적용."""
        # 제품 URL은 유지 (비어 있으면 범용 문구)
        self.var_site.set(ch.get("site_url") or "")
        self.var_login.set(ch.get("login_url") or "")
        self.var_write.set(ch.get("write_url") or "")
        self.var_board_url.set("")
        self.var_board_name.set(f"이번 주 {ch.get('slot')}순위: {ch.get('name')}")
        self.var_submit.set(False)
        style = ch.get("phrase_style") or "랜덤"
        if style in list_styles():
            self.var_phrase_style.set(style)
        if style in list_template_names():
            self.var_template.set(style)

        if make_phrase:
            profile = self._product_profile
            if profile is None or not getattr(profile, "ok", False):
                url = self.var_product_url.get().strip()
                if url:
                    try:
                        profile = analyze_site(url)
                        self._product_profile = profile
                        self.var_product_summary.set(
                            profile.summary_text().replace("\n", "  |  ")
                        )
                    except Exception as e:
                        self._log(f"제품 분석 실패(범용 문구로 진행): {e}")
                        profile = None
            title, body = generate_post(style, profile=profile)
            self.ent_title.delete(0, tk.END)
            self.ent_title.insert(0, title)
            self.txt_body.delete("1.0", tk.END)
            self.txt_body.insert("1.0", body)

        self._log(f"이번 주 올릴 곳: {ch.get('name')} ({ch.get('days')})")
        self._log(f"  목표: {ch.get('goal')}")
        self._log(
            f"  도움: {support_label(str(ch.get('support') or ''), short=True)} · 올리기 자동 끔"
        )
        for i, item in enumerate(ch.get("checklist") or [], 1):
            self._log(f"  체크{i}. {item}")
        # 작성 화면으로 이동 (사이드바 Write)
        if hasattr(self, "_show_page"):
            try:
                self._show_page("write")
            except Exception:
                pass

    def _show_weekly_channels(self) -> None:
        """이번 주 올릴 곳 선택 창 (앱 테마 팝업)."""
        win = tk.Toplevel(self)
        frm = style_window(
            win,
            self,
            title=WEEKLY_VALIDATION_LABEL,
            geometry="700x580",
            modal=True,
            minsize=(560, 440),
        )
        ttk.Label(
            frm,
            text="이번 주는 이 3곳만 · 한 곳당 주 1~2번 · 올리기는 직접 누르기",
            style="Muted.TLabel",
            wraplength=640,
        ).pack(anchor=tk.W)

        mid = ttk.Frame(frm)
        mid.pack(fill=tk.BOTH, expand=True, pady=8)
        left = ttk.Frame(mid)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        lb = tk.Listbox(left, font=self._F["nav"], height=8)
        style_listbox(lb)
        lb.pack(fill=tk.BOTH, expand=True)
        channels = list(WEEKLY_VALIDATION_CHANNELS)
        for ch in channels:
            lb.insert(
                tk.END,
                f"{ch['slot']}. {ch['name']}  ·  {ch['days']}  ·  {support_label(ch['support'], short=True)}",
            )
        lb.selection_set(0)

        right = ttk.LabelFrame(mid, text=" 자세히 · 할 일 목록 ", padding=8)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))
        detail = scrolledtext.ScrolledText(
            right, wrap=tk.WORD, font=self._F["list_sm"], height=14, width=40
        )
        style_text_widget(detail)
        detail.pack(fill=tk.BOTH, expand=True)

        def show(_e=None) -> None:
            sel = lb.curselection()
            if not sel:
                return
            ch = channels[int(sel[0])]
            lines = [
                f"【{ch['name']}】",
                f"요일: {ch['days']}",
                f"목표: {ch['goal']}",
                f"이유: {ch['why']}",
                f"문구 스타일: {ch['phrase_style']}",
                f"성공 기준: {ch['success_ok']}",
                f"팁: {ch['tip']}",
                f"주의: {ch['caution']}",
                "",
                "체크리스트:",
            ]
            for i, c in enumerate(ch.get("checklist") or [], 1):
                lines.append(f"  {i}. {c}")
            detail.configure(state=tk.NORMAL)
            detail.delete("1.0", tk.END)
            detail.insert("1.0", "\n".join(lines))
            detail.configure(state=tk.DISABLED)

        def apply_ch(and_open_login: bool = False) -> None:
            sel = lb.curselection()
            if not sel:
                return
            ch = channels[int(sel[0])]
            self._apply_weekly_channel(ch, make_phrase=True)
            win.destroy()
            self._show_page("home")
            self._update_next_hint()
            msg = (
                f"「{ch['name']}」을 골랐습니다.\n\n"
                f"홈 화면 ②에 주소가 들어갔습니다.\n"
                f"아이디/비밀번호 넣고 → ③ 브라우저에서 글 쓰기\n"
                f"(올리기는 직접)"
            )
            show_message(self, "올릴 곳 적용", msg, kind="success")
            if and_open_login and ch.get("login_url"):
                self._open_url(ch["login_url"], label=f"{ch['name']} 로그인")
            elif and_open_login and ch.get("site_url"):
                self._open_url(ch["site_url"], label=ch["name"])

        lb.bind("<<ListboxSelect>>", show)
        show()

        plan = scrolledtext.ScrolledText(frm, height=5, wrap=tk.WORD, font=self._F["list_sm"])
        style_text_widget(plan)
        plan.pack(fill=tk.X, pady=(4, 0))
        plan.insert("1.0", weekly_plan_text())
        plan.configure(state=tk.DISABLED)

        btns = ttk.Frame(frm)
        btns.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(
            btns,
            text="적용하고 사이트 열기",
            style="Accent.TButton",
            command=lambda: apply_ch(True),
        ).pack(side=tk.RIGHT)
        ttk.Button(btns, text="화면만 채우기", command=lambda: apply_ch(False)).pack(
            side=tk.RIGHT, padx=6
        )
        ttk.Button(btns, text="닫기", command=win.destroy).pack(side=tk.LEFT)

        self._log(f"{WEEKLY_VALIDATION_LABEL} 창을 열었습니다.")

    def _guard_or_abort(self, data: dict) -> bool:
        gr = check_before_post(
            title=data.get("title", ""),
            body=data.get("body", ""),
            submit=bool(data.get("submit")),
            max_per_day=int(self.var_max_day.get() or DEFAULT_MAX_POSTS_PER_DAY),
            cooldown_minutes=int(self.var_cooldown.get() or DEFAULT_COOLDOWN_MINUTES),
        )
        if not gr.ok:
            show_message(self, "안전 제한", gr.message, kind="warn")
            self._log(f"안전 제한: {gr.message.splitlines()[0]}")
            return False
        if gr.level == "warn":
            if not ask_confirm(self, "주의", gr.message + "\n\n계속할까요?"):
                return False
        return True

    def _on_analyze_product(self) -> None:
        if self._busy:
            return
        url = self.var_product_url.get().strip()
        if not url:
            show_message(self, "확인", "홍보할 내 사이트 주소를 입력하세요.\n예: https://example.com", kind="warn")
            return

        self._set_busy(True)
        self._log(f"사이트 분석 중… {url}")
        self.var_product_summary.set("분석 중… 잠시만 기다려 주세요.")

        def worker() -> None:
            try:
                profile = analyze_site(url)
                self.after(0, lambda p=profile: self._on_product_analyzed(p))
            except Exception as e:
                err = str(e)
                self.after(0, lambda msg=err: self._on_product_analyze_err(msg))

        threading.Thread(target=worker, daemon=True).start()

    def _on_product_analyze_err(self, err: str) -> None:
        self._set_busy(False)
        self.var_product_summary.set(f"분석 실패: {err}")
        self._log(f"분석 실패: {err}")
        show_message(self, "분석 실패", err, kind="error")

    def _on_product_analyzed(self, profile: SiteProfile) -> None:
        self._set_busy(False)
        self._product_profile = profile
        self.var_product_summary.set(profile.summary_text().replace("\n", "  |  "))
        self._log(profile.message)
        for line in profile.summary_text().splitlines():
            self._log(f"  {line}")

        style = self.var_phrase_style.get() or self.var_template.get() or "랜덤"
        title, body = generate_post(style, profile=profile)
        self.ent_title.delete(0, tk.END)
        self.ent_title.insert(0, title)
        self.txt_body.delete("1.0", tk.END)
        self.txt_body.insert("1.0", body)
        self._log(f"홍보 제목·본문 자동 작성 완료 (스타일: {style})")
        self._save_last()
        self._update_next_hint()
        self._show_page("home")
        show_message(
            self,
            "① 완료 · 홍보글 준비됨",
            "제목과 본문을 채워 두었습니다.\n\n"
            "다음(②): 올릴 곳 주소 + 아이디/비밀번호를 입력하세요.\n"
            "그다음(③): 「브라우저에서 글 쓰기」",
            kind="success",
        )

    def _creds_ok(self, need_content: bool = False) -> bool:
        data = self._form_data()
        if not data["site_url"]:
            show_message(self, "확인", "올릴 곳 주소를 입력하세요.\n(「어디에 올릴까」에서 고르거나 직접 입력)", kind="warn")
            return False
        if not data["username"] or not self.var_pass.get():
            show_message(self, "확인", "가입한 아이디와 비밀번호를 입력하세요.", kind="warn")
            return False
        if need_content:
            if not data["title"] or not data["body"]:
                show_message(self, "확인", "제목과 본문을 입력하세요.\n글 양식 또는 「다른 버전 만들기」를 쓸 수 있습니다.", kind="warn")
                return False
        return True

    def _make_job(self, *, auto_pick: bool = False, force_submit: bool | None = None) -> PostJob:
        data = self._form_data()
        return PostJob(
            site_url=data["site_url"],
            username=data["username"],
            password=self.var_pass.get(),
            title=data["title"],
            body=data["body"],
            write_url=data["write_url"],
            login_url=data["login_url"],
            board_url=data["board_url"],
            submit=bool(data["submit"]) if force_submit is None else force_submit,
            headless=False,
            selectors=dict(self._site_selectors or {}),
            auto_pick_board=auto_pick or (
                bool(data.get("auto_pick_board")) and not data["board_url"] and not data["write_url"]
            ),
        )

    def _on_structure_scan(self) -> None:
        if self._busy:
            return
        site = self.var_site.get().strip()
        if not site:
            show_message(self, "확인", "올릴 곳 주소(글을 올릴 사이트)를 입력하세요.\n"
                "가입·캡차·휴대폰 인증은 미리 직접 해 두세요.", kind="warn")
            return
        has_cred = bool(self.var_user.get().strip() and self.var_pass.get())
        warn = (
            "브라우저를 열고, 글 쓰는 칸 위치를 찾습니다.\n\n"
            "· 로그인 칸, 제목·본문 칸, 글쓰기 화면 주소를 찾아 저장합니다\n"
            "· 캡차·휴대폰 인증·2단계 인증은 대신하지 않습니다\n"
            "  (보통 가입할 때 한 번 — 직접 해 주세요)\n"
            "· 카페·사이트 규칙은 직접 확인하세요\n"
        )
        if has_cred:
            warn += "\n아이디·비밀번호가 있어 로그인 후 글쓰기 화면까지 찾아 봅니다."
        else:
            warn += "\n아이디·비번이 없으면 공개된 페이지만 봅니다(정확도가 떨어질 수 있음)."
        if not ask_confirm(self, "글 쓰는 칸 찾기", warn):
            return

        self._save_last(quiet=True)
        self._set_busy(True)
        self.txt_log.delete("1.0", tk.END)
        self._log("글 쓰는 칸 찾기 시작…")
        self.var_structure_summary.set("찾는 중… 브라우저 창을 확인해 주세요.")

        site_url = site
        login_url = self.var_login.get().strip()
        username = self.var_user.get().strip()
        password = self.var_pass.get()

        def worker() -> None:
            try:
                result = scan_site_structure(
                    site_url=site_url,
                    login_url=login_url,
                    username=username,
                    password=password,
                    headless=False,
                    log=self._log,
                )
                self.after(0, lambda r=result: self._on_structure_scanned(r))
            except Exception as e:
                err = str(e)
                self.after(0, lambda msg=err: self._on_structure_scan_err(msg))

        threading.Thread(target=worker, daemon=True).start()

    def _on_structure_scan_err(self, err: str) -> None:
        self._set_busy(False)
        self.var_structure_summary.set(f"칸 찾기 실패: {err}")
        self._log(err)
        show_message(self, "글 쓰는 칸 찾기 실패", err, kind="error")

    def _on_structure_scanned(self, result: StructureScanResult) -> None:
        self._set_busy(False)
        self._structure_scan = result
        self._site_selectors = dict(result.selectors or {})
        if result.login_url and not self.var_login.get().strip():
            self.var_login.set(result.login_url)
        elif result.login_url:
            self.var_login.set(result.login_url)
        if result.write_url:
            self.var_write.set(result.write_url)
        if result.board_url and not self.var_board_url.get().strip():
            self.var_board_url.set(result.board_url)
            self.var_board_name.set("칸 찾기로 추천된 게시판")
        if result.boards_top:
            # BoardCandidate 형태로 보관
            from poster import BoardCandidate

            self._last_boards = [
                BoardCandidate(
                    name=b.get("name", ""),
                    url=b.get("url", ""),
                    score=int(b.get("score") or 0),
                    reason=b.get("reason") or "칸 찾기",
                    write_url=b.get("write_url") or "",
                )
                for b in result.boards_top
            ]

        self.var_structure_summary.set(
            f"신뢰도 {result.confidence}%  ·  선택자 {len(result.selectors)}개  ·  {result.message}"
        )
        for line in result.summary_text().splitlines():
            self._log(line)
        self._save_last(quiet=True)

        extra = ""
        if result.notes:
            extra = "\n\n" + "\n".join(f"· {n}" for n in result.notes[:4])
        show_message(self, "칸 찾기 완료" if result.ok else "일부만 찾음", f"{result.message}\n\n"
            f"신뢰도: {result.confidence}%\n"
            f"선택자: {len(result.selectors)}개\n"
            f"글쓰기 화면 주소: {result.write_url or '(없음)'}\n"
            f"{extra}\n\n"
            "「설정 저장」을 누르면 이 사이트 설정을 기억해 두고\n"
            "다음에 글 쓰기가 더 잘 됩니다.", kind="info")

    def _show_structure_detail(self) -> None:
        if not self._structure_scan:
            show_message(self, "글 쓰는 칸 찾기", "아직 결과가 없습니다.\n올릴 곳 주소를 넣고 「글 쓰는 칸 찾기」를 눌러 주세요.", kind="info")
            return
        win = tk.Toplevel(self)
        frm = style_window(
            win,
            self,
            title="글 쓰는 칸 찾기 결과",
            geometry="560x480",
            modal=True,
            minsize=(420, 360),
        )
        txt = scrolledtext.ScrolledText(frm, wrap=tk.WORD, height=22)
        style_text_widget(txt)
        txt.pack(fill=tk.BOTH, expand=True)
        txt.insert("1.0", self._structure_scan.summary_text())
        txt.configure(state=tk.DISABLED)
        ttk.Button(frm, text="닫기", style="Secondary.TButton", command=win.destroy).pack(
            pady=(10, 0)
        )

    def _on_find_boards(self) -> None:
        if self._busy:
            return
        if not self._creds_ok(need_content=False):
            return
        if not ask_confirm(self, "게시판 자동 찾기", "브라우저를 열고 로그인한 뒤,\n"
            "홍보에 맞는 게시판·카테고리 링크를 점수순으로 찾습니다.\n\n"
            "· 본인 계정만 사용\n"
            "· 캡차가 나오면 직접 해결\n"
            "· 찾은 뒤 목록에서 게시판을 고르세요",):
            return

        self._save_last()
        job = self._make_job(auto_pick=False)
        self._set_busy(True)
        self.txt_log.delete("1.0", tk.END)
        self._log("게시판 자동 탐색 시작…")

        def worker() -> None:
            try:
                result = discover_boards(job, log=self._log)
                self.after(0, lambda r=result: self._on_boards_found(r))
            except Exception as e:
                err = str(e)
                self.after(0, lambda msg=err: self._on_boards_found_err(msg))

        threading.Thread(target=worker, daemon=True).start()

    def _on_boards_found_err(self, err: str) -> None:
        self._set_busy(False)
        self._log(err)
        show_message(self, "탐색 실패", err, kind="error")

    def _on_boards_found(self, result) -> None:
        self._set_busy(False)
        self._log(result.message)
        if not result.ok or not result.boards:
            show_message(self, "게시판 없음", result.message
                + "\n\n팁: 사이트 주소에 커뮤니티 메인/게시판 목록 주소를 넣고 다시 시도하거나,\n"
                "글쓰기 페이지 주소를 직접 지정하세요.", kind="warn")
            return
        self._last_boards = list(result.boards)
        # 최고점 자동 미리 선택
        best = result.boards[0]
        self._apply_board(best)
        self._show_board_picker()

    def _show_board_picker(self) -> None:
        if not self._last_boards:
            show_message(self, "목록 없음", "아직 찾은 게시판이 없습니다.\n먼저 「게시판 자동 찾기」를 실행하세요.", kind="info")
            return

        win = tk.Toplevel(self)
        frm = style_window(
            win,
            self,
            title="게시판 고르기",
            geometry="680x480",
            modal=True,
            minsize=(520, 360),
        )
        ttk.Label(
            frm,
            text="점수가 높을수록 홍보 게시판으로 비교적 맞는 이름·주소입니다. "
            "공지·관리자·홍보금지 게시판은 피하세요. 규정은 직접 확인.",
            wraplength=640,
            style="Muted.TLabel",
        ).pack(anchor=tk.W, pady=(0, 8))

        lb = tk.Listbox(frm, font=self._F["list"], height=14)
        style_listbox(lb)
        lb.pack(fill=tk.BOTH, expand=True)
        boards = self._last_boards
        for b in boards:
            line = f"[{b.score:3d}] {b.name}  ·  {b.reason}"
            lb.insert(tk.END, line)
        lb.selection_set(0)

        detail = tk.StringVar()
        ttk.Label(
            frm, textvariable=detail, wraplength=640, style="Muted.TLabel"
        ).pack(anchor=tk.W, pady=6)

        def update_detail(_e=None) -> None:
            sel = lb.curselection()
            if not sel:
                return
            b = boards[int(sel[0])]
            detail.set(
                f"목록: {b.url}\n"
                f"글쓰기 추정: {b.write_url or '(게시판 들어가서 글쓰기 버튼 탐색)'}"
            )

        lb.bind("<<ListboxSelect>>", update_detail)
        update_detail()

        def choose_only() -> None:
            sel = lb.curselection()
            if not sel:
                return
            self._apply_board(boards[int(sel[0])])
            win.destroy()
            show_message(self, "선택됨", "게시판을 적용했습니다.\n"
                "제목·본문을 확인한 뒤\n"
                "「브라우저에서 글 쓰기」또는「로그인 후 글 칸에 넣기」를 누르세요.",
                kind="info",
            )

        def choose_and_post() -> None:
            sel = lb.curselection()
            if not sel:
                return
            self._apply_board(boards[int(sel[0])])
            win.destroy()
            self._on_run()

        btns = ttk.Frame(frm)
        btns.pack(fill=tk.X, pady=(4, 0))
        ttk.Button(btns, text="이 게시판만 적용", command=choose_only).pack(side=tk.LEFT)
        ttk.Button(
            btns,
            text="이 게시판으로 글 칸에 넣기",
            style="Accent.TButton",
            command=choose_and_post,
        ).pack(side=tk.RIGHT)
        ttk.Button(btns, text="닫기", command=win.destroy).pack(side=tk.RIGHT, padx=6)

    def _on_smart_post(self) -> None:
        """게시판 자동 선택(필요 시) + 로그인 + 작성 (+선택 시 등록)."""
        if self._busy:
            return
        if not self._creds_ok(need_content=True):
            return
        data = self._form_data()
        if not self._guard_or_abort(data):
            return

        has_board = bool(self.var_board_url.get().strip() or self.var_write.get().strip())
        auto = bool(self.var_auto_pick.get()) or not has_board
        submit = bool(self.var_submit.get())

        warn = (
            f"【{PRODUCT_NAME} · 로그인 후 글 칸에 넣기】\n\n"
            "브라우저를 열고 아래를 순서대로 합니다.\n\n"
            "1) 로그인\n"
            f"2) {'고른 게시판 사용' if has_board and not auto else '맞는 게시판 찾아서 고르기'}\n"
            "3) 글쓰기 화면에 제목·본문 넣기\n"
            f"4) {'올리기 버튼까지 누르기' if submit else '입력까지만 → 올리기는 직접 (권장)'}\n\n"
            "· 본인 계정만 사용 · 카페/사이트 규칙 지키기\n"
            "· 캡차·2단계 인증은 직접 하기\n"
            "· 하루 횟수·같은 글 반복 제한이 있습니다\n"
        )
        if submit:
            warn += "\n※ 올리기까지 자동입니다. 내용·게시판이 맞는지 확인하세요."

        if not ask_confirm(self, "로그인 후 글 칸에 넣기", warn):
            return

        self._save_last(quiet=True)
        job = self._make_job(
            auto_pick=auto and not has_board,
            force_submit=submit,
        )
        if has_board and not job.auto_pick_board:
            job.board_url = self.var_board_url.get().strip()

        self._set_busy(True)
        self.txt_log.delete("1.0", tk.END)
        self._log("로그인 후 글 칸에 넣기 시작…")

        def worker() -> None:
            try:
                result = run_post(job, log=self._log)
                self.after(
                    0,
                    lambda r=result: self._done(
                        r.ok,
                        r.message,
                        r.final_url,
                        board_name=r.board_name,
                        board_url=r.board_url,
                    ),
                )
            except Exception as e:
                err = str(e)
                self.after(0, lambda msg=err: self._done(False, msg, ""))

        threading.Thread(target=worker, daemon=True).start()

    def _save_last(self, quiet: bool = False) -> None:
        CREDS_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = self._form_data()
        if not data["save_password"]:
            data["password"] = ""
        else:
            data["password"] = prepare_password_for_save(self.var_pass.get(), save=True)
        CREDS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        self._log(
            f"양식 저장: {CREDS_PATH}"
            + (" (비밀번호 암호화)" if data.get("password") else "")
        )
        if not quiet:
            show_message(self, "저장", "양식을 이 PC에 저장했습니다.\n비밀번호는 암호화되어 저장됩니다.", kind="info")

    def _load_last(self) -> None:
        if not CREDS_PATH.exists():
            return
        try:
            data = json.loads(CREDS_PATH.read_text(encoding="utf-8"))
            self._apply_data(data)
            self._log("이전 양식을 불러왔습니다.")
        except Exception as e:
            self._log(f"이전 양식 로드 실패: {e}")

    def _save_profile(self) -> None:
        data = self._form_data()
        if not data["site_url"]:
            show_message(self, "확인", "사이트 주소를 입력하세요.", kind="warn")
            return
        name = data["site_url"]
        payload = {
            "name": name,
            "site_url": data["site_url"],
            "login_url": data["login_url"],
            "write_url": data["write_url"],
            "board_url": data.get("board_url", ""),
            "board_name": data.get("board_name", ""),
            "username": data["username"],
            "selectors": dict(self._site_selectors or {}),
            "structure_scan": self._structure_scan.to_dict() if self._structure_scan else None,
        }
        save_site_profile(str(PROFILES_PATH), payload)
        self._log(f"프로필 저장: {PROFILES_PATH} (선택자 {len(self._site_selectors or {})}개)")
        show_message(self, "저장", "사이트 프로필을 저장했습니다.\n"
            f"구조 선택자 {len(self._site_selectors or {})}개 포함 (비밀번호 제외)", kind="info")

    def _load_profile_dialog(self) -> None:
        profiles = load_site_profiles(str(PROFILES_PATH))
        if not profiles:
            show_message(self, "프로필", "저장된 프로필이 없습니다.", kind="info")
            return
        win = tk.Toplevel(self)
        frm = style_window(
            win,
            self,
            title="설정 불러오기",
            geometry="440x320",
            modal=True,
            minsize=(360, 260),
        )
        lb = tk.Listbox(frm, font=self._F["list"])
        style_listbox(lb)
        lb.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        keys = list(profiles.keys())
        for k in keys:
            lb.insert(tk.END, k)

        def choose() -> None:
            sel = lb.curselection()
            if not sel:
                return
            key = keys[sel[0]]
            self._apply_data(profiles[key])
            # 프로필에 선택자만 있는 경우
            prof = profiles[key]
            if prof.get("selectors") and not self._site_selectors:
                self._site_selectors = dict(prof["selectors"])
            win.destroy()
            self._log(f"설정 불러옴: {key} (입력 칸 {len(self._site_selectors or {})}개)")

        ttk.Button(frm, text="불러오기", style="Accent.TButton", command=choose).pack(
            side=tk.RIGHT
        )

    def _on_run(self) -> None:
        if self._busy:
            return
        if not self._creds_ok(need_content=True):
            return
        data = self._form_data()
        if not self._guard_or_abort(data):
            return

        warn = (
            f"【{PRODUCT_NAME}】브라우저를 열고 로그인·글 쓰기를 시도합니다.\n\n"
            "· 본인 계정만 사용하세요.\n"
            "· 카페/사이트 광고·도배 규칙을 지키세요.\n"
            "· 캡차가 나오면 직접 해결하세요.\n"
        )
        if data.get("board_url"):
            warn += f"\n게시판: {data.get('board_name') or data['board_url']}\n"
        if data["submit"]:
            warn += "\n※ 올리기 버튼까지 자동으로 누릅니다. 내용이 맞는지 확인하세요."
        else:
            warn += "\n글 쓴 뒤 「올리기」는 직접 눌러 주세요. (권장)"

        if not ask_confirm(self, "글 쓰기 확인", warn):
            return

        self._save_last(quiet=True)
        job = self._make_job(
            auto_pick=bool(data.get("auto_pick_board"))
            and not data.get("board_url")
            and not data.get("write_url"),
        )

        self._set_busy(True)
        self.txt_log.delete("1.0", tk.END)
        self._log("작업 시작…")

        def worker() -> None:
            try:
                result = run_post(job, log=self._log)
                self.after(
                    0,
                    lambda r=result: self._done(
                        r.ok,
                        r.message,
                        r.final_url,
                        board_name=r.board_name,
                        board_url=r.board_url,
                    ),
                )
            except Exception as e:
                err = str(e)
                self.after(0, lambda msg=err: self._done(False, msg, ""))

        threading.Thread(target=worker, daemon=True).start()

    def _done(
        self,
        ok: bool,
        message: str,
        final_url: str,
        board_name: str = "",
        board_url: str = "",
    ) -> None:
        self._set_busy(False)
        self._log(message)
        data = self._form_data()
        # 가드레일·검증 로그
        try:
            record_attempt(
                title=data.get("title", ""),
                body=data.get("body", ""),
                site_url=data.get("site_url", ""),
                ok=ok,
                action="submit" if data.get("submit") else "write",
            )
            log_post_attempt(
                product_url=data.get("product_url", ""),
                community_url=data.get("site_url", ""),
                board_name=board_name or data.get("board_name", ""),
                title=data.get("title", ""),
                ok=ok,
                message=message,
                final_url=final_url,
                submit=bool(data.get("submit")),
                validation_mode=bool(self.var_validation.get()),
            )
        except Exception as e:
            self._log(f"기록 실패: {e}")
        self._refresh_stats_line()

        if board_name or board_url:
            self._log(f"사용 게시판: {board_name or ''} {board_url or ''}".strip())
            if board_url and not self.var_board_url.get().strip():
                self.var_board_url.set(board_url)
                if board_name:
                    self.var_board_name.set(board_name)
        if final_url:
            self._log(f"최종 주소: {final_url}")
        if ok:
            # 작성만 성공 ≠ 사이트에 발행됨
            title = "작성 보조 완료" if "올리기" in message or "칸에 넣" in message else "완료"
            show_message(self, title, message, kind="success")
        else:
            show_message(self, "글 자동 작성 실패", message, kind="error")


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()

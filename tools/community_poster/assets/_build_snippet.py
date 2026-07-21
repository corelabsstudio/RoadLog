# New App._build + _show_page methods (spliced into app.py)

BUILD_METHODS = r'''
    def _build(self) -> None:
        self._nav_btns: dict[str, ttk.Button] = {}
        self._pages: dict[str, ttk.Frame] = {}
        self._page_canvas: dict[str, tk.Canvas] = {}
        self._current_page = "overview"

        # Vars used across pages (must exist before building forms)
        self.var_site = tk.StringVar()
        self.var_login = tk.StringVar()
        self.var_write = tk.StringVar()
        self.var_user = tk.StringVar()
        self.var_pass = tk.StringVar()
        self.var_save_pw = tk.BooleanVar(value=False)
        self.var_submit = tk.BooleanVar(value=DEFAULT_SUBMIT_ENABLED)
        self.var_template = tk.StringVar(value=list_template_names()[0])
        self.var_phrase_style = tk.StringVar(value=list_styles()[0])

        shell = ttk.Frame(self, style="App.TFrame")
        shell.pack(fill=tk.BOTH, expand=True)

        # ===== TOP BAR (slim) =====
        header = ttk.Frame(shell, style="Header.TFrame", padding=(16, 12))
        header.pack(fill=tk.X)
        head_left = ttk.Frame(header, style="Header.TFrame")
        head_left.pack(side=tk.LEFT, fill=tk.X, expand=True)
        brand_row = ttk.Frame(head_left, style="Header.TFrame")
        brand_row.pack(anchor=tk.W)
        ttk.Label(brand_row, text=PRODUCT_DISPLAY_NAME, style="Brand.TLabel").pack(side=tk.LEFT)
        ttk.Label(brand_row, text=f"  v{PRODUCT_VERSION}", style="HeaderMuted.TLabel").pack(
            side=tk.LEFT, padx=(6, 0), pady=(4, 0)
        )
        ttk.Label(head_left, textvariable=self.var_stats_line, style="Stat.TLabel").pack(
            anchor=tk.W, pady=(6, 0)
        )
        head_right = ttk.Frame(header, style="Header.TFrame")
        head_right.pack(side=tk.RIGHT)
        ttk.Button(
            head_right, text="사용 방법", style="Ghost.TButton", command=self._show_help
        ).pack(side=tk.LEFT, padx=3)
        ttk.Button(
            head_right, text="면책", style="Ghost.TButton", command=self._show_disclaimer_only
        ).pack(side=tk.LEFT, padx=3)

        tk.Frame(shell, bg=ACCENT, height=2).pack(fill=tk.X)

        # ===== BODY: sidebar + main =====
        body = ttk.Frame(shell, style="App.TFrame")
        body.pack(fill=tk.BOTH, expand=True)

        # --- Sidebar ---
        side = ttk.Frame(body, style="Sidebar.TFrame", width=200, padding=(12, 16))
        side.pack(side=tk.LEFT, fill=tk.Y)
        side.pack_propagate(False)

        ttk.Label(side, text="NAVIGATION", style="SidebarMuted.TLabel").pack(
            anchor=tk.W, pady=(0, 10)
        )

        nav_items = [
            ("overview", "Overview", "개요 · 정책 · 제품"),
            ("write", "Write", "커뮤니티 · 문구 · 게시"),
            ("validate", "Validate", "검증 · 채널 · 지표"),
        ]
        for key, title, sub in nav_items:
            btn = ttk.Button(
                side,
                text=f"  {title}",
                style="Nav.TButton",
                command=lambda k=key: self._show_page(k),
            )
            btn.pack(fill=tk.X, pady=2)
            self._nav_btns[key] = btn
            ttk.Label(side, text=f"    {sub}", style="SidebarMuted.TLabel").pack(
                anchor=tk.W, pady=(0, 6)
            )

        ttk.Separator(side, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=12)
        ttk.Label(side, text="QUICK", style="SidebarMuted.TLabel").pack(anchor=tk.W, pady=(0, 8))
        ttk.Button(
            side,
            text="  이번 주 3채널",
            style="Nav.TButton",
            command=self._show_weekly_channels,
        ).pack(fill=tk.X, pady=2)
        ttk.Button(
            side,
            text="  채널 추천",
            style="Nav.TButton",
            command=self._open_site_recommend,
        ).pack(fill=tk.X, pady=2)

        ttk.Frame(side, style="Sidebar.TFrame").pack(fill=tk.BOTH, expand=True)
        ttk.Label(side, text=PRODUCT_TAGLINE, style="SidebarMuted.TLabel", wraplength=160).pack(
            anchor=tk.W, pady=(8, 0)
        )
        ttk.Label(side, text="local · no cloud API", style="SidebarMuted.TLabel").pack(
            anchor=tk.W, pady=(4, 0)
        )

        # --- Main column ---
        main = ttk.Frame(body, style="App.TFrame")
        main.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        pages_host = ttk.Frame(main, style="App.TFrame")
        pages_host.pack(fill=tk.BOTH, expand=True)

        self._pages["overview"] = self._build_page_overview(pages_host)
        self._pages["write"] = self._build_page_write(pages_host)
        self._pages["validate"] = self._build_page_validate(pages_host)

        # Shared activity log dock
        log_dock = make_card(main, "Activity log", None)
        log_dock.pack(fill=tk.X, padx=16, pady=(0, 12))
        self.txt_log = scrolledtext.ScrolledText(log_dock, height=5, wrap=tk.WORD)
        style_log_widget(self.txt_log)
        self.txt_log.pack(fill=tk.X, expand=False)

        self._show_page("overview")

    def _make_scroll_page(self, parent: ttk.Frame) -> tuple[ttk.Frame, tk.Canvas]:
        wrap = ttk.Frame(parent, style="App.TFrame")
        canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0, bd=0)
        vsb = ttk.Scrollbar(wrap, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        inner = ttk.Frame(canvas, style="App.TFrame", padding=(20, 16))
        win_id = canvas.create_window((0, 0), window=inner, anchor=tk.NW)

        def on_frame_cfg(_e=None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def on_canvas_cfg(e) -> None:
            canvas.itemconfigure(win_id, width=e.width)

        inner.bind("<Configure>", on_frame_cfg)
        canvas.bind("<Configure>", on_canvas_cfg)

        def wheel(e) -> None:
            # only scroll active page canvas
            if canvas.winfo_ismapped():
                canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

        canvas.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", wheel))
        canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))
        return wrap, canvas, inner  # type: ignore[return-value]

    def _show_page(self, key: str) -> None:
        if key not in self._pages:
            return
        self._current_page = key
        for k, fr in self._pages.items():
            if k == key:
                fr.pack(fill=tk.BOTH, expand=True)
            else:
                fr.pack_forget()
        for k, btn in self._nav_btns.items():
            btn.configure(style="NavActive.TButton" if k == key else "Nav.TButton")
        # refresh validate page metrics when opened
        if key == "validate" and hasattr(self, "_refresh_validate_panel"):
            try:
                self._refresh_validate_panel()
            except Exception:
                pass
        titles = {
            "overview": "Overview",
            "write": "Write",
            "validate": "Validate",
        }
        self._log(f"페이지: {titles.get(key, key)}")

    def _build_page_overview(self, parent: ttk.Frame) -> ttk.Frame:
        wrap, _canvas, frm = self._make_scroll_page(parent)  # type: ignore[misc]
        pad = {"padx": 0, "pady": (0, 12)}

        hero = make_card(frm, "ReachKit workspace", None)
        hero.pack(fill=tk.X, **pad)
        ttk.Label(
            hero,
            text=PRODUCT_TAGLINE,
            style="Surface.TLabel",
        ).pack(anchor=tk.W)
        ttk.Label(
            hero,
            text="사이드바에서 Write로 작성하고, Validate에서 제품 검증 지표를 확인하세요.",
            style="SurfaceMuted.TLabel",
            wraplength=720,
        ).pack(anchor=tk.W, pady=(6, 0))
        row = ttk.Frame(hero)
        row.pack(fill=tk.X, pady=(12, 0))
        ttk.Button(
            row, text="Write로 이동", style="Accent.TButton", command=lambda: self._show_page("write")
        ).pack(side=tk.LEFT)
        ttk.Button(
            row,
            text="Validate로 이동",
            style="Secondary.TButton",
            command=lambda: self._show_page("validate"),
        ).pack(side=tk.LEFT, padx=8)
        ttk.Button(
            row, text="이번 주 3채널", style="Ghost.TButton", command=self._show_weekly_channels
        ).pack(side=tk.LEFT)

        g_mode = make_card(frm, "Policy & Guardrails", "01")
        g_mode.pack(fill=tk.X, **pad)
        rowm = ttk.Frame(g_mode)
        rowm.pack(fill=tk.X)
        ttk.Checkbutton(
            rowm,
            text="제품 검증 모드 (성과 로그 기록)",
            variable=self.var_validation,
            command=self._on_toggle_validation,
        ).pack(side=tk.LEFT)
        ttk.Label(
            rowm,
            text=f"  ·  일일 {DEFAULT_MAX_POSTS_PER_DAY}회  ·  쿨다운 {DEFAULT_COOLDOWN_MINUTES}분  ·  등록 자동 OFF",
            style="SurfaceMuted.TLabel",
        ).pack(side=tk.LEFT, padx=8)
        ttk.Label(
            g_mode,
            text=DISCLAIMER_SHORT,
            wraplength=720,
            style="SurfaceMuted.TLabel",
        ).pack(anchor=tk.W, pady=(10, 0))

        g_prod = make_card(frm, "Product URL", "02")
        g_prod.pack(fill=tk.X, **pad)
        ttk.Label(
            g_prod,
            text="검증: 제품 URL  ·  판매: 고객 사이트 URL → 분석 후 홍보 문구 생성",
            wraplength=720,
            style="SurfaceMuted.TLabel",
        ).pack(anchor=tk.W)
        prow = ttk.Frame(g_prod)
        prow.pack(fill=tk.X, pady=(10, 6))
        ttk.Label(prow, text="Product URL", width=14, style="Surface.TLabel").pack(side=tk.LEFT)
        ttk.Entry(prow, textvariable=self.var_product_url).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=8
        )
        self.btn_analyze = ttk.Button(
            prow,
            text="분석 + 홍보글 생성",
            style="Accent.TButton",
            command=self._on_analyze_product,
        )
        self.btn_analyze.pack(side=tk.LEFT, padx=(4, 0))
        ttk.Button(
            prow, text="제품", style="Secondary.TButton", command=self._fill_roadlog_example
        ).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Label(
            g_prod,
            textvariable=self.var_product_summary,
            wraplength=720,
            style="SurfaceMuted.TLabel",
        ).pack(anchor=tk.W, pady=(4, 0))

        return wrap

    def _build_page_write(self, parent: ttk.Frame) -> ttk.Frame:
        wrap, _canvas, frm = self._make_scroll_page(parent)  # type: ignore[misc]
        pad = {"padx": 0, "pady": (0, 12)}

        g1 = make_card(frm, "Community target", "03")
        g1.pack(fill=tk.X, **pad)
        self._row_url(g1, 0, "Community URL *", self.var_site, width=58)
        self._row_url(g1, 1, "Login URL", self.var_login, width=58)
        self._row_url(g1, 2, "Write URL", self.var_write, width=58)
        self._row(g1, 3, "Username *", self.var_user, width=40)
        self._row(g1, 4, "Password *", self.var_pass, width=40, show="*")

        rec_row = ttk.Frame(g1)
        rec_row.grid(row=5, column=0, columnspan=2, sticky=tk.EW, pady=(10, 4))
        ttk.Button(
            rec_row,
            text="채널 추천",
            style="Secondary.TButton",
            command=self._open_site_recommend,
        ).pack(side=tk.LEFT)
        ttk.Button(
            rec_row,
            text="이번 주 3채널",
            style="Ghost.TButton",
            command=self._show_weekly_channels,
        ).pack(side=tk.LEFT, padx=6)
        ttk.Label(
            rec_row,
            text="가이드형  ·  규정 준수 필수",
            style="SurfaceMuted.TLabel",
        ).pack(side=tk.LEFT, padx=10)

        opt = ttk.Frame(g1)
        opt.grid(row=6, column=0, columnspan=2, sticky=tk.W, pady=4)
        ttk.Checkbutton(
            opt, text="비밀번호 암호화 저장 (DPAPI)", variable=self.var_save_pw
        ).pack(side=tk.LEFT, padx=(0, 16))
        ttk.Checkbutton(
            opt, text="등록까지 자동 (비권장)", variable=self.var_submit
        ).pack(side=tk.LEFT)

        g_board = make_card(frm, "Board discovery & smart write", "04")
        g_board.pack(fill=tk.X, **pad)
        ttk.Label(
            g_board,
            text="로그인 후 적합 게시판을 점수순으로 찾고 작성까지 보조합니다. CAPTCHA·등록은 직접.",
            wraplength=720,
            style="SurfaceMuted.TLabel",
        ).pack(anchor=tk.W)
        br = ttk.Frame(g_board)
        br.pack(fill=tk.X, pady=(10, 6))
        ttk.Label(br, text="Selected board", width=14, style="Surface.TLabel").pack(side=tk.LEFT)
        ttk.Label(br, textvariable=self.var_board_name, style="SurfaceMuted.TLabel").pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )
        btns_b = ttk.Frame(g_board)
        btns_b.pack(fill=tk.X, pady=(4, 0))
        self.btn_find_boards = ttk.Button(
            btns_b,
            text="게시판 자동 찾기",
            style="Secondary.TButton",
            command=self._on_find_boards,
        )
        self.btn_find_boards.pack(side=tk.LEFT)
        ttk.Button(
            btns_b, text="목록 다시 보기", style="Ghost.TButton", command=self._show_board_picker
        ).pack(side=tk.LEFT, padx=6)
        ttk.Checkbutton(
            btns_b, text="미지정 시 최고점 자동 선택", variable=self.var_auto_pick
        ).pack(side=tk.LEFT, padx=10)
        self.btn_smart = ttk.Button(
            btns_b, text="스마트 작성", style="Accent.TButton", command=self._on_smart_post
        )
        self.btn_smart.pack(side=tk.RIGHT)

        g2 = make_card(frm, "Title & body", "05")
        g2.pack(fill=tk.BOTH, expand=True, **pad)
        top = ttk.Frame(g2)
        top.pack(fill=tk.X)
        ttk.Label(top, text="Template", style="Surface.TLabel").pack(side=tk.LEFT)
        cb = ttk.Combobox(
            top,
            textvariable=self.var_template,
            values=list_template_names(),
            state="readonly",
            width=16,
        )
        cb.pack(side=tk.LEFT, padx=8)
        cb.bind("<<ComboboxSelected>>", lambda e: self._apply_template())
        ttk.Button(top, text="적용", style="Secondary.TButton", command=self._apply_template).pack(
            side=tk.LEFT
        )

        top2 = ttk.Frame(g2)
        top2.pack(fill=tk.X, pady=(10, 0))
        ttk.Label(top2, text="Rewrite", style="Surface.TLabel").pack(side=tk.LEFT)
        cb2 = ttk.Combobox(
            top2,
            textvariable=self.var_phrase_style,
            values=list_styles(),
            state="readonly",
            width=14,
        )
        cb2.pack(side=tk.LEFT, padx=8)
        ttk.Button(
            top2,
            text="다른 버전 만들기",
            style="Accent.TButton",
            command=self._generate_free_phrase,
        ).pack(side=tk.LEFT)
        ttk.Label(top2, text="로컬 조합 · API 없음", style="SurfaceMuted.TLabel").pack(
            side=tk.LEFT, padx=10
        )

        ttk.Label(g2, text="Title", style="Surface.TLabel").pack(anchor=tk.W, pady=(12, 4))
        self.ent_title = ttk.Entry(g2)
        self.ent_title.pack(fill=tk.X)

        ttk.Label(g2, text="Body", style="Surface.TLabel").pack(anchor=tk.W, pady=(12, 4))
        self.txt_body = scrolledtext.ScrolledText(g2, height=12, wrap=tk.WORD)
        style_text_widget(self.txt_body)
        self.txt_body.pack(fill=tk.BOTH, expand=True)

        act = ttk.Frame(frm, style="App.TFrame")
        act.pack(fill=tk.X, pady=(4, 8))
        self.btn_run = ttk.Button(
            act, text="브라우저에서 작성하기", style="Accent.TButton", command=self._on_run
        )
        self.btn_run.pack(side=tk.LEFT)
        ttk.Button(act, text="프로필 저장", style="Secondary.TButton", command=self._save_profile).pack(
            side=tk.LEFT, padx=8
        )
        ttk.Button(
            act, text="프로필 불러오기", style="Ghost.TButton", command=self._load_profile_dialog
        ).pack(side=tk.LEFT)
        ttk.Button(act, text="양식 저장", style="Ghost.TButton", command=self._save_last).pack(
            side=tk.RIGHT
        )

        return wrap

    def _build_page_validate(self, parent: ttk.Frame) -> ttk.Frame:
        wrap, _canvas, frm = self._make_scroll_page(parent)  # type: ignore[misc]
        pad = {"padx": 0, "pady": (0, 12)}

        g = make_card(frm, "Validation dashboard", None)
        g.pack(fill=tk.BOTH, expand=True, **pad)
        ttk.Label(
            g,
            text="제품 검증  ·  이번 주 3채널만  ·  목표: 시도 5회+ · 성공률 50%+",
            style="SurfaceMuted.TLabel",
            wraplength=720,
        ).pack(anchor=tk.W)

        btns = ttk.Frame(g)
        btns.pack(fill=tk.X, pady=(10, 8))
        ttk.Button(
            btns, text="이번 주 3채널 열기", style="Accent.TButton", command=self._show_weekly_channels
        ).pack(side=tk.LEFT)
        ttk.Button(
            btns, text="팝업 대시보드", style="Secondary.TButton", command=self._show_validation_dashboard
        ).pack(side=tk.LEFT, padx=8)
        ttk.Button(
            btns, text="새로고침", style="Ghost.TButton", command=lambda: self._refresh_validate_panel()
        ).pack(side=tk.LEFT)

        self.txt_validate = scrolledtext.ScrolledText(g, height=18, wrap=tk.WORD)
        style_text_widget(self.txt_validate)
        self.txt_validate.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

        conv = ttk.Frame(g)
        conv.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(
            conv,
            text="전환 메모 추가",
            style="Accent.TButton",
            command=self._validate_add_conversion,
        ).pack(side=tk.LEFT)
        ttk.Button(
            conv, text="일반 메모", style="Secondary.TButton", command=self._validate_add_note
        ).pack(side=tk.LEFT, padx=8)

        def _refresh() -> None:
            goals = "\n".join(f"  □ {x}" for x in ROADLOG_VALIDATION_GOALS)
            body = summary_text() + "\n\n" + weekly_plan_text() + "\n\n【검증 목표】\n" + goals
            self.txt_validate.configure(state=tk.NORMAL)
            self.txt_validate.delete("1.0", tk.END)
            self.txt_validate.insert("1.0", body)
            self.txt_validate.configure(state=tk.DISABLED)
            self._refresh_stats_line()

        self._refresh_validate_panel = _refresh  # type: ignore[method-assign]
        _refresh()
        return wrap

    def _validate_add_conversion(self) -> None:
        note = simple_prompt(self, "전환 메모", "예: 블라인드 글 후 Free 가입 1건")
        if note:
            log_conversion(note, source=self.var_site.get().strip())
            self._refresh_stats_line()
            if hasattr(self, "_refresh_validate_panel"):
                self._refresh_validate_panel()
            self._log(f"전환 메모 저장: {note}")

    def _validate_add_note(self) -> None:
        note = simple_prompt(self, "검증 메모", "느낀 점·버그·채널 반응 등")
        if note:
            log_note(note)
            if hasattr(self, "_refresh_validate_panel"):
                self._refresh_validate_panel()
            self._log(f"메모: {note}")

'''

/* RoadLog premium SPA */
(() => {
  const EXAMPLE_FORM = {
    vehicleNumber: "12가3456",
    odoStart: "45230.5",
    odoEnd: "45267.5",
    lunchPlace: "강남역 근처 논밭골",
    morningPlaces: "강남 고객사 미팅",
    afternoonPlaces: "역삼 협력사 방문",
    rawText: "",
  };
  const EXAMPLE_FIELD = {
    department: "영업1팀",
    summary: "강남·판교 고객 방문 및 견적 협의",
    visits:
      "강남 A사 — 계약 조건 협의 / 견적 재요청 예정\n판교 B사 — 제품 데모 / 다음 주 본사 방문 조율",
    next: "목요일까지 견적서 송부, 금요일 팔로업 콜",
    memo: "",
  };

  const TOKEN_KEY = "rl_token";
  const STAMPS_KEY_PREFIX = "rl_stamps_";
  const LAST_LOG_KEY = "rl_last_log";
  const REMEMBER_KEY = "rl_remember_session";
  /** 로그인 폼 자동입력 (이메일·비밀번호) — 이 기기 localStorage */
  const SAVED_LOGIN_KEY = "rl_saved_login";
  const LANG_KEY = "rl_lang";
  /** 관리자 전용: UI를 Pro/Enterprise/Free 사용자처럼 미리보기 */
  const VIEW_AS_KEY = "rl_admin_view_as";

  const state = {
    token: localStorage.getItem(TOKEN_KEY) || "",
    user: null,
    usage: 0,
    limit: 10,
    settings: null,
    lastLog: null,
    meta: null,
    styleProfile: null,
    stamps: [],
    lang: localStorage.getItem(LANG_KEY) || "ko",
    dict: {},
    /** admin | pro | enterprise | free — 실제 is_admin 일 때만 적용 */
    viewAs: localStorage.getItem(VIEW_AS_KEY) || "admin",
    /** driving | field — 일지 작성 유형 */
    reportMode: "driving",
  };

  // ── i18n ──────────────────────────────────────────
  /** JSON 로드 실패·지연 시에도 키가 화면에 안 나오게 하는 기본 문구 */
  const I18N_FALLBACK = {
    ko: {
      "nav.home": "홈",
      "nav.features": "기능",
      "nav.create": "일지 작성",
      "nav.pricing": "요금제",
      "nav.contact": "문의",
      "nav.about": "About",
      "nav.style": "회사 서식",
      "nav.settings": "설정",
      "nav.admin": "관리자",
      "nav.install": "앱 다운로드",
      "nav.login": "로그인",
      "nav.logout": "로그아웃",
      "nav.start": "시작하기",
      "nav.write_log": "일지 작성",
      "nav.menu": "메뉴",
      "create.generate": "✨ AI로 일지 작성",
      "create.generate_field": "✨ AI로 외근일지 작성",
      "create.title": "운행일지 작성",
      "create.title_field": "외근·출장 일지",
      "create.sub": "퀵 스탬프로 위치·시간을 찍고, 주행거리만 보완하면 AI가 일지를 완성합니다.",
      "create.sub_field": "오늘 방문한 곳과 결과만 적으면 AI가 회사 제출용 외근일지로 정리합니다.",
      "create.form_title": "오늘 운행 정보",
      "create.form_title_field": "오늘 외근 정보",
      "create.mode_driving": "운행일지",
      "create.mode_driving_hint": "차량 · 거리 · 방문지",
      "create.mode_field": "외근·출장",
      "create.mode_field_hint": "방문 · 결과 · 후속",
      "create.stamp_empty": "아직 스탬프가 없습니다. 현장에서 「지금 위치 스탬프」를 눌러 주세요.",
      "create.example": "예시 불러오기",
    },
    en: {
      "nav.home": "Home",
      "nav.features": "Features",
      "nav.create": "Write log",
      "nav.pricing": "Pricing",
      "nav.contact": "Contact",
      "nav.about": "About",
      "nav.style": "Company form",
      "nav.settings": "Settings",
      "nav.admin": "Admin",
      "nav.install": "Install app",
      "nav.login": "Log in",
      "nav.logout": "Log out",
      "nav.start": "Get started",
      "nav.write_log": "Write log",
      "nav.menu": "Menu",
      "create.generate": "✨ Generate with AI",
      "create.generate_field": "✨ Write field report with AI",
      "create.title": "Write driving log",
      "create.title_field": "Field / trip report",
      "create.form_title": "Today's trips",
      "create.form_title_field": "Today's field work",
      "create.mode_driving": "Driving log",
      "create.mode_driving_hint": "Vehicle · distance · stops",
      "create.mode_field": "Field visit",
      "create.mode_field_hint": "Visits · outcomes · follow-ups",
      "create.stamp_empty": "No stamps yet. Tap “Stamp location now” in the field.",
      "create.example": "Load example",
    },
  };

  // 시작 직 폴백을 dict에 넣어 두면 로드 전에도 키 노출 방지
  state.dict = { ...I18N_FALLBACK.ko };

  function fallbackDict(lang) {
    return I18N_FALLBACK[lang === "en" ? "en" : "ko"] || I18N_FALLBACK.ko;
  }

  /**
   * 번역 조회. 없으면 폴백 사전 → fallback 인자 → 키 순.
   * 절대 UI에 "nav.start" 같은 raw key 를 쓰지 않도록 tt() 권장.
   */
  function t(key, vars) {
    const dict = state.dict || {};
    const fb = fallbackDict(state.lang);
    let s = dict[key];
    if (s == null || s === "") s = fb[key];
    if (s == null || s === "") s = key;
    if (vars && typeof vars === "object") {
      Object.keys(vars).forEach((k) => {
        s = String(s).replace(new RegExp(`\\{${k}\\}`, "g"), String(vars[k]));
      });
    }
    return s;
  }

  /** UI 라벨 전용: 키가 그대로면 한글/영문 폴백 문자열 사용 */
  function tt(key, hardFallback) {
    const v = t(key);
    if (v && v !== key) return v;
    const fb = fallbackDict(state.lang)[key];
    if (fb) return fb;
    return hardFallback || key;
  }

  /**
   * i18n 초기화: state.lang 기준으로 /locales/${lang}.json 을 불러 state.dict 에 매핑
   * - 앱 시작(init) 및 언어 변경 시 사용
   */
  async function initLocales(lang) {
    // 인자 없으면 저장된 언어 → 기본 ko
    const code = (lang || state.lang || localStorage.getItem(LANG_KEY) || "ko") === "en"
      ? "en"
      : "ko";
    // 로드 전에도 폴백 적용
    state.dict = { ...fallbackDict(code) };
    state.lang = code;
    const urls = [
      `/locales/${code}.json`,
      `locales/${code}.json`,
      `./locales/${code}.json`,
    ];
    let loaded = null;
    let lastErr = null;
    for (const url of urls) {
      try {
        const res = await fetch(url, { cache: "no-cache" });
        if (!res.ok) throw new Error(`locale HTTP ${res.status} @ ${url}`);
        const ct = (res.headers.get("content-type") || "").toLowerCase();
        const text = await res.text();
        // SPA 폴백으로 HTML이 오면 JSON 파싱 실패 — 명시적으로 거름
        if (ct.includes("text/html") || text.trimStart().startsWith("<!")) {
          throw new Error(`locale returned HTML @ ${url}`);
        }
        loaded = JSON.parse(text);
        if (!loaded || typeof loaded !== "object") {
          throw new Error("locale JSON invalid");
        }
        break;
      } catch (e) {
        lastErr = e;
      }
    }
    if (loaded) {
      // 파일 번역 + 내장 폴백 병합 (파일 우선)
      state.dict = { ...fallbackDict(code), ...loaded };
      state.lang = code;
      localStorage.setItem(LANG_KEY, code);
      document.documentElement.lang = code === "en" ? "en" : "ko";
      return true;
    }
    console.warn("[i18n] initLocales failed", lastErr);
    state.dict = { ...fallbackDict(code) };
    state.lang = code;
    localStorage.setItem(LANG_KEY, code);
    document.documentElement.lang = code === "en" ? "en" : "ko";
    return false;
  }

  // 하위 호환: 기존 loadLocale 호출부를 initLocales 로 연결
  async function loadLocale(lang) {
    return initLocales(lang);
  }

  function applyI18n(root) {
    const scope = root || document;
    scope.querySelectorAll("[data-i18n]").forEach((el) => {
      const key = el.getAttribute("data-i18n");
      if (!key) return;
      const val = tt(key);
      // keep child icons: only replace text nodes or use data-i18n-target
      if (el.hasAttribute("data-i18n-keep-html")) {
        const span = el.querySelector("[data-i18n-text]");
        if (span) span.textContent = val;
        else el.appendChild(document.createTextNode(val));
      } else {
        el.textContent = val;
      }
    });
    scope.querySelectorAll("[data-i18n-html]").forEach((el) => {
      const key = el.getAttribute("data-i18n-html");
      if (!key) return;
      el.innerHTML = tt(key);
    });
    scope.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
      const key = el.getAttribute("data-i18n-placeholder");
      if (key) el.setAttribute("placeholder", tt(key));
    });
    scope.querySelectorAll("[data-i18n-title]").forEach((el) => {
      const key = el.getAttribute("data-i18n-title");
      if (key) el.setAttribute("title", tt(key));
    });
    scope.querySelectorAll("[data-i18n-aria]").forEach((el) => {
      const key = el.getAttribute("data-i18n-aria");
      if (key) el.setAttribute("aria-label", tt(key));
    });
    // 로그인/시작 버튼
    refreshAuthNavLabels();
    // generate buttons (외근 모드 반영)
    const genLabel =
      state.reportMode === "field"
        ? tt("create.generate_field", "✨ AI로 외근일지 작성")
        : tt("create.generate", "✨ AI로 일지 작성");
    ["#btnGenerate", "#btnGenerateSticky"].forEach((sel) => {
      const b = $(sel);
      if (b && !b.disabled) b.textContent = genLabel;
    });
    // stamp empty state if list is empty placeholder
    const stampEmpty = document.querySelector(".quick-stamp-empty");
    if (stampEmpty) stampEmpty.textContent = tt("create.stamp_empty");
    // 작성 모드 탭 문구 동기화
    if (typeof setReportMode === "function" && state.reportMode) {
      try {
        setReportMode(state.reportMode);
      } catch {
        /* init 순서상 미정의일 수 있음 */
      }
    }
  }

  /** 상단 로그인·시작 버튼 라벨 (raw key 절대 노출 금지) */
  function refreshAuthNavLabels() {
    const btnAuth = $("#btnAuth");
    const btnStart = $("#btnStart");
    if (!btnAuth && !btnStart) return;

    if (!state.user) {
      if (btnAuth) btnAuth.textContent = tt("nav.login", "로그인");
      if (btnStart) {
        btnStart.textContent = tt("nav.start", "시작하기");
        btnStart.dataset.nav = "create";
      }
      return;
    }

    const eu = typeof getEffectiveUser === "function" ? getEffectiveUser() : state.user;
    const name = (eu && (eu.name || eu.email?.split("@")[0])) || "계정";
    let plan = ((eu && eu.plan) || "free").toUpperCase();
    if (eu?.is_admin) plan = "ADMIN";
    else if (eu?.is_vip) plan = "VIP";
    else if (eu?.plan_type === "enterprise" || eu?._viewAs === "enterprise") plan = "ENT";

    const adminOnly =
      typeof isAdminMainMode === "function" ? isAdminMainMode() : !!(eu && eu.is_admin);
    if (btnAuth) {
      if (
        typeof isRealAdmin === "function" &&
        isRealAdmin() &&
        typeof getViewAsMode === "function" &&
        getViewAsMode() !== "admin"
      ) {
        btnAuth.textContent = `${name} · ${plan} (미리보기)`;
      } else {
        btnAuth.textContent = `${name} · ${plan}`;
      }
    }
    if (btnStart) {
      if (adminOnly) {
        btnStart.textContent = tt("nav.admin", "관리자");
        btnStart.dataset.nav = "admin";
      } else {
        btnStart.textContent = tt("nav.write_log", "일지 작성");
        btnStart.dataset.nav =
          typeof isWithinWorkHours === "function" && isWithinWorkHours()
            ? "stamp"
            : "report";
      }
    }
  }

  async function setLanguage(lang) {
    await loadLocale(lang);
    applyI18n();
    try {
      if (typeof loadStamps === "function") loadStamps();
      if (typeof renderStampList === "function") renderStampList();
    } catch {
      /* not ready */
    }
    try {
      if (typeof fillWorkHoursForm === "function") fillWorkHoursForm();
    } catch {
      /* ignore */
    }
    syncLangSelects();
    updateAuthUI();
    // 언어 변경 후 설치 버튼 기본 HTML 갱신 + 표시 상태 재계산
    document.querySelectorAll(".install-action").forEach((el) => {
      if (!el.hidden) el.dataset.defaultHtml = el.innerHTML;
    });
    if (typeof refreshInstallUI === "function") refreshInstallUI();
    toast(t("toast.lang"));
  }

  function loadLastLogFromStorage() {
    try {
      const raw = sessionStorage.getItem(LAST_LOG_KEY);
      if (!raw) return null;
      const log = JSON.parse(raw);
      if (log && typeof log === "object") {
        state.lastLog = log;
        return log;
      }
    } catch {
      /* ignore */
    }
    return null;
  }

  function persistLastLog(log) {
    state.lastLog = log || null;
    try {
      if (log) sessionStorage.setItem(LAST_LOG_KEY, JSON.stringify(log));
      else sessionStorage.removeItem(LAST_LOG_KEY);
    } catch {
      /* quota */
    }
    // 서버 동기화 훅 (실패해도 로컬 저장은 유지)
    saveData({ type: "lastLog", payload: log || null }).catch(() => {});
  }

  /**
   * 향후 서버 연동용 동기화 스텁
   * - 현재는 no-op resolve (오프라인 우선)
   * - 나중에 POST /api/sync 로 교체하면 됨
   */
  function syncData(bundle) {
    return new Promise((resolve) => {
      // TODO: 인증 토큰 + fetch('/api/sync', { method:'POST', body: JSON.stringify(bundle) })
      // 네트워크 없으면 여기서 resolve({ skipped: true }) 로 로컬만 유지
      if (!state.token) {
        resolve({ ok: true, skipped: true, reason: "no_token" });
        return;
      }
      // 서버 API 미구현 단계: 성공으로 간주해 UI 흐름을 막지 않음
      resolve({ ok: true, skipped: true, reason: "api_not_wired", bundleKeys: Object.keys(bundle || {}) });
    });
  }

  /**
   * 로컬 저장 + (비동기) 서버 동기화
   * @param {{ type?: string, payload?: any }} [opts] 부분 저장 시 힌트
   */
  async function saveData(opts = {}) {
    // 1) 로컬 영속화 — 스탬프(일자별) + 세션 일지
    try {
      const stampKey = typeof stampStorageKey === "function"
        ? stampStorageKey()
        : `${STAMPS_KEY_PREFIX}${new Date().toISOString().slice(0, 10)}`;
      localStorage.setItem(stampKey, JSON.stringify(state.stamps || []));
    } catch (e) {
      console.warn("[saveData] local stamps failed", e);
    }
    try {
      if (state.lastLog) {
        sessionStorage.setItem(LAST_LOG_KEY, JSON.stringify(state.lastLog));
      }
    } catch (e) {
      console.warn("[saveData] session lastLog failed", e);
    }

    // 2) 서버 동기화 파이프라인 (Promise) — 실패해도 throw 하지 않음
    const bundle = {
      type: opts.type || "full",
      stamps: state.stamps || [],
      lastLog: state.lastLog || null,
      lang: state.lang,
      payload: opts.payload,
      savedAt: new Date().toISOString(),
    };
    try {
      const syncResult = await syncData(bundle);
      return { ok: true, local: true, sync: syncResult };
    } catch (err) {
      console.warn("[saveData] sync failed (local kept)", err);
      return { ok: true, local: true, sync: { ok: false, error: String(err) } };
    }
  }

  const $ = (sel, el = document) => el.querySelector(sel);
  const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];

  function toast(msg) {
    const t = $("#toast");
    t.textContent = msg;
    t.classList.add("show");
    setTimeout(() => t.classList.remove("show"), 2600);
  }

  function alertBox(el, type, msg) {
    if (!el) return;
    if (!msg) {
      el.innerHTML = "";
      return;
    }
    el.innerHTML = `<div class="alert alert-${type}">${escapeHtml(msg)}</div>`;
  }

  function escapeHtml(s) {
    return String(s)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  async function api(path, opts = {}) {
    const headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
    if (state.token) headers.Authorization = `Bearer ${state.token}`;
    const res = await fetch(path, { ...opts, headers });
    const ct = res.headers.get("content-type") || "";
    if (ct.includes("application/json")) {
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const detail = data.detail || data.message || res.statusText;
        throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
      }
      return data;
    }
    if (!res.ok) throw new Error(await res.text());
    return res;
  }

  // ── Mobile sticky CTA ──
  function updateMobileSticky(viewName) {
    const bar = $("#mobileStickyCta");
    const isCreate =
      viewName === "create" || viewName === "stamp" || viewName === "report";
    const isMobile = window.matchMedia("(max-width: 900px)").matches;
    if (bar) {
      bar.hidden = !(isCreate && isMobile);
      bar.classList.toggle("is-visible", isCreate && isMobile);
    }
    document.body.classList.toggle("has-sticky-cta", isCreate && isMobile);
  }

  // ── 스마트 라우팅 (근무 시간) ──
  const WORK_HOURS_KEY = "rl_work_hours";
  const DEFAULT_WORK_START = "09:00";
  const DEFAULT_WORK_END = "18:00";

  function parseHmToMinutes(hm) {
    const m = String(hm || "").trim().match(/^(\d{1,2}):(\d{2})$/);
    if (!m) return null;
    const h = Number(m[1]);
    const min = Number(m[2]);
    if (h < 0 || h > 23 || min < 0 || min > 59) return null;
    return h * 60 + min;
  }

  function formatHm(hm, fallback) {
    const m = parseHmToMinutes(hm);
    if (m == null) return fallback;
    const h = String(Math.floor(m / 60)).padStart(2, "0");
    const min = String(m % 60).padStart(2, "0");
    return `${h}:${min}`;
  }

  function getWorkHours() {
    try {
      const raw = localStorage.getItem(WORK_HOURS_KEY);
      if (raw) {
        const o = JSON.parse(raw);
        return {
          start: formatHm(o.start, DEFAULT_WORK_START),
          end: formatHm(o.end, DEFAULT_WORK_END),
        };
      }
    } catch {
      /* ignore */
    }
    return { start: DEFAULT_WORK_START, end: DEFAULT_WORK_END };
  }

  function saveWorkHours(start, end) {
    const s = formatHm(start, DEFAULT_WORK_START);
    const e = formatHm(end, DEFAULT_WORK_END);
    localStorage.setItem(
      WORK_HOURS_KEY,
      JSON.stringify({ start: s, end: e, updated_at: new Date().toISOString() })
    );
    return { start: s, end: e };
  }

  /** 현재 시각이 근무 시간 구간인지 (야간 근무 교차 지원) */
  function isWithinWorkHours(now = new Date()) {
    const { start, end } = getWorkHours();
    const mins = now.getHours() * 60 + now.getMinutes();
    const s = parseHmToMinutes(start) ?? 9 * 60;
    const e = parseHmToMinutes(end) ?? 18 * 60;
    if (s === e) return true; // 24시간으로 간주
    if (s < e) return mins >= s && mins <= e;
    // 예: 22:00 ~ 06:00
    return mins >= s || mins <= e;
  }

  /**
   * 근무 중 → stamp(퀵 스탬프), 그 외 → report(일지 정리)
   * 명시적 딥링크(#pricing 등)가 있으면 호출하지 않음
   */
  function resolveSmartRoute(now = new Date()) {
    return isWithinWorkHours(now) ? "stamp" : "report";
  }

  function shouldApplySmartRoute() {
    const h = (location.hash || "").replace(/^#/, "").trim();
    // 빈 해시·홈만 스마트 라우팅 (딥링크 존중)
    return !h || h === "home";
  }

  function fillWorkHoursForm() {
    const wh = getWorkHours();
    if ($("#s_work_start")) $("#s_work_start").value = wh.start;
    if ($("#s_work_end")) $("#s_work_end").value = wh.end;
    const hint = $("#workHoursHint");
    if (hint) {
      const mode = isWithinWorkHours() ? "근무 중 · 스탬프 화면" : "근무 외 · 일지 정리 화면";
      hint.textContent = `현재 기준: ${wh.start} ~ ${wh.end} → 앱 실행 시 「${mode}」으로 이동합니다.`;
    }
  }

  // ── Navigation (전 구간 브라우저 뒤로가기 / 마우스 4번 버튼 지원) ──
  const VIEW_MAP = {
    home: "view-home",
    features: "view-home",
    demo: "view-home",
    create: "view-create",
    stamp: "view-create", // 근무 중 → 퀵 스탬프
    report: "view-create", // 퇴근 후 → 일지 정리
    pricing: "view-pricing",
    style: "view-style",
    settings: "view-settings",
    admin: "view-admin",
    terms: "view-terms",
    privacy: "view-privacy",
    about: "view-about",
    contact: "view-contact",
  };
  const VALID_VIEWS = Object.keys(VIEW_MAP);
  let currentViewName = "home";
  /** 히스토리 조작 중 hashchange 무시 */
  let navSilent = false;

  function normalizeViewName(name) {
    const n = String(name || "home").replace(/^#/, "").trim() || "home";
    return VALID_VIEWS.includes(n) ? n : "home";
  }

  function getViewFromLocation() {
    return normalizeViewName((location.hash || "").replace(/^#/, ""));
  }

  function viewHash(name) {
    return `#${normalizeViewName(name)}`;
  }

  function buildHistoryState(view, extra = {}) {
    return {
      rl: 1,
      view: normalizeViewName(view),
      modal: extra.modal || null,
    };
  }

  function readHistoryState(raw) {
    if (raw && raw.rl === 1 && raw.view) {
      return {
        view: normalizeViewName(raw.view),
        modal: raw.modal || null,
      };
    }
    return {
      view: getViewFromLocation(),
      modal: null,
    };
  }

  function syncUrl(name, mode /* push | replace | none */) {
    if (mode === "none") return;
    const nextHash = viewHash(name);
    navSilent = true;
    try {
      if (mode === "replace") {
        history.replaceState(buildHistoryState(name), "", nextHash);
      } else {
        // push: 동일 뷰 연속 push 방지 (모달 레이어만 있는 경우는 화면 이동으로 간주)
        const cur = readHistoryState(history.state);
        const sameView =
          cur.view === name &&
          getViewFromLocation() === name &&
          !cur.modal &&
          (location.hash || "#home") === nextHash;
        if (!sameView) {
          history.pushState(buildHistoryState(name), "", nextHash);
        }
      }
    } finally {
      setTimeout(() => {
        navSilent = false;
      }, 0);
    }
  }

  // settings: 근무시간·언어는 비로그인 사용 가능 → 로그인 강제 제외
  // style/admin: 진입 시 로그인 유도
  const AUTH_VIEWS = new Set(["style", "admin"]);

  /**
   * @param {string} name
   * @param {{ pushHistory?: boolean, replaceHistory?: boolean, skipScroll?: boolean, promptAuth?: boolean }} [opts]
   */
  function showView(name, opts = {}) {
    name = resolveAdminMainView(normalizeViewName(name));
    const replaceHistory = opts.replaceHistory === true;
    const pushHistory = opts.pushHistory !== false && !replaceHistory;
    const mode = replaceHistory ? "replace" : pushHistory ? "push" : "none";
    // 사용자 클릭 이동일 때만 로그인 유도 (히스토리 복원 시 재오픈 방지)
    const promptAuth =
      opts.promptAuth !== undefined
        ? opts.promptAuth
        : mode === "push" || mode === "replace";

    syncUrl(name, mode);
    currentViewName = name;
    applyView(name, { ...opts, promptAuth });
  }

  function applyView(name, opts = {}) {
    const requested = normalizeViewName(name);
    name = resolveAdminMainView(requested);
    // 관리자 메인으로 치환 시 URL 해시(#admin) 정합
    if (name !== requested) {
      navSilent = true;
      try {
        history.replaceState(buildHistoryState(name), "", viewHash(name));
      } finally {
        setTimeout(() => {
          navSilent = false;
        }, 0);
      }
    }
    currentViewName = name;

    $$(".view").forEach((v) => v.classList.remove("active"));
    const id = VIEW_MAP[name] || "view-home";
    document.getElementById(id)?.classList.add("active");

    $$(".nav-links a").forEach((a) => {
      const nav = a.dataset.nav;
      a.classList.toggle(
        "active",
        nav === name ||
          ((name === "features" || name === "demo") && nav === "home") ||
          (name === "home" && nav === "home") ||
          // 관리자 메인은 홈 진입도 관리자 탭으로 표시
          (name === "admin" && nav === "admin")
      );
    });

    $("#navLinks")?.classList.remove("open");

    if (name === "features" || name === "demo") {
      updateMobileSticky("home");
      // 기능·데모 섹션은 게스트 랜딩 안에 있음.
      // 로그인 상태에서도 해당 섹션이 보이도록 랜딩을 잠시 노출한다.
      $("#guestHome")?.classList.remove("hidden");
      $("#appHome")?.classList.add("hidden");
      if (!opts.skipScroll) {
        setTimeout(() => {
          if (name === "features") {
            document.getElementById("features")?.scrollIntoView({ behavior: "smooth" });
          } else {
            document.getElementById("demo")?.scrollIntoView({
              behavior: "smooth",
              block: "center",
            });
            window.__demoPlayer?.play?.();
          }
        }, 50);
      }
      return;
    }

    if (!opts.skipScroll) {
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
    updateMobileSticky(name);

    if (name === "home") updateHomeMode();
    if (name === "settings") {
      fillWorkHoursForm();
      loadSettingsForm({ promptAuth: false });
    }
    if (name === "style") loadStyleStatus({ promptAuth: false });
    if (name === "admin") loadAdminDashboard({ promptAuth: false });
    if (name === "create" || name === "stamp" || name === "report") {
      setReportMode(state.reportMode || "driving");
      prefillVehicleFromSettings();
      loadStamps();
      renderStampList();
      // 세션에 남은 최근 일지 복원 (새로고침 후 출력·공유 가능)
      if (!state.lastLog) loadLastLogFromStorage();
      if (state.lastLog) renderResult({ log: state.lastLog, engine: "restored" });
      // stamp: 퀵 스탬프 포커스 / report: 일지 입력 폼 포커스
      if (!opts.skipScroll) {
        setTimeout(() => {
          if (name === "stamp" && state.reportMode !== "field") {
            document.getElementById("quickStampPanel")?.scrollIntoView({
              behavior: "smooth",
              block: "start",
            });
            $("#btnQuickStamp")?.focus?.();
          } else if (name === "report" || state.reportMode === "field") {
            document.getElementById("reportFormPanel")?.scrollIntoView({
              behavior: "smooth",
              block: "start",
            });
            if (state.reportMode === "field") $("#fieldVisits")?.focus?.();
            else $("#vehicleNumber")?.focus?.();
          }
        }, 80);
      }
    }
    if (name === "terms") loadLegalDoc("terms");
    if (name === "privacy") loadLegalDoc("privacy");

    // 보호 화면: 사용자 의도 진입 시에만 로그인 모달 (닫기 후 재오픈 금지)
    if (opts.promptAuth && AUTH_VIEWS.has(name) && !state.token) {
      openAuth();
    }
  }

  function isAuthOpen() {
    return !!$("#authModal")?.classList.contains("show");
  }

  /** 히스토리/해시 복원 (뒤로·앞으로 가기) — 로그인 모달 강제 재오픈 없음 */
  function restoreFromHistory(rawState) {
    const st = readHistoryState(rawState);
    if (isAuthOpen() && st.modal !== "auth") {
      closeAuth({ fromHistory: true });
    }
    // promptAuth: false → 회사 서식 등에서 모달 닫은 뒤 뒤로가기 시 다시 안 뜸
    applyView(st.view, { skipScroll: false, promptAuth: false });
    if (st.modal === "auth" && !isAuthOpen() && !state.token) {
      openAuth({ fromHistory: true });
    }
  }

  function bindHistoryNav() {
    window.addEventListener("popstate", (e) => {
      restoreFromHistory(e.state);
    });

    // 주소창 해시 직접 변경·일부 브라우저 보조 경로
    window.addEventListener("hashchange", () => {
      if (navSilent) return;
      const name = getViewFromLocation();
      if (name !== currentViewName || (history.state && history.state.view !== name)) {
        navSilent = true;
        history.replaceState(buildHistoryState(name), "", viewHash(name));
        setTimeout(() => {
          navSilent = false;
        }, 0);
        // 해시 변경 시 열려 있던 로그인 모달도 정리
        if (isAuthOpen()) closeAuth({ fromHistory: true });
        applyView(name);
      }
    });

    // bfcache 복원 시 화면·모달 상태 재동기화
    window.addEventListener("pageshow", (e) => {
      if (e.persisted) restoreFromHistory(history.state);
    });
  }

  /** 간단한 Markdown → HTML (약관·개인정보처리방침용) */
  function renderSimpleMarkdown(md) {
    const lines = String(md || "").replace(/\r\n/g, "\n").split("\n");
    const out = [];
    let inOl = false;
    let inUl = false;
    let inBq = false;
    let i = 0;

    const closeLists = () => {
      if (inOl) {
        out.push("</ol>");
        inOl = false;
      }
      if (inUl) {
        out.push("</ul>");
        inUl = false;
      }
    };
    const closeBq = () => {
      if (inBq) {
        out.push("</blockquote>");
        inBq = false;
      }
    };
    const inline = (s) =>
      escapeHtml(s)
        .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
        .replace(/`([^`]+)`/g, "<code>$1</code>")
        .replace(
          /\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g,
          '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>'
        );
    const splitCells = (row) =>
      row
        .trim()
        .replace(/^\|/, "")
        .replace(/\|$/, "")
        .split("|")
        .map((c) => c.trim());
    const isSepRow = (row) => /^\s*\|?[\s:|-]+\|[\s:|-]*\|?\s*$/.test(row);

    while (i < lines.length) {
      const line = lines[i];
      if (/^\s*$/.test(line)) {
        closeLists();
        closeBq();
        i += 1;
        continue;
      }
      // Markdown table
      if (
        line.includes("|") &&
        i + 1 < lines.length &&
        isSepRow(lines[i + 1])
      ) {
        closeLists();
        closeBq();
        const headers = splitCells(line);
        i += 2; // skip header + separator
        const rows = [];
        while (i < lines.length && lines[i].includes("|") && !/^\s*$/.test(lines[i])) {
          if (isSepRow(lines[i])) {
            i += 1;
            continue;
          }
          rows.push(splitCells(lines[i]));
          i += 1;
        }
        out.push('<div class="legal-table-wrap"><table class="legal-table"><thead><tr>');
        headers.forEach((h) => out.push(`<th>${inline(h)}</th>`));
        out.push("</tr></thead><tbody>");
        rows.forEach((cells) => {
          out.push("<tr>");
          cells.forEach((c) => out.push(`<td>${inline(c)}</td>`));
          out.push("</tr>");
        });
        out.push("</tbody></table></div>");
        continue;
      }
      if (/^---+$/.test(line.trim())) {
        closeLists();
        closeBq();
        out.push("<hr />");
        i += 1;
        continue;
      }
      if (line.startsWith("> ")) {
        closeLists();
        if (!inBq) {
          out.push("<blockquote>");
          inBq = true;
        }
        out.push(`<p>${inline(line.slice(2))}</p>`);
        i += 1;
        continue;
      }
      closeBq();
      if (line.startsWith("# ")) {
        closeLists();
        out.push(`<h1>${inline(line.slice(2))}</h1>`);
        i += 1;
        continue;
      }
      if (line.startsWith("## ")) {
        closeLists();
        out.push(`<h2>${inline(line.slice(3))}</h2>`);
        i += 1;
        continue;
      }
      if (line.startsWith("### ")) {
        closeLists();
        out.push(`<h3>${inline(line.slice(4))}</h3>`);
        i += 1;
        continue;
      }
      const ol = line.match(/^\s*(\d+)\.\s+(.*)$/);
      if (ol) {
        if (inUl) {
          out.push("</ul>");
          inUl = false;
        }
        if (!inOl) {
          out.push("<ol>");
          inOl = true;
        }
        out.push(`<li>${inline(ol[2])}</li>`);
        i += 1;
        continue;
      }
      const ul = line.match(/^\s*[-*]\s+(.*)$/);
      if (ul) {
        if (inOl) {
          out.push("</ol>");
          inOl = false;
        }
        if (!inUl) {
          out.push("<ul>");
          inUl = true;
        }
        out.push(`<li>${inline(ul[1])}</li>`);
        i += 1;
        continue;
      }
      const nested = line.match(/^\s{2,}(\d+)\.\s+(.*)$/);
      if (nested && inOl) {
        out.push(`<li>${inline(nested[2])}</li>`);
        i += 1;
        continue;
      }
      closeLists();
      out.push(`<p>${inline(line)}</p>`);
      i += 1;
    }
    closeLists();
    closeBq();
    return out.join("\n");
  }

  const legalCache = {};
  async function loadLegalDoc(kind) {
    const el = kind === "terms" ? $("#termsBody") : $("#privacyBody");
    if (!el) return;
    if (legalCache[kind]) {
      el.innerHTML = legalCache[kind];
      return;
    }
    const path =
      kind === "terms"
        ? "/assets/legal/terms.md"
        : "/assets/legal/privacy.md";
    try {
      const res = await fetch(path, { cache: "no-cache" });
      if (!res.ok) throw new Error("load failed");
      const md = await res.text();
      const html = renderSimpleMarkdown(md);
      legalCache[kind] = html;
      el.innerHTML = html;
    } catch {
      el.innerHTML = `<div class="legal-card"><h3>문서를 불러오지 못했습니다</h3><p>잠시 후 다시 시도해 주세요. 파일 경로: ${escapeHtml(
        path
      )}</p></div>`;
    }
  }

  function prefillVehicleFromSettings() {
    const el = $("#vehicleNumber");
    if (!el) return;
    // 이미 입력된 값이 있으면 덮지 않음
    if ((el.value || "").trim()) return;
    const v =
      state.settings?.vehicle_number ||
      state.settings?.vehicle ||
      "";
    if (v) el.value = v;
  }

  function setReportMode(mode, opts = {}) {
    const m = mode === "field" ? "field" : "driving";
    state.reportMode = m;
    $$(".report-mode-tab").forEach((el) => {
      const on = el.dataset.reportMode === m;
      el.classList.toggle("is-active", on);
      el.setAttribute("aria-selected", on ? "true" : "false");
    });
    $$("[data-mode-panel]").forEach((el) => {
      el.classList.toggle("hidden", el.dataset.modePanel !== m);
    });
    const title = $("#createTitle");
    const sub = $("#createSub");
    const formTitle = $("#reportFormTitle");
    const genBtn = $("#btnGenerate");
    const genLabel =
      m === "field"
        ? tt("create.generate_field", "✨ AI로 외근일지 작성")
        : tt("create.generate", "✨ AI로 일지 작성");
    if (m === "field") {
      if (title) title.textContent = tt("create.title_field", "외근·출장 일지");
      if (sub) sub.textContent = tt("create.sub_field", "");
      if (formTitle) formTitle.textContent = tt("create.form_title_field", "오늘 외근 정보");
    } else {
      if (title) title.textContent = tt("create.title", "운행일지 작성");
      if (sub) sub.textContent = tt("create.sub", "");
      if (formTitle) formTitle.textContent = tt("create.form_title", "오늘 운행 정보");
    }
    if (genBtn && !genBtn.disabled) genBtn.textContent = genLabel;
    const genSticky = $("#btnGenerateSticky");
    if (genSticky && !genSticky.disabled) genSticky.textContent = genLabel;
    if (opts.toast) {
      toast(m === "field" ? "외근·출장 일지 모드" : "운행일지 모드");
    }
  }

  function bindReportModeTabs() {
    document.body.addEventListener("click", (e) => {
      const tab = e.target.closest(".report-mode-tab[data-report-mode]");
      if (!tab) return;
      e.preventDefault();
      setReportMode(tab.dataset.reportMode, { toast: true });
    });
  }

  function bindNav() {
    document.body.addEventListener("click", (e) => {
      // 로그인 모달이 열린 동안 배경 네비 클릭 차단
      if (isAuthOpen()) {
        if (!e.target.closest("#authModal")) {
          e.preventDefault();
          e.stopPropagation();
        }
        return;
      }
      const nav = e.target.closest("[data-nav]");
      if (!nav) return;
      e.preventDefault();
      e.stopPropagation();
      const target = nav.dataset.nav;
      if (
        nav.dataset.reportMode &&
        (target === "create" || target === "stamp" || target === "report")
      ) {
        setReportMode(nav.dataset.reportMode);
      }
      // 같은 화면 재클릭 시에도 해시/히스토리 정합성 유지
      showView(target);
      const scrollId = nav.dataset.scroll;
      if (scrollId) {
        setTimeout(() => {
          document.getElementById(scrollId)?.scrollIntoView({
            behavior: "smooth",
            block: "center",
          });
        }, 80);
      }
    });
    $("#menuToggle")?.addEventListener("click", () => {
      $("#navLinks")?.classList.toggle("open");
    });
  }

  // ── Auth UI ──
  let authBackdropReady = false;
  let authBusy = false;

  function encodeLoginSecret(s) {
    try {
      return btoa(unescape(encodeURIComponent(String(s || ""))));
    } catch {
      return "";
    }
  }

  function decodeLoginSecret(s) {
    try {
      return decodeURIComponent(escape(atob(String(s || ""))));
    } catch {
      return "";
    }
  }

  function loadSavedLogin() {
    try {
      const raw = localStorage.getItem(SAVED_LOGIN_KEY);
      if (!raw) return null;
      const o = JSON.parse(raw);
      if (!o || typeof o !== "object") return null;
      const email = String(o.email || "").trim();
      if (!email) return null;
      return {
        email,
        password: decodeLoginSecret(o.p || o.password || ""),
      };
    } catch {
      return null;
    }
  }

  function saveLoginCredentials(email, password) {
    const e = String(email || "").trim();
    if (!e) {
      clearSavedLogin();
      return;
    }
    try {
      localStorage.setItem(
        SAVED_LOGIN_KEY,
        JSON.stringify({
          email: e,
          p: encodeLoginSecret(password || ""),
          saved_at: new Date().toISOString(),
        })
      );
    } catch {
      /* quota */
    }
  }

  function clearSavedLogin() {
    try {
      localStorage.removeItem(SAVED_LOGIN_KEY);
    } catch {
      /* ignore */
    }
  }

  function applySavedLoginToForm() {
    const saved = loadSavedLogin();
    const emailEl = $("#loginEmail");
    const pwEl = $("#loginPw");
    const rememberEl = $("#loginRemember");
    if (saved) {
      if (emailEl) emailEl.value = saved.email;
      if (pwEl) pwEl.value = saved.password || "";
      if (rememberEl) rememberEl.checked = true;
      if (emailEl) delete emailEl.dataset.userEdited;
      if (pwEl) delete pwEl.dataset.userEdited;
    } else if (rememberEl) {
      rememberEl.checked = false;
    }
  }

  function openAuth(opts = {}) {
    const modal = $("#authModal");
    if (!modal) return;
    const wasOpen = modal.classList.contains("show");
    modal.classList.add("show");
    document.body.classList.add("modal-open");
    // 저장된 로그인 정보 자동 입력
    applySavedLoginToForm();
    // 히스토리에 모달 레이어 추가 → 뒤로가기로 모달 닫기
    if (!wasOpen && !opts.fromHistory) {
      navSilent = true;
      try {
        history.pushState(
          buildHistoryState(currentViewName, { modal: "auth" }),
          "",
          location.hash || viewHash(currentViewName)
        );
      } finally {
        setTimeout(() => {
          navSilent = false;
        }, 0);
      }
    }
    // 방금 연 직후 바깥 클릭으로 바로 닫히는 것 방지
    authBackdropReady = false;
    setTimeout(() => {
      authBackdropReady = true;
    }, 200);
    requestAnimationFrame(() => {
      const email = $("#loginEmail");
      const pw = $("#loginPw");
      if (email && !email.value.trim()) email.focus();
      else if (pw && !pw.value) pw.focus();
      else pw?.focus();
    });
  }

  function closeAuth(opts = {}) {
    // X/바깥클릭/Esc는 항상 닫기 (authBusy여도 UI는 닫음 — 요청 중 플래그만 해제)
    if (opts.fromHistory !== true) {
      authBusy = false;
    } else if (authBusy) {
      authBusy = false;
    }
    const modal = $("#authModal");
    if (!modal) return;
    modal.classList.remove("show");
    document.body.classList.remove("modal-open");
    authBackdropReady = false;

    // history.back() 사용 금지: 뷰 재적용 → loadStyleStatus → openAuth 재오픈 루프 유발
    // 대신 현재 엔트리에서 modal 플래그만 제거
    if (!opts.fromHistory && history.state && history.state.rl === 1) {
      navSilent = true;
      try {
        history.replaceState(
          buildHistoryState(currentViewName || getViewFromLocation()),
          "",
          location.hash || viewHash(currentViewName || "home")
        );
      } finally {
        setTimeout(() => {
          navSilent = false;
        }, 0);
      }
    }
  }

  /** 실제 관리자 계정 여부 (미리보기와 무관 · API/권한용) */
  function isRealAdmin() {
    return !!(state.user && state.user.is_admin);
  }

  function getViewAsMode() {
    if (!isRealAdmin()) return "admin";
    const v = String(state.viewAs || "admin").toLowerCase();
    if (v === "pro" || v === "enterprise" || v === "free" || v === "admin") return v;
    return "admin";
  }

  /** 관리자 운영 화면 모드 (역할 미리보기 아님) — 메인은 관리자 대시보드 */
  function isAdminMainMode() {
    return isRealAdmin() && getViewAsMode() === "admin";
  }

  /** 홈·근무시간 스마트 진입을 관리자 대시보드로 치환 */
  function resolveAdminMainView(name) {
    if (!isAdminMainMode()) return name;
    if (name === "home" || name === "stamp" || name === "report") return "admin";
    return name;
  }

  /**
   * UI에 쓰는 유효 사용자.
   * 관리자가 Pro/Enterprise/Free 미리보기 중이면 해당 플랜처럼 보이게 가공.
   */
  function getEffectiveUser() {
    const u = state.user;
    if (!u) return null;
    if (!u.is_admin) return u;
    const mode = getViewAsMode();
    if (mode === "admin") return { ...u, plan_type: u.plan_type || "enterprise" };
    if (mode === "pro") {
      return {
        ...u,
        is_admin: false,
        is_vip: false,
        plan: "pro",
        plan_type: "personal",
        _viewAs: "pro",
      };
    }
    if (mode === "enterprise") {
      return {
        ...u,
        is_admin: false,
        is_vip: false,
        plan: "pro",
        plan_type: "enterprise",
        _viewAs: "enterprise",
      };
    }
    // free
    return {
      ...u,
      is_admin: false,
      is_vip: false,
      plan: "free",
      plan_type: "personal",
      _viewAs: "free",
    };
  }

  function setViewAsMode(mode) {
    if (!isRealAdmin()) return;
    const m = String(mode || "admin").toLowerCase();
    const next =
      m === "pro" || m === "enterprise" || m === "free" || m === "admin" ? m : "admin";
    state.viewAs = next;
    localStorage.setItem(VIEW_AS_KEY, next);
    syncViewAsControls();
    updateAuthUI();
    const labels = {
      admin: "관리자 화면",
      pro: "Pro 사용자 화면",
      enterprise: "Enterprise 사용자 화면",
      free: "Free 사용자 화면",
    };
    toast(`${labels[next] || next}으로 전환했습니다`);
    // 미리보기 → 일반 유저 홈 / 관리자로 복귀 → 관리자 대시보드가 메인
    if (next !== "admin" && currentViewName === "admin") {
      showView("home", { replaceHistory: true });
    } else if (next === "admin") {
      showView("admin", { replaceHistory: true });
    }
  }

  function syncViewAsControls() {
    const mode = getViewAsMode();
    const real = isRealAdmin();
    const bar = $("#adminViewAsBar");
    if (bar) {
      bar.hidden = !real || mode === "admin";
      bar.classList.toggle("is-visible", real && mode !== "admin");
      const label = $("#adminViewAsLabel");
      if (label) {
        const map = {
          pro: "Pro 사용자로 보는 중",
          enterprise: "Enterprise 사용자로 보는 중",
          free: "Free 사용자로 보는 중",
        };
        label.textContent = map[mode] || "";
      }
    }
    document.body.classList.toggle("admin-view-as", real && mode !== "admin");
    document.body.dataset.viewAs = real ? mode : "";

    // 관리자 페이지 버튼 active
    $$("[data-view-as]").forEach((btn) => {
      const active = real && btn.dataset.viewAs === mode;
      btn.classList.toggle("is-active", active);
      btn.setAttribute("aria-pressed", active ? "true" : "false");
    });
    const panel = $("#adminViewAsPanel");
    if (panel) panel.hidden = !real;
  }

  function bindAdminViewAs() {
    document.body.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-view-as]");
      if (!btn) return;
      e.preventDefault();
      if (!isRealAdmin()) {
        toast("관리자 로그인 후 사용할 수 있습니다");
        return;
      }
      setViewAsMode(btn.dataset.viewAs);
    });
    syncViewAsControls();
  }

  function updateAuthUI() {
    const navSettings = $("#navSettings");
    const navCreate = $("#navCreate");
    const navStyle = $("#navStyle");
    const navAdmin = $("#navAdmin");
    const eu = getEffectiveUser();
    // 설정(근무 시간)은 로그인 없이 사용 가능
    navSettings?.classList.remove("hidden");
    // 관리자 보기 모드: 운영 화면에 일지 작성·회사 서식 메뉴 비노출
    const adminOnlyUi = isAdminMainMode();
    if (eu) {
      if (adminOnlyUi) {
        navCreate?.classList.add("hidden");
        navStyle?.classList.add("hidden");
      } else {
        navCreate?.classList.remove("hidden");
        navStyle?.classList.remove("hidden");
      }
      // 관리자 메뉴: 실제 관리자 + 관리자 보기 모드일 때만
      if (adminOnlyUi) navAdmin?.classList.remove("hidden");
      else navAdmin?.classList.add("hidden");
    } else {
      navCreate?.classList.remove("hidden");
      navStyle?.classList.add("hidden");
      navAdmin?.classList.add("hidden");
    }
    // 로그인·시작 버튼 한글 라벨
    refreshAuthNavLabels();
    syncViewAsControls();
    updateHomeMode();
    renderUsage();
  }

  function updateHomeMode() {
    const guest = $("#guestHome");
    const app = $("#appHome");
    const loggedIn = !!getEffectiveUser();
    if (guest) guest.classList.toggle("hidden", loggedIn);
    if (app) app.classList.toggle("hidden", !loggedIn);
    if (loggedIn) renderAppHome();
  }

  function renderAppHome() {
    const eu = getEffectiveUser();
    if (!eu) return;
    const name =
      eu.name || (eu.email ? eu.email.split("@")[0] : "회원");
    const now = new Date();
    const dateStr = now.toLocaleDateString("ko-KR", {
      year: "numeric",
      month: "long",
      day: "numeric",
      weekday: "short",
    });
    if ($("#appHomeDate")) $("#appHomeDate").textContent = dateStr;
    if ($("#appHomeGreeting")) $("#appHomeGreeting").textContent = `${name}님, 안녕하세요`;
    if ($("#appHomeSub")) {
      if (eu.is_admin) {
        $("#appHomeSub").textContent =
          "일지 작성과 관리자 운영을 이어서 진행할 수 있습니다.";
      } else if (eu.plan_type === "enterprise" || eu._viewAs === "enterprise") {
        $("#appHomeSub").textContent =
          "Enterprise · 팀 운행일지와 회사 서식을 관리하세요.";
      } else if (eu.plan === "pro") {
        $("#appHomeSub").textContent =
          "Pro · 운행·외근 일지를 무제한으로 작성하세요.";
      } else {
        $("#appHomeSub").textContent =
          "오늘 운행·외근 일지를 작성하거나 회사 서식을 관리하세요.";
      }
    }

    // 사용량
    const usageEl = $("#appHomeUsage");
    const usageText = $("#appHomeUsageText");
    if (usageEl && usageText) {
      const unlimited =
        eu.plan === "pro" || eu.is_admin || eu.is_vip;
      if (unlimited) {
        if (eu.is_vip) {
          usageEl.innerHTML = `<span class="uil-badge uil-badge-pro">VIP</span><span>평생 무료 · 무제한</span>`;
        } else if (eu.is_admin) {
          usageEl.innerHTML = `<span class="uil-badge uil-badge-pro">ADMIN</span><span>관리자 · 무제한</span>`;
        } else if (eu.plan_type === "enterprise" || eu._viewAs === "enterprise") {
          usageEl.innerHTML = `<span class="uil-badge uil-badge-ent">ENT</span><span>Enterprise · 무제한</span>`;
        } else {
          usageEl.innerHTML = `<span class="uil-badge uil-badge-pro">Pro</span><span>무제한 생성</span>`;
        }
      } else {
        const used = state.usage || 0;
        const limit = state.limit || 10;
        usageEl.innerHTML = `<span class="uil-badge uil-badge-free">Free</span><span>이번 달 ${used}/${limit}회 · 잔여 ${Math.max(
          0,
          limit - used
        )}회</span>`;
      }
    }

    // 관리자 타일 — 관리자 메인은 대시보드로 바로 가므로 홈 타일은 숨김
    const adminTile = $("#appTileAdmin");
    if (adminTile) {
      adminTile.classList.add("hidden");
    }

    // 체크리스트
    const vehicle = (state.settings?.vehicle_number || "").trim();
    const styleReady = !!(state.styleProfile?.learned || (state.styleProfile?.sample_count || 0) > 0);
    const hasResult = !!state.lastLog;
    const list = $("#appChecklist");
    if (list) {
      const items = [
        {
          ok: !!vehicle,
          warn: !vehicle,
          text: vehicle
            ? `기본 차량번호: ${vehicle}`
            : "설정에서 기본 차량번호를 등록해 두면 작성 시 자동 입력됩니다.",
        },
        {
          ok: styleReady,
          warn: !styleReady,
          text: styleReady
            ? `회사 서식 ${state.styleProfile?.sample_count || 0}장 등록됨`
            : "회사 서식(사진·문서)을 등록하면 AI가 양식에 맞춰 작성합니다.",
        },
        {
          ok: hasResult,
          warn: false,
          text: hasResult
            ? "최근 생성한 일지가 있습니다. 다운로드·인쇄는 작성 화면에서 가능합니다."
            : "아직 생성한 일지가 없습니다. AI로 일지 작성을 시작해 보세요.",
        },
      ];
      list.innerHTML = items
        .map(
          (it) => `<li class="${it.ok ? "is-done" : it.warn ? "is-warn" : ""}">
          <span class="ck">${it.ok ? "✓" : "!"}</span>
          <span>${escapeHtml(it.text)}</span>
        </li>`
        )
        .join("");
    }

    // 최근 결과 요약
    const lastBox = $("#appLastResult");
    const lastBody = $("#appLastResultBody");
    if (lastBox && lastBody) {
      if (state.lastLog) {
        lastBox.style.display = "";
        const log = state.lastLog;
        lastBody.innerHTML = `
          <div><strong>${escapeHtml(String(log.date || "—"))}</strong> · ${escapeHtml(
            String(log.vehicle || "차량 미기재")
          )} · ${escapeHtml(String(log.total_distance_km ?? "—"))} km</div>
          <div style="margin-top:0.35rem;color:#94a3b8">${escapeHtml(
            String(log.summary || "요약 없음")
          )}</div>`;
      } else {
        lastBox.style.display = "none";
        lastBody.innerHTML = "";
      }
    }
  }

  function renderUsage() {
    const label = $("#usageLabel");
    const remain = $("#usageRemain");
    const fill = $("#usageFill");
    const eu = getEffectiveUser();
    if (!eu) {
      label.textContent = "로그인 후 사용량 표시";
      remain.textContent = "";
      fill.style.width = "0%";
      fill.classList.remove("danger");
      return;
    }
    if (eu.is_admin) {
      label.textContent = "관리자 · 무제한";
      remain.textContent = "";
      fill.style.width = "100%";
      fill.classList.remove("danger");
      return;
    }
    if (eu.plan_type === "enterprise" || eu._viewAs === "enterprise") {
      label.textContent = "Enterprise · 무제한";
      remain.textContent = "";
      fill.style.width = "100%";
      fill.classList.remove("danger");
      return;
    }
    if (eu.plan === "pro" || eu.is_vip) {
      label.textContent = eu.is_vip ? "VIP · 무제한" : "Pro · 무제한";
      remain.textContent = "";
      fill.style.width = "100%";
      fill.classList.remove("danger");
      return;
    }
    const used = state.usage || 0;
    const limit = state.limit || 10;
    const pct = Math.min(100, Math.round((used / limit) * 100));
    label.innerHTML = `<strong style="color:#e2e8f0">Free</strong> · 이번 달 ${used}/${limit}회`;
    remain.textContent = `잔여 ${Math.max(0, limit - used)}회`;
    fill.style.width = `${pct}%`;
    fill.classList.toggle("danger", used >= limit);
  }

  function persistToken(token) {
    state.token = token || "";
    if (token) {
      localStorage.setItem(TOKEN_KEY, token);
      localStorage.setItem(REMEMBER_KEY, "1");
    } else {
      localStorage.removeItem(TOKEN_KEY);
    }
  }

  function clearSession() {
    state.token = "";
    state.user = null;
    state.settings = null;
    state.styleProfile = null;
    state.viewAs = "admin";
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(VIEW_AS_KEY);
    updateAuthUI();
  }

  async function refreshMe() {
    if (!state.token) return false;
    try {
      const data = await api("/api/me");
      state.user = data.user;
      state.usage = data.usage;
      state.limit = data.limit;
      state.settings = data.settings;
      // 토큰 유효 → 세션 유지 플래그 갱신
      localStorage.setItem(REMEMBER_KEY, "1");
      updateAuthUI();
      try {
        state.styleProfile = await api("/api/style");
        if (state.user) renderAppHome();
      } catch {
        /* ignore */
      }
      return true;
    } catch {
      clearSession();
      return false;
    }
  }

  function markSessionReady() {
    document.body.classList.remove("session-checking");
    document.body.classList.add("session-ready");
  }

  function bindAuth() {
    const authModal = $("#authModal");
    const authPanel = authModal?.querySelector(".modal");

    $("#btnAuth")?.addEventListener("click", () => {
      if (state.user) {
        if (confirm("로그아웃 할까요?")) {
          clearSession();
          localStorage.removeItem(REMEMBER_KEY);
          showView("home", { replaceHistory: true });
          toast("로그아웃되었습니다");
        }
        return;
      }
      openAuth();
    });
    $("#authClose")?.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      closeAuth();
    });

    // 패널 내부 클릭/포인터는 백드롭으로 전파되지 않게 (레이아웃 시프트·오탭 닫힘 방지)
    authPanel?.addEventListener("click", (e) => e.stopPropagation());
    authPanel?.addEventListener("pointerdown", (e) => e.stopPropagation());

    // 백드롭: pointerdown + pointerup 모두 백드롭일 때만 닫기
    // (버튼 클릭 중 에러 알림으로 높이 변하며 mouseup이 바깥으로 빠지는 경우 방지)
    let backdropPointerDown = false;
    authModal?.addEventListener("pointerdown", (e) => {
      backdropPointerDown = e.target === authModal;
    });
    authModal?.addEventListener("pointerup", (e) => {
      if (
        authBackdropReady &&
        backdropPointerDown &&
        e.target === authModal &&
        !authBusy
      ) {
        closeAuth();
      }
      backdropPointerDown = false;
    });
    authModal?.addEventListener("click", (e) => {
      // 레거시 클릭 경로 차단 — pointerup에서만 닫음
      if (e.target === authModal) {
        e.preventDefault();
        e.stopPropagation();
      }
    });

    // Escape로만 명시 닫기 (입력 중 실수 방지 위해 busy 아닐 때)
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && authModal?.classList.contains("show") && !authBusy) {
        closeAuth();
      }
    });

    $$("[data-auth-tab]").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        $$("[data-auth-tab]").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        const tab = btn.dataset.authTab;
        const isLogin = tab === "login";
        $("#authLoginForm")?.classList.toggle("hidden", !isLogin);
        $("#authRegisterForm")?.classList.toggle("hidden", isLogin);
        // 내부 래퍼도 동기화 (레거시 선택자 호환)
        $("#authLogin")?.classList.toggle("hidden", !isLogin);
        $("#authRegister")?.classList.toggle("hidden", isLogin);
        alertBox($("#authAlert"), "info", "");
        if (isLogin) $("#loginEmail")?.focus();
        else $("#regEmail")?.focus();
      });
    });

    async function applyLogin(data, successMsg) {
      persistToken(data.token);
      state.user = data.user;
      state.usage = data.usage;
      state.limit = data.limit;
      updateAuthUI();
      authBusy = false;
      // 로그인 성공: 모달 히스토리 정리 후 홈으로
      closeAuth({ fromHistory: true });
      if (history.state && history.state.modal === "auth") {
        history.replaceState(buildHistoryState(currentViewName), "", viewHash(currentViewName));
      }
      toast(successMsg || "로그인 성공 · 세션이 유지됩니다");
      await refreshMe();
      // 관리자: 메인 = 매출·회원 대시보드 / 일반: 홈
      showView(isAdminMainMode() ? "admin" : "home", { replaceHistory: true });
    }

    async function doLogin() {
      if (authBusy) return;
      const email = ($("#loginEmail")?.value || "").trim();
      const password = $("#loginPw")?.value || "";
      const remember = !!$("#loginRemember")?.checked;
      if (!email || !password) {
        // 모달 유지 + 안내
        openAuth();
        alertBox($("#authAlert"), "error", "이메일(또는 ID)과 비밀번호를 입력해 주세요.");
        ($("#loginEmail")?.value ? $("#loginPw") : $("#loginEmail"))?.focus();
        return;
      }
      authBusy = true;
      const btn = $("#btnLogin");
      if (btn) {
        btn.disabled = true;
        btn.dataset.label = btn.textContent || "";
        btn.textContent = "로그인 중…";
      }
      // 요청 중 모달이 절대 닫히지 않도록 유지
      openAuth();
      try {
        const data = await api("/api/auth/login", {
          method: "POST",
          body: JSON.stringify({ email, password }),
        });
        // 로그인 정보 저장 / 해제
        if (remember) saveLoginCredentials(email, password);
        else clearSavedLogin();
        await applyLogin(
          data,
          remember
            ? "로그인 성공 · 이 기기에 로그인 정보를 저장했습니다"
            : "로그인 성공 · 세션이 유지됩니다"
        );
      } catch (err) {
        // 실패 시 모달 유지 · 비밀번호만 비우고 재입력 유도
        authBusy = false;
        openAuth();
        alertBox(
          $("#authAlert"),
          "error",
          err.message || "로그인에 실패했습니다. 비밀번호를 확인해 주세요."
        );
        const pw = $("#loginPw");
        if (pw) {
          // 저장된 비번이 틀렸을 수 있음 — 필드만 비움 (저장본은 유지, 재저장은 성공 시)
          pw.value = "";
          pw.dataset.userEdited = "1";
          pw.focus();
        }
      } finally {
        authBusy = false;
        if (btn) {
          btn.disabled = false;
          btn.textContent = btn.dataset.label || "로그인";
        }
      }
    }

    // 사용자가 직접 수정하면 덮어쓰지 않도록 표시
    $("#loginEmail")?.addEventListener("input", () => {
      if ($("#loginEmail")) $("#loginEmail").dataset.userEdited = "1";
    });
    $("#loginPw")?.addEventListener("input", () => {
      if ($("#loginPw")) $("#loginPw").dataset.userEdited = "1";
    });
    // 체크 해제 시 즉시 저장된 정보 삭제 (원하면)
    $("#loginRemember")?.addEventListener("change", () => {
      const on = !!$("#loginRemember")?.checked;
      if (!on) clearSavedLogin();
    });

    $("#btnLogin")?.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      doLogin();
    });

    // form submit / Enter 모두 동일 처리 (페이지 리로드·모달 소실 방지)
    $("#authLoginForm")?.addEventListener("submit", (e) => {
      e.preventDefault();
      e.stopPropagation();
      doLogin();
    });
    $("#loginEmail")?.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        $("#loginPw")?.focus();
      }
    });
    $("#loginPw")?.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        e.stopPropagation();
        doLogin();
      }
    });

    async function doRegister() {
      if (authBusy) return;
      const name = ($("#regName")?.value || "").trim();
      const email = ($("#regEmail")?.value || "").trim();
      const password = $("#regPw")?.value || "";
      const pw2 = $("#regPw2")?.value || "";
      if (password !== pw2) {
        openAuth();
        alertBox($("#authAlert"), "error", "비밀번호가 일치하지 않습니다.");
        $("#regPw2")?.focus();
        return;
      }
      authBusy = true;
      openAuth();
      try {
        await api("/api/auth/register", {
          method: "POST",
          body: JSON.stringify({ email, password, name }),
        });
        openAuth();
        alertBox($("#authAlert"), "ok", "가입 완료. 로그인해 주세요.");
        // 로그인 탭으로 전환
        $$("[data-auth-tab]").forEach((b) =>
          b.classList.toggle("active", b.dataset.authTab === "login")
        );
        $("#authLoginForm")?.classList.remove("hidden");
        $("#authRegisterForm")?.classList.add("hidden");
        $("#authLogin")?.classList.remove("hidden");
        $("#authRegister")?.classList.add("hidden");
        if ($("#loginEmail")) $("#loginEmail").value = email;
        $("#loginPw")?.focus();
      } catch (err) {
        openAuth();
        alertBox($("#authAlert"), "error", err.message || "회원가입에 실패했습니다.");
      } finally {
        authBusy = false;
      }
    }

    $("#btnRegister")?.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      doRegister();
    });
    $("#authRegisterForm")?.addEventListener("submit", (e) => {
      e.preventDefault();
      e.stopPropagation();
      doRegister();
    });
  }

  // ── 퇴근 위로 모달 (일지 생성 완료 시) ──
  // 제약: 내일/다시/출근/다음 날 등 업무 재개 연상 단어 금지 — 퇴근·휴식만
  const CARE_MESSAGES = [
    "오늘 하루, 누구보다 열심히 사신 대표님의 노고에 박수를 보냅니다. 이제 푹 쉬세요!",
    "오늘도 정말 고생 많으셨습니다. 이제 일 생각은 여기 두고, 편안한 저녁 시간 되세요.",
    "로드로그에 오늘 기록을 모두 담았습니다. 오늘 하루 정말 애쓰셨어요. 이제 온전한 휴식을 즐기시길 바랍니다.",
    "오늘 방문하신 곳들만큼이나 대표님의 하루도 참 알찼네요. 정말 고생 많으셨습니다.",
    "오늘 일과는 여기서 끝입니다. 이제 가벼운 마음으로 퇴근하세요. 고생하셨습니다.",
  ];

  function pickCareMessage() {
    const i = Math.floor(Math.random() * CARE_MESSAGES.length);
    return CARE_MESSAGES[i] || CARE_MESSAGES[0];
  }

  function countPlacesFromText(text) {
    return String(text || "")
      .split(/[\n,;]+/)
      .map((s) => s.trim())
      .filter(Boolean).length;
  }

  /** 오늘 방문지 수: 일지 trips → 폼 방문지 → 스탬프 순 */
  function countTodayVisits(log, form) {
    const trips = Array.isArray(log?.trips) ? log.trips : [];
    if (trips.length) {
      const nonLunch = trips.filter(
        (t) => !/중식|점심|식사/.test(String(t.purpose || t.place || ""))
      );
      return nonLunch.length || trips.length;
    }
    const fromForm =
      countPlacesFromText(form?.morning_places) +
      countPlacesFromText(form?.afternoon_places) +
      (form?.lunch_restaurant ? 1 : 0);
    if (fromForm > 0) return fromForm;
    return (state.stamps && state.stamps.length) || 0;
  }

  function buildCareVisitLine(n) {
    if (n <= 0) {
      return "오늘 하루의 기록을 마쳤습니다. 이제 푹 쉬세요.";
    }
    return `오늘 총 ${n}곳을 방문하며 고생하셨습니다. 이제 푹 쉬세요!`;
  }

  /**
   * care-modal 표시
   * - hidden 속성 제거 + is-open 클래스 토글 (CSS transition)
   * - log/form 있으면 방문 수·랜덤 위로 문구 채움
   */
  function showCareModal(log, form) {
    const modal = $("#careModal");
    const msgEl = $("#careModalMsg");
    const visitEl = $("#careModalVisit");
    if (!modal) return;

    // 문구·방문 수 주입 (옵션)
    if (msgEl) {
      msgEl.textContent = pickCareMessage();
    }
    if (visitEl) {
      const n = countTodayVisits(log, form);
      visitEl.textContent = buildCareVisitLine(n);
    }

    // display: 숨김 해제 (hidden 속성 제거)
    modal.hidden = false;
    modal.style.display = "flex";
    // 애니메이션 프레임에 클래스 토글 → opacity/transform 전환
    requestAnimationFrame(() => {
      modal.classList.add("is-open");
      document.body.classList.add("modal-open");
      $("#careModalOk")?.focus();
    });
  }

  /** care-modal 닫기 — 클래스 제거 후 애니메이션 끝나면 display:none */
  function hideCareModal() {
    const modal = $("#careModal");
    if (!modal) return;
    modal.classList.remove("is-open");
    document.body.classList.remove("modal-open");
    // CSS transition(~280ms) 후 완전 숨김
    setTimeout(() => {
      if (!modal.classList.contains("is-open")) {
        modal.hidden = true;
        modal.style.display = "none";
      }
    }, 280);
  }

  function bindCareModal() {
    $("#careModalOk")?.addEventListener("click", hideCareModal);
    $("#careModal")?.addEventListener("click", (e) => {
      if (e.target === $("#careModal")) hideCareModal();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && $("#careModal")?.classList.contains("is-open")) {
        hideCareModal();
      }
    });
  }

  // ── Generate ──
  function readForm() {
    return {
      vehicle_number: $("#vehicleNumber")?.value?.trim() ?? "",
      odometer_start: $("#odoStart")?.value ?? "",
      odometer_end: $("#odoEnd")?.value ?? "",
      lunch_restaurant: $("#lunchPlace")?.value?.trim() ?? "",
      morning_places: $("#morningPlaces")?.value?.trim() ?? "",
      afternoon_places: $("#afternoonPlaces")?.value?.trim() ?? "",
      raw_text: $("#rawText")?.value?.trim() ?? "",
    };
  }

  function readFieldForm() {
    return {
      department: $("#fieldDepartment")?.value?.trim() ?? "",
      work_summary: $("#fieldSummary")?.value?.trim() ?? "",
      visits_text: $("#fieldVisits")?.value?.trim() ?? "",
      next_actions: $("#fieldNext")?.value?.trim() ?? "",
      raw_text: $("#fieldMemo")?.value?.trim() ?? "",
    };
  }

  function updateDistHint() {
    const s = parseFloat($("#odoStart")?.value);
    const e = parseFloat($("#odoEnd")?.value);
    const el = $("#distHint");
    if (!el) return;
    if (Number.isFinite(s) && Number.isFinite(e)) {
      const d = Math.round((e - s) * 10) / 10;
      el.textContent =
        d >= 0
          ? `금일 주행거리: ${d} km  (종료 ${e} − 최초 ${s})`
          : "종료 주행거리가 최초보다 작습니다. 숫자를 확인해 주세요.";
      el.style.color = d >= 0 ? "var(--cyan)" : "var(--danger)";
    } else {
      el.textContent = "금일 주행거리: — km  (최초·종료 주행거리를 입력하면 자동 계산됩니다)";
      el.style.color = "var(--muted)";
    }
  }

  function bindGenerate() {
    $("#odoStart")?.addEventListener("input", updateDistHint);
    $("#odoEnd")?.addEventListener("input", updateDistHint);
    updateDistHint();

    $("#btnExample")?.addEventListener("click", () => {
      if (state.reportMode === "field") {
        if ($("#fieldDepartment")) $("#fieldDepartment").value = EXAMPLE_FIELD.department;
        if ($("#fieldSummary")) $("#fieldSummary").value = EXAMPLE_FIELD.summary;
        if ($("#fieldVisits")) $("#fieldVisits").value = EXAMPLE_FIELD.visits;
        if ($("#fieldNext")) $("#fieldNext").value = EXAMPLE_FIELD.next;
        if ($("#fieldMemo")) $("#fieldMemo").value = EXAMPLE_FIELD.memo;
        toast("외근 예시 내용을 불러왔습니다");
        return;
      }
      if ($("#vehicleNumber")) $("#vehicleNumber").value = EXAMPLE_FORM.vehicleNumber;
      $("#odoStart").value = EXAMPLE_FORM.odoStart;
      $("#odoEnd").value = EXAMPLE_FORM.odoEnd;
      $("#lunchPlace").value = EXAMPLE_FORM.lunchPlace;
      $("#morningPlaces").value = EXAMPLE_FORM.morningPlaces;
      $("#afternoonPlaces").value = EXAMPLE_FORM.afternoonPlaces;
      $("#rawText").value = EXAMPLE_FORM.rawText;
      updateDistHint();
      toast("예시 내용을 불러왔습니다");
    });

    async function runGenerate() {
      if (!state.token) {
        alertBox($("#genAlert"), "info", "로그인한 뒤 생성할 수 있습니다.");
        openAuth();
        return;
      }

      const isField = state.reportMode === "field";
      const btns = [$("#btnGenerate"), $("#btnGenerateSticky")].filter(Boolean);

      if (isField) {
        const form = readFieldForm();
        if (!form.visits_text && !form.work_summary && !form.next_actions && !form.raw_text) {
          alertBox(
            $("#genAlert"),
            "warn",
            "방문·업무 내용, 한 줄 요약, 후속 조치 중 하나 이상 입력해 주세요."
          );
          $("#fieldVisits")?.focus?.();
          return;
        }
        btns.forEach((btn) => {
          btn.disabled = true;
          btn.innerHTML = `<span class="spinner"></span> 생성 중...`;
        });
        alertBox($("#genAlert"), "info", "입력 내용으로 AI가 외근·출장 일지를 작성 중입니다…");
        try {
          const data = await api("/api/generate", {
            method: "POST",
            body: JSON.stringify({
              report_type: "field",
              raw_text: form.raw_text,
              settings: state.settings || undefined,
              visits_text: form.visits_text,
              work_summary: form.work_summary,
              next_actions: form.next_actions,
              department: form.department,
            }),
          });
          state.usage = data.usage ?? state.usage;
          renderUsage();
          if (!data.log) {
            const errs = (data.errors || []).join(" / ") || "생성에 실패했습니다.";
            alertBox($("#genAlert"), "error", errs);
            return;
          }
          persistLastLog(data.log);
          renderResult(data);
          if (state.user) renderAppHome();
          alertBox(
            $("#genAlert"),
            data.engine === "openai" ? "ok" : "warn",
            formatGenerateUserMessage(data)
          );
          toast(
            data.engine === "openai"
              ? "외근일지 생성 완료"
              : data.engine_title
                ? `${data.engine_title} · 규칙 초안 완료`
                : "규칙 초안으로 생성 완료"
          );
          document.getElementById("resultBox")?.scrollIntoView({ behavior: "smooth", block: "start" });
          showCareModal(data.log, form);
        } catch (err) {
          alertBox($("#genAlert"), "error", err.message);
        } finally {
          btns.forEach((btn) => {
            btn.disabled = false;
            btn.innerHTML = tt("create.generate_field", "✨ AI로 외근일지 작성");
          });
        }
        return;
      }

      // ① 스탬프 → 오전/오후 필드 자동 병합 (폼 비워도 LocalStorage 스탬프 보존)
      const merged = mergeStampsIntoFormFields();
      const form = readForm();
      const hasPlaces = form.morning_places || form.afternoon_places;
      const hasOdo = form.odometer_start !== "" || form.odometer_end !== "";
      if (!hasPlaces && !hasOdo && !form.lunch_restaurant) {
        alertBox(
          $("#genAlert"),
          "warn",
          "퀵 스탬프를 찍거나, 주행거리·점심·방문지 중 하나 이상 입력해 주세요."
        );
        return;
      }
      if (form.odometer_start !== "" && form.odometer_end !== "") {
        const s = parseFloat(form.odometer_start);
        const e = parseFloat(form.odometer_end);
        if (Number.isFinite(s) && Number.isFinite(e) && e < s) {
          alertBox($("#genAlert"), "error", "운행 종료 주행거리는 최초 누적 주행거리 이상이어야 합니다.");
          return;
        }
      }

      btns.forEach((btn) => {
        btn.disabled = true;
        btn.innerHTML = `<span class="spinner"></span> 생성 중...`;
      });
      const mergeHint =
        merged.morning + merged.afternoon > 0
          ? ` (스탬프 오전+${merged.morning} · 오후+${merged.afternoon})`
          : "";
      alertBox(
        $("#genAlert"),
        "info",
        `입력·스탬프 데이터로 AI가 운행일지를 작성 중입니다…${mergeHint}`
      );

      try {
        const data = await api("/api/generate", {
          method: "POST",
          body: JSON.stringify({
            report_type: "driving",
            raw_text: form.raw_text,
            settings: state.settings || undefined,
            vehicle_number: form.vehicle_number,
            odometer_start: form.odometer_start === "" ? null : Number(form.odometer_start),
            odometer_end: form.odometer_end === "" ? null : Number(form.odometer_end),
            lunch_restaurant: form.lunch_restaurant,
            morning_places: form.morning_places || "",
            afternoon_places: form.afternoon_places || "",
          }),
        });
        state.usage = data.usage ?? state.usage;
        renderUsage();

        if (!data.log) {
          const errs = (data.errors || []).join(" / ") || "생성에 실패했습니다.";
          alertBox($("#genAlert"), "error", errs);
          return;
        }

        // ② 결과 즉시 표시 + sessionStorage 보존 (새로고침 대비)
        persistLastLog(data.log);
        renderResult(data);
        if (state.user) renderAppHome();
        const genMsg = formatGenerateUserMessage(data);
        alertBox(
          $("#genAlert"),
          data.engine === "openai" ? "ok" : "warn",
          genMsg
        );
        toast(
          data.engine === "openai"
            ? "AI 일지 생성 완료"
            : data.engine_title
              ? `${data.engine_title} · 규칙 초안 완료`
              : "규칙 초안으로 생성 완료"
        );
        document.getElementById("resultBox")?.scrollIntoView({ behavior: "smooth", block: "start" });
        showCareModal(data.log, form);
      } catch (err) {
        alertBox($("#genAlert"), "error", err.message);
      } finally {
        btns.forEach((btn) => {
          btn.disabled = false;
          btn.innerHTML = tt("create.generate", "✨ AI로 일지 작성");
        });
      }
    }

    $("#btnGenerate")?.addEventListener("click", runGenerate);
    $("#btnGenerateSticky")?.addEventListener("click", runGenerate);
    window.addEventListener("resize", () => {
      const active = document.querySelector(".view.active");
      const name =
        active?.id === "view-create"
          ? "create"
          : active?.id?.replace("view-", "") || "home";
      updateMobileSticky(name === "create" ? "create" : name);
    });

    $$("[data-export]").forEach((btn) => {
      btn.addEventListener("click", () => exportFile(btn.dataset.export));
    });
    $("#btnCopyLog")?.addEventListener("click", async () => {
      if (!state.lastLog) {
        toast("먼저 일지를 생성해 주세요");
        return;
      }
      const text = logToPlainText(state.lastLog);
      try {
        await navigator.clipboard.writeText(text);
        toast("일지 텍스트를 복사했습니다");
      } catch {
        // fallback
        const ta = document.createElement("textarea");
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        ta.remove();
        toast("일지 텍스트를 복사했습니다");
      }
    });
  }

  function logToPlainText(log) {
    if (!log) return "";
    const isField = String(log.report_type || "").toLowerCase() === "field";
    if (isField) {
      const lines = [
        `[로드로그 외근일지] ${log.date || ""}`,
        `작성자: ${log.author_name || log.driver_name || "—"}`,
        `부서: ${log.department || "—"}`,
        `회사: ${log.company_name || "—"}`,
        "",
      ];
      const visits = log.visits || [];
      if (visits.length) {
        visits.forEach((v, i) => {
          lines.push(
            `${i + 1}. ${v.time || "—"} ${v.place || "—"} | ${v.purpose || ""} | 결과: ${v.result || "—"} | 후속: ${v.next_action || "—"}`
          );
        });
      } else {
        (log.trips || []).forEach((t, i) => {
          lines.push(
            `${i + 1}. ${t.depart_time || "—"} ${t.to || "—"} | ${t.purpose || ""} | ${t.memo || ""}`
          );
        });
      }
      if (log.summary) lines.push("", `요약: ${log.summary}`);
      return lines.join("\n");
    }
    const lines = [
      `[로드로그 운행일지] ${log.date || ""}`,
      `차량: ${log.vehicle || "—"}`,
      `누적: ${log.odometer_start ?? "—"} → ${log.odometer_end ?? "—"} km`,
      `총 거리: ${log.total_distance_km ?? 0} km`,
      `점심: ${log.lunch_place || "—"}`,
      "",
    ];
    (log.trips || []).forEach((t, i) => {
      lines.push(
        `${i + 1}. ${t.depart_time || "—"}~${t.arrive_time || "—"} ${t.from || "—"} → ${t.to || "—"} (${t.distance_km ?? "—"}km) ${t.purpose || ""}`
      );
    });
    if (log.summary) {
      lines.push("", `요약: ${log.summary}`);
    }
    return lines.join("\n");
  }

  /** 서버 generate 응답 → 사용자용 한 줄/단락 안내 */
  function formatGenerateUserMessage(data) {
    if (!data) return "일지가 생성되었습니다.";
    if (data.message && String(data.message).trim()) {
      // 마크다운 ** ** 제거 (alert 박스 텍스트용)
      return String(data.message).replace(/\*\*/g, "").trim();
    }
    if (data.engine === "openai") {
      return "일지가 생성되었습니다. 시간·구간은 AI가 채웠으니 확인해 주세요.";
    }
    const reason = data.engine_reason || "";
    const map = {
      no_api_key:
        "AI 키가 연결되지 않아 규칙 기반 초안으로 작성했습니다. 구간·시간을 확인해 주세요.",
      quota_exceeded:
        "AI 사용량(할당량)이 초과되어 규칙 기반 초안으로 작성했습니다. OpenAI 결제/크레딧 충전 후 다시 시도해 주세요.",
      rate_limit:
        "AI 서버가 잠시 바빠 규칙 기반 초안으로 작성했습니다. 잠시 후 다시 생성해 보세요.",
      auth_error:
        "AI 키 인증에 실패해 규칙 기반 초안으로 작성했습니다. 관리자에게 API 키 확인을 요청해 주세요.",
      network_error:
        "AI 서버에 연결하지 못해 규칙 기반 초안으로 작성했습니다. 네트워크 확인 후 다시 시도해 주세요.",
      api_error:
        "AI 생성 중 오류가 나 규칙 기반 초안으로 작성했습니다. 구간·시간을 확인해 주세요.",
    };
    return map[reason] || "규칙 기반 초안으로 작성되었습니다. 내용을 확인해 주세요.";
  }

  function renderResult(data) {
    const log = data.log;
    const box = $("#resultBox");
    if (!box || !log) return;
    box.classList.add("show");

    const badge = $("#engineBadge");
    if (badge) {
      if (data.engine === "openai") {
        badge.textContent = "AI 생성";
        badge.classList.remove("pill-warn");
        badge.title = "OpenAI로 작성된 일지입니다";
      } else {
        const title = data.engine_title || "규칙 초안";
        badge.textContent = title === "규칙 초안" ? "규칙 초안" : `규칙 초안 · ${title}`;
        badge.classList.add("pill-warn");
        badge.title = formatGenerateUserMessage(data);
      }
    }

    // 결과 패널 상단 엔진 안내 (폴백 시 항상 노출)
    let notice = $("#engineNotice");
    if (!notice && box) {
      notice = document.createElement("div");
      notice.id = "engineNotice";
      notice.className = "engine-notice";
      const head = box.querySelector(".panel-head");
      if (head && head.nextSibling) {
        head.parentNode.insertBefore(notice, head.nextSibling);
      } else {
        box.insertBefore(notice, box.firstChild);
      }
    }
    if (notice) {
      if (data.engine && data.engine !== "openai" && data.engine !== "restored") {
        notice.hidden = false;
        notice.className = "engine-notice is-warn";
        const detail = data.engine_detail
          ? `<span class="engine-notice-detail">${escapeHtml(String(data.engine_detail))}</span>`
          : "";
        notice.innerHTML = `<strong>${escapeHtml(
          data.engine_title || "규칙 기반 초안"
        )}</strong><span>${escapeHtml(formatGenerateUserMessage(data))}</span>${detail}`;
      } else if (data.engine === "openai") {
        notice.hidden = false;
        notice.className = "engine-notice is-ok";
        notice.innerHTML =
          "<strong>AI 생성</strong><span>시간·구간을 한 번 확인한 뒤 제출해 주세요.</span>";
      } else {
        notice.hidden = true;
        notice.innerHTML = "";
      }
    }

    // 서버 warnings (폴백 안내 등)
    let warnBox = $("#resultWarnings");
    if (!warnBox && box) {
      warnBox = document.createElement("div");
      warnBox.id = "resultWarnings";
      warnBox.className = "result-warnings";
      const metrics = box.querySelector("#metrics");
      if (metrics) {
        metrics.parentNode.insertBefore(warnBox, metrics);
      } else {
        box.appendChild(warnBox);
      }
    }
    if (warnBox) {
      const warns = Array.isArray(data.warnings) ? data.warnings : [];
      // 폴백 user_message 와 중복되는 첫 줄은 engineNotice 에 이미 있음 → 나머지/서식 안내만
      const extra =
        data.engine === "fallback" && warns.length > 1 ? warns.slice(1) : data.engine === "openai" ? warns : warns.slice(1);
      if (extra.length) {
        warnBox.hidden = false;
        warnBox.innerHTML = extra
          .map((w) => `<div class="result-warn-item">${escapeHtml(String(w).replace(/\*\*/g, ""))}</div>`)
          .join("");
      } else {
        warnBox.hidden = true;
        warnBox.innerHTML = "";
      }
    }

    const isField = String(log.report_type || "").toLowerCase() === "field";
    const mins = log.total_net_minutes || 0;
    const dur =
      mins >= 60 ? `${Math.floor(mins / 60)}시간 ${mins % 60}분` : `${mins}분`;

    const odoS = log.odometer_start != null && log.odometer_start !== "" ? `${log.odometer_start}` : "—";
    const odoE = log.odometer_end != null && log.odometer_end !== "" ? `${log.odometer_end}` : "—";
    if ($("#metrics")) {
      const metrics = isField
        ? [
            ["작성일", log.date || "—"],
            ["작성자", log.author_name || log.driver_name || "—"],
            ["부서", log.department || "—"],
            ["회사", log.company_name || "—"],
            ["방문 건수", String((log.visits || log.trips || []).length)],
          ]
        : [
            ["작성일", log.date || "—"],
            ["차량번호", log.vehicle || "—"],
            ["최초 누적", odoS === "—" ? "—" : `${odoS} km`],
            ["종료 누적", odoE === "—" ? "—" : `${odoE} km`],
            ["총 거리", `${log.total_distance_km ?? 0} km`],
            ["순수 운행", dur],
            ["점심", log.lunch_place || "—"],
          ];
      $("#metrics").innerHTML = metrics
        .map(
          ([k, v]) =>
            `<div class="metric"><div class="label">${escapeHtml(k)}</div><div class="value">${escapeHtml(
              String(v)
            )}</div></div>`
        )
        .join("");
    }

    if (log.summary) {
      $("#summaryBox").innerHTML = `<div class="label">${
        isField ? "업무 요약" : "운행 요약"
      }</div><div>${escapeHtml(log.summary)}</div>`;
      $("#summaryBox").style.display = "";
    } else if ($("#summaryBox")) {
      $("#summaryBox").style.display = "none";
    }

    if ($("#trips")) {
      if (isField) {
        const visits = log.visits || [];
        if (!visits.length && !(log.trips || []).length) {
          $("#trips").innerHTML =
            '<div class="trip"><div class="trip-route"><strong>방문 기록 없음</strong><span>방문처를 입력한 뒤 다시 생성해 주세요.</span></div></div>';
        } else if (visits.length) {
          $("#trips").innerHTML = visits
            .map((v) => {
              const detail = [v.result && `결과: ${v.result}`, v.next_action && `후속: ${v.next_action}`, v.memo]
                .filter(Boolean)
                .join(" · ");
              return `<div class="trip">
          <div class="trip-time">${escapeHtml(v.time || "—")}</div>
          <div class="trip-route">
            <strong>${escapeHtml(v.place || "—")}</strong>
            <span>${escapeHtml(v.purpose || "업무 방문")}</span>
            ${detail ? `<span style="display:block;margin-top:0.25rem;color:#94a3b8">${escapeHtml(detail)}</span>` : ""}
          </div>
          <div class="trip-meta"><b>외근</b></div>
        </div>`;
            })
            .join("");
        } else {
          $("#trips").innerHTML = (log.trips || [])
            .map((t) => {
              return `<div class="trip">
          <div class="trip-time">${escapeHtml(t.depart_time || "—")}</div>
          <div class="trip-route">
            <strong>${escapeHtml(t.to || "—")}</strong>
            <span>${escapeHtml(t.purpose || "업무 방문")}</span>
            ${t.memo ? `<span style="display:block;margin-top:0.25rem;color:#94a3b8">${escapeHtml(t.memo)}</span>` : ""}
          </div>
          <div class="trip-meta"><b>외근</b></div>
        </div>`;
            })
            .join("");
        }
      } else {
        const trips = log.trips || [];
        if (!trips.length) {
          $("#trips").innerHTML =
            '<div class="trip"><div class="trip-route"><strong>기록된 구간 없음</strong><span>오전 또는 오후 방문지를 추가한 뒤 다시 생성해 주세요.</span></div></div>';
        } else {
          $("#trips").innerHTML = trips
            .map((t) => {
              return `<div class="trip">
          <div class="trip-time">${escapeHtml(t.depart_time || "—")}<small>→ ${escapeHtml(
                t.arrive_time || "—"
              )}</small></div>
          <div class="trip-route">
            <strong>${escapeHtml(t.from || "—")} → ${escapeHtml(t.to || "—")}</strong>
            <span>${escapeHtml(t.purpose || "업무 운행")}</span>
          </div>
          <div class="trip-meta"><b>${escapeHtml(String(t.distance_km ?? "—"))} km</b>${escapeHtml(
                t.duration_display || ""
              )}</div>
        </div>`;
            })
            .join("");
        }
      }
    }
  }

  async function exportFile(fmt) {
    if (!state.token) {
      openAuth();
      return;
    }
    if (!state.lastLog) {
      toast("먼저 일지를 생성해 주세요");
      return;
    }
    try {
      const res = await fetch("/api/export", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${state.token}`,
        },
        body: JSON.stringify({ log: state.lastLog, format: fmt }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "다운로드 실패");
      }
      const blob = await res.blob();
      const cd = res.headers.get("Content-Disposition") || "";
      const m = cd.match(/filename="?([^"]+)"?/);
      const name = m ? m[1] : `운행일지.${fmt === "excel" ? "xlsx" : fmt}`;
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = name;
      a.click();
      URL.revokeObjectURL(a.href);
      toast(`${fmt.toUpperCase()} 다운로드`);
    } catch (err) {
      toast(err.message);
    }
  }

  // ── Settings ──
  function placesToText(places) {
    if (!Array.isArray(places)) return "";
    return places
      .map((p) => `${p.name || ""}${p.address ? " | " + p.address : ""}`.trim())
      .filter(Boolean)
      .join("\n");
  }

  function textToPlaces(text) {
    return text
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean)
      .map((l) => {
        const [name, address = ""] = l.split("|").map((x) => x.trim());
        return { name, address };
      });
  }

  function fillSettings(s) {
    if (!s) return;
    state.settings = s;
    $("#s_vehicle").value = s.vehicle_number || "";
    // 작성 폼 차량번호가 비어 있으면 설정값 반영
    prefillVehicleFromSettings();
    $("#s_driver").value = s.driver_name || "";
    $("#s_company").value = s.company_name || "";
    $("#s_fuel").value = s.fuel_type || "휘발유";
    $("#s_lunch_start").value = s.lunch_start || "12:00";
    $("#s_lunch_end").value = s.lunch_end || "13:00";
    $("#s_exclude_lunch").checked = s.exclude_lunch !== false;
    $("#s_purpose").value = s.default_purpose || "업무 출장";
    $("#s_places").value = placesToText(s.frequent_places || []);
  }

  async function loadSettingsForm(_opts = {}) {
    if (!state.token) {
      alertBox(
        $("#settingsAlert"),
        "info",
        "설정은 로그인 후 이용할 수 있습니다. 우측 상단에서 로그인해 주세요."
      );
      return;
    }
    try {
      const data = await api("/api/settings");
      state.settings = data.settings;
      fillSettings(data.settings);
    } catch (err) {
      alertBox($("#settingsAlert"), "error", err.message);
    }
  }

  function syncLangSelects() {
    const v = state.lang === "en" ? "en" : "ko";
    if ($("#s_lang")) $("#s_lang").value = v;
    if ($("#navLang")) $("#navLang").value = v;
  }

  function bindSettings() {
    fillWorkHoursForm();
    syncLangSelects();
    // 설정 페이지 + 상단 네비 언어 선택기
    const onLangChange = (e) => {
      const val = e.target?.value || "ko";
      setLanguage(val);
      syncLangSelects();
    };
    $("#s_lang")?.addEventListener("change", onLangChange);
    $("#navLang")?.addEventListener("change", onLangChange);

    $("#btnSaveWorkHours")?.addEventListener("click", () => {
      const start = $("#s_work_start")?.value || DEFAULT_WORK_START;
      const end = $("#s_work_end")?.value || DEFAULT_WORK_END;
      if (parseHmToMinutes(start) == null || parseHmToMinutes(end) == null) {
        alertBox($("#workHoursAlert"), "error", "시간 형식을 확인해 주세요. (예: 09:00)");
        return;
      }
      saveWorkHours(start, end);
      fillWorkHoursForm();
      alertBox(
        $("#workHoursAlert"),
        "ok",
        `근무 시간이 ${formatHm(start, DEFAULT_WORK_START)} ~ ${formatHm(
          end,
          DEFAULT_WORK_END
        )} 으로 저장되었습니다.`
      );
      toast(t("toast.work_saved"));
    });

    $("#btnResetWorkHours")?.addEventListener("click", () => {
      saveWorkHours(DEFAULT_WORK_START, DEFAULT_WORK_END);
      fillWorkHoursForm();
      alertBox($("#workHoursAlert"), "ok", "기본값 09:00 ~ 18:00 으로 되돌렸습니다.");
      toast(t("toast.work_saved"));
    });

    $("#btnSaveSettings")?.addEventListener("click", async () => {
      // 근무 시간도 함께 저장
      const ws = $("#s_work_start")?.value;
      const we = $("#s_work_end")?.value;
      if (ws && we) saveWorkHours(ws, we);

      if (!state.token) {
        openAuth();
        alertBox(
          $("#settingsAlert"),
          "info",
          "근무 시간은 저장되었습니다. 차량 설정은 로그인 후 저장할 수 있습니다."
        );
        return;
      }
      const settings = {
        vehicle_number: $("#s_vehicle").value.trim(),
        driver_name: $("#s_driver").value.trim(),
        company_name: $("#s_company").value.trim(),
        fuel_type: $("#s_fuel").value,
        lunch_start: $("#s_lunch_start").value.trim() || "12:00",
        lunch_end: $("#s_lunch_end").value.trim() || "13:00",
        exclude_lunch: $("#s_exclude_lunch").checked,
        default_purpose: $("#s_purpose").value.trim() || "업무 출장",
        frequent_places: textToPlaces($("#s_places").value),
      };
      try {
        const data = await api("/api/settings", {
          method: "PUT",
          body: JSON.stringify({ settings }),
        });
        state.settings = data.settings;
        fillWorkHoursForm();
        alertBox($("#settingsAlert"), "ok", t("toast.settings_saved"));
        toast(t("toast.settings_saved"));
      } catch (err) {
        alertBox($("#settingsAlert"), "error", err.message);
      }
    });
  }

  // ── Style learn ──
  function renderStyleStatus(data) {
    if (!data) return;
    state.styleProfile = data;
    const n = data.sample_count || 0;
    const max = data.max_samples || 5;
    const minRec = data.min_recommended || 3;
    const samples = data.samples || [];
    const photos = samples.filter((s) => s.source_type === "photo").length;
    const docs = Math.max(0, n - photos);
    const cols = data.form_columns || [];
    const learned = !!data.learned;

    // 준비도: 등록 60% + 학습 완료 40% (권장 3장 기준 스케일)
    const regScore = Math.min(1, n / minRec) * 60;
    const learnScore = learned ? 40 : n > 0 ? 15 : 0;
    const pct = Math.round(Math.min(100, regScore + learnScore));

    let stateKey = "empty";
    let badgeText = "미등록";
    if (learned && n >= 1) {
      stateKey = "ready";
      badgeText = "학습 완료 · 작성 반영 가능";
    } else if (n > 0) {
      stateKey = "progress";
      badgeText = n >= minRec ? "학습 대기 · 다시 학습 권장" : "등록 중";
    }

    const pill = $("#styleStatusPill");
    if (pill) {
      pill.textContent = badgeText;
      pill.dataset.state = stateKey;
    }

    const ring = $("#styleLearnRing");
    if (ring) {
      ring.style.setProperty("--pct", String(pct));
      ring.dataset.state = stateKey;
    }
    if ($("#styleRingPct")) $("#styleRingPct").textContent = `${pct}%`;
    if ($("#styleRingLabel")) {
      $("#styleRingLabel").textContent =
        stateKey === "ready" ? "준비 완료" : stateKey === "progress" ? "학습 중" : "준비도";
    }
    if ($("#styleProgressLabel")) {
      $("#styleProgressLabel").textContent =
        `등록 ${n} / ${max}장` + (data.recommended_ready ? " · 권장 충족" : n > 0 ? ` · 권장 ${minRec}장` : "");
    }
    if ($("#styleStatusMsg")) {
      $("#styleStatusMsg").textContent =
        data.message ||
        (state.token
          ? "회사 서식을 등록하면 AI 학습 상태가 여기에 표시됩니다."
          : "로그인 후 학습 상태를 확인할 수 있습니다.");
    }

    // 통계
    if ($("#statSamples")) $("#statSamples").textContent = String(n);
    if ($("#statPhotos")) $("#statPhotos").textContent = String(photos);
    if ($("#statDocs")) $("#statDocs").textContent = String(docs);
    if ($("#statCols")) $("#statCols").textContent = String(cols.length);

    // 3단계 파이프라인
    const step1 = document.querySelector('.learn-step[data-step="1"]');
    const step2 = document.querySelector('.learn-step[data-step="2"]');
    const step3 = document.querySelector('.learn-step[data-step="3"]');
    [step1, step2, step3].forEach((el) => {
      if (!el) return;
      el.classList.remove("is-done", "is-active");
    });
    if ($("#step1Cap")) {
      $("#step1Cap").textContent = n > 0 ? `${n}장 등록됨` : "사진·문서 업로드";
    }
    if ($("#step2Cap")) {
      $("#step2Cap").textContent = learned
        ? "분석 완료"
        : n > 0
          ? "분석 필요"
          : "구조·말투 분석";
    }
    if ($("#step3Cap")) {
      $("#step3Cap").textContent = learned ? "일지 작성에 적용 중" : "일지 생성 시 적용";
    }
    if (n > 0) {
      step1?.classList.add("is-done");
      if (learned) {
        step2?.classList.add("is-done");
        step3?.classList.add("is-done");
      } else {
        step2?.classList.add("is-active");
      }
    } else {
      step1?.classList.add("is-active");
    }

    // 인사이트
    if (data.style_summary || cols.length || data.form_title) {
      $("#styleSummaryBox").style.display = "";
      const title = data.form_title
        ? `<strong>${escapeHtml(data.form_title)}</strong><br/>`
        : "";
      const rules = (data.tone_rules || [])
        .slice(0, 4)
        .map((r) => `· ${escapeHtml(r)}`)
        .join("<br/>");
      $("#styleSummaryText").innerHTML =
        title +
        escapeHtml(data.style_summary || "서식 구조가 인식되었습니다.") +
        (rules
          ? `<br/><br/><span style="color:#94a3b8;font-size:0.85rem">${rules}</span>`
          : "");
    } else {
      $("#styleSummaryBox").style.display = "none";
    }

    const chips = $("#styleFormMeta");
    if (chips) {
      if (cols.length) {
        chips.style.display = "flex";
        chips.innerHTML = cols
          .slice(0, 12)
          .map((c) => `<span>${escapeHtml(String(c))}</span>`)
          .join("");
      } else {
        chips.style.display = "none";
        chips.innerHTML = "";
      }
    }

    const list = $("#styleSampleList");
    if (!list) return;
    if (!samples.length) {
      list.innerHTML = `<p style="color:var(--muted);font-size:0.9rem">아직 저장된 회사 서식이 없습니다.</p>`;
      return;
    }
    list.innerHTML = samples
      .map(
        (s) => `<div class="style-sample${s.is_active ? " is-active" : ""}">
        <div>
          <strong>${escapeHtml(s.filename || "회사 서식")}${s.is_active ? " · 주 서식" : ""}${
          s.source_type === "photo" ? " · 📷 사진" : ""
        }</strong>
          <span>${escapeHtml(s.preview || "")}</span>
          <div class="meta">${s.char_count || 0}자 · ${escapeHtml((s.uploaded_at || "").slice(0, 19).replace("T", " "))}</div>
        </div>
        <div class="style-sample-actions">
          ${
            s.is_active
              ? `<button class="btn btn-ghost" type="button" disabled>사용 중</button>`
              : `<button class="btn btn-ghost" type="button" data-activate-sample="${escapeHtml(s.id)}">주 서식</button>`
          }
          <button class="btn btn-ghost" type="button" data-del-sample="${escapeHtml(s.id)}">삭제</button>
        </div>
      </div>`
      )
      .join("");

    list.querySelectorAll("[data-del-sample]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        if (!confirm("이 회사 서식을 삭제할까요? 삭제 후 남은 서식으로 다시 학습합니다.")) return;
        try {
          const res = await api(`/api/style/samples/${btn.dataset.delSample}`, { method: "DELETE" });
          renderStyleStatus(res);
          toast("서식 삭제됨");
        } catch (err) {
          toast(err.message);
        }
      });
    });
    list.querySelectorAll("[data-activate-sample]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        try {
          const res = await api(`/api/style/samples/${btn.dataset.activateSample}/activate`, {
            method: "POST",
          });
          renderStyleStatus(res);
          toast("주 사용 서식으로 지정했습니다");
        } catch (err) {
          toast(err.message);
        }
      });
    });
  }

  async function loadDefaultTemplates() {
    const box = $("#defaultTemplateList");
    if (!box) return;
    try {
      const res = await fetch("/assets/templates/manifest.json", { cache: "no-store" });
      if (!res.ok) throw new Error("manifest missing");
      const list = await res.json();
      if (!Array.isArray(list) || !list.length) {
        box.innerHTML = `<p style="color:var(--muted);font-size:0.9rem">기본 서식이 없습니다.</p>`;
        return;
      }
      box.innerHTML = list
        .map(
          (t) => `<article class="template-pack-card">
          <strong>${escapeHtml(t.title || t.full_title || "서식")}</strong>
          <p>${escapeHtml(t.desc || t.full_title || "")}</p>
          <div class="template-pack-actions">
            <a href="${escapeHtml(t.xlsx)}" download>Excel 받기</a>
            <a href="${escapeHtml(t.docx)}" download>Word 받기</a>
          </div>
        </article>`
        )
        .join("");
    } catch {
      box.innerHTML = `<p style="color:var(--muted);font-size:0.9rem">기본 서식을 불러오지 못했습니다. 서버를 재시작해 주세요.</p>`;
    }
  }

  async function loadStyleStatus(_opts = {}) {
    // 기본 서식은 로그인 없이도 목록 표시
    // 로그인 모달은 showView(promptAuth)에서만 연다 — 여기서 openAuth 하면
    // 모달 닫기/뒤로가기 시 재오픈 루프가 생긴다
    loadDefaultTemplates();
    if (!state.token) {
      renderStyleStatus({
        sample_count: 0,
        max_samples: 5,
        min_recommended: 3,
        learned: false,
        samples: [],
        form_columns: [],
        message: "로그인 후 회사 서식을 등록하면 학습 상태가 표시됩니다.",
      });
      alertBox(
        $("#styleUploadAlert"),
        "info",
        "회사 서식 등록은 로그인 후 이용할 수 있습니다."
      );
      return;
    }
    try {
      const data = await api("/api/style");
      renderStyleStatus(data);
    } catch (err) {
      alertBox($("#styleUploadAlert"), "error", err.message);
    }
  }

  async function uploadStyleFiles(fileList) {
    if (!state.token) {
      openAuth();
      return;
    }
    const files = [...fileList];
    if (!files.length) return;
    const isPhoto = (f) =>
      (f.type || "").startsWith("image/") ||
      /\.(jpe?g|png|webp|gif|bmp|heic|heif)$/i.test(f.name || "");
    alertBox(
      $("#styleUploadAlert"),
      "info",
      files.some(isPhoto)
        ? `${files.length}개 업로드 중… 사진 서식은 AI가 분석합니다. 잠시만 기다려 주세요.`
        : `${files.length}개 파일 업로드 중...`
    );
    let last = null;
    for (const file of files) {
      const fd = new FormData();
      fd.append("file", file);
      try {
        const res = await fetch("/api/style/upload", {
          method: "POST",
          headers: { Authorization: `Bearer ${state.token}` },
          body: fd,
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          const detail = data.detail;
          throw new Error(
            typeof detail === "string" ? detail : detail?.msg || "업로드 실패"
          );
        }
        last = data;
        if (data.warning) toast(data.warning);
      } catch (err) {
        alertBox($("#styleUploadAlert"), "error", `${file.name}: ${err.message}`);
        return;
      }
    }
    if (last) {
      renderStyleStatus(last);
      alertBox(
        $("#styleUploadAlert"),
        "ok",
        last.learned
          ? "회사 서식이 저장·학습되었습니다. 일지 작성·인쇄에 반영됩니다."
          : "서식이 저장되었습니다. 3장 이상 권장 · 필요 시 ‘서식 다시 학습’을 눌러 주세요."
      );
      toast("회사 서식 저장 완료");
    }
  }

  function bindStyle() {
    const drop = $("#styleDrop");
    const input = $("#styleFile");
    $("#btnPickStyleFile")?.addEventListener("click", () => input?.click());
    drop?.addEventListener("click", () => input?.click());
    input?.addEventListener("change", () => {
      if (input.files?.length) uploadStyleFiles(input.files);
      input.value = "";
    });
    drop?.addEventListener("dragover", (e) => {
      e.preventDefault();
      drop.classList.add("dragover");
    });
    drop?.addEventListener("dragleave", () => drop.classList.remove("dragover"));
    drop?.addEventListener("drop", (e) => {
      e.preventDefault();
      drop.classList.remove("dragover");
      if (e.dataTransfer?.files?.length) uploadStyleFiles(e.dataTransfer.files);
    });

    $("#btnStyleLearn")?.addEventListener("click", async () => {
      if (!state.token) {
        openAuth();
        return;
      }
      try {
        alertBox($("#styleUploadAlert"), "info", "회사 서식·말투를 다시 학습 중...");
        const data = await api("/api/style/learn", { method: "POST" });
        renderStyleStatus(data);
        alertBox($("#styleUploadAlert"), "ok", "회사 서식 학습 완료");
        toast("서식 학습 완료");
      } catch (err) {
        alertBox($("#styleUploadAlert"), "error", err.message);
      }
    });

    $("#btnStylePaste")?.addEventListener("click", async () => {
      if (!state.token) {
        openAuth();
        return;
      }
      const title = $("#stylePasteTitle")?.value?.trim() || "회사 서식";
      const text = $("#stylePasteText")?.value?.trim() || "";
      try {
        const data = await api("/api/style/paste", {
          method: "POST",
          body: JSON.stringify({ title, text }),
        });
        renderStyleStatus(data);
        $("#stylePasteText").value = "";
        alertBox($("#styleUploadAlert"), "ok", "회사 서식이 저장되었습니다.");
        toast("서식 저장 완료");
      } catch (err) {
        alertBox($("#styleUploadAlert"), "error", err.message);
      }
    });
  }

  // ── Print ──
  function paperCssSize(paper, orient) {
    const map = {
      A4: "A4",
      A5: "A5",
      B5: "B5",
      Letter: "letter",
      Legal: "legal",
    };
    const size = map[paper] || "A4";
    return `${size} ${orient === "landscape" ? "landscape" : "portrait"}`;
  }

  function buildPrintHtml(log, paper, orient) {
    const trips = log.trips || [];
    const formTitle =
      (state.styleProfile && state.styleProfile.form_title) || "차량 운행일지";
    const rows = trips
      .map((t, i) => {
        return `<tr>
          <td>${i + 1}</td>
          <td>${escapeHtml(t.depart_time || "")}</td>
          <td>${escapeHtml(t.arrive_time || "")}</td>
          <td>${escapeHtml(t.from || "")}</td>
          <td>${escapeHtml(t.to || "")}</td>
          <td>${escapeHtml(t.purpose || "")}</td>
          <td style="text-align:right">${escapeHtml(String(t.distance_km ?? ""))}</td>
          <td>${escapeHtml(t.memo || "")}</td>
        </tr>`;
      })
      .join("");

    const page = paperCssSize(paper, orient);
    return `<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8" />
<title>${escapeHtml(formTitle)}</title>
<style>
  @page { size: ${page}; margin: 12mm; }
  * { box-sizing: border-box; }
  body {
    font-family: "Malgun Gothic", "Apple SD Gothic Neo", "Noto Sans KR", sans-serif;
    color: #111;
    font-size: 11pt;
    line-height: 1.45;
    margin: 0;
    padding: 0;
  }
  h1 {
    text-align: center;
    font-size: 18pt;
    margin: 0 0 14px;
    letter-spacing: -0.02em;
  }
  .meta {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 12px;
    font-size: 10pt;
  }
  .meta th, .meta td {
    border: 1px solid #333;
    padding: 6px 8px;
    text-align: left;
  }
  .meta th {
    background: #f3f4f6;
    width: 18%;
    font-weight: 700;
  }
  .trips {
    width: 100%;
    border-collapse: collapse;
    font-size: 9.5pt;
  }
  .trips th, .trips td {
    border: 1px solid #333;
    padding: 6px 5px;
    vertical-align: top;
  }
  .trips th {
    background: #111827;
    color: #fff;
    font-weight: 700;
    text-align: center;
  }
  .summary {
    margin-top: 12px;
    border: 1px solid #333;
    padding: 10px 12px;
    min-height: 48px;
  }
  .summary strong { display: block; margin-bottom: 4px; }
  .sign {
    margin-top: 22px;
    display: flex;
    justify-content: flex-end;
    gap: 40px;
    font-size: 10pt;
  }
  .sign div { min-width: 140px; text-align: center; }
  .sign .line { border-bottom: 1px solid #333; height: 28px; margin-top: 6px; }
  .foot {
    margin-top: 10px;
    font-size: 8.5pt;
    color: #555;
    text-align: right;
  }
  @media print {
    body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  }
</style>
</head>
<body>
  <h1>${escapeHtml(formTitle)}</h1>
  <table class="meta">
    <tr>
      <th>작성일</th><td>${escapeHtml(String(log.date || ""))}</td>
      <th>차량번호</th><td>${escapeHtml(String(log.vehicle || ""))}</td>
    </tr>
    <tr>
      <th>운전자</th><td>${escapeHtml(String(log.driver_name || ""))}</td>
      <th>회사명</th><td>${escapeHtml(String(log.company_name || ""))}</td>
    </tr>
    <tr>
      <th>최초 누적(km)</th><td>${escapeHtml(String(log.odometer_start ?? ""))}</td>
      <th>종료 누적(km)</th><td>${escapeHtml(String(log.odometer_end ?? ""))}</td>
    </tr>
    <tr>
      <th>총 거리(km)</th><td>${escapeHtml(String(log.total_distance_km ?? ""))}</td>
      <th>점심 장소</th><td>${escapeHtml(String(log.lunch_place || ""))}</td>
    </tr>
  </table>
  <table class="trips">
    <thead>
      <tr>
        <th style="width:36px">순번</th>
        <th style="width:70px">출발</th>
        <th style="width:70px">도착</th>
        <th>출발지</th>
        <th>도착지</th>
        <th>목적</th>
        <th style="width:64px">거리</th>
        <th>비고</th>
      </tr>
    </thead>
    <tbody>
      ${rows || `<tr><td colspan="8" style="text-align:center;padding:16px">운행 구간 없음</td></tr>`}
    </tbody>
  </table>
  <div class="summary">
    <strong>운행 요약</strong>
    ${escapeHtml(String(log.summary || ""))}
  </div>
  <div class="sign">
    <div>작성자<div class="line"></div></div>
    <div>확인자<div class="line"></div></div>
  </div>
  <div class="foot">용지: ${escapeHtml(paper)} · ${orient === "landscape" ? "가로" : "세로"}</div>
  <script>
    window.onload = function () {
      setTimeout(function () { window.focus(); window.print(); }, 250);
    };
  <\/script>
</body>
</html>`;
  }

  function openPrint(previewOnly) {
    if (!state.lastLog) {
      toast("먼저 일지를 생성해 주세요");
      return;
    }
    const paper = $("#paperSize")?.value || "A4";
    const orient = $("#printOrient")?.value || "portrait";
    const html = buildPrintHtml(state.lastLog, paper, orient);
    const w = window.open("", "_blank", "noopener,noreferrer,width=900,height=1000");
    if (!w) {
      toast("팝업이 차단되었습니다. 브라우저에서 팝업을 허용해 주세요.");
      return;
    }
    w.document.open();
    w.document.write(html);
    w.document.close();
    if (previewOnly) {
      // 미리보기만 — 자동 print 스크립트 제거를 위해 다시 씀
      const htmlNoAuto = html.replace(
        /<script>[\s\S]*?<\/script>/i,
        "<script>/* preview */<\/script>"
      );
      w.document.open();
      w.document.write(htmlNoAuto);
      w.document.close();
      toast("인쇄 미리보기 창을 열었습니다");
    } else {
      toast("인쇄 대화상자를 엽니다");
    }
  }

  function bindPrint() {
    $("#btnPrint")?.addEventListener("click", () => openPrint(false));
    $("#btnPrintPreview")?.addEventListener("click", () => openPrint(true));
  }

  // ── Admin ──
  function fmtWon(n) {
    return `₩${Number(n || 0).toLocaleString("ko-KR")}`;
  }

  function renderBarList(el, rows, labelKey, valueKey) {
    if (!el) return;
    const max = Math.max(1, ...rows.map((r) => Number(r[valueKey] || 0)));
    el.innerHTML = rows
      .map((r) => {
        const v = Number(r[valueKey] || 0);
        const pct = Math.round((v / max) * 100);
        return `<div class="admin-bar-row">
          <span>${escapeHtml(String(r[labelKey] || ""))}</span>
          <div class="admin-bar-track"><div class="admin-bar-fill" style="width:${pct}%"></div></div>
          <b>${fmtWon(v)}</b>
        </div>`;
      })
      .join("");
  }

  function renderAdminUsage(usage) {
    const metricsEl = $("#adminUsageMetrics");
    const tableEl = $("#adminUsageTable");
    const labelEl = $("#adminUsageTableLabel");
    const limitEl = $("#adminUsageFreeLimit");
    if (!metricsEl || !tableEl) return;

    if (!usage || !usage.summary) {
      metricsEl.innerHTML = `<p style="color:var(--muted);font-size:0.9rem">사용량 데이터를 불러오지 못했습니다.</p>`;
      tableEl.innerHTML = "";
      return;
    }

    const s = usage.summary;
    const month = usage.month || "";
    const freeLimit = usage.free_limit ?? 10;
    if (limitEl) limitEl.textContent = String(freeLimit);
    if (labelEl) {
      labelEl.textContent = `회원별 사용 횟수 (${month}) · 총 생성 ${s.total_generations ?? 0}회`;
    }

    metricsEl.innerHTML = [
      ["무료 회원 수", `${s.free_users ?? 0}명`],
      ["유료 회원 수", `${s.paid_users ?? 0}명`],
      ["무료 생성 합계", `${s.free_generations ?? 0}회`],
      ["유료 생성 합계", `${s.paid_generations ?? 0}회`],
      ["관리자 생성", `${s.admin_generations ?? 0}회`],
      ["이번 달 전체 생성", `${s.total_generations ?? 0}회`],
    ]
      .map(
        ([k, v]) =>
          `<div class="metric"><div class="label">${escapeHtml(k)}</div><div class="value">${escapeHtml(
            String(v)
          )}</div></div>`
      )
      .join("");

    const users = usage.users || [];
    if (!users.length) {
      tableEl.innerHTML = `<p style="color:var(--muted);padding:0.75rem;font-size:0.9rem">등록된 회원·사용 기록이 없습니다.</p>`;
      return;
    }

    const tierLabel = (t) => {
      if (t === "paid") return "유료";
      if (t === "admin") return "관리자";
      return "무료";
    };
    const tierClass = (t) => {
      if (t === "paid") return "uil-badge uil-badge-pro";
      if (t === "admin") return "uil-badge uil-badge-ent";
      return "uil-badge uil-badge-free";
    };

    const rowsHtml = users
      .map((u) => {
        const lim =
          u.limit == null ? "무제한" : `${u.usage ?? 0} / ${u.limit}`;
        const remain =
          u.remaining == null ? "—" : String(u.remaining);
        const badges = [
          `<span class="${tierClass(u.tier)}">${tierLabel(u.tier)}</span>`,
        ];
        if (u.is_vip) badges.push(`<span class="uil-badge uil-badge-pro">VIP</span>`);
        return `<tr>
          <td>${escapeHtml(u.email || "")}</td>
          <td>${escapeHtml(u.name || "—")}</td>
          <td>${badges.join(" ")}</td>
          <td style="text-align:right;font-variant-numeric:tabular-nums"><strong>${Number(
            u.usage || 0
          )}</strong></td>
          <td style="text-align:right;color:var(--muted)">${escapeHtml(lim)}</td>
          <td style="text-align:right;color:var(--muted)">${escapeHtml(remain)}</td>
        </tr>`;
      })
      .join("");

    tableEl.innerHTML = `<table class="admin-table">
      <thead>
        <tr>
          <th>이메일</th>
          <th>이름</th>
          <th>구분</th>
          <th style="text-align:right">이번 달 생성</th>
          <th style="text-align:right">한도</th>
          <th style="text-align:right">잔여</th>
        </tr>
      </thead>
      <tbody>${rowsHtml}</tbody>
    </table>`;
  }

  function renderVipList(members) {
    const list = $("#vipList");
    if (!list) return;
    if (!members?.length) {
      list.innerHTML = `<p style="color:var(--muted);font-size:0.9rem">등록된 VIP가 없습니다.</p>`;
      return;
    }
    list.innerHTML = members
      .map(
        (m) => `<div class="style-sample">
        <div>
          <strong>${escapeHtml(m.id || m.email || "VIP")}</strong>
          <span>${escapeHtml(m.note || "평생 무료")}</span>
          <div class="meta">${escapeHtml((m.added_at || "").slice(0, 19).replace("T", " "))} · ${escapeHtml(
          m.added_by || ""
        )}</div>
        </div>
        <button class="btn btn-ghost" type="button" data-del-vip="${escapeHtml(m.id || m.email)}">삭제</button>
      </div>`
      )
      .join("");
    list.querySelectorAll("[data-del-vip]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        if (!confirm("이 VIP를 삭제할까요?")) return;
        try {
          const res = await api(`/api/admin/vip/${encodeURIComponent(btn.dataset.delVip)}`, {
            method: "DELETE",
          });
          renderVipList(res.vip_members || []);
          toast("VIP 삭제됨");
        } catch (err) {
          toast(err.message);
        }
      });
    });
  }

  function ymdLocal(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
  }

  function setRevenueDateDefaults(mode) {
    const to = new Date();
    let from = new Date();
    if (mode === "today") {
      // same day
    } else if (mode === "7") {
      from.setDate(to.getDate() - 6);
    } else if (mode === "30") {
      from.setDate(to.getDate() - 29);
    } else {
      // this month
      from = new Date(to.getFullYear(), to.getMonth(), 1);
    }
    if ($("#revDateFrom")) $("#revDateFrom").value = ymdLocal(from);
    if ($("#revDateTo")) $("#revDateTo").value = ymdLocal(to);
  }

  async function loadAdminDashboard(opts = {}) {
    if (!state.token) {
      // 로그인 유도는 showView promptAuth에서 처리
      return;
    }
    // 실제 관리자만 (미리보기 모드와 무관)
    if (!isRealAdmin()) {
      toast("관리자만 접근할 수 있습니다");
      showView("home", { replaceHistory: true });
      return;
    }
    // Pro/Ent 미리보기 중이면 관리자 UI 대신 전환 안내
    if (getViewAsMode() !== "admin") {
      toast("관리자 기능은 「관리자로 보기」로 전환 후 이용하세요");
      showView("home", { replaceHistory: true });
      return;
    }

    // 날짜 기본값 (첫 로드)
    if (!$("#revDateFrom")?.value || !$("#revDateTo")?.value) {
      setRevenueDateDefaults("month");
    }
    if (opts.preset) {
      setRevenueDateDefaults(opts.preset);
    }

    const dateFrom = $("#revDateFrom")?.value || "";
    const dateTo = $("#revDateTo")?.value || "";
    const q = new URLSearchParams();
    if (dateFrom) q.set("date_from", dateFrom);
    if (dateTo) q.set("date_to", dateTo);
    const qs = q.toString() ? `?${q.toString()}` : "";

    try {
      const data = await api(`/api/admin/dashboard${qs}`);
      // date inputs sync from server
      if (data.date_from && $("#revDateFrom")) $("#revDateFrom").value = data.date_from;
      if (data.date_to && $("#revDateTo")) $("#revDateTo").value = data.date_to;

      $("#adminMetrics").innerHTML = [
        ["선택 기간 매출", fmtWon(data.range_revenue)],
        ["선택 기간 결제", `${data.range_payment_count ?? 0}건`],
        ["오늘 매출", fmtWon(data.day_revenue)],
        ["이번 달 매출", fmtWon(data.month_revenue)],
        ["전체 회원", `${data.total_users}명`],
        ["Pro 회원", `${data.pro_users}명`],
        ["VIP 회원", `${data.vip_count}명`],
      ]
        .map(
          ([k, v]) =>
            `<div class="metric"><div class="label">${escapeHtml(k)}</div><div class="value">${escapeHtml(
              String(v)
            )}</div></div>`
        )
        .join("");

      renderAdminUsage(data.usage || null);

      const rangeLabel = $("#adminRangeLabel");
      if (rangeLabel) {
        rangeLabel.textContent = `선택 기간 날짜별 매출 (${data.date_from || ""} ~ ${data.date_to || ""}) · 합계 ${fmtWon(
          data.range_revenue
        )}`;
      }

      // 날짜별 breakdown (선택 기간) — 있으면 사용, 없으면 14일 트렌드
      const dailyRows = (data.daily_breakdown || data.daily_trend || []).map((r) => ({
        date: r.date,
        revenue: r.revenue,
        label: r.count != null ? `${r.date} (${r.count}건)` : r.date,
      }));
      // bar list uses date key — extend render for count in label
      renderBarList($("#adminDailyBars"), dailyRows, "date", "revenue");
      // enhance bar labels with count if present
      const bars = $("#adminDailyBars");
      if (bars && data.daily_breakdown) {
        const map = Object.fromEntries(
          (data.daily_breakdown || []).map((r) => [r.date, r])
        );
        bars.querySelectorAll(".admin-bar-row").forEach((row) => {
          const d = row.querySelector("span")?.textContent;
          if (d && map[d]) {
            const c = map[d].count || 0;
            const span = row.querySelector("span");
            if (span) span.textContent = c ? `${d} · ${c}건` : d;
          }
        });
      }

      renderBarList($("#adminMonthlyBars"), data.monthly_trend || [], "month", "revenue");

      const pays = data.range_payments || data.month_payments || [];
      const payLabel = $("#adminPayTableLabel");
      if (payLabel) {
        payLabel.textContent = `선택 기간 결제 내역 (${pays.length}건 · ${fmtWon(data.range_revenue)})`;
      }
      const table = $("#adminPayTable");
      if (table) {
        if (!pays.length) {
          table.innerHTML = `<p style="color:var(--muted);padding:0.75rem;font-size:0.9rem">선택 기간에 결제 내역이 없습니다.</p>`;
        } else {
          // 날짜별 소계 테이블 상단
          const byDay = {};
          pays.forEach((p) => {
            const d = String(p.paid_at || "").slice(0, 10);
            if (!d) return;
            byDay[d] = (byDay[d] || 0) + Number(p.amount || 0);
          });
          const daySumRows = Object.keys(byDay)
            .sort()
            .reverse()
            .map((d) => `<tr class="admin-day-sum"><td colspan="2"><strong>${escapeHtml(d)}</strong> 합계</td><td></td><td><strong>${fmtWon(
              byDay[d]
            )}</strong></td><td></td></tr>`)
            .join("");

          table.innerHTML = `<table class="admin-table">
            <thead><tr><th>일시</th><th>이메일</th><th>플랜</th><th>금액</th><th>메모</th></tr></thead>
            <tbody>
              ${pays
                .map(
                  (p) => `<tr>
                  <td>${escapeHtml(String(p.paid_at || "").slice(0, 19).replace("T", " "))}</td>
                  <td>${escapeHtml(p.email || "")}</td>
                  <td>${escapeHtml(p.plan || "")}</td>
                  <td>${fmtWon(p.amount)}</td>
                  <td>${escapeHtml(p.note || "")}</td>
                </tr>`
                )
                .join("")}
              ${daySumRows ? `<tr><td colspan="5" style="padding-top:0.75rem;color:#94a3b8;font-size:0.8rem">— 날짜별 합계 —</td></tr>${daySumRows}` : ""}
            </tbody>
          </table>`;
        }
      }

      const b = data.billing || {};
      if ($("#adminProPrice")) $("#adminProPrice").value = b.pro_price_krw ?? 9900;
      if ($("#adminEntPrice")) $("#adminEntPrice").value = b.enterprise_price_krw ?? 99000;
      renderVipList(data.vip_members || []);
    } catch (err) {
      toast(err.message);
    }
  }

  function bindAdmin() {
    $("#btnRevApply")?.addEventListener("click", () => loadAdminDashboard());
    $("#btnRevThisMonth")?.addEventListener("click", () => loadAdminDashboard({ preset: "month" }));
    $("#btnRevToday")?.addEventListener("click", () => loadAdminDashboard({ preset: "today" }));
    $("#btnRev7")?.addEventListener("click", () => loadAdminDashboard({ preset: "7" }));
    $("#btnRev30")?.addEventListener("click", () => loadAdminDashboard({ preset: "30" }));

    $("#btnSaveBilling")?.addEventListener("click", async () => {
      try {
        const pro = Number($("#adminProPrice")?.value || 0);
        const ent = Number($("#adminEntPrice")?.value || 0);
        await api("/api/admin/billing", {
          method: "PUT",
          body: JSON.stringify({
            pro_price_krw: pro,
            enterprise_price_krw: ent,
          }),
        });
        alertBox($("#adminBillingAlert"), "ok", "구독 요금이 저장되었습니다.");
        toast("요금 저장 완료");
        // meta 가격 갱신 → 요금제 화면 반영
        try {
          state.meta = await api("/api/meta");
          applyPricingFromMeta(state.meta);
        } catch {
          /* ignore */
        }
      } catch (err) {
        alertBox($("#adminBillingAlert"), "error", err.message);
      }
    });

    $("#btnAddVip")?.addEventListener("click", async () => {
      try {
        const id = $("#vipId")?.value?.trim() || "";
        const note = $("#vipNote")?.value?.trim() || "";
        const res = await api("/api/admin/vip", {
          method: "POST",
          body: JSON.stringify({ id, email: id.includes("@") ? id : "", note }),
        });
        renderVipList(res.vip_members || []);
        if ($("#vipId")) $("#vipId").value = "";
        if ($("#vipNote")) $("#vipNote").value = "";
        alertBox($("#adminVipAlert"), "ok", "VIP가 등록되었습니다. (평생 무료)");
        toast("VIP 등록 완료");
      } catch (err) {
        alertBox($("#adminVipAlert"), "error", err.message);
      }
    });
  }

  // ── Product demo player ──
  function bindDemoPlayer() {
    const SCENE_MS = 4200;
    const TOTAL = 4;
    let idx = 0;
    let playing = true;
    let timer = null;
    let tickTimer = null;
    let progress = 0;

    const scenes = $$(".demo-scene");
    const steps = $$("#demoSteps button");
    const fill = $("#demoProgress");
    const playBtn = $("#demoPlayBtn");
    const videoWrap = $("#demoVideoWrap");
    const player = $("#demoPlayer");
    const video = $("#demoVideo");

    // 랜딩 개편 후 데모 씬이 없으면 스킵
    if (!scenes.length && !video) {
      window.__demoPlayer = { play() {}, pause() {}, setScene() {} };
      return;
    }

    function setScene(i) {
      idx = ((i % TOTAL) + TOTAL) % TOTAL;
      scenes.forEach((s, n) => s.classList.toggle("is-active", n === idx));
      steps.forEach((b, n) => b.classList.toggle("is-on", n === idx));
      progress = 0;
      if (fill) fill.style.width = "0%";
      // re-trigger type animations
      scenes[idx]?.querySelectorAll(".type-num").forEach((el) => {
        el.style.animation = "none";
        // force reflow
        void el.offsetWidth;
        el.style.animation = "";
      });
    }

    function stopTick() {
      if (tickTimer) clearInterval(tickTimer);
      tickTimer = null;
      if (timer) clearTimeout(timer);
      timer = null;
    }

    function startTick() {
      stopTick();
      if (!playing) return;
      const start = Date.now();
      tickTimer = setInterval(() => {
        const p = Math.min(1, (Date.now() - start) / SCENE_MS);
        progress = p;
        if (fill) fill.style.width = `${p * 100}%`;
        if (p >= 1) {
          clearInterval(tickTimer);
          tickTimer = null;
          setScene(idx + 1);
          startTick();
        }
      }, 40);
    }

    function play() {
      playing = true;
      if (playBtn) playBtn.textContent = "❚❚";
      startTick();
    }
    function pause() {
      playing = false;
      if (playBtn) playBtn.textContent = "▶";
      stopTick();
    }

    playBtn?.addEventListener("click", () => {
      if (playing) pause();
      else play();
    });
    steps.forEach((b) => {
      b.addEventListener("click", () => {
        setScene(Number(b.dataset.go) || 0);
        if (playing) startTick();
      });
    });

    // real mp4 detection (SPA fallback이 HTML을 줄 수 있어 content-type 확인)
    async function tryRealVideo() {
      try {
        const res = await fetch("/assets/demo.mp4", { method: "GET", headers: { Range: "bytes=0-0" } });
        const ct = (res.headers.get("content-type") || "").toLowerCase();
        if (res.ok && (ct.includes("video") || ct.includes("mp4") || ct.includes("octet-stream"))) {
          videoWrap?.classList.remove("hidden");
          player?.classList.add("hidden");
          pause();
          return true;
        }
      } catch {
        /* use animated demo */
      }
      videoWrap?.classList.add("hidden");
      player?.classList.remove("hidden");
      setScene(0);
      play();
      return false;
    }

    window.__demoPlayer = { play, pause, setScene };
    tryRealVideo();

    // pause when off-screen to save CPU
    if (player && "IntersectionObserver" in window) {
      const io = new IntersectionObserver(
        (entries) => {
          entries.forEach((e) => {
            if (!e.isIntersecting) pause();
          });
        },
        { threshold: 0.2 }
      );
      io.observe(player);
    }
  }

  function formatPriceKrw(n) {
    return Number(n || 0).toLocaleString("ko-KR");
  }

  function applyPricingFromMeta(meta) {
    if (!meta) return;
    state.meta = { ...(state.meta || {}), ...meta };
    if (meta.free_limit && $("#priceFreeLimit")) {
      $("#priceFreeLimit").textContent = String(meta.free_limit);
    }
    if (meta.pro_price != null && $("#pricePro")) {
      $("#pricePro").textContent = formatPriceKrw(meta.pro_price);
    }
    if (meta.enterprise_price != null && $("#priceEnt")) {
      $("#priceEnt").textContent = formatPriceKrw(meta.enterprise_price);
    }
    const wirePayLink = (sel, url) => {
      const el = $(sel);
      if (!el) return;
      const u = (url || "").trim();
      const isPlaceholder = isPlaceholderPayUrl(u);
      if (!isPlaceholder) {
        el.href = u;
        el.target = "_blank";
        el.rel = "noopener noreferrer";
        el.hidden = false;
        el.removeAttribute("aria-disabled");
      } else {
        // href="#" 클릭 시 SPA 해시/스크롤 깨짐 방지
        el.href = "#pricing";
        el.removeAttribute("target");
        el.hidden = true;
        el.setAttribute("aria-disabled", "true");
      }
    };
    wirePayLink("#proLink", meta.pro_url);
    wirePayLink(
      "#entLink",
      meta.enterprise_url || meta.pro_url || ""
    );
    applyPricingCtaLabels();
    applyContactFromMeta(meta);
  }

  const DEFAULT_CONTACT_FORM_URL =
    "https://docs.google.com/forms/d/e/1FAIpQLScl9ZJD_crv1d6JPDzdNaYTDzUQXKkLNx_X6pmyEwsg_1DnGg/viewform?usp=sf_link";

  function applyContactFromMeta(meta) {
    if (!meta) return;
    const email = (meta.contact_email || "corelabs.studio@gmail.com").trim();
    const formUrl = (
      meta.contact_form_url ||
      DEFAULT_CONTACT_FORM_URL
    ).trim();
    const mailto = `mailto:${email}`;

    const setMail = (sel) => {
      const el = $(sel);
      if (!el) return;
      el.href = mailto;
      if (el.classList.contains("contact-mail") || el.id === "contactMailLink") {
        el.textContent = email;
      }
    };

    setMail("#contactMailLink");
    setMail("#contactMailBtn");
    setMail("#btnFeedbackMail");

    // Footer contact
    $$(".footer-contact").forEach((a) => {
      a.href = mailto;
      const span = a.querySelector("span");
      if (span) span.textContent = `문의: ${email}`;
    });

    // 문의 폼 버튼: 구글 폼 새 탭 고정
    const formBtn = $("#btnFeedbackForm");
    if (formBtn) {
      const url =
        formUrl && /^https?:\/\//i.test(formUrl)
          ? formUrl
          : DEFAULT_CONTACT_FORM_URL;
      formBtn.href = url;
      formBtn.target = "_blank";
      formBtn.rel = "noopener noreferrer";
      formBtn.setAttribute("aria-label", "서비스 피드백 및 문의하기 (새 탭에서 구글 폼 열기)");
    }
  }

  function bindFeedbackForm() {
    const formBtn = $("#btnFeedbackForm");
    if (!formBtn) return;
    // 클릭 시 항상 새 탭으로 구글 폼 (중간 가로채기·SPA 네비 방지)
    formBtn.addEventListener("click", (e) => {
      const url = (formBtn.getAttribute("href") || DEFAULT_CONTACT_FORM_URL).trim();
      if (!/^https?:\/\//i.test(url)) return;
      e.preventDefault();
      const w = window.open(url, "_blank", "noopener,noreferrer");
      if (!w) {
        // 팝업 차단 시 동일 탭 폴백
        window.location.assign(url);
      }
    });
  }

  // ── 퀵 스탬프 (GPS + 시간 + 주소) ──
  function stampStorageKey() {
    const d = new Date();
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${STAMPS_KEY_PREFIX}${y}-${m}-${day}`;
  }

  /** 스탬프 시각 → 오전/오후 카테고리 (12:00 미만 = morning) */
  function stampPeriodFromTs(ts) {
    try {
      const h = new Date(ts || Date.now()).getHours();
      return h < 12 ? "morning" : "afternoon";
    } catch {
      return "afternoon";
    }
  }

  function periodLabel(period) {
    return period === "morning" ? t("period.morning") : t("period.afternoon");
  }

  function loadStamps() {
    try {
      const raw = localStorage.getItem(stampStorageKey());
      const arr = raw ? JSON.parse(raw) : [];
      let stamps = Array.isArray(arr) ? arr : [];
      // 레거시 스탬프에 period 태그 보정
      let migrated = false;
      stamps = stamps.map((s) => {
        if (!s || typeof s !== "object") return s;
        if (!s.period) {
          migrated = true;
          return { ...s, period: stampPeriodFromTs(s.timestamp) };
        }
        return s;
      });
      state.stamps = stamps;
      if (migrated) saveStamps();
    } catch {
      state.stamps = [];
    }
    return state.stamps;
  }

  function saveStamps() {
    // localStorage 즉시 기록 + syncData 파이프라인 (saveData)
    try {
      localStorage.setItem(stampStorageKey(), JSON.stringify(state.stamps || []));
    } catch (e) {
      console.warn("stamp persist failed", e);
      toast("스탬프 저장 공간이 부족합니다. 일부 데이터를 비워 주세요.");
      return;
    }
    // 서버 연동 대비: 백그라운드 동기화 (UI 블로킹 없음)
    saveData({ type: "stamps", payload: state.stamps }).catch(() => {});
  }

  function formatStampTime(iso) {
    try {
      const d = new Date(iso);
      return d.toLocaleString("ko-KR", {
        month: "numeric",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      });
    } catch {
      return iso;
    }
  }

  /** 긴 주소 → 건물/시설명 + 동 단위 짧은 표기 */
  function shortenKoreanAddress(displayName, raw) {
    const text = String(displayName || "").trim();
    raw = raw && typeof raw === "object" ? raw : {};

    const placeKeys = [
      "building",
      "amenity",
      "tourism",
      "leisure",
      "shop",
      "office",
    ];
    const dongKeys = [
      "suburb",
      "neighbourhood",
      "neighborhood",
      "quarter",
      "city_district",
      "borough",
      "hamlet",
      "village",
    ];
    let place = "";
    for (const k of placeKeys) {
      const v = String(raw[k] || "").trim();
      if (v) {
        place = v;
        break;
      }
    }
    let dong = "";
    for (const k of dongKeys) {
      const v = String(raw[k] || "").trim();
      if (v && /(동|가|리|읍|면)$/.test(v)) {
        dong = v;
        break;
      }
    }
    if (!dong) {
      for (const k of dongKeys) {
        const v = String(raw[k] || "").trim();
        if (v) {
          dong = v;
          break;
        }
      }
    }
    if (place && dong && place !== dong) return `${place}, ${dong}`;
    if (place) return place;
    if (dong) return dong;

    if (!text) return "";
    const parts = text
      .split(/[,/|]/)
      .map((p) => p.trim())
      .filter(Boolean);
    const dropExact = new Set([
      "대한민국",
      "한국",
      "korea",
      "south korea",
      "republic of korea",
    ]);
    const roadRe = /(로|길|대로|거리|로\d*번길)$/;
    const dongRe = /(동|가|리|읍|면)$/;
    const cityRe = /(특별자치도|광역시|특별시|자치시|도|시|군)$/;
    const buildingRe =
      /(아파트|APT|빌라|타워|오피스텔|센터|빌딩|병원|학교|마트|역|터미널|공원|시장|교회|성당|사찰)/i;

    const buildings = [];
    const dongs = [];
    for (const p of parts) {
      const pl = p.toLowerCase();
      if (dropExact.has(pl)) continue;
      if (/^\d{4,6}$/.test(p)) continue; // 우편번호
      if (cityRe.test(p) && !dongRe.test(p) && !buildingRe.test(p)) continue;
      if (roadRe.test(p) && !buildingRe.test(p)) continue; // 도로명
      if (dongRe.test(p)) dongs.push(p);
      else if (buildingRe.test(p) || p.length >= 3) buildings.push(p);
    }
    const out = [];
    if (buildings[0]) out.push(buildings[0]);
    if (dongs[0]) out.push(dongs[0]);
    if (out.length) return out.join(", ");
    const filtered = parts.filter(
      (p) => !dropExact.has(p.toLowerCase()) && !/^\d{4,6}$/.test(p)
    );
    return (filtered.slice(0, 2).join(", ") || text).trim();
  }

  function stampShortAddress(s) {
    if (!s) return "주소 없음";
    if (s.address_short) return s.address_short;
    if (s.short_address) return s.short_address;
    const full = s.address_full || s.address || "";
    return shortenKoreanAddress(full, s.raw) || full || "주소 없음";
  }

  function stampFullAddress(s) {
    if (!s) return "";
    return s.address_full || s.address || "";
  }

  function renderStampList() {
    const list = $("#quickStampList");
    if (!list) return;
    const stamps = state.stamps || [];
    if (!stamps.length) {
      list.innerHTML =
        '<li class="quick-stamp-empty">아직 스탬프가 없습니다. 현장에서 「지금 위치 스탬프」를 눌러 주세요.</li>';
      return;
    }
    list.innerHTML = stamps
      .map((s) => {
        const shortA = stampShortAddress(s);
        const fullA = stampFullAddress(s);
        const showDetail = fullA && fullA !== shortA;
        const period = s.period || stampPeriodFromTs(s.timestamp);
        const pLabel = periodLabel(period);
        return `<li class="quick-stamp-item" data-id="${escapeHtml(s.id)}" data-period="${escapeHtml(
          period
        )}">
          <div class="stamp-body">
            <div class="stamp-head-row">
              <time datetime="${escapeHtml(s.timestamp)}">${escapeHtml(
                formatStampTime(s.timestamp)
              )}</time>
              <span class="stamp-period-tag stamp-period-${escapeHtml(period)}">${escapeHtml(
                pLabel
              )}</span>
            </div>
            <div class="addr-short">${escapeHtml(shortA)}</div>
            ${
              showDetail
                ? `<button type="button" class="stamp-detail-btn" data-toggle-detail="${escapeHtml(
                    s.id
                  )}" aria-expanded="false">상세 주소</button>
            <div class="addr-full" id="stamp-full-${escapeHtml(
              s.id
            )}" hidden>${escapeHtml(fullA)}</div>`
                : ""
            }
            <div class="meta">${
              s.lat != null && s.lon != null
                ? `${Number(s.lat).toFixed(5)}, ${Number(s.lon).toFixed(5)}`
                : ""
            }</div>
          </div>
          <button type="button" class="stamp-del" data-del-stamp="${escapeHtml(
            s.id
          )}">삭제</button>
        </li>`;
      })
      .join("");
  }

  function getPosition() {
    return new Promise((resolve, reject) => {
      if (!navigator.geolocation) {
        reject(new Error("이 브라우저는 위치 정보를 지원하지 않습니다."));
        return;
      }
      navigator.geolocation.getCurrentPosition(resolve, reject, {
        enableHighAccuracy: true,
        timeout: 15000,
        maximumAge: 0,
      });
    });
  }

  async function reverseGeocode(lat, lon) {
    const data = await api(
      `/api/geo/reverse?lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lon)}`
    );
    const full =
      data.address_full ||
      data.address ||
      `${lat.toFixed(5)}, ${lon.toFixed(5)}`;
    const short =
      data.short_address ||
      data.address ||
      shortenKoreanAddress(full, data.raw) ||
      full;
    return {
      address_short: short,
      address_full: full,
      raw: data.raw || {},
    };
  }

  function stampLine(s) {
    const t = formatStampTime(s.timestamp);
    const p = periodLabel(s.period || stampPeriodFromTs(s.timestamp));
    return `[${p}] ${t} · ${stampShortAddress(s)}`;
  }

  /** 일지 생성 직전: localStorage 스탬프 → 오전/오후 필드 병합 (데이터 손실 방지) */
  function mergeStampsIntoFormFields() {
    loadStamps();
    const stamps = state.stamps || [];
    if (!stamps.length) return { morning: 0, afternoon: 0 };

    const morningEl = $("#morningPlaces");
    const afternoonEl = $("#afternoonPlaces");
    let mAdd = 0;
    let aAdd = 0;

    const ensureLine = (el, line) => {
      if (!el || !line) return false;
      const prev = el.value || "";
      if (prev.includes(line)) return false;
      el.value = prev.trim() ? `${prev.trim()}\n${line}` : line;
      return true;
    };

    // 시간 오름차순으로 병합 (일지 가독성)
    const ordered = [...stamps].sort(
      (a, b) => new Date(a.timestamp) - new Date(b.timestamp)
    );
    for (const s of ordered) {
      const period = s.period || stampPeriodFromTs(s.timestamp);
      const line = stampLine(s);
      if (period === "morning") {
        if (ensureLine(morningEl, line)) mAdd += 1;
      } else {
        if (ensureLine(afternoonEl, line)) aAdd += 1;
      }
    }
    return { morning: mAdd, afternoon: aAdd };
  }

  function appendStampsToField(fieldId) {
    const el = $(fieldId);
    if (!el) return;
    loadStamps();
    const wantMorning = fieldId.includes("morning");
    const stamps = (state.stamps || []).filter((s) => {
      const p = s.period || stampPeriodFromTs(s.timestamp);
      return wantMorning ? p === "morning" : p === "afternoon";
    });
    if (!stamps.length) {
      toast(
        wantMorning
          ? "오전 스탬프가 없습니다"
          : "오후 스탬프가 없습니다"
      );
      return;
    }
    const ordered = [...stamps].sort(
      (a, b) => new Date(a.timestamp) - new Date(b.timestamp)
    );
    let added = 0;
    for (const s of ordered) {
      const line = stampLine(s);
      if (!(el.value || "").includes(line)) {
        const prev = (el.value || "").trim();
        el.value = prev ? `${prev}\n${line}` : line;
        added += 1;
      }
    }
    toast(
      wantMorning
        ? `오전 방문지에 ${added}건 반영`
        : `오후 방문지에 ${added}건 반영`
    );
  }

  function bindQuickStamp() {
    loadStamps();
    renderStampList();

    $("#btnQuickStamp")?.addEventListener("click", async () => {
      const btn = $("#btnQuickStamp");
      btn?.classList.add("is-loading");
      if (btn) btn.disabled = true;
      alertBox($("#stampAlert"), "info", "위치·주소를 확인하는 중…");
      try {
        const pos = await getPosition();
        const lat = pos.coords.latitude;
        const lon = pos.coords.longitude;
        const timestamp = new Date().toISOString();
        let address_short;
        let address_full;
        let raw = {};
        try {
          const geo = await reverseGeocode(lat, lon);
          address_short = geo.address_short;
          address_full = geo.address_full;
          raw = geo.raw || {};
        } catch (geoErr) {
          address_full = `좌표 ${lat.toFixed(5)}, ${lon.toFixed(5)} (주소 변환 실패)`;
          address_short = address_full;
          console.warn(geoErr);
        }
        const period = stampPeriodFromTs(timestamp);
        const stamp = {
          id: `s_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 7)}`,
          timestamp,
          date: new Date(timestamp).toISOString().slice(0, 10),
          period, // morning | afternoon — 일지 매핑 핵심
          address: address_short, // 일지·리스트 기본 = 짧은 주소
          address_short,
          address_full,
          raw,
          lat,
          lon,
        };
        state.stamps = [stamp, ...(state.stamps || [])];
        saveStamps();
        renderStampList();
        alertBox(
          $("#stampAlert"),
          "ok",
          `기록됨 · ${periodLabel(period)} · ${formatStampTime(timestamp)} · ${address_short}`
        );
        toast(`퀵 스탬프 저장 (${periodLabel(period)})`);

        // 카테고리 필드에 자동 반영 (짧은 주소 + 오전/오후 태그)
        const field = period === "morning" ? "#morningPlaces" : "#afternoonPlaces";
        const el = $(field);
        if (el) {
          const line = stampLine(stamp);
          const prev = (el.value || "").trim();
          if (!prev.includes(line)) {
            el.value = prev ? `${prev}\n${line}` : line;
          }
        }
      } catch (err) {
        const denied =
          err &&
          (err.code === 1 ||
            /denied|permission|권한/i.test(String(err.message || err)));
        const msg = denied
          ? "위치 접근 권한이 필요합니다"
          : err.message || "위치를 가져오지 못했습니다";
        alertBox($("#stampAlert"), "error", msg);
        toast(msg);
      } finally {
        btn?.classList.remove("is-loading");
        if (btn) btn.disabled = false;
      }
    });

    $("#quickStampList")?.addEventListener("click", (e) => {
      const del = e.target.closest("[data-del-stamp]");
      if (del) {
        const id = del.dataset.delStamp;
        state.stamps = (state.stamps || []).filter((s) => s.id !== id);
        saveStamps();
        renderStampList();
        return;
      }
      const tog = e.target.closest("[data-toggle-detail]");
      if (tog) {
        const id = tog.dataset.toggleDetail;
        const panel = document.getElementById(`stamp-full-${id}`);
        if (!panel) return;
        const open = panel.hasAttribute("hidden");
        if (open) {
          panel.removeAttribute("hidden");
          tog.setAttribute("aria-expanded", "true");
          tog.textContent = "상세 접기";
        } else {
          panel.setAttribute("hidden", "");
          tog.setAttribute("aria-expanded", "false");
          tog.textContent = "상세 주소";
        }
      }
    });

    $("#btnStampsToMorning")?.addEventListener("click", () =>
      appendStampsToField("#morningPlaces")
    );
    $("#btnStampsToAfternoon")?.addEventListener("click", () =>
      appendStampsToField("#afternoonPlaces")
    );
    $("#btnClearStamps")?.addEventListener("click", () => {
      if (!state.stamps?.length) return;
      if (!confirm("오늘 스탬프를 모두 삭제할까요?")) return;
      state.stamps = [];
      saveStamps();
      renderStampList();
      alertBox($("#stampAlert"), "info", "");
    });
  }

  // ── PWA 설치 ──
  let deferredInstallPrompt = null;

  function isStandaloneApp() {
    return (
      window.matchMedia("(display-mode: standalone)").matches ||
      window.navigator.standalone === true
    );
  }

  /**
   * 설치 UI 통합 관리
   * - 이미 설치(standalone): .install-action 전부 숨김
   * - 미설치: data-install-primary(또는 첫 버튼) 1개만 표시
   */
  function refreshInstallUI() {
    // 브라우저 탭 vs 홈화면 앱 구분
    const isInstalled =
      window.matchMedia("(display-mode: standalone)").matches ||
      window.navigator.standalone === true;

    const installElements = document.querySelectorAll(".install-action");
    if (!installElements.length) return;

    if (isInstalled) {
      // 1) 이미 설치됨 → 설치 유도 UI 전부 숨김
      installElements.forEach((el) => {
        el.style.display = "none";
        el.hidden = true;
        el.setAttribute("aria-hidden", "true");
      });
      console.log("RoadLog: 앱이 설치됨, 설치 UI 숨김.");
      return;
    }

    // 2) 미설치 → 대표 버튼 1개만 남김 (primary 우선, 없으면 index 0)
    const primary =
      document.querySelector(".install-action[data-install-primary]") ||
      installElements[0];

    installElements.forEach((el) => {
      const show = el === primary;
      // 인라인 버튼은 flex 레이아웃 유지
      if (show) {
        el.hidden = false;
        el.style.display = "";
        el.removeAttribute("aria-hidden");
        el.disabled = false;
        el.classList.remove("is-installed");
        // 기본 HTML 복원 (설치됨 문구가 남아 있을 수 있음)
        if (el.dataset.defaultHtml) el.innerHTML = el.dataset.defaultHtml;
      } else {
        el.style.display = "none";
        el.hidden = true;
        el.setAttribute("aria-hidden", "true");
      }
    });

    // iOS 등: beforeinstallprompt 없이도 primary 는 안내 클릭 가능
    const isIOS =
      /iphone|ipad|ipod/i.test(navigator.userAgent) && !window.MSStream;
    if (primary && isIOS && !deferredInstallPrompt) {
      primary.title = "Safari 공유 → 홈 화면에 추가";
    }
  }

  // 기존 호출부 호환 별칭
  function updateInstallButtonVisibility() {
    // 기본 HTML 스냅샷 (최초 1회)
    document.querySelectorAll(".install-action").forEach((el) => {
      if (!el.dataset.defaultHtml) el.dataset.defaultHtml = el.innerHTML;
    });
    refreshInstallUI();
  }

  function playInstallIconFx(fromEl) {
    const fx = document.createElement("div");
    fx.className = "install-fx";
    fx.textContent = "로드";
    const rect = fromEl?.getBoundingClientRect?.();
    if (rect) {
      fx.style.left = `${rect.left + rect.width / 2 - 28}px`;
      fx.style.top = `${rect.top + rect.height / 2 - 28}px`;
    } else {
      fx.style.left = "50%";
      fx.style.top = "40%";
      fx.style.marginLeft = "-28px";
    }
    document.body.appendChild(fx);
    requestAnimationFrame(() => fx.classList.add("is-play"));
    setTimeout(() => fx.remove(), 1100);
  }

  async function triggerPwaInstall(fromEl) {
    if (isStandaloneApp()) {
      toast("이미 홈 화면에 설치되어 있습니다");
      return;
    }
    fromEl?.classList?.add("is-installing");
    playInstallIconFx(fromEl);

    if (deferredInstallPrompt) {
      try {
        deferredInstallPrompt.prompt();
        const choice = await deferredInstallPrompt.userChoice;
        if (choice?.outcome === "accepted") {
          toast("홈 화면에 로드로그를 설치합니다");
        } else {
          toast("설치가 취소되었습니다. 언제든 다시 눌러 주세요");
        }
      } catch {
        toast("설치 창을 열 수 없습니다. 브라우저 메뉴에서 설치해 주세요");
      }
      deferredInstallPrompt = null;
      updateInstallButtonVisibility();
      fromEl?.classList?.remove("is-installing");
      return;
    }

    if (/iphone|ipad|ipod/i.test(navigator.userAgent)) {
      toast("공유 버튼 → '홈 화면에 추가'를 선택하세요");
      fromEl?.classList?.remove("is-installing");
      return;
    }

    // beforeinstallprompt 미수신(데스크톱 등): 안내 + 앱 사용 유도
    toast(
      "Chrome/Edge에서 주소창 설치 아이콘을 누르거나, ‘바로 써보기’로 시작해 보세요"
    );
    fromEl?.classList?.remove("is-installing");
  }

  function bindPwaInstall() {
    window.addEventListener("beforeinstallprompt", (e) => {
      e.preventDefault();
      deferredInstallPrompt = e;
      updateInstallButtonVisibility();
    });
    window.addEventListener("appinstalled", () => {
      deferredInstallPrompt = null;
      updateInstallButtonVisibility();
      toast("로드로그가 홈 화면에 설치되었습니다");
    });

    document.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-install-app], #btnInstallApp");
      if (!btn) return;
      e.preventDefault();
      triggerPwaInstall(btn);
    });

    $("#btnLandingLogin")?.addEventListener("click", () => openAuth());

    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch((err) => {
        console.warn("SW register failed", err);
      });
    }
    updateInstallButtonVisibility();
  }

  function isPlaceholderPayUrl(url) {
    const u = (url || "").trim();
    return (
      !u ||
      /example\.com|your-payment|localhost/i.test(u) ||
      !/^https?:\/\//i.test(u)
    );
  }

  function paymentUrlForPlan(plan) {
    const meta = state.meta || {};
    if (plan === "enterprise") {
      return (meta.enterprise_url || meta.pro_url || "").trim();
    }
    return (meta.pro_url || "").trim();
  }

  /** 결제 없이 plan 올리는 데모 API — 운영에서는 비활성 */
  function demoBillingUpgradeEnabled() {
    return Boolean(state.meta?.demo_billing_upgrade);
  }

  function applyPricingCtaLabels() {
    const demo = demoBillingUpgradeEnabled();
    const proBtn = $("#btnUpgradePro");
    const entBtn = $("#btnUpgradeEnt");
    const proHint = $("#proTrialHint");
    const entHint = $("#entTrialHint");
    const note = $("#pricingNote");
    if (demo) {
      if (proBtn) proBtn.textContent = "7일 무료 체험 시작하기 (데모)";
      if (entBtn) entBtn.textContent = "7일 무료 체험 시작하기 (데모)";
      if (proHint) proHint.textContent = "데모 모드 · 결제 없이 체험 플랜 적용";
      if (entHint) entHint.textContent = "데모 모드 · 결제 없이 체험 플랜 적용";
      if (note) {
        note.textContent =
          "데모 업그레이드가 켜져 있습니다. 운영 배포 전 ALLOW_DEMO_BILLING_UPGRADE=false 로 끄세요.";
      }
    } else {
      if (proBtn) proBtn.textContent = "Pro 결제하기";
      if (entBtn) entBtn.textContent = "Enterprise 결제하기";
      if (proHint) proHint.textContent = "결제 완료 후 Pro 요금제가 적용됩니다";
      if (entHint) entHint.textContent = "법인 결제 · 세금계산서 지원";
    }
  }

  function bindPricing() {
    async function startPaidOrDemo(plan) {
      const planLabel = plan === "enterprise" ? "Enterprise" : "Pro";

      // 운영 기본: 결제 링크로 이동 (무료 plan 변경 없음)
      if (!demoBillingUpgradeEnabled()) {
        if (!state.token) {
          openAuth();
          toast("결제·업그레이드는 로그인 후 진행할 수 있습니다");
          return;
        }
        const url = paymentUrlForPlan(plan);
        if (!isPlaceholderPayUrl(url)) {
          window.open(url, "_blank", "noopener,noreferrer");
          toast(
            `${planLabel} 결제 페이지를 열었습니다. 결제 완료 후 관리자 확인 또는 웹훅으로 요금제가 적용됩니다.`
          );
          return;
        }
        const contact =
          (state.meta && state.meta.contact_email) || "corelabs.studio@gmail.com";
        toast(
          `${planLabel} 결제 링크가 아직 연결되지 않았습니다. ${contact} 로 문의해 주세요.`
        );
        return;
      }

      // 로컬 데모 전용 (ALLOW_DEMO_BILLING_UPGRADE=true)
      if (!state.token) {
        openAuth();
        toast("데모 체험은 로그인 후 시작할 수 있습니다");
        return;
      }
      try {
        const data = await api("/api/billing/upgrade", {
          method: "POST",
          body: JSON.stringify({ plan }),
        });
        if (data.user) {
          state.user = data.user;
          updateAuthUI();
        }
        await refreshMe();
        toast(
          data.message ||
            `${planLabel} 데모 체험이 시작되었습니다. (결제 없음 · 데모 전용)`
        );
        if (plan === "enterprise") {
          showView("home");
        }
      } catch (err) {
        toast(err.message);
      }
    }
    $("#btnUpgradePro")?.addEventListener("click", () => startPaidOrDemo("pro"));
    $("#btnUpgradeEnt")?.addEventListener("click", () =>
      startPaidOrDemo("enterprise")
    );
  }

  // ── Init ──
  async function init() {
    // 1) i18n: state.lang 기준 사전 로드 후 DOM 텍스트 적용
    await initLocales(state.lang || localStorage.getItem(LANG_KEY) || "ko");

    bindNav();
    bindReportModeTabs();
    bindHistoryNav();
    bindAuth();
    bindGenerate();
    setReportMode(state.reportMode || "driving");
    bindCareModal();
    bindQuickStamp();
    bindSettings();
    bindStyle();
    bindPrint();
    bindAdmin();
    bindAdminViewAs();
    bindPricing();
    bindFeedbackForm();
    bindDemoPlayer();
    bindPwaInstall();

    applyI18n(); // data-i18n 노드에 t() 결과 반영

    try {
      state.meta = await api("/api/meta");
      applyPricingFromMeta(state.meta);
      if (state.meta?.free_limit) state.limit = state.meta.free_limit;
    } catch {
      /* offline meta ok */
    }

    // 자동 로그인: localStorage 토큰 → 서버 세션 검증
    let sessionOk = false;
    if (state.token) {
      sessionOk = await refreshMe();
      if (sessionOk) {
        prefillVehicleFromSettings();
        // 자동 로그인 성공 — 조용히 메인 진입 (토스트 생략)
      }
    } else {
      updateAuthUI();
    }
    markSessionReady();

    // 스마트 라우팅: 홈/빈 해시로 실행 시 근무 시간에 따라 stamp | report
    // 관리자 세션: 메인은 관리자 대시보드 (매출·사용 건수)
    // 딥링크(#pricing, #settings 등)는 그대로 존중
    let initial;
    if (shouldApplySmartRoute()) {
      if (sessionOk && isAdminMainMode()) {
        initial = "admin";
      } else {
        const isPwa =
          window.matchMedia("(display-mode: standalone)").matches ||
          window.navigator.standalone === true;
        const hasSessionHint =
          sessionOk || localStorage.getItem(REMEMBER_KEY) === "1" || isPwa;
        // 세션·PWA·바로가기: 비서형 진입 / 첫 방문 게스트: 랜딩
        initial = hasSessionHint ? resolveSmartRoute() : "home";
      }
    } else {
      initial = getViewFromLocation();
    }

    showView(initial, { replaceHistory: true });

    if (sessionOk && currentViewName === "home") {
      updateHomeMode();
    }

    // 스마트 진입 안내 (stamp/report 일 때만 1회성 · 관리자 제외)
    if (
      !isAdminMainMode() &&
      (initial === "stamp" || initial === "report")
    ) {
      const wh = getWorkHours();
      const label =
        initial === "stamp"
          ? `근무 중 (${wh.start}~${wh.end}) · 퀵 스탬프`
          : `근무 외 시간 · 일지 정리`;
      setTimeout(() => toast(label), 400);
    }
  }

  init();
})();

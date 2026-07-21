/**
 * CoreLabs UI click sounds — soft "I pressed it" feedback (Web Audio, no assets).
 * Mute: localStorage corelabs_ui_sound = "0"  |  Opt-out: data-sound="off"
 */
(function () {
  "use strict";

  var STORAGE_KEY = "corelabs_ui_sound";
  var VOLUME = 0.38;
  var ctx = null;
  var lastPlay = 0;
  var MIN_GAP_MS = 28;

  function enabled() {
    try {
      if (localStorage.getItem(STORAGE_KEY) === "0") return false;
    } catch (e) {}
    return true;
  }

  function getCtx() {
    if (ctx) return ctx;
    var AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return null;
    ctx = new AC();
    return ctx;
  }

  function unlock() {
    var c = getCtx();
    if (!c) return;
    if (c.state === "suspended") {
      c.resume().catch(function () {});
    }
  }

  function playTone(kind) {
    if (!enabled()) return;
    var now = performance.now();
    if (now - lastPlay < MIN_GAP_MS) return;
    lastPlay = now;

    var c = getCtx();
    if (!c) return;
    if (c.state === "suspended") {
      c.resume().catch(function () {});
    }

    var t0 = c.currentTime;
    var primary = kind === "primary";
    var soft = kind === "soft";
    var success = kind === "success";

    var master = c.createGain();
    var base = (primary ? 0.09 : soft ? 0.045 : success ? 0.07 : 0.06) * VOLUME;
    master.gain.setValueAtTime(base, t0);
    master.connect(c.destination);

    var osc = c.createOscillator();
    var og = c.createGain();
    osc.type = "sine";
    var f0 = success ? 980 : primary ? 1280 : soft ? 2100 : 1650;
    var f1 = success ? 620 : primary ? 720 : soft ? 1100 : 880;
    osc.frequency.setValueAtTime(f0, t0);
    osc.frequency.exponentialRampToValueAtTime(Math.max(80, f1), t0 + 0.045);
    og.gain.setValueAtTime(0.0001, t0);
    og.gain.exponentialRampToValueAtTime(1, t0 + 0.003);
    og.gain.exponentialRampToValueAtTime(0.0001, t0 + (success ? 0.09 : 0.055));
    osc.connect(og);
    og.connect(master);
    osc.start(t0);
    osc.stop(t0 + 0.1);

    var dur = 0.028;
    var n = Math.max(1, Math.floor(c.sampleRate * dur));
    var buf = c.createBuffer(1, n, c.sampleRate);
    var data = buf.getChannelData(0);
    for (var i = 0; i < n; i++) {
      data[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / n, 2.2);
    }
    var noise = c.createBufferSource();
    noise.buffer = buf;
    var ng = c.createGain();
    var bp = c.createBiquadFilter();
    bp.type = "bandpass";
    bp.frequency.value = primary ? 1800 : soft ? 3200 : 2400;
    bp.Q.value = 0.9;
    ng.gain.setValueAtTime(0.55, t0);
    ng.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
    noise.connect(bp);
    bp.connect(ng);
    ng.connect(master);
    noise.start(t0);
    noise.stop(t0 + dur + 0.01);

    if (success) {
      var osc2 = c.createOscillator();
      var g2 = c.createGain();
      osc2.type = "triangle";
      osc2.frequency.setValueAtTime(1310, t0 + 0.02);
      g2.gain.setValueAtTime(0.0001, t0 + 0.02);
      g2.gain.exponentialRampToValueAtTime(0.5, t0 + 0.03);
      g2.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.12);
      osc2.connect(g2);
      g2.connect(master);
      osc2.start(t0 + 0.02);
      osc2.stop(t0 + 0.14);
    }
  }

  function isInteractive(el) {
    if (!el || el.nodeType !== 1) return null;
    if (el.closest && el.closest("[data-sound='off']")) return null;
    var hit =
      el.closest &&
      el.closest(
        "a[href], button, [role='button'], summary, " +
          "input[type='button'], input[type='submit'], input[type='reset'], " +
          "input[type='checkbox'], input[type='radio'], " +
          "label[for], select, .btn, .nav-link, .tab, .chip, .card, " +
          "[data-sound], [onclick]"
      );
    if (!hit) return null;
    if (hit.disabled || hit.getAttribute("aria-disabled") === "true") return null;
    if (
      hit.matches &&
      hit.matches(
        "input:not([type]), input[type='text'], input[type='email'], input[type='password'], input[type='search'], input[type='number'], input[type='tel'], input[type='url'], textarea"
      )
    ) {
      return null;
    }
    return hit;
  }

  function kindFor(el) {
    if (!el) return "tap";
    var custom = el.getAttribute && el.getAttribute("data-sound");
    if (custom && custom !== "on" && custom !== "off") return custom;
    if (el.matches && el.matches(".btn-primary, [type='submit'], #btnGenerate, #btnGenerateSticky, .btn-lg")) {
      return "primary";
    }
    if (el.matches && el.matches(".btn-ghost, .btn-secondary, nav a, .nav a, .lang-btn")) {
      return "soft";
    }
    return "tap";
  }

  document.addEventListener(
    "pointerdown",
    function (e) {
      if (e.button != null && e.button !== 0) return;
      unlock();
      var hit = isInteractive(e.target);
      if (!hit) return;
      playTone(kindFor(hit));
    },
    true
  );

  document.addEventListener(
    "keydown",
    function (e) {
      if (e.key !== "Enter" && e.key !== " ") return;
      if (e.repeat) return;
      unlock();
      var hit = isInteractive(e.target);
      if (!hit) return;
      playTone(kindFor(hit));
    },
    true
  );

  window.CoreLabsSound = {
    play: playTone,
    unlock: unlock,
    setEnabled: function (on) {
      try {
        localStorage.setItem(STORAGE_KEY, on ? "1" : "0");
      } catch (e) {}
    },
    isEnabled: enabled,
  };
})();

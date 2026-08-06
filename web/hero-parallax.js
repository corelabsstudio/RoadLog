/**
 * RoadLog hero — mouse-follow background parallax (guest landing only).
 * Desktop-only (hover:hover + pointer:fine), skipped under prefers-reduced-motion.
 */
(function () {
  "use strict";

  var reduce =
    window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var canHover =
    window.matchMedia && window.matchMedia("(hover: hover) and (pointer: fine)").matches;
  if (reduce || !canHover) return;

  function init() {
    var heroEl = document.querySelector(".landing-hero--photo");
    var heroPhoto = heroEl && heroEl.querySelector(".landing-hero-photo img");
    if (!heroEl || !heroPhoto) return;

    heroPhoto.classList.add("rl-hero-mouse");
    var mx = 0,
      my = 0,
      raf = null;
    var STRENGTH = 16;

    function apply() {
      raf = null;
      heroPhoto.style.setProperty("--hero-mx", mx.toFixed(1) + "px");
      heroPhoto.style.setProperty("--hero-my", my.toFixed(1) + "px");
    }
    function onMove(e) {
      var rect = heroEl.getBoundingClientRect();
      var nx = (e.clientX - rect.left) / rect.width - 0.5;
      var ny = (e.clientY - rect.top) / rect.height - 0.5;
      mx = -nx * STRENGTH * 2;
      my = -ny * STRENGTH * 2;
      if (!raf) raf = requestAnimationFrame(apply);
    }
    function onLeave() {
      mx = 0;
      my = 0;
      if (!raf) raf = requestAnimationFrame(apply);
    }
    heroEl.addEventListener("mousemove", onMove);
    heroEl.addEventListener("mouseleave", onLeave);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

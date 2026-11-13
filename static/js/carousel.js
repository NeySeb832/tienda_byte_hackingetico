// Accessible hero carousel (progressive enhancement over CSS scroll-snap).
// Without JS the slides remain a swipeable list. With JS: arrows, dots, keyboard,
// autoplay that pauses on hover/focus, a pause button (WCAG 2.2.2) and no autoplay
// when the user prefers reduced motion. CSP-safe: no inline styles or eval.
(function () {
  "use strict";
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function setup(root) {
    var track = root.querySelector("[data-carousel-track]");
    var slides = Array.prototype.slice.call(track.children);
    var dots = Array.prototype.slice.call(root.querySelectorAll("[data-carousel-dot]"));
    var toggle = root.querySelector("[data-carousel-toggle]");
    var pauseIcon = root.querySelector("[data-carousel-pause-icon]");
    var playIcon = root.querySelector("[data-carousel-play-icon]");
    var interval = parseInt(root.getAttribute("data-interval"), 10) || 6000;
    var current = 0;
    var timer = null;
    var userPaused = reduceMotion;
    var interacting = false;
    var scrollTimer = null;

    function render() {
      slides.forEach(function (slide, index) {
        slide.inert = index !== current;
      });
      dots.forEach(function (dot, index) {
        dot.setAttribute("aria-current", index === current ? "true" : "false");
      });
      toggle.setAttribute("aria-label", userPaused ? "Reproducir el carrusel" : "Pausar el carrusel");
      pauseIcon.hidden = userPaused;
      playIcon.hidden = !userPaused;
    }

    function go(index) {
      current = (index + slides.length) % slides.length;
      track.scrollTo({ left: slides[current].offsetLeft, behavior: reduceMotion ? "auto" : "smooth" });
      render();
    }

    function schedule() {
      window.clearInterval(timer);
      timer = null;
      if (!userPaused && !interacting && document.visibilityState === "visible") {
        timer = window.setInterval(function () { go(current + 1); }, interval);
      }
    }

    root.querySelector("[data-carousel-prev]").addEventListener("click", function () { go(current - 1); schedule(); });
    root.querySelector("[data-carousel-next]").addEventListener("click", function () { go(current + 1); schedule(); });
    dots.forEach(function (dot, index) {
      dot.addEventListener("click", function () { go(index); schedule(); });
    });
    toggle.addEventListener("click", function () {
      userPaused = !userPaused;
      render();
      schedule();
    });
    track.addEventListener("keydown", function (event) {
      if (event.key === "ArrowRight") { event.preventDefault(); go(current + 1); schedule(); }
      if (event.key === "ArrowLeft") { event.preventDefault(); go(current - 1); schedule(); }
    });
    // Keep the active slide in sync when the user swipes the track.
    track.addEventListener("scroll", function () {
      window.clearTimeout(scrollTimer);
      scrollTimer = window.setTimeout(function () {
        var index = Math.round(track.scrollLeft / track.clientWidth);
        if (index !== current && index >= 0 && index < slides.length) {
          current = index;
          render();
        }
      }, 120);
    });
    ["mouseenter", "focusin"].forEach(function (name) {
      root.addEventListener(name, function () { interacting = true; schedule(); });
    });
    ["mouseleave", "focusout"].forEach(function (name) {
      root.addEventListener(name, function () { interacting = false; schedule(); });
    });
    document.addEventListener("visibilitychange", schedule);

    root.classList.add("is-enhanced");
    render();
    schedule();
  }

  function init() {
    Array.prototype.forEach.call(document.querySelectorAll("[data-carousel]"), setup);
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

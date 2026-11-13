// Applies the saved (or OS) colour scheme before first paint. Loaded synchronously in <head>.
(function () {
  "use strict";
  var stored = null;
  try {
    stored = window.localStorage.getItem("byte-theme");
  } catch (e) {
    stored = null; // storage blocked (private mode): fall back to the OS preference
  }
  var prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  var dark = stored ? stored === "dark" : prefersDark;
  document.documentElement.classList.toggle("dark", dark);
})();

// Alpine.js components (CSP build: logic lives here, templates only reference names). ADR-0006.
document.addEventListener("alpine:init", function () {
  "use strict";
  var Alpine = window.Alpine;

  Alpine.data("themeToggle", function () {
    return {
      dark: document.documentElement.classList.contains("dark"),
      get light() { return !this.dark; },
      get pressed() { return this.dark ? "true" : "false"; },
      get label() { return this.dark ? "Activar modo claro" : "Activar modo oscuro"; },
      toggle: function () {
        this.dark = !this.dark;
        document.documentElement.classList.toggle("dark", this.dark);
        try {
          window.localStorage.setItem("byte-theme", this.dark ? "dark" : "light");
        } catch (e) {
          // storage blocked: the choice simply is not remembered
        }
      },
    };
  });

  Alpine.data("mobileMenu", function () {
    return {
      open: false,
      get expanded() { return this.open ? "true" : "false"; },
      toggle: function () { this.open = !this.open; },
    };
  });
});

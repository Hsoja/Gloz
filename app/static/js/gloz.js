// Small progressive enhancements. The site works fully without JavaScript.
// No innerHTML, eval or third-party code: only attribute and property changes.
(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    // Mobile navigation
    var toggle = document.querySelector("[data-nav-toggle]");
    var nav = document.getElementById("site-nav");
    if (toggle && nav) {
      toggle.addEventListener("click", function () {
        var open = nav.classList.toggle("is-open");
        toggle.setAttribute("aria-expanded", open ? "true" : "false");
      });
      document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && nav.classList.contains("is-open")) {
          nav.classList.remove("is-open");
          toggle.setAttribute("aria-expanded", "false");
          toggle.focus();
        }
      });
    }

    // Show / hide password
    document.querySelectorAll("[data-reveal]").forEach(function (button) {
      var input = document.getElementById(button.getAttribute("data-reveal"));
      var label = button.querySelector(".visually-hidden");
      if (!input) return;
      button.addEventListener("click", function () {
        var show = input.type === "password";
        input.type = show ? "text" : "password";
        button.setAttribute("aria-pressed", show ? "true" : "false");
        if (label) label.textContent = show ? "Hide password" : "Show password";
      });
    });

    // Delete account: keep the button disabled until DELETE is typed
    var confirmInput = document.querySelector("[data-confirm-input]");
    var confirmButton = document.querySelector("[data-confirm-button]");
    if (confirmInput && confirmButton) {
      var sync = function () { confirmButton.disabled = confirmInput.value !== "DELETE"; };
      confirmInput.addEventListener("input", sync);
      sync();
    }
  });
})();

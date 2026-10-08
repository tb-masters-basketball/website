/* Masters Basketball: theme toggle. Everything else on the site works
   without JavaScript. The head snippet has already applied a saved choice. */
(function () {
  var root = document.documentElement;
  var button = document.querySelector("[data-theme-toggle]");
  var metas = document.querySelectorAll('meta[name="theme-color"]');
  var system = window.matchMedia("(prefers-color-scheme: dark)");
  // The light and dark theme colours, read from the tags in the page head.
  var colours = metas.length > 1 ? { light: metas[0].content, dark: metas[1].content } : null;

  function current() {
    return root.dataset.theme || (system.matches ? "dark" : "light");
  }

  // Keep the button's label and the browser's toolbar colour in step.
  function sync() {
    var theme = current();
    if (button) {
      button.setAttribute("aria-label", theme === "dark" ? "Switch to light theme" : "Switch to dark theme");
    }
    if (colours) {
      for (var i = 0; i < metas.length; i++) metas[i].content = colours[theme];
    }
  }

  if (button) {
    button.addEventListener("click", function () {
      var next = current() === "dark" ? "light" : "dark";
      root.dataset.theme = next;
      try { localStorage.setItem("mb-theme", next); } catch (e) {}
      sync();
    });
  }

  if (system.addEventListener) system.addEventListener("change", sync);
  sync();
})();

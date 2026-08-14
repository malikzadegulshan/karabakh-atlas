// Applies a stored light/dark override (if any) before first paint, so a
// preference that disagrees with the OS setting doesn't flash the wrong
// theme for a frame — see the #theme-toggle button and
// scheme()/getStoredTheme() in app.js, which read/write this same
// "kba_theme" key and attribute.
//
// A separate file (not inline in index.html) so it can run under a
// script-src that doesn't need 'unsafe-inline' — loaded as a plain,
// non-deferred <script src>, which is just as render-blocking/synchronous
// as an inline block would have been, so the pre-paint timing this exists
// for is unaffected.
(function () {
  try {
    var theme = localStorage.getItem("kba_theme");
    if (theme === "light" || theme === "dark") {
      document.documentElement.dataset.theme = theme;
    }
  } catch (err) {
    /* localStorage unavailable (e.g. private browsing); system
       preference alone still applies via CSS, nothing else to do */
  }
})();

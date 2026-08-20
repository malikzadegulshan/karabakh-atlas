// Registers sw.js so the app shell can be installed and loaded
// offline (see sw.js for exactly what is/isn't cached). Feature-detected
// and deferred to the window "load" event — a service worker install
// competing with the initial page's own network requests would only
// slow down the first real visit for a benefit that only matters on
// a second one.
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("sw.js").catch(() => {
      // Offline support is a progressive enhancement, not a
      // requirement — a failed registration (unsupported browser,
      // blocked by a privacy setting, served over plain HTTP in local
      // dev where some browsers restrict service workers to
      // localhost only, ...) shouldn't surface as an error to the
      // visitor or block anything else on the page.
    });
  });
}

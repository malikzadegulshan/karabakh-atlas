// Service worker for offline/installable support. Deliberately narrow
// in scope: it only ever caches the static app shell (HTML/CSS/JS/
// fonts/icons), never API responses or map tiles — so cached content
// can never go stale in a way that shows outdated regions/cities/
// weather to someone who's actually online. Bump CACHE_NAME whenever
// the shell file list below changes, so activate() below evicts the
// old cache instead of an install silently reusing it.
const CACHE_NAME = "kba-shell-v1";
const SHELL_ASSETS = [
  "./",
  "index.html",
  "style.css",
  "manifest.json",
  "config.js",
  "i18n.js",
  "theme-init.js",
  "app.js",
  "auth.js",
  "admin.js",
  "forum.js",
  "favorites.js",
  "stats.js",
  "vendor/leaflet/leaflet.js",
  "vendor/leaflet/leaflet.css",
  "vendor/leaflet/images/layers.png",
  "vendor/leaflet/images/layers-2x.png",
  "vendor/leaflet/images/marker-icon.png",
  "vendor/leaflet/images/marker-icon-2x.png",
  "vendor/leaflet/images/marker-shadow.png",
  "vendor/icons/icons.js",
  "vendor/fonts/roboto-flex-latin.woff2",
  "vendor/fonts/roboto-flex-latin-ext.woff2",
  "vendor/fonts/roboto-flex-cyrillic.woff2",
  "favicon.svg",
  "favicon-16.png",
  "favicon-32.png",
  "apple-touch-icon.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
    ))
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  // Only ever intercept same-origin GETs — every API call, map tile,
  // and weather request is cross-origin (or, for the API in local dev,
  // a different port) and passes straight through untouched. Nothing
  // this worker doesn't explicitly recognize is ever cached.
  if (event.request.method !== "GET" || url.origin !== self.location.origin) {
    return;
  }
  event.respondWith(
    caches.match(event.request).then((cached) => cached || fetch(event.request))
  );
});

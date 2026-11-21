const CACHE_NAME = "mediometeo-genova-v3.0";
const LEGACY_TAG = "mediometeo-genova-v1";
const STATIC_ASSETS = [
  "/",
  "/static/styles.css?v=3.0",
  "/static/app.js?v=3.0",
  "/static/js/state.js?v=3.0",
  "/static/js/api.js?v=3.0",
  "/static/js/charts.js?v=3.0",
  "/static/js/security.js?v=3.0",
  "/static/js/icons.js?v=3.0",
  "/static/vendor/leaflet.css?v=3.0",
  "/static/vendor/leaflet.js?v=3.0",
  "/static/vendor/chart.umd.min.js?v=3.0",
  "/manifest.json"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Network-first strategy so live code updates are always served immediately (never caches 5xx/errors)
self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  event.respondWith(
    fetch(event.request)
      .then((res) => {
        if (res && res.ok) {
          const clone = res.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone)).catch(() => {});
        }
        return res;
      })
      .catch(() => caches.match(event.request))
  );
});

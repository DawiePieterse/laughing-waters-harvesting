// App-shell cache so the admin PWA installs cleanly and its own UI still
// loads if the connection briefly drops. Data (dashboard, reports, etc.)
// always goes over the network when available.
const CACHE = "lw-admin-v6";
const SHELL = [
  "./",
  "./index.html",
  "./app.js",
  "./manifest.json",
  "../shared/styles.css",
  "../shared/api.js",
  "../shared/qrcode.min.js",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (url.pathname.startsWith("/api/")) return; // never cache API calls
  event.respondWith(
    caches.match(event.request).then((cached) => cached || fetch(event.request).catch(() => cached))
  );
});

// App-shell cache so the pack house PWA installs cleanly and its own UI
// still loads if the connection briefly drops. Data (queue, receiving)
// always goes over the network when available.
const CACHE_PREFIX = "lw-packhouse-";
const CACHE = "lw-packhouse-v9";
const SHELL = [
  "./",
  "./index.html",
  "./receiving.js",
  "./manifest.json",
  "../shared/styles.css",
  "../shared/api.js",
  "../shared/ptr.js",
  "../shared/tailwind.js",
  "../shared/vendor/fontawesome/css/all.min.css",
  "../shared/vendor/fontawesome/webfonts/fa-solid-900.woff2",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)));
  self.skipWaiting();
});

// Drop only THIS screen's older caches. CacheStorage is shared per-origin,
// so deleting every non-matching key would wipe the other screens' offline
// shells the moment someone opens two of the apps on the same device.
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys.filter((k) => k.startsWith(CACHE_PREFIX) && k !== CACHE).map((k) => caches.delete(k))
    ))
  );
  self.clients.claim();
});

// Stale-while-revalidate: answer instantly from cache (so a device with no
// signal still gets the whole UI), but refresh the cached copy in the
// background whenever the server IS reachable. Without the revalidate half,
// a cache-first worker pins a device to old JS until the CACHE name changes.
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (url.pathname.startsWith("/api/")) return; // never cache API calls
  if (event.request.method !== "GET" || url.origin !== self.location.origin) return;

  // Page loads are cached by path only. The Owner View is opened as
  // /owner/?key=..., and a cache lookup matches the query string too - so
  // without this the shell would never be found and the page would fail
  // offline. It also stops one cache entry piling up per distinct link.
  const isPageLoad = event.request.mode === "navigate";
  const cacheKey = isPageLoad ? url.origin + url.pathname : event.request;

  event.respondWith(
    caches.match(cacheKey).then((cached) => {
      const network = fetch(event.request)
        .then((res) => {
          if (res.ok) {
            const copy = res.clone();
            caches.open(CACHE).then((cache) => cache.put(cacheKey, copy));
          }
          return res;
        })
        .catch(() => cached); // offline: fall back to whatever we have
      return cached || network;
    })
  );
});

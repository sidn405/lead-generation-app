// service-worker.js
const CACHE_VERSION = "lge-v1.0.0"; // bump this to invalidate old caches
const CACHE_NAME = `lge-cache-${CACHE_VERSION}`;

const ASSETS = [
  "/", // the app shell
  // Icons & manifest
  "/assets/favicon.ico",
  "/assets/favicon.png",
  "/assets/favicon-16x16.png",
  "/assets/favicon-32x32.png",
  "/assets/favicon-180x180.png",
  "/assets/favicon-192x192.png",
  "/assets/favicon-256x256.png",
  "/assets/favicon-512x512.png",
  "/assets/apple-touch-icon.png",
  "/assets/manifest-fullscreen.json",
];

// Install: pre-cache core assets
self.addEventListener("install", (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS))
  );
});

// Activate: clean up old caches
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key.startsWith("lge-cache-") && key !== CACHE_NAME)
          .map((key) => caches.delete(key))
      )
    )
  );
  self.clients.claim();
});

// Strategy:
// - HTML/doc requests: network-first (fresh app)
// - Static assets (icons, images, manifest): cache-first (fast load)
self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // Only handle same-origin
  if (url.origin !== self.location.origin) return;

  // Heuristic: treat navigations and HTML as network-first
  const isHTML =
    req.mode === "navigate" ||
    (req.headers.get("accept") || "").includes("text/html");

  if (isHTML) {
    event.respondWith(
      fetch(req)
        .then((res) => {
          // Stash a copy in cache for offline fallback
          const copy = res.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(req, copy));
          return res;
        })
        .catch(async () => {
          const cached = await caches.match(req);
          return (
            cached ||
            // fallback to cached app shell
            caches.match("/")
          );
        })
    );
    return;
  }

  // Cache-first for everything else (icons, manifest, images)
  event.respondWith(
    caches.match(req).then((cached) => {
      if (cached) return cached;
      return fetch(req).then((res) => {
        const copy = res.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(req, copy));
        return res;
      });
    })
  );
});

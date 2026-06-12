// VPS Attendance Service Worker
const CACHE_NAME = "vps-attendance-cache-v1";
const ASSETS_TO_CACHE = [
  "/checkin",
  "/static/css/styles.css",
  "/static/js/main.js",
  "/static/images/icon-192.png",
  "/static/images/icon-512.png",
  "https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap",
  "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"
];

// Install Event
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log("PWA Cache: Pre-caching static assets.");
      return cache.addAll(ASSETS_TO_CACHE);
    })
  );
  self.skipWaiting();
});

// Activate Event
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            console.log("PWA Cache: Removing obsolete cache keys.");
            return caches.delete(key);
          }
        })
      );
    })
  );
  self.clients.claim();
});

// Fetch Event
self.addEventListener("fetch", (event) => {
  // Only handle GET requests
  if (event.request.method !== "GET") return;

  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      if (cachedResponse) {
        return cachedResponse; // Return cached asset if offline
      }
      return fetch(event.request).catch(() => {
        // Fallback when network is down
        if (event.request.mode === "navigate") {
          return caches.match("/checkin");
        }
      });
    })
  );
});

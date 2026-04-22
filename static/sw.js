// Minimal service worker for Mochi Academia Planner.
//
// Strategy:
//   - Static assets (CSS, JS, icons) → cache-first. They change rarely; bump
//     CACHE_VERSION to force refresh.
//   - HTML pages and API requests → network-first. We always want fresh data
//     from Supabase/Flask; the cache is only a fallback if the user is offline.
//
// This is intentionally simple. A fancier offline story (queued mutations,
// IndexedDB, etc.) would fight with Supabase RLS and isn't worth the complexity
// for v1.

const CACHE_VERSION = 'mochi-v1';
const APP_SHELL = [
  '/static/css/app.css',
  '/static/js/app.js',
  '/static/js/timer.js',
  '/static/js/charts.js',
  '/static/manifest.json',
  '/static/images/icon-192.png',
  '/static/images/icon-512.png',
  '/static/images/apple-touch-icon.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION).then((cache) => cache.addAll(APP_SHELL))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  // Clear any older caches so we don't ship stale JS after a deploy.
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(names.filter((n) => n !== CACHE_VERSION).map((n) => caches.delete(n)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return; // Don't cache mutations.

  const url = new URL(request.url);
  const isStatic = url.pathname.startsWith('/static/');

  if (isStatic) {
    // Cache-first for static assets.
    event.respondWith(
      caches.match(request).then(
        (cached) => cached || fetch(request).then((res) => {
          const copy = res.clone();
          caches.open(CACHE_VERSION).then((c) => c.put(request, copy));
          return res;
        })
      )
    );
  } else {
    // Network-first for everything else, falling back to cached HTML if offline.
    event.respondWith(
      fetch(request)
        .then((res) => {
          // Cache successful HTML GETs so the last-known page is available offline.
          if (res.ok && res.headers.get('content-type')?.includes('text/html')) {
            const copy = res.clone();
            caches.open(CACHE_VERSION).then((c) => c.put(request, copy));
          }
          return res;
        })
        .catch(() => caches.match(request))
    );
  }
});

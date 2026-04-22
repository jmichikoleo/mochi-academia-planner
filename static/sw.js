// Service worker — intentionally minimal.
//
// We ONLY cache static assets (CSS/JS/icons). HTML pages, auth flows, and API
// calls pass through untouched. This avoids the classic PWA failure mode where
// the SW intercepts a login redirect and iOS Safari reports "network lost."

const CACHE_VERSION = 'mochi-v2';
const APP_SHELL = [
  '/static/css/app.css',
  '/static/js/app.js',
  '/static/js/timer.js',
  '/static/js/charts.js',
  '/static/manifest.json',
  '/static/images/icon-192.png',
  '/static/images/icon-512.png',
  '/static/images/apple-touch-icon.png',
  '/static/images/favicon.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION).then((cache) =>
      cache.addAll(APP_SHELL.map((url) => new Request(url, { cache: 'reload' })))
    ).catch(() => null)
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(names.filter((n) => n !== CACHE_VERSION).map((n) => caches.delete(n)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (!url.pathname.startsWith('/static/')) return;

  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) return cached;
      return fetch(request).then((res) => {
        if (res.ok && res.type === 'basic') {
          const copy = res.clone();
          caches.open(CACHE_VERSION).then((c) => c.put(request, copy));
        }
        return res;
      });
    })
  );
});

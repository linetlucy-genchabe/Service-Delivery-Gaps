/* ============================================================
   Service Worker — Service Delivery Gaps Dashboard PWA
   Caches static assets for fast load; network-first for data
   ============================================================ */

const CACHE_NAME = 'sd-gaps-v1';

const STATIC_ASSETS = [
  '/static/dashboard/css/styles.css',
  '/static/dashboard/js/dashboard.js',
  '/static/dashboard/lg_logo.png',
  '/static/dashboard/manifest.json',
  '/static/dashboard/icons/icon-192.png',
  '/static/dashboard/icons/icon-512.png',
  'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap',
  'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js',
];

// Install — cache static assets
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return cache.addAll(STATIC_ASSETS).catch(err => {
        console.warn('Some assets failed to cache:', err);
      });
    })
  );
  self.skipWaiting();
});

// Activate — clean old caches
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Fetch strategy:
// - Static assets (CSS/JS/images): cache-first
// - API calls and HTML pages: network-first with cache fallback
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // Skip non-GET and chrome-extension requests
  if (event.request.method !== 'GET') return;
  if (url.protocol === 'chrome-extension:') return;

  // Static assets — cache first
  if (url.pathname.startsWith('/static/') || url.hostname.includes('googleapis') || url.hostname.includes('cloudflare')) {
    event.respondWith(
      caches.match(event.request).then(cached => {
        return cached || fetch(event.request).then(response => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
          }
          return response;
        });
      })
    );
    return;
  }

  // API endpoints — network only (always fresh data)
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/download/')) {
    event.respondWith(fetch(event.request));
    return;
  }

  // HTML pages — network first, cache fallback
  event.respondWith(
    fetch(event.request)
      .then(response => {
        if (response.ok) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
        }
        return response;
      })
      .catch(() => caches.match(event.request))
  );
});
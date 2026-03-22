// AgatClean Service Worker
const CACHE_NAME = 'agatclean-v1';
const OFFLINE_URL = '/offline';

const PRECACHE_URLS = [
  '/',
  '/schedule',
  '/quick',
  '/manage',
  '/settings',
  '/static/manifest.json',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png'
];

// Instalacja - przedpamietaj strony
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return cache.addAll(PRECACHE_URLS).catch(() => {
        // Kontynuuj nawet gdy nie wszystkie zasoby sa dostepne
        return Promise.resolve();
      });
    })
  );
  self.skipWaiting();
});

// Aktywacja - usun stare cache
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => {
      return Promise.all(
        keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
      );
    })
  );
  self.clients.claim();
});

// Fetch - Network first, fallback to cache
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;

  const url = new URL(event.request.url);

  // Nie przechwytuj requestow do zewnetrznych CDN na zywo
  if (!url.origin.includes(self.location.origin)) return;

  event.respondWith(
    fetch(event.request)
      .then(response => {
        // Zapisz swiezy odpowiedz w cache
        if (response.ok) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => {
            cache.put(event.request, clone);
          });
        }
        return response;
      })
      .catch(() => {
        // Offline - uzyj cache
        return caches.match(event.request).then(cached => {
          if (cached) return cached;
          // Strona 503 gdy brak internetu i brak cache
          return new Response(
            '<html><body style="font-family:sans-serif;text-align:center;padding:2rem">' +
            '<h2>&#128247; Brak połączenia</h2>' +
            '<p>AgatClean nie może się połączyć z serwerem.</p>' +
            '<p>Upewnij się, że serwer działa w sieci lokalnej.</p>' +
            '<a href="/" style="color:#1a73e8">Spróbuj ponownie</a>' +
            '</body></html>',
            { status: 503, headers: { 'Content-Type': 'text/html; charset=utf-8' } }
          );
        });
      })
  );
});

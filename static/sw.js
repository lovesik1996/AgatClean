// AgatClean Service Worker – v2 (Capacitor + Firestore offline)
const CACHE_VERSION = 'agatclean-v2';
const CACHE_NAME = CACHE_VERSION;

// Zasoby precachowane przy instalacji
const PRECACHE_URLS = [
  '/',
  '/schedule',
  '/quick',
  '/manage',
  '/settings',
  '/periodic',
  '/static/manifest.json',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png'
];

// Instalacja – zapisz strony w cache
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return cache.addAll(PRECACHE_URLS).catch(() => Promise.resolve());
    }).then(() => self.skipWaiting())
  );
});

// Aktywacja – usuń stare cache
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

// Fetch – Network first, fallback to cache
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;

  const url = new URL(event.request.url);

  // Pomiń requesty do zewnętrznych CDN (Firebase, Bootstrap) – obsługuje je Firestore JS SDK
  const isExternal = url.origin !== self.location.origin;
  const isFirebase = url.hostname.includes('firebase') || url.hostname.includes('gstatic') || url.hostname.includes('googleapis');
  if (isExternal && !isFirebase) return;
  if (isFirebase) return; // Firebase SDK ma własny cache offline

  // Nie cachuj endpointów API ani SSE – zawsze żądaj sieci
  if (url.pathname.startsWith('/api/')) return;

  event.respondWith(
    fetch(event.request)
      .then(response => {
        if (response.ok) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
        }
        return response;
      })
      .catch(() =>
        caches.match(event.request).then(cached => {
          if (cached) return cached;
          // Strona offline gdy brak cache i internet niedostępny
          return new Response(
            `<!doctype html>
<html lang="pl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>AgatClean – Offline</title>
  <style>
    body { font-family: -apple-system, sans-serif; background: #f7faf9;
           display:flex; flex-direction:column; align-items:center;
           justify-content:center; min-height:100vh; text-align:center; padding:2rem; }
    svg  { margin-bottom: 1.5rem; }
    h2   { font-size: 1.4rem; color: #1a73e8; margin-bottom: .5rem; }
    p    { color: #666; margin-bottom: 1.5rem; }
    a    { background:#1a73e8; color:#fff; padding:.6rem 1.4rem;
           border-radius:8px; text-decoration:none; font-weight:600; }
  </style>
</head>
<body>
  <svg width="72" height="72" viewBox="0 0 64 64" fill="none">
    <rect width="64" height="64" rx="12" fill="#1a73e8"/>
    <rect x="14" y="18" width="36" height="7" rx="3" fill="white"/>
    <rect x="14" y="31" width="28" height="7" rx="3" fill="white"/>
    <rect x="14" y="44" width="20" height="7" rx="3" fill="white"/>
  </svg>
  <h2>AgatClean – Offline</h2>
  <p>Brak połączenia z serwerem.<br>
     Dane zapisane lokalnie są nadal dostępne przez Firestore.</p>
  <a href="/">Spróbuj ponownie</a>
</body>
</html>`,
            { status: 503, headers: { 'Content-Type': 'text/html; charset=utf-8' } }
          );
        })
      )
  );
});

// Wiadomości z głównego wątku (np. wymuszenie aktualizacji cache)
self.addEventListener('message', event => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});

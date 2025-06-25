const CACHE_NAME = 'peachjam-offline-docs-v1';
const OFFLINE_PAGE = '/offline/';

self.addEventListener('install', (event) => {
  console.log('Service Worker installing');
  event.waitUntil(
    // TODO: don't need to always do this?
    // caches.open(CACHE_NAME).then(cache => cache.add(OFFLINE_PAGE))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  console.log('Service Worker activated');
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;

  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) {
        console.log('Service Worker FETCH ', event.request.url, cached);
      }
      return cached || fetch(event.request).catch(() => {
        if (event.request.mode === 'navigate') {
          return caches.match(OFFLINE_PAGE);
        }
      });
    })
  );
});

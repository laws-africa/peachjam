const CACHE_NAME = 'peachjam-offline-v1';
const OFFLINE_PAGE = '/offline/offline';

self.addEventListener('install', (event) => {
  console.log('Service Worker installing');
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
    // try a normal fetch
    fetch(event.request)
      .then(async (response) => {
        // update the existing cache value (if any)
        if (response.ok && response.type === 'basic') {
          // clone because response is a stream
          const responseForCache = response.clone();

          caches.open(CACHE_NAME).then((cache) => {
            cache.match(event.request).then((match) => {
              if (match) {
                // it exists in the cache, update it
                cache.put(event.request, responseForCache);
              }
            });
          });
        }

        return response;
      })
      .catch(async () => {
        // it failed, try the cache
        const cache = await caches.open(CACHE_NAME);
        const response = await cache.match(event.request);

        if (response) {
          // we found a cached response, return it
          return response;
        }

        if (event.request.mode === 'navigate') {
          // resort to offline page for navigation requests
          return cache.match(OFFLINE_PAGE);
        }
      })
  );
});

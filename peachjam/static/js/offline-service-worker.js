const CACHE_NAME = 'peachjam-offline-v1';
const OFFLINE_PAGE = '/offline/offline';

let isOffline = false;

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
        if (event.request.mode === 'navigate' && response.ok && response.type === 'basic' && isOffline) {
          // we're back online
          notifyOfflineStatus(false);
        }
        return response;
      })
      .catch(async () => {
        // it failed, try the cache
        const cache = await caches.open(CACHE_NAME);
        const response = await cache.match(event.request);

        if (event.request.mode === 'navigate' && !isOffline) {
          notifyOfflineStatus(true);
        }

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

// respond when the browser wants to determine offline status
self.addEventListener('message', (event) => {
  if (event.data?.type === 'requestOfflineStatus') {
    notifyOfflineStatus(isOffline);
  }
});

function notifyOfflineStatus (offline) {
  isOffline = offline;
  self.clients.matchAll({ type: 'window' }).then(clients => {
    for (const client of clients) {
      client.postMessage({ type: 'notifyOfflineStatus', value: isOffline });
    }
  });
}

interface OfflineDocument {
  url: string;
  title: string;
}

export class OfflineManager {
  // This MUST match CACHE_NAME in offline-service-worker.js
  public static CACHE_NAME = 'peachjam-offline-v1';
  public static INVENTORY_KEY = 'offlineDocs';
  public static OFFLINE_PAGE = '/offline/offline';

  cache: Cache | null = null;

  async getCache () {
    if (!this.cache) {
      this.cache = await caches.open(OfflineManager.CACHE_NAME);
    }
    return this.cache;
  }

  async makeAvailableOffline (url: string, title: string) {
    const cache = await this.getCache();
    const assets = [url, OfflineManager.OFFLINE_PAGE, ...this.getStaticAssets()];
    await cache.addAll(assets);

    // Store metadata for listing later
    const saved: OfflineDocument[] = JSON.parse(localStorage.getItem(OfflineManager.INVENTORY_KEY) || '[]');
    if (!saved.find((doc: OfflineDocument) => doc.url === url)) {
      saved.push({ url, title });
      localStorage.setItem(OfflineManager.INVENTORY_KEY, JSON.stringify(saved));
    }
  }

  getStaticAssets (): Array<string> {
    const urls = new Set<string>();

    document.querySelectorAll('link[rel="stylesheet"], script[src], img[src]').forEach(el => {
      // @ts-ignore
      const src = el.href || el.src;
      if (src && src.startsWith(location.origin)) {
        urls.add(new URL(src).pathname);
      }
    });

    return Array.from(urls);
  }

  getOfflineDocs (): OfflineDocument[] {
    return JSON.parse(localStorage.getItem(OfflineManager.INVENTORY_KEY) || '[]');
  }

  async clearOfflineDocs () {
    // Clear the cache
    await caches.delete(OfflineManager.CACHE_NAME);
    this.cache = null;
    // Clear metadata from localStorage
    localStorage.removeItem(OfflineManager.INVENTORY_KEY);
  }
}

let registered = false;

async function registerServiceWorker () {
  if (!registered && 'serviceWorker' in navigator) {
    try {
      await navigator.serviceWorker.register('/offline-service-worker.js');
      registered = true;
    } catch (err) {
      console.error('Service worker registration failed:', err);
    }
  }
}

// if the user has offline content, then register the service worker
if (localStorage.getItem(OfflineManager.INVENTORY_KEY)) {
  registerServiceWorker();
}

let manager: OfflineManager | null = null;

export function getManager (): OfflineManager {
  if (!manager) {
    registerServiceWorker();
    manager = new OfflineManager();
  }
  return manager;
}

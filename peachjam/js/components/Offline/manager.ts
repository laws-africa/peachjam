interface OfflineDocument {
  url: string;
  title: string;
}

interface OfflineTopic {
  id: string;
  url: string;
  name: string;
  documents: OfflineDocument[];
}

interface Inventory {
  documents: OfflineDocument[],
  topics: OfflineTopic[],
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

  getInventory (): Inventory {
    const saved = localStorage.getItem(OfflineManager.INVENTORY_KEY);
    if (saved) {
      return JSON.parse(saved);
    }
    return {
      documents: [],
      topics: []
    };
  }

  saveInventory (inventory: Inventory) {
    localStorage.setItem(OfflineManager.INVENTORY_KEY, JSON.stringify(inventory));
  }

  addTopicToInventory (inventory: Inventory, topic: OfflineTopic) {
    if (!inventory.topics.find((t: OfflineTopic) => t.id === topic.id)) {
      inventory.topics.push(topic);
    }
    for (const doc of topic.documents) {
      this.addDocumentToInventory(inventory, doc);
    }
  }

  addDocumentToInventory (inventory: Inventory, doc: OfflineDocument) {
    if (!inventory.documents.find((d: OfflineDocument) => d.url === doc.url)) {
      inventory.documents.push(doc);
    }
  }

  async makeDocumentAvailableOffline (url: string, title: string) {
    const cache = await this.getCache();
    // TODO: common static assets?
    const assets = [url, OfflineManager.OFFLINE_PAGE, ...this.getStaticAssets()];
    await cache.addAll(assets);

    const inventory = this.getInventory();
    this.addDocumentToInventory(inventory, { url, title });
    this.saveInventory(inventory);
  }

  async makeTopicAvailableOffline (id: string, url: string, name: string) {
    try {
      // get the manifest to know what to cache
      const resp = await fetch(`/offline/topic/${encodeURIComponent(id)}/manifest.json`);
      if (resp.ok) {
        const manifest = await resp.json();

        // TODO: common static assets?
        const assets = [
          OfflineManager.OFFLINE_PAGE,
          ...manifest.assets,
          ...manifest.documents.map((doc: OfflineDocument) => doc.url)
        ];

        const cache = await this.getCache();
        await cache.addAll(assets);

        const inventory = this.getInventory();
        this.addTopicToInventory(inventory, {
          id,
          url,
          name,
          documents: manifest.documents
        });
        this.saveInventory(inventory);
      }
    } catch (e) {
      console.error('Failed to fetch topic manifest:', e);
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

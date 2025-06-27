interface OfflineDocument {
  url: string;
  title: string;
}

interface OfflineTaxonomy {
  id: string;
  url: string;
  name: string;
  documents: OfflineDocument[];
}

interface Inventory {
  version: number,
  documents: OfflineDocument[],
  taxonomies: OfflineTaxonomy[],
}

export class OfflineManager {
  // This MUST match CACHE_NAME in offline-service-worker.js
  public static CACHE_NAME = 'peachjam-offline-v1';
  public static INVENTORY_KEY = 'peachjam-offline-inventory';
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
      version: 1,
      documents: [],
      taxonomies: []
    };
  }

  saveInventory (inventory: Inventory) {
    localStorage.setItem(OfflineManager.INVENTORY_KEY, JSON.stringify(inventory));
  }

  addTopicToInventory (inventory: Inventory, taxonomy: OfflineTaxonomy) {
    // delete any existing taxonomy with the same ID
    inventory.taxonomies = inventory.taxonomies.filter((t: OfflineTaxonomy) => t.id !== taxonomy.id);
    inventory.taxonomies.push(taxonomy);
    for (const doc of taxonomy.documents) {
      this.addDocumentToInventory(inventory, doc);
    }
  }

  addDocumentToInventory (inventory: Inventory, doc: OfflineDocument) {
    // delete any existing document with the same URL
    inventory.documents = inventory.documents.filter((d: OfflineDocument) => d.url !== doc.url);
    inventory.documents.push(doc);
  }

  async makeDocumentAvailableOffline (url: string, title: string) {
    const cache = await this.getCache();
    const urls = [url, OfflineManager.OFFLINE_PAGE, ...this.getStaticAssets()];
    console.log('Caching urls for offline:', urls);
    await cache.addAll(urls);

    const inventory = this.getInventory();
    this.addDocumentToInventory(inventory, { url, title });
    this.saveInventory(inventory);
  }

  async makeTaxonomyAvailableOffline (id: string) {
    try {
      // get the manifest to know what to cache
      const resp = await fetch(`/offline/taxonomy/${encodeURIComponent(id)}/manifest.json`);
      if (resp.ok) {
        const manifest = await resp.json();

        const urls = [
          OfflineManager.OFFLINE_PAGE,
          ...this.getStaticAssets(),
          ...manifest.urls,
          ...manifest.documents.map((doc: OfflineDocument) => doc.url)
        ];

        const cache = await this.getCache();
        console.log('Caching urls for offline:', urls);
        await cache.addAll(urls);

        const inventory = this.getInventory();
        this.addTopicToInventory(inventory, {
          id,
          url: manifest.url,
          name: manifest.name,
          documents: manifest.documents
        });
        this.saveInventory(inventory);
      }
    } catch (e) {
      console.error('Failed to fetch taxonomy manifest: ', e);
    }
  }

  /**
   * Get a list of asset URLs on this page that should be cached. This is easier than explicitly listing all
   * static assets, and will include things like images in footers, etc.
   */
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

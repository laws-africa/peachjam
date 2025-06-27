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

/**
 * This class handles storing and tracking content that is available offline.
 *
 * Offline content works in collaboration with a ServiceWorker script (see peachjam/static/js/offline-service-worker.js).
 *
 * The service worker must be registered for the offline functionality to work. Whenever a user tries to make content
 * available offline the service worker is registered, and it then remains registered. Because browsers check for
 * updates to service workers only when they are registered, we also re-register every time a page loads if the user
 * has content stored offline.
 *
 * The offline functionality works with two data sources:
 *
 * - inventory: list of documents and topics that are available offline
 * - cache: the actual cached pages used while offline, including documents, javascript, images, stylesheets, etc.
 *
 * When a user makes content available offline, the manager stores information in the inventory of what is available.
 * This is purely informational to tell the user what they do/don't have access to. It also then fires off requests
 * to populate the offline content cache. This is the actual content (handled by the service worker) that is then
 * available offline.
 */
export class OfflineManager {
  // This MUST match CACHE_NAME in offline-service-worker.js
  public static CACHE_NAME = 'peachjam-offline-v1';
  public static INVENTORY_KEY = 'peachjam-offline-inventory';
  public static OFFLINE_PAGE = '/offline/offline';

  cache: Cache | null = null;
  registered = false;

  constructor () {
    if (localStorage.getItem(OfflineManager.INVENTORY_KEY)) {
      this.registerServiceWorker();
    }
  }

  async registerServiceWorker () {
    if (!this.registered && 'serviceWorker' in navigator) {
      try {
        await navigator.serviceWorker.register('/offline-service-worker.js');
        this.registered = true;
      } catch (err) {
        console.error('Service worker registration failed:', err);
      }
    }
  }

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

  async makeTaxonomyAvailableOffline (id: string) {
    this.registerServiceWorker();

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
    // Clear metadata from localStorage
    localStorage.removeItem(OfflineManager.INVENTORY_KEY);
    // Clear the cache
    await caches.delete(OfflineManager.CACHE_NAME);
    this.cache = null;
  }
}

export const manager = new OfflineManager();

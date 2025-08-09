interface OfflineDocument {
  url: string;
  title: string;
}

interface OfflineTaxonomy {
  id: string;
  url: string;
  name: string;
  fingerprint: string;
  checkedAt: string;
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
 *
 * The service worker detects when the user is offline. This class then requests that state from the service worker
 * so that it can update a class on the whole page, so that some elements that we know don't work offline can be hidden.
 */
export class OfflineManager {
  // This MUST match CACHE_NAME in offline-service-worker.js
  public static CACHE_NAME = 'peachjam-offline-v1';
  public static INVENTORY_KEY = 'peachjam-offline-inventory';
  public static OFFLINE_PAGE = '/offline/offline';
  public static OFFLINE_KEY = 'peachjam-offline-status';

  cache: Cache | null = null;
  registered = false;
  isOffline = false;

  constructor () {
    this.setupOffline();
    if (localStorage.getItem(OfflineManager.INVENTORY_KEY)) {
      this.registerServiceWorker();
      this.checkForUpdates();
    }
  }

  setupOffline () {
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.addEventListener('message', (event) => {
        if (event.data?.type === 'notifyOfflineStatus') {
          this.setOfflineStatus(event.data.value);
        }
      });

      // Request offline status from the service worker
      navigator.serviceWorker.ready.then((registration) => {
        registration.active?.postMessage({ type: 'requestOfflineStatus' });
      });
    }
  }

  setOfflineStatus (offline: boolean) {
    if (this.isOffline !== offline) {
      this.isOffline = offline;
      if (offline) {
        document.documentElement.classList.add('offline');
        console.log('You are currently offline.');
      } else {
        document.documentElement.classList.remove('offline');
        console.log('You are back online.');
      }
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

  async checkForUpdates (force = false) {
    // Check every 24 hours for updates to the topics store in the inventory
    const inventory = this.getInventory();
    const changed = [];
    const threshold = new Date();
    threshold.setHours(threshold.getHours() - 24);

    for (const taxonomy of inventory.taxonomies) {
      if (force) {
        changed.push(taxonomy);
        continue;
      }

      if (new Date(taxonomy.checkedAt) < threshold) {
        console.log(`Checking for updates to ${taxonomy.name}...`);

        try {
          const resp = await fetch(`/offline/taxonomy/${taxonomy.id}/manifest.json`);
          if (resp.ok) {
            const manifest = await resp.json();
            // If the fingerprint has changed, update the cache
            if (manifest.fingerprint !== taxonomy.fingerprint) {
              console.log(`Taxonomy ${taxonomy.name} has changed`);
              changed.push(taxonomy);
            } else {
              console.log(`Taxonomy ${taxonomy.name} has not changed`);
              taxonomy.checkedAt = new Date().toISOString();
            }
          }
        } catch (e) {
          console.error('Failed to fetch taxonomy manifest for periodic update: ', e);
        }
      }
    }

    // write updated timestamps
    this.saveInventory(inventory);

    // now update the changed ones
    for (const taxonomy of changed) {
      console.log(`Updating offline taxonomy ${taxonomy.name}...`);
      await this.makeTaxonomyAvailableOffline(taxonomy.id);
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

  removeTopicFromInventory (inventory: Inventory, id: string) {
    const taxonomy = inventory.taxonomies.find((t: OfflineTaxonomy) => t.id === id);
    inventory.taxonomies = inventory.taxonomies.filter((t: OfflineTaxonomy) => t.id !== id);

    const toDelete : string[] = [];

    for (const doc of taxonomy?.documents || []) {
      // do any other taxonomies have this document?
      const others = inventory.taxonomies.filter((t: OfflineTaxonomy) => t.documents.some(d => d.url === doc.url));
      if (others.length === 0) {
        // no other taxonomies have this document, so remove it
        this.removeDocumentFromInventory(inventory, doc);
        toDelete.push(doc.url);
      }
    }

    this.getCache().then(cache => {
      for (const url of toDelete) {
        console.log(`Removing document ${url} from cache`);
        cache.delete(url);
      }
    });
  }

  addDocumentToInventory (inventory: Inventory, doc: OfflineDocument) {
    // delete any existing document with the same URL
    this.removeDocumentFromInventory(inventory, doc);
    inventory.documents.push(doc);
  }

  removeDocumentFromInventory (inventory: Inventory, doc: OfflineDocument) {
    inventory.documents = inventory.documents.filter((d: OfflineDocument) => d.url !== doc.url);
  }

  isTaxonomyAvailableOffline (id: string) {
    const inventory = this.getInventory();
    return inventory.taxonomies.some((taxonomy: OfflineTaxonomy) => taxonomy.id === id);
  }

  async * makeTaxonomyAvailableOfflineDetails (id: string) {
    this.registerServiceWorker();
    console.log(`Making taxonomy ${id} available offline...`);

    try {
      // get the manifest to know what to cache
      const resp = await fetch(`/offline/taxonomy/${id}/manifest.json`);
      if (resp.ok) {
        const manifest = await resp.json();

        const urls = [
          OfflineManager.OFFLINE_PAGE,
          ...this.getStaticAssets(),
          ...manifest.urls,
          ...manifest.documents.map((doc: OfflineDocument) => doc.url)
        ];

        const inventory = this.getInventory();
        this.addTopicToInventory(inventory, {
          id,
          url: manifest.url,
          name: manifest.name,
          fingerprint: manifest.fingerprint,
          documents: manifest.documents,
          checkedAt: new Date().toISOString()
        });
        this.saveInventory(inventory);

        const cache = await this.getCache();
        console.log('Caching urls for offline:', urls);

        let completed = 0;
        for (const url of urls) {
          try {
            await cache.add(url);
            completed++;
            yield {url, completed, total: urls.length, success: true};
          } catch (e) {
            console.error(`Failed to cache URL: ${url}`, e);
            yield {url, completed, total: urls.length, success: false};
          }
          // wait a bit to avoid overwhelming the server, and to give the browser a chance to re-render progress
          await new Promise(resolve => setTimeout(resolve, 100));
        }

        console.log('Cached URLs');
        console.log(`Taxonomy ${id} is now available offline.`);
      }
    } catch (e) {
      console.error('Failed to fetch taxonomy manifest: ', e);
    }

    yield { completed: 1, total: 1, success: true, finished: true };
  }

  async makeTaxonomyAvailableOffline (id: string) {
    for await (const result of this.makeTaxonomyAvailableOfflineDetails(id)) {
      // do nothing, just consume the iterables to ensure it progresses
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
    console.log('Clearing offline documents...');
    // Clear metadata from localStorage
    localStorage.removeItem(OfflineManager.INVENTORY_KEY);
    // Clear the cache
    await caches.delete(OfflineManager.CACHE_NAME);
    this.cache = null;
  }

  /**
   * Remove a taxonomy and its documents from offline storage.
   * @param id taxonomy id
   */
  removeOfflineTaxonomy (id: string) {
    const inventory = this.getInventory();
    this.removeTopicFromInventory(inventory, id);
    this.saveInventory(inventory);
  }
}

export const manager = new OfflineManager();

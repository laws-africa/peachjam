const cacheName = 'peachjam-offline-docs-v1';
const listingKey = 'offlineDocs';

export class OfflineDocumentButton {
  constructor (button: HTMLElement) {
    button.addEventListener('click', (event: Event) => {
      const url = document.location.pathname;
      const title = document.querySelector('meta[property="og:title"]')?.getAttribute('content') || "";
      this.makeAvailableOffline(url, title);
    });
  }

  async makeAvailableOffline (url: string, title: string) {
    const cache = await caches.open(cacheName);
    const assets = [
      url,
      ...this.getStaticAssets()
    ];
    await cache.addAll(assets);

    // Store metadata for listing later
    const saved = JSON.parse(localStorage.getItem(listingKey) || '[]');
    if (!saved.find((doc: any) => doc.url === url)) {
      saved.push({
        url: url, title: title
      });
      localStorage.setItem(listingKey, JSON.stringify(saved));
    }

    alert('Document saved for offline use');
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
}

async function registerServiceWorker () {
  if ('serviceWorker' in navigator) {
    try {
      // TODO: URL
      await navigator.serviceWorker.register('/offline-service-worker.js');
      console.log('Service worker registered');
    } catch (err) {
      console.error('Service worker registration failed:', err);
    }
  }
}

// when should this be done?
registerServiceWorker();

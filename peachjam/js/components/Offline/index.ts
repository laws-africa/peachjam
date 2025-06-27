import { getManager } from './manager';

export { default as OfflineDetails } from './OfflineDetails.vue';

export class OfflineDocumentButton {
  constructor (button: HTMLElement) {
    button.addEventListener('click', (event: Event) => {
      const url = document.location.pathname;
      const title = document.querySelector('meta[property="og:title"]')?.getAttribute('content') || '';
      getManager().makeDocumentAvailableOffline(url, title);
    });
  }
}

export class OfflineTaxonomyButton {
  constructor (button: HTMLElement) {
    const id = button.getAttribute('data-taxonomy');

    // TODO: is it available offline already?

    if (id) {
      button.addEventListener('click', (event: Event) => {
        const url = document.location.pathname;
        getManager().makeTaxonomyAvailableOffline(id);
      });
    }
  }
}

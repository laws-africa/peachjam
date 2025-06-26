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

export class OfflineTopicButton {
  constructor (button: HTMLElement) {
    const id = button.getAttribute('data-topic');
    const name = button.getAttribute('data-name');
    const url = button.getAttribute('data-url');

    // TODO: is it available offline already?

    if (id && name && url) {
      button.addEventListener('click', (event: Event) => {
        const url = document.location.pathname;
        getManager().makeTopicAvailableOffline(id, url, name);
      });
    }
  }
}

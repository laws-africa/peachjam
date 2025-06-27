import { manager } from './manager';

export { default as OfflineDetails } from './OfflineDetails.vue';

export class OfflineTaxonomyButton {
  constructor (button: HTMLElement) {
    const id = button.getAttribute('data-taxonomy');

    // TODO: is it available offline already?

    if (id) {
      button.addEventListener('click', (event: Event) => {
        const url = document.location.pathname;
        manager.makeTaxonomyAvailableOffline(id);
      });
    }
  }
}

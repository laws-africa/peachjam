import ShareSelectionModal from './DocumentContent/ShareSelectionModal.vue';
import { createAndMountApp } from '../utils/vue-utils';
import { vueI18n } from '../i18n';

export default class ShareMenuItem {
  private documentTitle: string;

  constructor (root: HTMLElement) {
    root.addEventListener('click', this.showModal.bind(this));
    // @ts-ignore
    this.documentTitle = document.querySelector('.document-content')?.dataset?.title || '';
  }

  showModal () {
    // open the share dialog
    createAndMountApp({
      component: ShareSelectionModal,
      props: {
        url: window.location.toString(),
        text: this.documentTitle
      },
      use: [vueI18n],
      mountTarget: document.createElement('div')
    });
  }
}

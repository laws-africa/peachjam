import { createAndMountApp } from '../../utils/vue-utils';
import SavedDocumentModal from './SavedDocumentModal.vue';
import { vueI18n } from '../../i18n';

let globalModal: any = null;

export class SavedDocumentModalToggle {
  button: HTMLElement;

  constructor (button: HTMLElement) {
    this.button = button;
    this.button.addEventListener('click', this.show.bind(this));

    // todo remove this
    if (!globalModal) {
      globalModal = createAndMountApp({
        component: SavedDocumentModal,
        props: {
          url: this.button.getAttribute('data-modal-url')
        },
        use: [vueI18n],
        mountTarget: document.createElement('div') as HTMLElement
      });
    }
  }

  show () {
    // @ts-ignore
    globalModal.show();
  }
}

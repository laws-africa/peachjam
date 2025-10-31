import DocumentChatButton from './DocumentChatButton.vue';
import { createAndMountApp } from '../../utils/vue-utils';
import { vueI18n } from '../../i18n';

export class DocumentChat {
  constructor (documentId: string) {
    // TODO: check if enabled
    const div = document.createElement('div');
    document.body.appendChild(div);
    createAndMountApp({
      component: DocumentChatButton,
      props: {
        documentId: documentId
      },
      use: [vueI18n],
      mountTarget: div
    });
  }
}

import DocumentChatButton from './DocumentChatButton.vue';
import { createAndMountApp } from '../../utils/vue-utils';
import { vueI18n } from '../../i18n';
import peachjam from '../../peachjam';

export class DocumentChat {
  constructor (documentId: string) {
    if (peachjam.config.chat.enabled) {
      peachjam.whenUserLoaded().then((user) => {
        if (user.perms.includes('peachjam_ml.add_chatthread')) {
          this.setup(documentId);
        }
      });
    }
  }

  setup (documentId: string) {
    const div = document.createElement('div');
    document.body.appendChild(div);
    createAndMountApp({
      component: DocumentChatButton,
      props: {
        documentId: documentId,
        assistantName: peachjam.config.chat.assistantName
      },
      use: [vueI18n],
      mountTarget: div
    });
  }
}

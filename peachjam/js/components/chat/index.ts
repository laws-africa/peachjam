import DocumentChatPopup from './DocumentChatPopup.vue';
import { createAndMountApp } from '../../utils/vue-utils';
import { vueI18n } from '../../i18n';
import peachjam from '../../peachjam';

let chatPopup: any = null;

/**
 * Temporary component that only shows the document chat banner if the user has the correct perms. Once chat is
 * available to all users, this component can be removed.
 */
export class DocumentChatBanner {
  root: HTMLElement;

  constructor (root: HTMLElement) {
    this.root = root;

    peachjam.whenUserLoaded().then((user) => {
      if (user.perms.includes('peachjam_ml.add_chatthread')) {
        this.root.classList.remove('d-none');
      }
    });
  }
}

export class DocumentChatOpenButton {
  constructor (root: HTMLElement) {
    root.addEventListener('click', () => {
      if (chatPopup) {
        chatPopup.show();
      }
    });
  }
}

export class DocumentChatFloatingButton {
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
    chatPopup = createAndMountApp({
      component: DocumentChatPopup,
      props: {
        documentId: documentId,
        assistantName: peachjam.config.chat.assistantName
      },
      use: [vueI18n],
      mountTarget: div
    });
  }
}

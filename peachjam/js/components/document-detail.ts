import peachJam from '../peachjam';
import { htmxAjax } from '../utils/function';

export default class DocumentDetail {
  private documentId: string;
  private debugUrl: string;

  constructor (root: HTMLElement) {
    this.documentId = root.dataset.documentId || '';
    this.debugUrl = root.dataset.debugUrl || '';
    peachJam.whenUserLoaded().then((user) => {
      if (user.perms.includes('peachjam.can_debug_document')) {
        this.loadDebug();
      }
    });
  }

  loadDebug () {
    if (this.debugUrl) {
      htmxAjax('GET', this.debugUrl);
    }
  }
}

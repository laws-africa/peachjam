import { createApp } from 'vue';
import DocumentSearch from './DocumentSearch/index.vue';

class DocumentContent {
  protected root: HTMLElement;
  constructor (root: HTMLElement) {
    this.root = root;
    let targetMountElement;
    const aknDoc = root.querySelector('la-akoma-ntoso');
    if (aknDoc) {
      targetMountElement = root.querySelector('#akn-document-search');
      if (targetMountElement) {
        createApp(DocumentSearch, {
          document: aknDoc
        }).mount(targetMountElement);
      }
    }
  }
}

export default DocumentContent;

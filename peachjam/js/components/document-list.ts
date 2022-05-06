import ListFacets from './ListFacets.vue';
import { createApp } from 'vue';

class DocumentList {
  constructor (root: HTMLElement) {
    const overlayElement = root.querySelector('#overlay');
    const facetsElement:any = root.querySelector('#list-facets');
    createApp(ListFacets).mount(facetsElement);
    if (overlayElement) {
      facetsElement.addEventListener('submitted', () => {
        overlayElement.classList.remove('d-flex');
      });
    }
  }
}

export default DocumentList;

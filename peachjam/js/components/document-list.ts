import ListFacets from './ListFacets.vue';
import { createApp } from 'vue';

class DocumentList {
  constructor (root: HTMLElement) {
    const facetsElement:any = root.querySelector('#list-facets');
    const facetDataJsonElement = root.querySelector('#facet-data');
    let alphabet = []; let years = []; let authors = [];
    if (facetDataJsonElement && facetDataJsonElement.textContent != null) {
      alphabet = JSON.parse(facetDataJsonElement.textContent).alphabet;
      years = JSON.parse(facetDataJsonElement.textContent).years;
      authors = JSON.parse(facetDataJsonElement.textContent).authors;
    }
    createApp(ListFacets, {
      alphabet,
      years,
      authors
    }).mount(facetsElement);
  }
}

export default DocumentList;

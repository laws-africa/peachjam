import ListFacets from './ListFacets.vue';
import { createApp } from 'vue';
import { i18n } from '../i18n';

class DocumentList {
  constructor (root: HTMLElement) {
    const facetsElement:any = root.querySelector('#list-facets');
    const facetDataJsonElement = root.querySelector('#facet-data');
    let alphabet, years, authors, docTypes;
    if (facetDataJsonElement && facetDataJsonElement.textContent) {
      alphabet = JSON.parse(facetDataJsonElement.textContent).alphabet;
      years = JSON.parse(facetDataJsonElement.textContent).years;
      docTypes = JSON.parse(facetDataJsonElement.textContent).doc_types;
      authors = JSON.parse(facetDataJsonElement.textContent).authors;

      // Treaties and protocols don't have associated authors
      if (window.location.href.includes('/legislation/')) {
        authors = [];
      }
    }
    const app = createApp(ListFacets, {
      alphabet,
      years,
      authors,
      docTypes
    });
    app.use(i18n);
    app.mount(facetsElement);
  }
}

export default DocumentList;

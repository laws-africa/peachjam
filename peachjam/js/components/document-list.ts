import ListFacets from './ListFacets.vue';
import { createApp } from 'vue';

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
      // // Authoring body facet appears every list page except /judgments/ and /legislation/
      // if (!['/judgments/', '/legislation/'].some(value => window.location.href.includes(value))) {
      //   authors = JSON.parse(facetDataJsonElement.textContent).authors;
      // }
    }
    createApp(ListFacets, {
      alphabet,
      years,
      authors,
      docTypes
    }).mount(facetsElement);
  }
}

export default DocumentList;

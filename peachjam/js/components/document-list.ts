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

      // // Court facet only appears on the judgments page
      // if (window.location.href.includes('/judgments/')) {
      //   authors = JSON.parse(facetDataJsonElement.textContent).authors;
      // }
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

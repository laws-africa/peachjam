import ListFacets from './ListFacets.vue';
import { createApp } from 'vue';

class DocumentList {
  constructor (root: HTMLElement) {
    const facetsElement:any = root.querySelector('#list-facets');
    const facetDataJsonElement = root.querySelector('#facet-data');
    let alphabet, years, courts, authoringBodies, docTypes;
    if (facetDataJsonElement && facetDataJsonElement.textContent) {
      alphabet = JSON.parse(facetDataJsonElement.textContent).alphabet;
      years = JSON.parse(facetDataJsonElement.textContent).years;

      // Court facet only appears on the judgments page
      if (window.location.href.includes('/judgments/')) {
        courts = JSON.parse(facetDataJsonElement.textContent).courts;
      }
      // Authoring body facet appears every list page except /judgments/ and /legislation/
      if (!['/judgments/', '/legislation/'].some(value => window.location.href.includes(value))) {
        authoringBodies = JSON.parse(facetDataJsonElement.textContent).authoring_bodies;
      }

      if (!['/courts/', '/authors/'].some(value => window.location.href.includes(value))) {
        docTypes = JSON.parse(facetDataJsonElement.textContent).doc_type;
      }
    }
    createApp(ListFacets, {
      alphabet,
      years,
      authoringBodies,
      courts,
      docTypes
    }).mount(facetsElement);
  }
}

export default DocumentList;

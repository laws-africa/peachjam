import ListFacets from './ListFacets.vue';
import { createApp } from 'vue';

class DocumentList {
  constructor (root: HTMLElement) {
    const facetsElement:any = root.querySelector('#list-facets');
    const facetDataJsonElement = root.querySelector('#facet-data');
    let alphabet = []; let years = []; let courts = []; let authoringBodies = [];
    if (facetDataJsonElement && facetDataJsonElement.textContent) {
      alphabet = JSON.parse(facetDataJsonElement.textContent).alphabet;
      years = JSON.parse(facetDataJsonElement.textContent).years;
      if (window.location.href.includes('/judgments/')) {
        courts = JSON.parse(facetDataJsonElement.textContent).courts;
      } else {
        authoringBodies = JSON.parse(facetDataJsonElement.textContent).authoring_bodies;
      }
    }
    createApp(ListFacets, {
      alphabet,
      years,
      authors: [...courts, ...authoringBodies]
    }).mount(facetsElement);
  }
}

export default DocumentList;

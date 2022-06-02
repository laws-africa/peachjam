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

      // Court facet only appears on the judgments page
      if (window.location.href.includes('/judgments/')) {
        courts = JSON.parse(facetDataJsonElement.textContent).courts;
      }
      // Authoring body facet appears every list page except /judgments/ and /legislation/
      if (!['/judgments/', '/legislation/'].some(value => window.location.href.includes(value))) {
        authoringBodies = JSON.parse(facetDataJsonElement.textContent).authoring_bodies;
      }
    }
    createApp(ListFacets, {
      alphabet,
      years,
      authoringBodies,
      courts
    }).mount(facetsElement);
  }
}

export default DocumentList;

import ListFacets from './ListFacets.vue';
import { vueI18n } from '../i18n';
import { createAndMountApp } from '../utils/vue-utils';

type FacetType = [] | undefined

class DocumentList {
  constructor (root: HTMLElement) {
    const mountTargets: HTMLElement[] = Array.from(root.querySelectorAll('[data-list-facets]'));
    const facetDataJsonElement = root.querySelector('#facet-data');

    let alphabet: FacetType, years: FacetType, authors: FacetType, docTypes: FacetType, documentNatures: FacetType, judges: FacetType, courts: FacetType;
    if (facetDataJsonElement && facetDataJsonElement.textContent) {
      alphabet = JSON.parse(facetDataJsonElement.textContent).alphabet;
      years = JSON.parse(facetDataJsonElement.textContent).years;
      docTypes = JSON.parse(facetDataJsonElement.textContent).doc_types;
      documentNatures = JSON.parse(facetDataJsonElement.textContent).document_natures;
      authors = JSON.parse(facetDataJsonElement.textContent).authors;
      judges = JSON.parse(facetDataJsonElement.textContent).judges;
      courts = JSON.parse(facetDataJsonElement.textContent).courts;

      // Treaties and protocols don't have associated authors
      if (window.location.href.includes('/legislation/')) {
        authors = [];
      }
    }

    mountTargets.forEach(mountTarget => {
      createAndMountApp({
        component: ListFacets,
        props: {
          alphabet,
          years,
          docTypes,
          documentNatures,
          authors,
          judges,
          courts
        },
        use: [vueI18n],
        mountTarget
      });
    });
  }
}

export default DocumentList;

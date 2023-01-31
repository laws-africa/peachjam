import ListFacets from './ListFacets.vue';
import { vueI18n } from '../i18n';
import { createAndMountApp } from '../utils/vue-utils';

class DocumentList {
  constructor (root: HTMLElement) {
    const mountTargets: HTMLElement[] = Array.from(root.querySelectorAll('[data-list-facets]'));
    const facetDataJsonElement = root.querySelector('#facet-data');
    let props : any = {};

    if (facetDataJsonElement && facetDataJsonElement.textContent) {
      props = JSON.parse(facetDataJsonElement.textContent);

      // Treaties and protocols don't have associated authors
      if (window.location.href.includes('/legislation/')) {
        props.authors = [];
      }
    }

    mountTargets.forEach(mountTarget => {
      createAndMountApp({
        component: ListFacets,
        props: props,
        use: [vueI18n],
        mountTarget
      });
    });
  }
}

export default DocumentList;

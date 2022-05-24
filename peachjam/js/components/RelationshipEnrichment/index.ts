import { createApp, defineComponent, ComponentPublicInstance } from 'vue';
import RelationshipEnrichmentList from './RelationshipEnrichmentList.vue';
import { IRelationshipEnrichment } from './enrichment';

export class RelationshipEnrichments {
  root: HTMLElement;
  gutter: Element | null;
  akn: Element | null;
  enrichments: IRelationshipEnrichment[];
  listComponent: ComponentPublicInstance;

  constructor (root: HTMLElement) {
    this.root = root;
    this.gutter = root.querySelector('la-gutter');
    this.akn = root.querySelector('la-akoma-ntoso');

    const node = document.getElementById('provision-relationships');
    if (node) {
      this.enrichments = JSON.parse(node.innerText || '[]');
    } else {
      this.enrichments = [];
    }

    // @ts-ignore
    this.listComponent = createApp(defineComponent(RelationshipEnrichmentList), {
      gutter: this.gutter,
      viewRoot: this.root,
      enrichments: this.enrichments,
      readonly: false,
      thisWorkFrbrUri: '/akn/aa-au/act/charter/1990/rights-and-welfare-of-the-child'
    }).mount(document.createElement('div'));

    const observer = new MutationObserver(() => {
      // @ts-ignore
      this.listComponent.markAndAnchorAll();
    });
    if (this.akn) {
      observer.observe(this.akn, { childList: true });
    }
  }
}

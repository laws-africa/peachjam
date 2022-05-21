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
    // TODO
    this.enrichments = [{
      id: 1,
      title: 'test',
      target: {
        anchor_id: 'part_I-Rightsandduties__chp_One__art_I__para_1'
      }
    }];

    // @ts-ignore
    this.listComponent = createApp(defineComponent(RelationshipEnrichmentList), {
      gutter: this.gutter,
      viewRoot: this.root,
      enrichments: this.enrichments,
      readonly: false
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

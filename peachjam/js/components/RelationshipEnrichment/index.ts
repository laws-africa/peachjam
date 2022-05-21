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
      subject_work_frbr_uri: '/akn/foo',
      subject_target_id: null,
      subject_documents: [{
        title: 'Foo document (ger)',
        expression_frbr_uri: '/akn/foo/ger@1910-01-01',
        language: 'ger',
        date: '1909-01-01'
      }, {
        title: 'Foo document (fre)',
        expression_frbr_uri: '/akn/foo/fre@1910-01-01',
        language: 'fre',
        date: '1910-01-01'
      }],
      predicate: {
        id: 1,
        name: 'gives effect to',
        verb: 'gives effect to',
        reverse_verb: 'is effected by'
      },
      object_work_frbr_uri: '/akn/aa-au/act/charter/1990/rights-and-welfare-of-the-child',
      object_target_id: 'part_I-Rightsandduties__chp_One__art_I__para_1',
      object_documents: []
    }];

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

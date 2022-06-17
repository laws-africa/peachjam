import { createApp, defineComponent, ComponentPublicInstance } from 'vue';
import RelationshipEnrichmentList from './RelationshipEnrichmentList.vue';
import { IRelationshipEnrichment } from './enrichment';
import { GutterEnrichmentManager, IGutterEnrichmentProvider } from '@laws-africa/indigo-akn/dist/enrichments';
import { IRangeTarget } from '@laws-africa/indigo-akn/dist/ranges';

export class RelationshipEnrichments implements IGutterEnrichmentProvider {
  root: HTMLElement;
  gutter: Element | null;
  akn: Element | null;
  enrichments: IRelationshipEnrichment[];
  listComponent: ComponentPublicInstance;
  manager: GutterEnrichmentManager;
  thisWorkFrbrUri: string;

  constructor (root: HTMLElement) {
    this.root = root;
    this.gutter = root.querySelector('la-gutter');
    this.akn = root.querySelector('la-akoma-ntoso');
    // TODO: this work
    this.thisWorkFrbrUri = '/akn/aa-au/act/charter/1990/rights-and-welfare-of-the-child';

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
      thisWorkFrbrUri: this.thisWorkFrbrUri
    }).mount(document.createElement('div'));

    const observer = new MutationObserver(() => {
      // @ts-ignore
      this.listComponent.markAndAnchorAll();
    });
    if (this.akn) {
      observer.observe(this.akn, { childList: true });
    }

    // TODO: permissions
    this.manager = new GutterEnrichmentManager(this.root);
    this.manager.addProvider(this);
  }

  getButton (target: IRangeTarget): HTMLButtonElement | null {
    const btn = document.createElement('button');
    btn.className = 'btn btn-outline-secondary';
    btn.type = 'button';
    btn.innerText = 'hi';
    return btn;
  }

  addEnrichment (target: IRangeTarget): void {
    // @ts-ignore
    this.listComponent.creating = {
      id: 999,
      // TODO
      predicate: {
        id: 999,
        verb: 'verb',
        reverse_verb: 'reverse'
      },
      // @ts-ignore
      subject_work: {
        frbr_uri: this.thisWorkFrbrUri,
      },
      subject_target_id: target.anchor_id,
      subject_documents: [],

      // @ts-ignore
      object_work: {},
      object_target_id: null,
      object_documents: []
    };
  }
}

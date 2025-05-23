import { ComponentPublicInstance } from 'vue';
import RelationshipEnrichmentList from './RelationshipEnrichmentList.vue';
import { IRelationshipEnrichment } from './enrichment';
import { GutterEnrichmentManager, IGutterEnrichmentProvider } from '@lawsafrica/indigo-akn/dist/enrichments';
import { IRangeTarget } from '@lawsafrica/indigo-akn/dist/ranges';
import { vueI18n } from '../../i18n';
import { createAndMountApp } from '../../utils/vue-utils';

export class RelationshipEnrichments implements IGutterEnrichmentProvider {
  root: HTMLElement;
  gutter: Element | null;
  akn: Element | null;
  enrichments: IRelationshipEnrichment[];
  listComponent: ComponentPublicInstance;
  manager: GutterEnrichmentManager;
  workFrbrUri: string;
  workId: string;
  editable: boolean;
  displayType: string; // html, pdf or akn

  constructor (root: HTMLElement, manager: GutterEnrichmentManager, displayType: string) {
    this.root = root;
    this.manager = manager;
    this.displayType = displayType;
    this.gutter = root.querySelector('la-gutter');
    this.akn = root.querySelector('la-akoma-ntoso');
    this.workFrbrUri = root.dataset.workFrbrUri || '';
    this.workId = root.dataset.workId || '';
    this.editable = this.root.hasAttribute('data-editable-relationships');

    const node = document.getElementById('provision-relationships');
    if (node) {
      this.enrichments = JSON.parse(node.innerText || '[]');
    } else {
      this.enrichments = [];
    }

    // @ts-ignore
    this.listComponent = createAndMountApp({
      component: RelationshipEnrichmentList,
      props: {
        gutter: this.gutter,
        viewRoot: this.root,
        enrichments: this.enrichments,
        editable: this.editable,
        useSelectors: this.displayType === 'pdf',
        thisWorkFrbrUri: this.workFrbrUri
      },
      use: [vueI18n],
      mountTarget: document.createElement('div') as HTMLElement
    });

    const observer = new MutationObserver(() => {
      // @ts-ignore
      this.listComponent.markAndAnchorAll();
    });
    if (this.akn) {
      observer.observe(this.akn, { childList: true });
    }

    if (this.editable) {
      this.manager.addProvider(this);
    }
  }

  getButton (target: IRangeTarget): HTMLButtonElement | null {
    return null;
  }

  addEnrichment (target: IRangeTarget): void {
    // @ts-ignore
    this.listComponent.creating = {
      id: null,
      predicate_id: null,
      predicate: {},

      subject_work_id: this.workId,
      subject_work: {
        frbr_uri: this.workFrbrUri
      },
      subject_target_id: target.anchor_id,
      subject_selectors: target.selectors,
      subject_documents: [],

      object_work: {},
      object_target_id: null,
      object_documents: []
    };
  }
}

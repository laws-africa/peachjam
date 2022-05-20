import { createApp, App, defineComponent } from 'vue';
import ProvisionEnrichmentList from './ProvisionEnrichmentList.vue';
import { IProvisionEnrichment } from './enrichment';

export class ProvisionEnrichments {
  root: HTMLElement;
  gutter: Element | null;
  akn: Element | null;
  enrichments: IProvisionEnrichment[];
  listComponent: App<Element>;

  constructor (root: HTMLElement) {
    this.root = root;
    this.gutter = root.querySelector('la-gutter');
    this.akn = root.querySelector('la-akoma-ntoso');
    // TODO
    this.enrichments = [{
      title: 'test',
      target: {
        anchor_id: 'part_I-Rightsandduties__chp_One__art_I__para_1'
      }
    }];

    // @ts-ignore
    this.listComponent = createApp(defineComponent(ProvisionEnrichmentList), {
      gutter: this.gutter,
      viewRoot: this.root,
      enrichments: this.enrichments
    });
    this.listComponent.mount(document.createElement('div'));

    const observer = new MutationObserver(() => {
      // @ts-ignore
      this.listComponent.markAndAnchorAll();
    });
    if (this.akn) {
      observer.observe(this.akn, { childList: true });
    }
  }
}

import { GutterEnrichmentManager, IGutterEnrichmentProvider } from '@lawsafrica/indigo-akn/dist/enrichments';
import ProvisionEnrichmentsList from './ProvisionEnrichmentList.vue';
import { IRangeTarget } from '@lawsafrica/indigo-akn/dist/ranges';
import { createAndMountApp } from '../../utils/vue-utils';
import { vueI18n } from '../../i18n';
import { ComponentPublicInstance } from 'vue';
import i18next from 'i18next';

export class ProvisionEnrichments implements IGutterEnrichmentProvider {
    root: HTMLElement;
    gutter: Element | null;
    manager: GutterEnrichmentManager;
    listComponent: ComponentPublicInstance;
    enrichments: any;

    constructor (root: HTMLElement, manager: GutterEnrichmentManager, displayType: string) {
      this.root = root;
      this.manager = manager;
      this.gutter = root.querySelector('la-gutter');
      const node = document.getElementById('unconstitutional-provisions-json');
      if (node) {
        this.enrichments = JSON.parse(node.innerText || '[]');
      } else {
        this.enrichments = [];
      }

      // @ts-ignore
      this.listComponent = createAndMountApp({
        component: ProvisionEnrichmentsList,
        props: {
          gutter: this.gutter,
          viewRoot: this.root,
          enrichments: this.enrichments
        },
        use: [vueI18n],
        mountTarget: document.createElement('div') as HTMLElement

      });
      this.manager.addProvider(this);
    }

    getButton (target: IRangeTarget): HTMLButtonElement | null {
      return null;
    }

    addEnrichment (target: IRangeTarget): void {
      document.getSelection()?.removeAllRanges();
      // @ts-ignore
      this.listComponent.addAnnotation(target);
    }
}

import { GutterEnrichmentManager, IGutterEnrichmentProvider } from '@lawsafrica/indigo-akn/dist/enrichments';
import AnnotationList from './AnnotationList.vue';
import AddAnnotation from './AddAnnotation.vue';
import { IRangeTarget } from '@lawsafrica/indigo-akn/dist/ranges';
import { createAndMountApp } from '../../utils/vue-utils';
import { vueI18n } from '../../i18n';
import { ComponentPublicInstance, VueElement } from 'vue';
import { IAnnotation } from './annotation';

export class AnnotationsProvider implements IGutterEnrichmentProvider {
    root: HTMLElement;
    gutter: Element | null;
    manager: GutterEnrichmentManager;
    listComponent: ComponentPublicInstance;

    constructor (root: HTMLElement, manager: GutterEnrichmentManager, displayType: string) {
      this.root = root;
      this.manager = manager;
      this.gutter = root.querySelector('la-gutter');
      // @ts-ignore
      this.listComponent = createAndMountApp({
        component: AnnotationList,
        props: {
          gutter: this.gutter,
          viewRoot: this.root
        },
        use: [vueI18n],
        mountTarget: document.createElement('div') as HTMLElement

      });
      this.manager.addProvider(this);
    }

    getButton (target: IRangeTarget): HTMLButtonElement | null {
      const btn = document.createElement('button');
      btn.className = 'btn btn-outline-secondary';
      btn.type = 'button';
      btn.innerText = 'Add annotation...';
      return btn;
    }

    addEnrichment (target: IRangeTarget): void {
      // @ts-ignore
      this.listComponent.addAnnotation(target);
    }
}

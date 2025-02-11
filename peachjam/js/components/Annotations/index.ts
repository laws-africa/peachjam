import { GutterEnrichmentManager, IGutterEnrichmentProvider } from '@lawsafrica/indigo-akn/dist/enrichments';
import AnnotationsList from './AnnotationsList.vue';
import AddAnnotation from './AddAnnotation.vue';
import { IRangeTarget } from '@lawsafrica/indigo-akn/dist/ranges';
import { createAndMountApp } from '../../utils/vue-utils';
import { vueI18n } from '../../i18n';
import { ComponentPublicInstance, VueElement } from 'vue';

export class AnnotationsProvider implements IGutterEnrichmentProvider {
    root: HTMLElement;
    gutter: Element | null;
    akn: Element | null;
    manager: GutterEnrichmentManager;
    displayType: string;
    listComponent: ComponentPublicInstance;
    addAnnotationComponent: ComponentPublicInstance | null;

    constructor (root: HTMLElement, manager: GutterEnrichmentManager, displayType: string) {
      this.root = root;
      this.manager = manager;
      this.displayType = displayType;
      this.gutter = root.querySelector('la-gutter');
      this.akn = root.querySelector('la-akoma-ntoso');
      this.addAnnotationComponent = null;
      // @ts-ignore
      this.listComponent = createAndMountApp({
        component: AnnotationsList,
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
      console.log('adding enrichment');
      if (this.addAnnotationComponent) {
        this.addAnnotationComponent.$el.remove();
      }
      this.addAnnotationComponent = createAndMountApp({
        component: AddAnnotation,
        props: {
          gutter: this.gutter,
          target,
          viewRoot: this.root
        },
        use: [vueI18n],
        mountTarget: document.createElement('div') as HTMLElement
      });
    }
}

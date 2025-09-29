import { GutterEnrichmentManager, IGutterEnrichmentProvider } from '@lawsafrica/indigo-akn/dist/enrichments';
import AnnotationList from './AnnotationList.vue';
import { IRangeTarget } from '@lawsafrica/indigo-akn/dist/ranges';
import { createAndMountApp } from '../../utils/vue-utils';
import { vueI18n } from '../../i18n';
import { ComponentPublicInstance } from 'vue';
import i18next from 'i18next';

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
          viewRoot: this.root,
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
      btn.innerText = i18next.t('Add comment...');
      return btn;
    }

    addEnrichment (target: IRangeTarget): void {
      document.getSelection()?.removeAllRanges();
      // @ts-ignore
      this.listComponent.addAnnotation(target);
    }
}

import { GutterEnrichmentManager, IGutterEnrichmentProvider } from '@lawsafrica/indigo-akn/dist/enrichments';
import AnnotationsList from './AnnotationsList.vue';

export class AnnotationsProvider implements IGutterEnrichmentProvider {
    root: HTMLElement;
    gutter: Element;
    manager: GutterEnrichmentManager;

    constructor (root: HTMLElement, manager: GutterEnrichmentManager) {
      this.root = root;
      this.manager = manager;
      this.gutter = root.querySelector('la-gutter');
      this.manager.addProvider(this);
    }
}

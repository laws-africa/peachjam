import { GutterEnrichmentManager, IGutterEnrichmentProvider } from '@lawsafrica/indigo-akn/dist/enrichments';
import debounce from 'lodash/debounce';
import { IRangeTarget } from '@lawsafrica/indigo-akn/dist/ranges';
import type { ComponentPublicInstance } from 'vue';
import { createAndMountApp } from '../../utils/vue-utils';
import { vueI18n } from '../../i18n';
import PortionDetailsGutterItem from './PortionDetailsGutterItem.vue';

type PortionDetailsGutterItemInstance = ComponentPublicInstance & {
  $el: HTMLElement;
  setActiveElement: (element: HTMLElement | null) => void;
  deactivate: () => void;
};

export class PortionDetails implements IGutterEnrichmentProvider {
  root: HTMLElement;
  gutter: Element | null;
  manager: GutterEnrichmentManager;
  akn: Element | null;
  expressionFrbrUri: string;
  activeElement: HTMLElement | null = null;
  gutterItem: PortionDetailsGutterItemInstance | null = null;

  constructor (root: HTMLElement, manager: GutterEnrichmentManager, displayType: string, expressionFrbrUri: string) {
    this.root = root;
    this.akn = this.root.querySelector('.content');
    this.manager = manager;
    this.gutter = root.querySelector('la-gutter');
    this.expressionFrbrUri = expressionFrbrUri;

    this.setup();
  }

  setup (): void {
    if (this.akn && this.gutter) {
      this.akn.addEventListener('mouseover', debounce(this.onMouseOver.bind(this), 500));
      this.akn.addEventListener('mouseout', debounce(this.onMouseOut.bind(this), 500));
      this.gutterItem = this.createGutterItem();
      this.gutter.appendChild(this.gutterItem.$el);
    }
  }

  createGutterItem (): PortionDetailsGutterItemInstance {
    return createAndMountApp({
      component: PortionDetailsGutterItem,
      props: {
        baseUrl: window.location.pathname.replace(/\/$/, ''),
        expressionFrbrUri: this.expressionFrbrUri
      },
      use: [vueI18n],
      mountTarget: document.createElement('div')
    }) as PortionDetailsGutterItemInstance;
  }

  onMouseOver (event: Event) {
    const target = event.target;

    if (target && target instanceof HTMLElement) {
      const el = target.closest('.akn-part, .akn-chapter, .akn-section, .akn-subsection, .akn-paragraph');
      if (el && el instanceof HTMLElement && el.dataset.eid) {
        this.activate(el);
      }
    }
  }

  onMouseOut (event: Event) {
    if (event.target && event.target === this.activeElement) {
      this.deactivate();
    }
  }

  activate (element: HTMLElement) {
    if (this.activeElement !== element) {
      this.deactivate();
    }
    this.activeElement = element;
    this.activeElement.classList.add('active-portion');
    if (this.gutterItem) {
      this.gutterItem.setActiveElement(this.activeElement);
    }
  }

  deactivate () {
    // Handle mouse out event if needed
    if (this.activeElement) {
      this.activeElement.classList.remove('active-portion');
      this.activeElement = null;
      if (this.gutterItem) {
        this.gutterItem.deactivate();
      }
    }
  }

  addEnrichment (target: IRangeTarget) {
  }

  getButton (target: IRangeTarget): HTMLButtonElement | null {
    return null;
  }
}

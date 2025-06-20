import { GutterEnrichmentManager, IGutterEnrichmentProvider } from '@lawsafrica/indigo-akn/dist/enrichments';
import debounce from 'lodash/debounce';
import { IRangeTarget } from '@lawsafrica/indigo-akn/dist/ranges';

export class PortionDetails implements IGutterEnrichmentProvider {
  root: HTMLElement;
  gutter: Element | null;
  manager: GutterEnrichmentManager;
  akn: Element | null;
  activeElement: HTMLElement | null = null;
  // eslint-disable-next-line no-undef
  gutterItem: HTMLLaGutterItemElement | null = null;

  constructor (root: HTMLElement, manager: GutterEnrichmentManager, displayType: string) {
    this.root = root;
    this.akn = this.root.querySelector('.content');
    this.manager = manager;
    this.gutter = root.querySelector('la-gutter');

    this.setup();
  }

  setup (): void {
    if (this.akn && this.gutter) {
      this.akn.addEventListener('mouseover', debounce(this.onMouseOver.bind(this), 500));
      this.akn.addEventListener('mouseout', debounce(this.onMouseOut.bind(this), 500));
      this.gutterItem = document.createElement('la-gutter-item');
      this.gutterItem.innerHTML = '<div class="gutter-enrichment-active-portion"><a href="#">What cites this?</a><br><a href="#">Similar portions...</a><br><a href="#">Comment...</a></div>';
      this.gutter.appendChild(this.gutterItem);
    }
  }

  onMouseOver (event: Event) {
    const target = event.target;

    if (target && target instanceof HTMLElement) {
      if (target.tagName === 'P' || target.classList.contains('akn-p')) {
        this.activate(target);
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
      this.gutterItem.anchor = this.activeElement;
    }
  }

  deactivate () {
    // Handle mouse out event if needed
    if (this.activeElement) {
      this.activeElement.classList.remove('active-portion');
      this.activeElement = null;
      if (this.gutterItem) {
        this.gutterItem.anchor = undefined;
        this.gutterItem.active = false;
      }
    }
  }

  addEnrichment (target: IRangeTarget) {
  }

  getButton (target: IRangeTarget): HTMLButtonElement | null {
    return null;
  }
}

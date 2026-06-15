import { IGutterEnrichmentProvider } from '@lawsafrica/indigo-akn/dist/enrichments';
import debounce from 'lodash/debounce';
import { IRangeTarget } from '@lawsafrica/indigo-akn/dist/ranges';
import { LaGutterItem } from '@lawsafrica/law-widgets/components/la-gutter-item';

type LaGutterItemElement = InstanceType<typeof LaGutterItem>;

interface ActiveProvisionManagerOptions {
  shouldShow?: () => boolean;
}

/**
 * Shows provider actions for the currently active provision.
 *
 * Unlike GutterEnrichmentManager and SelectionToolbar, this manager is driven by
 * the active portion under the pointer rather than by a text selection.
 */
export class ActiveProvisionManager {
  root: HTMLElement;
  gutter: Element | null;
  akn: Element | null;
  activeElement: HTMLElement | null = null;
  gutterItem: LaGutterItemElement;
  buttonGroup: HTMLDivElement;
  providers: IGutterEnrichmentProvider[] = [];
  shouldShow: () => boolean;
  // Note: .subparagraph is excluded because it's too deply nested
  // Note: .blockContainer is included because that wraps defined terms
  provisionSelectors = '.akn-alinea, .akn-article, .akn-chapter, .akn-clause, .akn-division, .akn-indent, .akn-level, .akn-list, .akn-paragraph, ' +
    '.akn-part, .akn-point, .akn-proviso, .akn-rule, .akn-section, .akn-subchapter, .akn-subclause, .akn-subdivision, .akn-sublist, .akn-subpart, .akn-subrule, ' +
    '.akn-subsection, .akn-subtitle, .akn-title, .akn-tome, .akn-transitional, .akn-blockContainer';

  constructor (root: HTMLElement, options: ActiveProvisionManagerOptions = {}) {
    this.root = root;
    this.shouldShow = options.shouldShow || (() => true);
    this.akn = this.root.querySelector('.content');
    this.gutter = root.querySelector('la-gutter');
    this.gutterItem = this.createGutterItem();
    this.buttonGroup = this.createButtonGroup();
    this.gutterItem.appendChild(this.buttonGroup);

    this.setup();
  }

  addProvider (provider: IGutterEnrichmentProvider) {
    this.providers.push(provider);
    this.renderButtons();
  }

  setup (): void {
    if (this.akn && this.gutter) {
      this.akn.addEventListener('mouseover', debounce(this.onMouseOver.bind(this), 500));
      this.gutter.appendChild(this.gutterItem);
    }
  }

  createGutterItem (): LaGutterItemElement {
    return document.createElement('la-gutter-item') as LaGutterItemElement;
  }

  createButtonGroup (): HTMLDivElement {
    const buttonGroup = document.createElement('div');
    buttonGroup.className = 'gutter-enrichment-active-portion btn-group-vertical bg-white';
    return buttonGroup;
  }

  onMouseOver (event: Event) {
    if (!this.shouldShow()) {
      this.deactivate();
      return;
    }

    const target = event.target;

    if (target && target instanceof HTMLElement) {
      const el = target.closest(this.provisionSelectors);
      if (el && el instanceof HTMLElement && el.dataset.eid) {
        this.activate(el);
      }
    }
  }

  activate (element: HTMLElement) {
    if (this.activeElement !== element) {
      this.deactivate();
    }
    this.activeElement = element;
    this.activeElement.classList.add('active-portion');
    this.gutterItem.anchor = this.activeElement;
    this.renderButtons();
  }

  deactivate () {
    if (this.activeElement) {
      this.activeElement.classList.remove('active-portion');
      this.activeElement = null;
    }
    this.gutterItem.anchor = undefined;
    this.gutterItem.active = false;
    this.buttonGroup.innerHTML = '';
  }

  renderButtons () {
    this.buttonGroup.innerHTML = '';
    const target = this.getActiveTarget();
    if (!target) return;

    for (const provider of this.providers) {
      const button = provider.getButton(target);
      if (button) {
        button.addEventListener('click', () => {
          provider.addEnrichment(target);
        });
        this.buttonGroup.appendChild(button);
      }
    }
  }

  getActiveTarget (): IRangeTarget | null {
    const provisionEid = this.activeElement?.dataset.eid;
    if (!provisionEid) return null;
    return {
      anchor_id: provisionEid
    };
  }
}

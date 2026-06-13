import { IGutterEnrichmentProvider } from '@lawsafrica/indigo-akn/dist/enrichments';
import debounce from 'lodash/debounce';
import { IRangeTarget } from '@lawsafrica/indigo-akn/dist/ranges';
import { LaGutterItem } from '@lawsafrica/law-widgets/components/la-gutter-item';

type LaGutterItemElement = InstanceType<typeof LaGutterItem>;

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
  provisionSelectors = '.akn-part, .akn-chapter, .akn-section, .akn-subsection, .akn-paragraph';

  constructor (root: HTMLElement) {
    this.root = root;
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

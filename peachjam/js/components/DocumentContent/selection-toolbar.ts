import { IGutterEnrichmentProvider } from '@lawsafrica/indigo-akn/src/enrichments/gutter';
import { IRangeTarget } from '@lawsafrica/indigo-akn/src/ranges';
import { rangeToTarget } from '@lawsafrica/indigo-akn/dist/ranges';
import tippy, { Instance as Tippy } from 'tippy.js';
import debounce from 'lodash/debounce';

/**
 * This class handles showing a popup toolbar when the user selects text in the document body. Providers can
 * register themselves with addProvider, using the same interface as the gutter element provider.
 */
export class SelectionToolbarManager {
  protected root: Element;
  protected providers: IGutterEnrichmentProvider[];
  protected btnGroup: HTMLDivElement;
  protected popup: Tippy;
  protected target: IRangeTarget | null = null;
  protected range: Range | null = null;

  constructor (root: Element) {
    this.root = root;
    this.providers = [];
    this.btnGroup = document.createElement('div');
    this.btnGroup.className = 'btn-group btn-group-sm bg-light';
    this.popup = this.createPopup();
    document.addEventListener('selectionchange', debounce(this.selectionChanged.bind(this), 100));
  }

  createPopup () {
    return tippy(this.root, {
      appendTo: document.body,
      interactive: true,
      theme: 'dark',
      zIndex: 0,
      // on mobile devices, the selection toolbar overlaps this otherwise
      placement: 'bottom',
      trigger: 'manual',
      delay: [0, 0],
      getReferenceClientRect: () => this.getBoundingClientRect(),
      onShow: (instance) => {
        if (this.target) {
          // some providers re-use the same element as the content between popups, so we must clear the content
          // first otherwise the popup doesn't re-render itself
          instance.setContent('');
          instance.setContent(this.getPopupContent(this.target));
        } else {
          this.hidePopup();
        }
      }
    });
  }

  addProvider (provider: IGutterEnrichmentProvider) {
    this.providers.push(provider);
  }

  selectionChanged () {
    const sel = document.getSelection();

    if (sel && sel.rangeCount > 0 && !sel.getRangeAt(0).collapsed) {
      const range = sel.getRangeAt(0);

      // is the common ancestor inside the content container?
      if (range.commonAncestorContainer.compareDocumentPosition(this.root) & Node.DOCUMENT_POSITION_CONTAINS) {
        // stash the range as converted to a target; this may be null!
        const target = rangeToTarget(range, this.root);
        if (target) {
          this.range = range;
          this.target = target;
          this.popup.show();
          return;
        }
      }
    }

    // cleanup if anything fails
    this.hidePopup();
  }

  getBoundingClientRect () {
    // @ts-ignore
    return this.range.getBoundingClientRect();
  }

  getPopupContent (target: IRangeTarget) {
    this.btnGroup.innerHTML = '';

    for (const provider of this.providers) {
      const btn = provider.getButton(target);
      if (btn) {
        btn.addEventListener('click', () => {
          this.hidePopup();
          provider.addEnrichment(target);
        });
        this.btnGroup.appendChild(btn);
      }
    }

    return this.btnGroup;
  }

  hidePopup () {
    this.popup.hide();
  }
}

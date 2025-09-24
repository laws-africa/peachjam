import { IGutterEnrichmentProvider } from '@lawsafrica/indigo-akn/src/enrichments/gutter';
import { IRangeTarget } from '@lawsafrica/indigo-akn/src/ranges';
import { rangeToTarget } from '@lawsafrica/indigo-akn/dist/ranges';
import tippy, { Instance as Tippy } from 'tippy.js';
import debounce from 'lodash/debounce';

export class SelectionToolbarManager {
  protected root: Element;
  protected providers: IGutterEnrichmentProvider[];
  protected btnGroup: HTMLDivElement;
  public popup: Tippy | null = null;

  constructor (root: Element) {
    this.root = root;
    this.providers = [];
    this.btnGroup = document.createElement('div');
    this.btnGroup.className = 'btn-group btn-group-sm bg-light';
    document.addEventListener('selectionchange', debounce(this.selectionChanged.bind(this), 100));
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
          // get the closest element
          let node: Node | null = range.startContainer;
          while (node && node.nodeType !== Node.ELEMENT_NODE) node = node.parentElement;
          if (node) {
            // show the popup
            this.createPopup(node as HTMLElement, target, range);
            return;
          }
        }
      }
    }

    // cleanup if anything fails
    this.removePopup();
  }

  createPopup (node: Element, target: IRangeTarget, range: Range) {
    this.popup = tippy(node, {
      appendTo: document.body,
      interactive: true,
      theme: 'dark',
      zIndex: 0,
      // on mobile devices, the selection toolbar overlaps this otherwise
      placement: 'bottom',
      trigger: 'manual',
      delay: [0, 0],
      showOnCreate: true,
      getReferenceClientRect: () => range.getBoundingClientRect(),
      onShow: (instance) => {
        // some providers re-use the same element as the content between popups, so we must clear the content
        // first otherwise the popup doesn't re-render itself
        instance.setContent('');
        instance.setContent(this.getPopupContent(target));
      }
    });
  }

  getPopupContent (target: IRangeTarget) {
    this.btnGroup.innerHTML = '';

    for (const provider of this.providers) {
      const btn = provider.getButton(target);
      if (btn) {
        btn.addEventListener('click', () => {
          this.removePopup();
          provider.addEnrichment(target);
        });
        this.btnGroup.appendChild(btn);
      }
    }

    return this.btnGroup;
  }

  removePopup () {
    if (this.popup) {
      this.popup.destroy();
      this.popup = null;
    }
  }
}

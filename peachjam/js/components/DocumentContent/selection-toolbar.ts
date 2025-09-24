import { IGutterEnrichmentProvider } from '@lawsafrica/indigo-akn/src/enrichments/gutter';
import { IRangeTarget } from '@lawsafrica/indigo-akn/src/ranges';
import { markRange, targetToRange } from '@lawsafrica/indigo-akn/dist/ranges';
import { rangeToTarget } from '@lawsafrica/indigo-akn/dist/ranges';
import tippy, { Instance as Tippy } from 'tippy.js';

export class SelectionToolbarManager {
  protected root: Element;
  protected providers: IGutterEnrichmentProvider[];
  protected btnGroup: HTMLDivElement;
  protected marks: HTMLElement[];
  public popup: Tippy | null = null;
  private listener: any;

  constructor (root: Element) {
    this.root = root;
    this.providers = [];
    this.marks = [];
    this.btnGroup = document.createElement('div');
    this.btnGroup.className = 'btn-group btn-group-sm bg-light';
    this.listener = this.selectionChanged.bind(this);
    document.addEventListener('selectionchange', this.listener);
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
          // mark the range then get the first mark as the popup anchor
          // TODO: can we just set the bounding client rect of the range as the popup anchor?
          markRange(range, 'span', mark => {
            this.marks.push(mark);
            return mark;
          });

          if (this.marks.length) {
            // select the range again (marking it may have disturbed the selection)
            const newRange = targetToRange(target, this.root);
            if (newRange) {
              // disable the selectionchange listener while we modify the selection to avoid recursion
              document.removeEventListener('selectionchange', this.listener);
              try {
                sel.removeAllRanges();
                sel.addRange(newRange);
              } finally {
                setTimeout(() => {
                  document.addEventListener('selectionchange', this.listener);
                }, 0);
              }

              // show the popup
              this.createPopup(this.marks[0], target);
              return;
            }
          }
        }
      }
    }

    // cleanup if anything fails
    this.removePopup();
  }

  createPopup (node: Element, target: IRangeTarget) {
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
    this.unmark();
    if (this.popup) {
      this.popup.destroy();
      this.popup = null;
    }
  }

  unmark () {
    for (const mark of this.marks) {
      if (mark.parentElement) {
        while (mark.firstChild) {
          mark.parentElement.insertBefore(mark.firstChild, mark);
        }
        mark.parentElement.removeChild(mark);
      }
    }
    this.marks = [];
  }
}

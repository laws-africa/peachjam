import { IRangeSelector, IRangeTarget, markRange, targetToRange } from '@lawsafrica/indigo-akn/dist/ranges';
import { GutterEnrichmentManager, IGutterEnrichmentProvider } from '@lawsafrica/indigo-akn/dist/enrichments';

export interface ICitationLink {
  text: string;
  url: string;
  // eslint-disable-next-line camelcase
  target_id: string;
  // eslint-disable-next-line camelcase
  target_selectors: IRangeSelector[];
}

/**
 * Inserts citation links into rendered PDF documents, and allows admins to manage them.
 */
export default class PDFCitationLinks implements IGutterEnrichmentProvider {
  protected root: HTMLElement;
  protected links: ICitationLink[];
  protected manager: GutterEnrichmentManager;

  constructor (root: HTMLElement, manager: GutterEnrichmentManager) {
    this.root = root;
    this.manager = manager;
    const el = document.getElementById('citation-links');
    this.links = JSON.parse((el ? el.textContent : '') || '[]');

    this.insertLinks();

    // TODO: if !readonly
    this.manager.addProvider(this);
  }

  insertLinks () {
    for (const link of this.links) {
      this.insertLink(link);
    }
  }

  insertLink (link: ICitationLink) {
    const target = {
      anchor_id: link.target_id,
      selectors: link.target_selectors
    };
    const range = targetToRange(target, this.root);
    if (!range) return;
    markRange(range, 'a', a => {
      a.setAttribute('href', link.url);
      return a;
    });
  }

  getButton (target: IRangeTarget): HTMLButtonElement | null {
    const btn = document.createElement('button');
    btn.className = 'btn btn-outline-secondary';
    btn.type = 'button';
    btn.innerText = 'Link citation...';
    return btn;
  }

  addEnrichment(target: IRangeTarget): void {
    throw new Error('Method not implemented.');
  }
}

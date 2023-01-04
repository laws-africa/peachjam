import { IRangeSelector, markRange, targetToRange } from '@lawsafrica/indigo-akn/dist/ranges';

export interface ICitationLink {
  text: string;
  url: string;
  // eslint-disable-next-line camelcase
  target_id: string;
  // eslint-disable-next-line camelcase
  target_selectors: IRangeSelector[];
}

/**
 * Inserts citation links into rendered PDF documents.
 */
export default class PDFCitationLinks {
  protected root: HTMLElement;
  protected links: ICitationLink[];

  constructor (root: HTMLElement) {
    this.root = root;
    const el = document.getElementById('citation-links');
    this.links = JSON.parse((el ? el.textContent : '') || '[]');

    this.insertLinks();
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
}

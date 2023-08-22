import { RelationshipEnrichments } from '../RelationshipEnrichment';
import DocDiffsManager from '../DocDiffs';
import PDFCitationLinks from './citation-links';
import { GutterEnrichmentManager } from '@lawsafrica/indigo-akn/dist/enrichments';
import SelectionSearch from './selection-search';
import SelectionShare from './selection-share';

/**
 * Class for handling the setup of all enrichments and interactions between enrichments
 */
class EnrichmentsManager {
  private relationshipsManager: RelationshipEnrichments;
  private selectionSearch: SelectionSearch;
  private selectionShare: SelectionShare;
  private root: HTMLElement;
  private docDiffsManager: null | DocDiffsManager;
  // eslint-disable-next-line no-undef
  private readonly gutter: HTMLLaGutterElement | null;
  private readonly akn: HTMLElement | null;
  private citationLinks: PDFCitationLinks | null = null;
  gutterManager: GutterEnrichmentManager;

  constructor (contentAndEnrichmentsElement: HTMLElement) {
    this.root = contentAndEnrichmentsElement;
    this.gutter = this.root.querySelector('la-gutter');
    // this is either div.content (for HTML and PDF) or la-akoma-ntoso.content (for AKN)
    this.akn = this.root.querySelector('.content');

    this.docDiffsManager = this.setDocDiffs();
    this.gutterManager = new GutterEnrichmentManager(this.root);
    // @ts-ignore
    // GutterEnrichmentManager by default looks for la-akoma-ntoso, and we might not be working with that
    this.gutterManager.akn = this.root.querySelector('.content');
    this.relationshipsManager = new RelationshipEnrichments(contentAndEnrichmentsElement, this.gutterManager);
    this.selectionSearch = new SelectionSearch(this.gutterManager);
    this.selectionShare = new SelectionShare(this.gutterManager);

    this.gutter?.addEventListener('laItemChanged', (e: any) => {
      if (e.target.classList.contains('relationship-gutter-item') && e.target.active) {
        this.docDiffsManager?.closeInlineDiff();
      }
    });
  }

  setDocDiffs () {
    if (!this.akn || !this.gutter) return null;
    const frbrExpressionUri = this.akn.getAttribute('frbr-expression-uri');
    if (!frbrExpressionUri) return null;
    return new DocDiffsManager(frbrExpressionUri, this.gutter);
  }

  setupPdfCitationLinks () {
    this.citationLinks = new PDFCitationLinks(this.root, this.gutterManager);
  }
}

export default EnrichmentsManager;

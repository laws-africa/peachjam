import { RelationshipEnrichments } from '../RelationshipEnrichment';
import DocDiffsManager from '../DocDiffs';

// Class for handling the setup of all enrichments and interactions between enrichments

class EnrichmentsManager {
  private relationshipsManager: RelationshipEnrichments;
  private root: HTMLElement;
  private docDiffsManager: null | DocDiffsManager;
  // eslint-disable-next-line no-undef
  private readonly gutter: HTMLLaGutterElement | null;
  private readonly akn: HTMLElement | null;
  constructor (contentAndEnrichmentsElement: HTMLElement) {
    this.root = contentAndEnrichmentsElement;
    this.gutter = this.root.querySelector('la-gutter');
    this.akn = this.root.querySelector('la-akoma-ntoso');

    this.docDiffsManager = this.setDocDiffs();
    this.relationshipsManager = new RelationshipEnrichments(contentAndEnrichmentsElement);

    this.gutter?.addEventListener('laItemChanged', (e: any) => {
      if (e.target.classList.contains('relationship-gutter-item') && e.target.active) {
        this.docDiffsManager?.closeInlineDiff();
      }
    });
  }

  layoutItems () {
    if (!this.gutter) return;
    this.gutter.layoutItems();
  }

  setDocDiffs () {
    if (!this.akn || !this.gutter) return null;
    const frbrExpressionUri = this.akn.getAttribute('expression-frbr-uri');
    if (!frbrExpressionUri) return null;
    return new DocDiffsManager(frbrExpressionUri, this.gutter);
  }
}

export default EnrichmentsManager;

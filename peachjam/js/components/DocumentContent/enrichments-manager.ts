import { RelationshipEnrichments } from '../RelationshipEnrichment';
import DocDiffsManager from '../DocDiffs';
import PDFCitationLinks from './citation-links';
import { GutterEnrichmentManager } from '@lawsafrica/indigo-akn/dist/enrichments';
import SelectionSearch from './selection-search';
import SelectionShare from './selection-share';
import { AnnotationsProvider } from '../Annotations';
import { ProvisionEnrichments } from '../ProvisionEnrichments';
import { ProvisionCitations } from '../ProvisionCitations';
import { SelectionToolbarManager } from './selection-toolbar';

/**
 * Class for handling the setup of all enrichments and interactions between enrichments
 */
class EnrichmentsManager {
  private relationshipsManager: RelationshipEnrichments | null = null;
  private annotationsManager: AnnotationsProvider | null = null;
  private provisionEnrichmentsManager: ProvisionEnrichments | null = null;
  private selectionSearch: SelectionSearch;
  private selectionShare: SelectionShare;
  private root: HTMLElement;
  private docDiffsManager: null | DocDiffsManager;
  // eslint-disable-next-line no-undef
  private readonly gutter: HTMLLaGutterElement | null;
  private readonly akn: HTMLElement | null;
  private citationLinks: PDFCitationLinks | null = null;
  private gutterManager: GutterEnrichmentManager;
  private displayType: string; // html, pdf or akn
  private provisionCitations: ProvisionCitations | null = null;
  private selectionToolbarManager: SelectionToolbarManager | null = null;

  constructor (contentAndEnrichmentsElement: HTMLElement) {
    this.root = contentAndEnrichmentsElement;
    this.gutter = this.root.querySelector('la-gutter');
    // this is either div.content (for HTML and PDF) or la-akoma-ntoso.content (for AKN)
    this.akn = this.root.querySelector('.content');
    this.displayType = this.root.getAttribute('data-display-type') || 'html';

    this.docDiffsManager = this.setupDocDiffs();
    this.gutterManager = new GutterEnrichmentManager(this.root);
    // @ts-ignore
    // GutterEnrichmentManager by default looks for la-akoma-ntoso, and we might not be working with that
    this.gutterManager.akn = this.root.querySelector('.content');
    // @ts-ignore
    this.gutterManager.floatingContainer.querySelector('.gutter-enrichment-new-buttons')?.classList.remove('btn-group-sm');

    // the order here matters for the order of buttons in the gutter
    if (this.displayType !== 'pdf') {
      this.annotationsManager = new AnnotationsProvider(this.root, this.gutterManager, this.displayType);
      this.provisionEnrichmentsManager = new ProvisionEnrichments(this.root, this.gutterManager, this.displayType);
      this.provisionCitations = new ProvisionCitations(this.root);
    }

    this.selectionSearch = new SelectionSearch(this.gutterManager);
    this.selectionShare = new SelectionShare(this.gutterManager);

    if (this.displayType !== 'pdf') {
      this.relationshipsManager = new RelationshipEnrichments(this.root, this.gutterManager, this.displayType);
      this.setupSelectionToolbar();
    }

    this.gutter?.addEventListener('laItemChanged', (e: any) => {
      if (e.target.classList.contains('relationship-gutter-item') && e.target.active) {
        this.docDiffsManager?.closeInlineDiff();
      }
    });
  }

  setupDocDiffs () {
    if (!this.akn || !this.gutter) return null;
    const frbrExpressionUri = this.akn.getAttribute('frbr-expression-uri');
    if (!frbrExpressionUri) return null;
    return new DocDiffsManager(
      frbrExpressionUri, this.gutter, this.root.getAttribute('data-diffs-url') || ''
    );
  }

  addPdfEnrichments () {
    // setup PDF enrichments after the PDF has been rendered
    this.annotationsManager = new AnnotationsProvider(this.root, this.gutterManager, this.displayType);
    this.citationLinks = new PDFCitationLinks(this.root, this.gutterManager);
    this.relationshipsManager = new RelationshipEnrichments(this.root, this.gutterManager, this.displayType);
    this.setupSelectionToolbar();
  }

  setupSelectionToolbar () {
    // @ts-ignore
    this.selectionToolbarManager = new SelectionToolbarManager(this.gutterManager.akn);
    if (this.annotationsManager) {
      this.selectionToolbarManager.addProvider(this.annotationsManager);
    }
    this.selectionToolbarManager.addProvider(this.selectionShare);
    this.selectionToolbarManager.addProvider(this.selectionSearch);
  }
}

export default EnrichmentsManager;

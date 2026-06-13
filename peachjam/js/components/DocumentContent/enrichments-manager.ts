import { RelationshipEnrichments } from '../RelationshipEnrichment';
import DocDiffsManager from '../DocDiffs';
import PDFCitationLinks from './citation-links';
import { GutterEnrichmentManager, SelectionToolbar } from '@lawsafrica/indigo-akn/dist/enrichments';
import { SelectionSearch, SelectionShare, CompareProvisionProvider, SimilarProvisionsProvider } from './providers';
import { AnnotationsProvider } from '../Annotations';
import { ProvisionEnrichments } from '../ProvisionEnrichments';
import { ProvisionCitations } from '../ProvisionCitations';
import { ActiveProvisionManager } from './active-provision';

/**
 * Class for handling the setup of all enrichments and interactions between enrichments
 *
 * This class sets up various managers to handle the different enrichments. Some managers provide a mechanism
 * for providers to register themselves, and the provider is called when the selection or something else
 * changes and the provider update itself.
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
  // Allows providers to add buttons to a gutter toolbar when the selection in the document content changes
  private gutterManager: GutterEnrichmentManager;
  // Allows providers to add buttons to a popup toolbar when the selection in the document content changes.
  // This is only shown on mobile when the gutter is not easily accessible.
  private selectionToolbarManager: SelectionToolbar | null = null;
  private displayType: string; // html, pdf or akn
  private expressionFrbrUri: string;
  private provisionCitations: ProvisionCitations | null = null;
  private compareProvisionProvider: CompareProvisionProvider;
  private similarProvisionsProvider: SimilarProvisionsProvider;
  private activeProvisionManager: ActiveProvisionManager | null = null;

  constructor (contentAndEnrichmentsElement: HTMLElement) {
    this.root = contentAndEnrichmentsElement;
    this.gutter = this.root.querySelector('la-gutter');
    // this is either div.content (for HTML and PDF) or la-akoma-ntoso.content (for AKN)
    this.akn = this.root.querySelector('.content');
    this.displayType = this.root.getAttribute('data-display-type') || 'html';
    this.expressionFrbrUri = this.akn?.getAttribute('frbr-expression-uri') || '';

    this.docDiffsManager = this.setupDocDiffs();
    this.gutterManager = new GutterEnrichmentManager(this.root);
    // @ts-ignore
    // GutterEnrichmentManager by default looks for la-akoma-ntoso, and we might not be working with that
    this.gutterManager.akn = this.akn;

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

    this.compareProvisionProvider = new CompareProvisionProvider(this.expressionFrbrUri);
    this.similarProvisionsProvider = new SimilarProvisionsProvider(this.expressionFrbrUri);
    if (this.displayType === 'akn') {
      this.gutterManager.addProvider(this.compareProvisionProvider);
      this.gutterManager.addProvider(this.similarProvisionsProvider);
      const activeProvisionMedia = window.matchMedia('(min-width: 992px)');
      this.activeProvisionManager = new ActiveProvisionManager(this.root, {
        shouldShow: () => activeProvisionMedia.matches
      });
      if (this.annotationsManager) {
        this.activeProvisionManager.addProvider(this.annotationsManager);
      }
      this.activeProvisionManager.addProvider(this.compareProvisionProvider);
      this.activeProvisionManager.addProvider(this.similarProvisionsProvider);
    }

    this.gutter?.addEventListener('laItemChanged', (e: any) => {
      if (e.target.classList.contains('relationship-gutter-item') && e.target.active) {
        this.docDiffsManager?.closeInlineDiff();
      }
    });
  }

  setupDocDiffs () {
    if (!this.akn || !this.gutter) return null;
    const documentId = this.root.dataset.documentId;
    if (!this.expressionFrbrUri || !documentId) return null;
    return new DocDiffsManager(
      this.expressionFrbrUri, documentId, this.gutter, this.root.getAttribute('data-diffs-url') || ''
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
    if (this.akn) {
      // @ts-ignore
      this.selectionToolbarManager = new SelectionToolbar(this.akn, {
        shouldShow: () => window.matchMedia('(max-width: 991px)').matches
      });
      if (this.annotationsManager) {
        this.selectionToolbarManager.addProvider(this.annotationsManager);
      }
      this.selectionToolbarManager.addProvider(this.selectionShare);
      this.selectionToolbarManager.addProvider(this.selectionSearch);
      if (this.displayType === 'akn') {
        this.selectionToolbarManager.addProvider(this.compareProvisionProvider);
        this.selectionToolbarManager.addProvider(this.similarProvisionsProvider);
      }
    }
  }
}

export default EnrichmentsManager;

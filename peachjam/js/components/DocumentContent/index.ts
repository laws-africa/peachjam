import DocumentSearch from '../DocumentSearch/index.vue';
import PdfRenderer from '../pdf-renderer';
import debounce from 'lodash/debounce';
import { createAndMountApp } from '../../utils/vue-utils';
import { vueI18n } from '../../i18n';
import { createTocController, generateHtmlTocItems } from '../../utils/function';
import EnrichmentsManager from './enrichments-manager';
import i18next from 'i18next';

class OffCanvas {
  protected offCanvas: any;
  body: HTMLElement | null;
  constructor (element: HTMLElement) {
    this.offCanvas = new (window as { [key: string]: any }).bootstrap.Offcanvas(element);
    this.body = element.querySelector('[data-offcanvas-body]');
  }

  show () {
    this.offCanvas.show();
  }

  hide () {
    this.offCanvas.hide();
  }
}

class DocumentContent {
  protected root: HTMLElement;
  private pdfRenderer: PdfRenderer | undefined;
  private searchApp: any;
  private navOffCanvas: OffCanvas | undefined;
  private enchrichmentsManager: EnrichmentsManager | null;
  private storedDocument: Node | undefined;
  private tocController: HTMLElement| null;
  constructor (root: HTMLElement) {
    this.root = root;
    this.navOffCanvas = undefined;
    this.enchrichmentsManager = null;
    this.storedDocument = this.root.querySelector('[data-document-element]')?.cloneNode(true);
    this.tocController = this.setupTocForTab();

    if (root.dataset.frbrUriSubtype === 'book' && root.getAttribute('data-display-type') === 'akn') {
      this.setupBookTocActivity();
    }

    const tocTabTriggerEl = this.root.querySelector('#toc-tab');
    const searchTabTriggerEl = this.root.querySelector('#navigation-search-tab');
    const pdfPreviewsTabTriggerEl = this.root.querySelector('#pdf-previews-tab');

    // If toc setup and mounted successfully, activate toc tab otherwise activate search tab
    if (this.tocController && tocTabTriggerEl) {
      tocTabTriggerEl.classList.remove('d-none');
      const tocTab = new (window as { [key: string]: any }).bootstrap.Tab(tocTabTriggerEl);
      tocTab.show();
    } else if (root.getAttribute('data-display-type') === 'pdf' && pdfPreviewsTabTriggerEl) {
      const pdfPreviewsTab = new (window as { [key: string]: any }).bootstrap.Tab(pdfPreviewsTabTriggerEl);
      pdfPreviewsTab.show();
    } else if (searchTabTriggerEl) {
      const searchTab = new (window as { [key: string]: any }).bootstrap.Tab(searchTabTriggerEl);
      searchTab.show();
    }

    const navColumn: HTMLElement | null = this.root.querySelector('#navigation-column');
    const navContent: HTMLElement | null = this.root.querySelector('#navigation-content .navigation__inner');
    const navOffCanvasElement: HTMLElement | null = this.root.querySelector('#navigation-offcanvas');

    if (navColumn && navOffCanvasElement && navContent) {
      this.navOffCanvas = new OffCanvas(navOffCanvasElement);
      if (this.navOffCanvas.body) {
        this.setupResponsiveContentTransporter(navColumn, this.navOffCanvas.body, navContent);
      }
    }

    // if pdf setup pdf renderer instance
    if (root.getAttribute('data-display-type') === 'pdf') {
      // get dataset attributes
      const pdfAttrsElement: HTMLElement | null = this.root.querySelector('[data-pdf]');
      if (pdfAttrsElement) {
        Object.keys(pdfAttrsElement.dataset).forEach(key => { root.dataset[key] = pdfAttrsElement.dataset[key]; });
      }
      this.pdfRenderer = new PdfRenderer(root);
      this.pdfRenderer.onPreviewPanelClick = () => { this.navOffCanvas?.hide(); };
      this.pdfRenderer.onPdfLoaded = () => {
        const urlParams = new URLSearchParams(window.location.search);
        const search = urlParams.get('q');
        const searchForm: HTMLFormElement | null = this.root.querySelector('.doc-search__form');
        if (search) {
          searchForm?.dispatchEvent(new Event('submit'));
        }

        const targetPage = urlParams.get('page');
        if (!targetPage) return;
        this.pdfRenderer?.triggerScrollToPage(targetPage);
      };
    }

    // Close navOffCanvas on lac-toc title click
    if (root.getAttribute('data-display-type') === 'akn') {
      const element = root.querySelector('la-table-of-contents-controller');
      if (element) {
        element.addEventListener('itemTitleClicked', () => {
          this.navOffCanvas?.hide();
        });
      }
    }

    const targetMountElement = this.root.querySelector('[data-doc-search]');
    const documentElement = this.root.querySelector('[data-document-element]');
    if (targetMountElement && documentElement) {
      this.searchApp = createAndMountApp({
        component: DocumentSearch,
        props: {
          document: documentElement,
          docType: root.getAttribute('data-display-type'),
          mountElement: targetMountElement
        },
        use: [vueI18n],
        mountTarget: targetMountElement as HTMLElement
      });
      targetMountElement.addEventListener('going-to-snippet', () => {
        this.navOffCanvas?.hide();
      });
    }

    this.setupEnrichments();
  }

  setupResponsiveContentTransporter (desktopElement: HTMLElement, mobileElement: HTMLElement, content: HTMLElement) {
    const placeContent = (vw: number) => {
      // reference _variables.scss for grid-breakpoints
      if (vw < 992) {
        // transport content to mobile element on tablet/mobile view
        mobileElement.appendChild(content);
      } else {
        this.navOffCanvas?.hide();
        // transport content to desktop element on desktop view
        desktopElement.appendChild(content);
      }
    };

    const initialVw = Math.max(document.documentElement.clientWidth || 0, window.innerWidth || 0);
    placeContent(initialVw);

    window.addEventListener('resize', debounce(() => {
      const vw = Math.max(document.documentElement.clientWidth || 0, window.innerWidth || 0);
      const inputs: HTMLInputElement[] = Array.from(this.root.querySelectorAll('input'));
      // If window resize was triggered by device virtual keyboard, dont place content
      if (inputs.some(input => input === document.activeElement)) {
        return;
      }
      placeContent(vw);
    }
    , 200));
  }

  setupBookTocActivity () {
    this.tocController?.addEventListener('itemTitleClicked', (e) => {
      const customEvt = e as CustomEvent;
      const id = customEvt.detail.target.getAttribute('href').replace('#', '');
      const documentElement = this.root.querySelector('[data-document-element]');
      if (!documentElement) return;
      if (!(this.storedDocument && this.storedDocument instanceof HTMLElement)) return;
      if (id) {
        const sectionOfFocus = this.storedDocument.querySelector(`#${id}`)?.cloneNode(true) as HTMLElement | undefined;
        if (!sectionOfFocus) return;
        // Delete content within document element and then append section of focus
        documentElement.replaceChildren(sectionOfFocus);
      } else {
        const storedDocument = this.storedDocument.cloneNode(true);
        // @ts-ignore
        documentElement.replaceChildren(...this.storedDocument.children);
        this.storedDocument = storedDocument;
      }
      this.enchrichmentsManager?.layoutItems();
    });
  }

  setupTocForTab () {
    // If there is no toc item don't create and mount la-toc-controller
    const tocItems = this.getTocItems();
    if (!tocItems.length) return null;
    const tocController = createTocController(tocItems);
    tocController.titleFilterPlaceholder = i18next.t('Search table of contents');
    const tocContainer = this.root.querySelector('.toc');
    if (!tocContainer) return null;
    tocContainer.appendChild(tocController);
    return tocController;
  }

  getTocItems = () => {
    let items = [];
    if (this.root.getAttribute('data-display-type') === 'akn') {
      const aknTocJsonElement: HTMLElement | null = this.root.querySelector('#akn_toc_json');
      items = aknTocJsonElement && JSON.parse(aknTocJsonElement.textContent as string)
        ? JSON.parse(aknTocJsonElement.textContent as string) : [];
    } else if (this.root.getAttribute('data-display-type') === 'html') {
      const content: HTMLElement | null = this.root.querySelector('.content__html');
      items = content ? generateHtmlTocItems(content) : [];
    }
    return items;
  }

  setupEnrichments () {
    const contentAndEnrichmentsElement = this.root.querySelector('.content-and-enrichments');
    if (!contentAndEnrichmentsElement) return;
    this.enchrichmentsManager = new EnrichmentsManager(contentAndEnrichmentsElement as HTMLElement);
  }
}

export default DocumentContent;

import DocumentSearch from './DocumentSearch/index.vue';
import PdfRenderer from './pdf-renderer';
import debounce from 'lodash/debounce';
import { createAndMountApp } from '../utils/vue-utils';
import { i18n } from '../i18n';
import DocDiffsManager from './DocDiffs';
import { generateHtmlTocItems } from '../utils/function';

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
  private docDiffsManager: DocDiffsManager | null;
  constructor (root: HTMLElement) {
    this.root = root;
    this.navOffCanvas = undefined;
    this.docDiffsManager = null;

    this.setupDiffs();

    const tocTabTriggerEl = this.root.querySelector('#toc-tab');
    const searchTabTriggerEl = this.root.querySelector('#navigation-search-tab');

    const tocSetupOnTab = this.setupTocForTab();
    // If toc setup and mounted successfully, activate toc tab otherwise activate search tab
    if (tocSetupOnTab && tocTabTriggerEl) {
      tocTabTriggerEl.classList.remove('d-none');
      const tocTab = new (window as { [key: string]: any }).bootstrap.Tab(tocTabTriggerEl);
      tocTab.show();
    } else if (searchTabTriggerEl) {
      const searchTab = new (window as { [key: string]: any }).bootstrap.Tab(searchTabTriggerEl);
      searchTab.show();
    }

    const documentElement: HTMLElement | null = this.root.querySelector('[data-document-element]');

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
    if (targetMountElement) {
      this.searchApp = createAndMountApp({
        component: DocumentSearch,
        props: {
          document: documentElement,
          docType: root.getAttribute('data-display-type'),
          mountElement: targetMountElement
        },
        use: [i18n],
        mountTarget: targetMountElement as HTMLElement
      });
      targetMountElement.addEventListener('going-to-snippet', () => {
        this.navOffCanvas?.hide();
      });
    }
  }

  setupDiffs () {
    const gutter: HTMLElement | null = this.root.querySelector('la-gutter');
    const akn: HTMLElement | null = this.root.querySelector('la-akoma-ntoso');
    if (!akn || !gutter) return;
    const frbrExpressionUri = akn.getAttribute('expression-frbr-uri');
    if (!frbrExpressionUri) return;
    this.docDiffsManager = new DocDiffsManager(frbrExpressionUri, gutter);
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

  setupTocForTab () {
    // If there is no toc item don't create and mount la-toc-controller
    const tocItems = this.getTocItems();
    if (!tocItems.length) return false;
    const tocController = this.createTocController(tocItems);
    const tocContainer = this.root.querySelector('.toc');
    if (!tocContainer) return;
    tocContainer.appendChild(tocController);
    return true;
  }

  createTocController (items: []) {
    const laTocController = document.createElement('la-table-of-contents-controller');
    laTocController.items = items;
    laTocController.expandAllBtnClasses = 'btn btn-secondary btn-sm';
    laTocController.collapseAllBtnClasses = 'btn btn-secondary btn-sm';
    laTocController.titleFilterInputClasses = 'form-control';
    laTocController.titleFilterClearBtnClasses = 'btn btn-secondary btn-sm';
    return laTocController;
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
}

export default DocumentContent;

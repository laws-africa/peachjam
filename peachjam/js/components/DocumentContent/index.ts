import DocumentSearch from '../DocumentSearch/index.vue';
import PdfRenderer from './pdf-renderer';
import debounce from 'lodash/debounce';
import { createAndMountApp } from '../../utils/vue-utils';
import { vueI18n } from '../../i18n';
import { createTocController, generateHtmlTocItems, wrapTocItems } from '../../utils/function';
import EnrichmentsManager from './enrichments-manager';
import i18next from 'i18next';

class OffCanvas {
  protected offCanvas: any;
  body: HTMLElement | null;
  constructor (element: HTMLElement) {
    this.offCanvas = new window.bootstrap.Offcanvas(element);
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
  private navOffCanvas: OffCanvas | undefined;
  private enrichmentsManager: EnrichmentsManager | null = null;
  private originalDocument: HTMLElement | undefined;
  private tocController: HTMLElement| null = null;
  private documentElement: Element | null;
  private tocShowActiveItemOnly: boolean = false;
  private displayType: string;
  private tocItemIndex = new Map<String, any>();
  private activeTocItem: any = null;

  constructor (root: HTMLElement) {
    this.root = root;
    this.documentElement = this.root.querySelector('.content');
    this.displayType = this.root.getAttribute('data-display-type') || '';

    this.setupTabs();
    this.setupOffCanvasNav();
    this.setupPdf();
    this.setupSearch();
    this.setupEnrichments();
    this.setSharedPortion();
    if (this.displayType !== 'pdf') {
      // for PDFs, this will be done once the pages are rendered
      this.setupPopups();
    }
  }

  setupTabs () {
    const tocTabTriggerEl = this.root.querySelector('#toc-tab');
    const searchTabTriggerEl = this.root.querySelector('#navigation-search-tab');
    const pdfPreviewsTabTriggerEl = this.root.querySelector('#pdf-previews-tab');
    const summaryTabTriggerEl = this.root.querySelector('#doc-summary-tab');
    const tocCreated = this.setupToc();

    // If toc setup and mounted successfully, activate toc tab otherwise activate search tab
    if (summaryTabTriggerEl) {
      const tocTab = new window.bootstrap.Tab(summaryTabTriggerEl);
      tocTab.show();
    } else if (tocCreated && tocTabTriggerEl) {
      tocTabTriggerEl.classList.remove('d-none');
      const tocTab = new window.bootstrap.Tab(tocTabTriggerEl);
      tocTab.show();
    } else if (this.displayType === 'pdf' && pdfPreviewsTabTriggerEl) {
      const pdfPreviewsTab = new window.bootstrap.Tab(pdfPreviewsTabTriggerEl);
      pdfPreviewsTab.show();
    } else if (searchTabTriggerEl) {
      const searchTab = new window.bootstrap.Tab(searchTabTriggerEl);
      searchTab.show();
    }
  }

  setupOffCanvasNav () {
    const navColumn: HTMLElement | null = this.root.querySelector('#navigation-column');
    const navContent: HTMLElement | null = this.root.querySelector('#navigation-content .navigation__inner');
    const navOffCanvasElement: HTMLElement | null = this.root.querySelector('#navigation-offcanvas');

    if (navColumn && navOffCanvasElement && navContent) {
      this.navOffCanvas = new OffCanvas(navOffCanvasElement);
      if (this.navOffCanvas.body) {
        this.setupResponsiveContentTransporter(navColumn, this.navOffCanvas.body, navContent);
      }
    }
  }

  setupPdf () {
    // if pdf setup pdf renderer instance
    if (this.displayType === 'pdf') {
      // get dataset attributes
      const pdfAttrsElement: HTMLElement | null = this.root.querySelector('[data-pdf]');
      if (pdfAttrsElement) {
        Object.keys(pdfAttrsElement.dataset).forEach(key => {
          this.root.dataset[key] = pdfAttrsElement.dataset[key];
        });
      }
      this.pdfRenderer = new PdfRenderer(this.root, this);
      this.pdfRenderer.onPreviewPanelClick = () => {
        this.navOffCanvas?.hide();
      };
      this.pdfRenderer.onPdfLoaded = () => {
        if (this.enrichmentsManager) {
          this.enrichmentsManager.addPdfEnrichments();
        }
        this.setupPopups();

        const urlParams = new URLSearchParams(window.location.search);
        const targetPage = urlParams.get('page');
        if (!targetPage) return;
        this.pdfRenderer?.triggerScrollToPage(targetPage);
      };
    }
  }

  setupSearch () {
    const targetMountElement = this.root.querySelector('[data-doc-search]');
    if (targetMountElement) {
      createAndMountApp({
        component: DocumentSearch,
        props: {
          document: this.documentElement,
          docType: this.displayType,
          mountElement: targetMountElement
        },
        use: [vueI18n],
        mountTarget: targetMountElement as HTMLElement
      });
      targetMountElement.addEventListener('going-to-snippet', () => {
        this.navOffCanvas?.hide();
      });
    }
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

  setupToc () {
    this.tocShowActiveItemOnly = this.root.hasAttribute('data-toc-show-active-item-only');

    // If there is no toc item don't create and mount la-toc-controller
    const tocItems = this.getTocItems();
    if (!tocItems.length) return false;

    // index from id to TOC items
    const indexItems = (items: any[]) => {
      for (const item of items) {
        // @ts-ignore
        this.tocItemIndex.set(item.id, item);
        indexItems(item.children);
      }
    };
    indexItems(tocItems);

    this.tocController = createTocController(tocItems);
    // @ts-ignore
    this.tocController.titleFilterPlaceholder = i18next.t('Search table of contents');

    const tocContainer = this.root.querySelector('.toc');
    if (!tocContainer) return;
    tocContainer.appendChild(this.tocController);

    if (this.tocShowActiveItemOnly && this.documentElement) {
      this.originalDocument = this.documentElement.cloneNode(true) as HTMLElement;
    }

    this.tocController.addEventListener('itemTitleClicked', (e) => {
      // @ts-ignore
      this.setSharedPortion(e.target?.item?.title);
      // hide off-canvas nav, if necessary
      this.navOffCanvas?.hide();
      if (this.tocShowActiveItemOnly) {
        this.showDocumentPortion((e as CustomEvent).detail.target.getAttribute('href'));
      }
    });

    // now that the page has loaded, check if there is a hash in the URL and if so, activate the corresponding TOC item
    if (window.location.hash) {
      this.showDocumentPortion(window.location.hash);
    }

    return true;
  }

  getTocItems = () => {
    let items = [];

    const tocElement: HTMLElement | null = this.root.querySelector('#akn_toc_json');
    // use the injected TOC if available
    if (tocElement && tocElement.textContent) {
      items = JSON.parse(tocElement.textContent) || [];
    }

    if (!items.length && this.displayType === 'html') {
      const content: HTMLElement | null = this.root.querySelector('.content__html');
      if (content) {
        items = generateHtmlTocItems(content);
        wrapTocItems(content, items);
      }
    }

    if (this.tocShowActiveItemOnly) {
      // Add a "Show full text" item to the top of the TOC when the "show active item only" option is enabled
      items.unshift({
        tag: 'H1',
        title: i18next.t('Show full text'),
        id: '',
        children: []
      });
    }

    // recursively add parent and depth information
    function addParentAndDepth (items: any[], parent: any = null, depth: number = 1) {
      for (const item of items) {
        item.parent = parent;
        item.depth = depth;
        addParentAndDepth(item.children, item, depth + 1);
      }
    }
    addParentAndDepth(items);

    return items;
  }

  setupEnrichments () {
    const contentAndEnrichmentsElement = this.root.querySelector('.content-and-enrichments');
    if (!contentAndEnrichmentsElement) return;
    this.enrichmentsManager = new EnrichmentsManager(contentAndEnrichmentsElement as HTMLElement);
  }

  setupPopups () {
    if (!this.documentElement) return;

    // if the document isn't using la-akoma-ntoso, then fiddle existing <a> elements to ensure that the external popups
    // functionality finds them (it expects AKN-style a tags)
    if (this.documentElement.tagName !== 'LA-AKOMA-NTOSO') {
      for (const a of Array.from(this.documentElement.querySelectorAll('a[href^="/akn/"]'))) {
        a.classList.add('akn-ref');
        // @ts-ignore
        a.setAttribute('data-href', a.getAttribute('href'));
      }
    }

    const el = document.createElement('la-decorate-external-refs');
    el.akomaNtoso = (this.documentElement as HTMLElement);
    el.popups = true;
    el.provider = '//' + window.location.host;
    this.documentElement.appendChild(el);
  }

  /** Show only the portion of the document identified by the given ID, or the entire document if no ID is given. */
  showDocumentPortion (id: string) {
    // strip leading #
    if (id && id.startsWith('#')) id = id.substring(1);

    if (this.originalDocument && this.documentElement) {
      if (!id) {
        // show entire document
        this.documentElement.replaceChildren(...Array.from(this.originalDocument.children).map(node => node.cloneNode(true)));
        this.activeTocItem = null;
      } else {
        // find the owning portion for this portion, by looking for the container that has a TOC entry of depth 1
        // @ts-ignore
        let tocItem = this.tocItemIndex.get(id);
        while (tocItem && tocItem.depth > 1) {
          tocItem = tocItem.parent;
        }
        if (!tocItem) return;

        // swap in the main owner of this portion, if necessary
        if (this.activeTocItem !== tocItem) {
          const portion = this.originalDocument.querySelector(`[id="${tocItem.id}"]`)?.cloneNode(true) as HTMLElement;
          this.documentElement.replaceChildren(portion);
          this.activeTocItem = tocItem;
        }
      }
    }
  }

  /**
   * When the user is focused only on a certain portion of the document, update the social sharing mechanisms
   * to reflect that.
   * @param portion a description of the portion being shared
   */
  setSharedPortion (portion: string = '') {
    const parts = [this.root.dataset.title];
    if (portion) parts.push(portion);
    parts.push(window.location.toString());
    const text = parts.join(' - ');

    for (const el of Array.from(document.querySelectorAll('.share-link'))) {
      const a = el as HTMLAnchorElement;
      const url = new URL(a.href);
      for (const key of Array.from(url.searchParams.keys())) {
        if (key === 'text') {
          url.searchParams.set(key, text);
        }
      }
      a.href = url.toString();
    }
  }
}

export default DocumentContent;

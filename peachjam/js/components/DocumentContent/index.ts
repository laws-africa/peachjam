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
  private searchApp: any;
  private navOffCanvas: OffCanvas | undefined;
  private enchrichmentsManager: EnrichmentsManager | null = null;
  private originalDocument: HTMLElement | undefined;
  private tocController: HTMLElement| null = null;
  private documentElement: Element | null;

  constructor (root: HTMLElement) {
    this.root = root;
    this.documentElement = this.root.querySelector('.content');

    this.setupTabs();
    this.setupNav();
    this.setupPdf();
    this.setupSearch();
    this.setupEnrichments();
    this.setSharedPortion();
    if (this.root.getAttribute('data-display-type') !== 'pdf') {
      // for PDFs, this will be done once the pages are rendered
      this.setupPopups();
    }
  }

  setupTabs () {
    const tocTabTriggerEl = this.root.querySelector('#toc-tab');
    const searchTabTriggerEl = this.root.querySelector('#navigation-search-tab');
    const pdfPreviewsTabTriggerEl = this.root.querySelector('#pdf-previews-tab');
    const tocSetupOnTab = this.setupTocForTab();

    // If toc setup and mounted successfully, activate toc tab otherwise activate search tab
    if (tocSetupOnTab && tocTabTriggerEl) {
      tocTabTriggerEl.classList.remove('d-none');
      const tocTab = new window.bootstrap.Tab(tocTabTriggerEl);
      tocTab.show();
    } else if (this.root.getAttribute('data-display-type') === 'pdf' && pdfPreviewsTabTriggerEl) {
      const pdfPreviewsTab = new window.bootstrap.Tab(pdfPreviewsTabTriggerEl);
      pdfPreviewsTab.show();
    } else if (searchTabTriggerEl) {
      const searchTab = new window.bootstrap.Tab(searchTabTriggerEl);
      searchTab.show();
    }
  }

  setupNav () {
    const navColumn: HTMLElement | null = this.root.querySelector('#navigation-column');
    const navContent: HTMLElement | null = this.root.querySelector('#navigation-content .navigation__inner');
    const navOffCanvasElement: HTMLElement | null = this.root.querySelector('#navigation-offcanvas');

    if (navColumn && navOffCanvasElement && navContent) {
      this.navOffCanvas = new OffCanvas(navOffCanvasElement);
      if (this.navOffCanvas.body) {
        this.setupResponsiveContentTransporter(navColumn, this.navOffCanvas.body, navContent);
        const toc = this.root.querySelector('la-table-of-contents-controller');
        if (toc) {
          toc.addEventListener('itemTitleClicked', () => {
            this.navOffCanvas?.hide();
          });
        }
      }
    }
  }

  setupPdf () {
    // if pdf setup pdf renderer instance
    if (this.root.getAttribute('data-display-type') === 'pdf') {
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
        if (this.enchrichmentsManager) {
          this.enchrichmentsManager.setupPdfCitationLinks();
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
      this.searchApp = createAndMountApp({
        component: DocumentSearch,
        props: {
          document: this.documentElement,
          docType: this.root.getAttribute('data-display-type'),
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

  /**
   * Setup the TOC so that when an item is activated, only the content for that item is shown in the document view.
   */
  setupTocShowActiveItemOnly () {
    if (this.documentElement) {
      this.originalDocument = this.documentElement.cloneNode(true) as HTMLElement;

      this.tocController?.addEventListener('itemTitleClicked', (e) => {
        if (this.originalDocument && this.documentElement) {
          const id = (e as CustomEvent).detail.target.getAttribute('href');
          if (!id || id === '#') {
            this.documentElement.replaceChildren(...Array.from(this.originalDocument.children).map(node => node.cloneNode(true)));
          } else {
            // @ts-ignore
            const sectionOfFocus = this.originalDocument.querySelector(id)?.cloneNode(true) as HTMLElement;
            if (sectionOfFocus) {
              // Delete content within document element and then append section of focus
              this.documentElement.replaceChildren(sectionOfFocus);
            }
          }
        }
      });
    }
  }

  setupTocForTab () {
    // If there is no toc item don't create and mount la-toc-controller
    const tocItems = this.getTocItems();

    if (this.root.hasAttribute('data-toc-show-active-item-only')) {
      // Add a "Show full text" item to the top of the TOC when the "show active item only" option is enabled
      tocItems.unshift({
        tag: 'H1',
        title: i18next.t('Show full text'),
        id: '',
        children: []
      });
    }

    if (!tocItems.length) return false;

    this.tocController = createTocController(tocItems);
    // @ts-ignore
    this.tocController.titleFilterPlaceholder = i18next.t('Search table of contents');

    const tocContainer = this.root.querySelector('.toc');
    if (!tocContainer) return;
    tocContainer.appendChild(this.tocController);

    if (this.root.hasAttribute('data-toc-show-active-item-only')) {
      this.setupTocShowActiveItemOnly();
    }

    this.tocController.addEventListener('itemTitleClicked', (e) => {
      // @ts-ignore
      this.setSharedPortion(e.target?.item?.title);
    });

    return true;
  }

  getTocItems = () => {
    let items = [];

    if (this.root.getAttribute('data-display-type') === 'akn') {
      const tocElement: HTMLElement | null = this.root.querySelector('#akn_toc_json');
      if (tocElement) {
        items = JSON.parse(tocElement.textContent as string) || [];
      }
    } else if (this.root.getAttribute('data-display-type') === 'html') {
      const content: HTMLElement | null = this.root.querySelector('.content__html');
      if (content) {
        items = generateHtmlTocItems(content);
        wrapTocItems(content, items);
      }
    }

    return items;
  }

  setupEnrichments () {
    const contentAndEnrichmentsElement = this.root.querySelector('.content-and-enrichments');
    if (!contentAndEnrichmentsElement) return;
    this.enchrichmentsManager = new EnrichmentsManager(contentAndEnrichmentsElement as HTMLElement);
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

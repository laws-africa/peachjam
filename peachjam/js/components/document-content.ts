import DocumentSearch from './DocumentSearch/index.vue';
import PdfRenderer from './pdf-renderer';
import debounce from 'lodash/debounce';
import { createAndMountApp } from '../utils/vue-utils';
import { i18n } from '../i18n';

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
  constructor (root: HTMLElement) {
    this.root = root;
    this.navOffCanvas = undefined;

    // Activate first tab
    const firstTabEl = this.root.querySelector('#navigation-tab .nav-link:first-child');
    if (firstTabEl) {
      const firstTab = new (window as { [key: string]: any }).bootstrap.Tab(firstTabEl);
      firstTab.show();
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
      placeContent(vw);
    }, 200));
  }
}

export default DocumentContent;

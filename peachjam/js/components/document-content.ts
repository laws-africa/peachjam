import { createApp } from 'vue';
import DocumentSearch from './DocumentSearch/index.vue';
import PdfRenderer from './pdf-renderer';
import debounce from 'lodash/debounce';

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
  private pdf: PdfRenderer | undefined;
  private searchApp: any;
  constructor (root: HTMLElement) {
    this.root = root;

    const documentElement: HTMLElement | null = this.root.querySelector('[data-document-element]');

    const navColumn: HTMLElement | null = this.root.querySelector('#navigation-column');
    const navContent: HTMLElement | null = this.root.querySelector('#navigation-content .navigation__inner');
    const navOffCanvasElement: HTMLElement | null = this.root.querySelector('#navigation-offcanvas');
    let navOffCanvas: OffCanvas | undefined;

    if (navColumn && navOffCanvasElement && navContent) {
      navOffCanvas = new OffCanvas(navOffCanvasElement);
      if (navOffCanvas.body) {
        this.setupResponsiveContentTransporter(navColumn, navOffCanvas.body, navContent);
      }
    }

    // if pdf setup pdf renderer instance
    if (root.getAttribute('data-display-type') === 'pdf') {
      // get dataset attributes
      const pdfAttrsElement: HTMLElement | null = this.root.querySelector('[data-pdf]');
      if (pdfAttrsElement) {
        Object.keys(pdfAttrsElement.dataset).forEach(key => { root.dataset[key] = pdfAttrsElement.dataset[key]; });
      }
      this.pdf = new PdfRenderer(root);
    }

    const targetMountElement = this.root.querySelector('[data-doc-search]');
    if (targetMountElement) {
      const app = createApp(DocumentSearch, {
        document: documentElement,
        docType: root.getAttribute('data-display-type'),
        mountElement: targetMountElement
      });
      this.searchApp = app;
      app.mount(targetMountElement);
      targetMountElement.addEventListener('going-to-snippet', () => {
        navOffCanvas?.hide();
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
        // transport content to desktop element on desktop view
        desktopElement.appendChild(content);
      }
    };

    const initialVw = Math.max(document.documentElement.clientWidth || 0, window.innerWidth || 0);
    placeContent(initialVw);

    window.addEventListener('resize', debounce(() => {
      const vw = Math.max(document.documentElement.clientWidth || 0, window.innerWidth || 0);
      placeContent(vw);
    }, 300));
  }
}

export default DocumentContent;

import { createApp } from 'vue';
import DocumentSearch from './DocumentSearch/index.vue';
import PdfRenderer from './pdf-renderer';
import debounce from 'lodash/debounce';

class OffCanvas {
  protected triggerButton: HTMLElement | null;
  protected offCanvas: any;
  protected element: HTMLElement;
  body: HTMLElement | null;
  constructor (element: HTMLElement) {
    this.offCanvas = new (window as { [key: string]: any }).bootstrap.Offcanvas(element);
    this.element = element;
    this.triggerButton = document.querySelector(`[data-bs-target="#${element.getAttribute('id')}"]`);
    this.body = element.querySelector('[data-offcanvas-body]');
  }

  open () {
    this.offCanvas.show();
  }

  close () {
    this.offCanvas.show();
  }
}

class ResponsiveContentTransporter {
  constructor (desktopElement: HTMLElement, mobileElement: HTMLElement, content: HTMLElement) {
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

    window.visualViewport.addEventListener('resize', debounce(() => {
      const vw = Math.max(document.documentElement.clientWidth || 0, window.innerWidth || 0);
      placeContent(vw);
    }, 300));
  }
}

class DocumentContent {
  protected root: HTMLElement;
  private pdf: PdfRenderer | undefined;
  private navOffCanvas: OffCanvas | undefined;
  private navResponsiveContentTransporter: ResponsiveContentTransporter | undefined;
  private offCanvases: {};
  private documentSearch: any;
  constructor (root: HTMLElement) {
    this.root = root;
    this.navResponsiveContentTransporter = undefined;
    this.offCanvases = {};

    const navColumn: HTMLElement | null = this.root.querySelector('#navigation-column');
    const navContent: HTMLElement | null = this.root.querySelector('#navigation-content .navigation__inner');
    const navOffCanvasElement: HTMLElement | null = this.root.querySelector('#navigation-offcanvas');
    if (navColumn && navOffCanvasElement && navContent) {
      this.navOffCanvas = new OffCanvas(navOffCanvasElement);
      if (this.navOffCanvas.body) {
        this.navResponsiveContentTransporter = new ResponsiveContentTransporter(navColumn, this.navOffCanvas.body, navContent);
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
      const component = createApp(DocumentSearch, {
        document,
        docType: root.getAttribute('data-display-type')
      });
      this.documentSearch = component;
      // this.documentSearch.$on('going-to-snippet', () => {
      //
      // });
      component.mount(targetMountElement);
    }
  }
}

export default DocumentContent;

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

/*
* TODO:
*  1 - Refactor class to something generic.perhaps ResponsiveContentTransporter
*  2 - Seperate offcanvas logic from class
* */
class ColumnOffsetCanvasLinker {
  private readonly offsetCanvasElement: HTMLElement;
  private readonly content: HTMLElement;
  private readonly column: HTMLElement;
  public offsetCanvas: OffCanvas;
  constructor (column: HTMLElement, content: HTMLElement, offsetCanvasElement: HTMLElement) {
    this.column = column;
    this.content = content;
    this.offsetCanvasElement = offsetCanvasElement;
    this.offsetCanvas = new OffCanvas(this.offsetCanvasElement);

    const placeContent = (vw: number, content: HTMLElement, possibleTargets: {
      column: HTMLElement,
      offCanvasBody: HTMLElement
    }) => {
      // reference _variables.scss for grid-breakpoints
      // Transport navigation content offcanvas on table/mobile view and nav column on desktop view
      if (vw < 992) {
        possibleTargets.offCanvasBody.appendChild(content);
      } else {
        possibleTargets.column.appendChild(content);
      }
    };

    // place content initially
    if (this.offsetCanvas.body) {
      const possibleTargets = {
        column: this.column,
        offCanvasBody: this.offsetCanvas.body
      };

      const initialVw = Math.max(document.documentElement.clientWidth || 0, window.innerWidth || 0);
      placeContent(initialVw, this.content, possibleTargets);

      window.visualViewport.addEventListener('resize', debounce(() => {
        const vw = Math.max(document.documentElement.clientWidth || 0, window.innerWidth || 0);
        placeContent(vw, this.content, possibleTargets);
      }, 500));
    }
  }
}

class DocumentContent {
  protected root: HTMLElement;
  private pdf: PdfRenderer | undefined;
  constructor (root: HTMLElement) {
    this.root = root;
    const navColumn: HTMLElement | null = this.root.querySelector('#navigation-column');
    const navContent: HTMLElement | null = this.root.querySelector('#navigation-content .navigation__inner');
    const navOffCanvasElement: HTMLElement | null = this.root.querySelector('#navigation-offcanvas');

    if (navColumn && navOffCanvasElement && navContent) {
      const instance = new ColumnOffsetCanvasLinker(navColumn, navContent, navOffCanvasElement);
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
      createApp(DocumentSearch, {
        document,
        docType: root.getAttribute('data-display-type')
      }).mount(targetMountElement);
    }
  }
}

export default DocumentContent;

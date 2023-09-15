import debounce from 'lodash/debounce';
import peachJam from '../../peachjam';
// @ts-ignore
import { markRange, rangeToTarget, targetToRange } from '../../dom';
import { scrollToElement } from '../../utils/function';
import DocumentContent from './index';
import i18next from 'i18next';

type GlobalWorkerOptionsType = {
  [key: string]: any,
  workerSrc: string
}

interface iPdfLib {
  [key: string]: any,
  GlobalWorkerOptions: GlobalWorkerOptionsType,
}

const pdfjsLib = require('pdfjs-dist');

class PdfRenderer {
  protected pdfjsLib: iPdfLib;
  protected pdfUrl: any;
  protected pdfContentWrapper: HTMLElement | null;
  protected root: HTMLElement;
  protected scrollListenerActive: boolean = true;
  protected pdfContentMarks: any[] = [];
  protected progressBarElement: HTMLElement | null;
  protected previewPanelsContainer: Element | null;
  protected manager: DocumentContent;
  public onPreviewPanelClick: () => void = () => {};
  public onPdfLoaded: () => void = () => {};

  constructor (root: HTMLElement, manager: DocumentContent) {
    this.root = root;
    this.manager = manager;
    this.pdfjsLib = pdfjsLib as iPdfLib;
    if (!this.pdfjsLib) {
      throw new Error('Failed to load pdf.js');
    }
    this.pdfjsLib.GlobalWorkerOptions.workerSrc = peachJam.config.pdfWorker;
    this.pdfUrl = root.dataset.pdf;
    this.pdfContentWrapper = root.querySelector('.pdf-content');
    this.progressBarElement = root.querySelector('.progress-bar');
    this.previewPanelsContainer = root.querySelector('.pdf-previews');
    this.root.querySelector('button[data-load-doc-button]')?.addEventListener('click', () => {
      this.loadPdf();
    });
    if (!Object.keys(this.root.dataset).includes('largePdf')) {
      this.loadPdf();
    }
  }

  loadPdf () {
    // should we jump to a specific page?
    let initialPage = null;
    if ((document.location.hash || '').startsWith('#page-')) {
      try {
        initialPage = parseInt(document.location.hash.substring(6));
      } catch {}
    }

    this.root.removeAttribute('data-large-pdf');
    this.setupPdfAndPreviewPanels(initialPage).then(() => {
      this.setupPreviewSyncing();
      this.onPdfLoaded();
    }).catch((e:ErrorEvent) => {
      throw e;
    });
  }

  setupPreviewSyncing () {
    const pages: Array<HTMLElement> = Array.from(this.root.querySelectorAll('.pdf-content__page'));
    window.addEventListener('scroll', debounce(() => {
      if (!this.scrollListenerActive) return;

      let current: HTMLElement | null;
      for (const page of pages) {
        if (!(window.scrollY >= page.offsetTop)) return;

        current = this.root.querySelector(`.preview-panel[data-page="${page.dataset.page}"]`);
        if (current) {
          this.activatePreviewPanel(current);
          const scrollableContainer = this.root.querySelector('[data-preview-scroll-container]');
          if (scrollableContainer) {
            scrollableContainer.scrollTop = (current.offsetTop + current.clientHeight) - (current.offsetHeight * 2);
          }
        }
      }
    }, 20));
  }

  activatePreviewPanel (nextActivePreviewPanel: HTMLElement | EventTarget) {
    for (const element of Array.from(this.root.querySelectorAll('.preview-panel'))) {
      element.classList.remove('active');
      if (element === nextActivePreviewPanel) {
        if ('classList' in nextActivePreviewPanel) {
          nextActivePreviewPanel.classList.add('active');
        }
      }
    }
  }

  handlePreviewPanelClick (e: Event) {
    this.onPreviewPanelClick();
    if (!e.currentTarget) return;
    this.activatePreviewPanel(e.currentTarget);
    if (!(e.currentTarget instanceof HTMLElement)) return;
    document.location.hash = `#page-${e.currentTarget.dataset.page}`;
    // update the current portion for sharing purposes
    const portion = i18next.t('Page') + ' ' + e.currentTarget.dataset.page;
    this.manager.setSharedPortion(portion);
    this.scrollToPage(e.currentTarget.dataset.page);
  }

  scrollToPage (pageNumber: string | number | undefined) {
    const targetPage = this.root.querySelector(`.pdf-content__page[data-page="${pageNumber}"]`);
    if (!targetPage) return;
    this.scrollListenerActive = false;
    scrollToElement(targetPage as HTMLElement, () => {
      this.scrollListenerActive = true;
    });
  }

  triggerScrollToPage (pageNumber: string | number) {
    const panel = this.root.querySelector(`.preview-panel[data-page='${pageNumber}']`);
    if (!panel) return;
    this.activatePreviewPanel(panel);
    this.scrollToPage(pageNumber);
  }

  async setupPdfAndPreviewPanels (initialPage: number | null) {
    const docElement = document.querySelector('.content-and-enrichments .content');
    if (!docElement) return;
    const containerWidth = docElement.clientWidth || 0;
    // render pdf at double scale, for high resolution
    const scale = 2;

    this.root.removeAttribute('data-pdf-standby');
    this.root.setAttribute('data-pdf-loading', '');

    // load the PDF asynchronously
    const loadingTask = this.pdfjsLib.getDocument(this.pdfUrl);
    loadingTask.onProgress = (data: { loaded: number, total: number }) => {
      if (data.total && this.progressBarElement) {
        const progress = data.loaded / data.total * 100;
        this.progressBarElement.style.width = `${progress}%`;
        this.progressBarElement.innerText = `${Math.ceil(progress)}%`;
      }
    };

    try {
      const pdf = await loadingTask.promise;
      this.root.removeAttribute('data-pdf-loading');

      const canvas = document.createElement('canvas');

      for (let i = 0; i < pdf.numPages; i++) {
        const page = await pdf.getPage(i + 1);
        await this.renderSinglePage(page, i, scale, containerWidth, canvas);
        if (initialPage && initialPage === i + 1) {
          this.scrollToPage(i + 1);
        }
      }
    } catch (e) {
      console.log(e);
    }
  }

  async renderSinglePage (page: any, index: number, scale: number, containerWidth: number, canvas: HTMLCanvasElement) {
    const viewport = page.getViewport({ scale });
    canvas.style.display = 'block';
    // set the logical size of the canvas to match the scaled-up size of the viewport
    canvas.width = viewport.width;
    canvas.height = viewport.height;
    // force the canvas to be the width of the container in the dom
    canvas.style.width = `${containerWidth}px`;

    const context = canvas.getContext('2d');
    const renderContext = {
      canvasContext: context,
      viewport
    };

    const pageContainer = document.createElement('div');
    pageContainer.setAttribute('id', `page-${index + 1}`);
    pageContainer.dataset.page = String(index + 1);
    pageContainer.classList.add('pdf-content__page');
    pageContainer.style.position = 'relative';

    if (this.pdfContentWrapper) {
      this.pdfContentWrapper.appendChild(pageContainer);
    }

    // render the page
    await page.render(renderContext).promise;
    // add the text layer
    pageContainer.append(this.addImageLayer(page, containerWidth, canvas));
    // add image previews
    this.addPreviewPanel(canvas, index + 1);
  }

  addImageLayer (page: any, containerWidth: number, canvas: HTMLCanvasElement) {
    const image = new Image();
    image.src = canvas.toDataURL('image/jpeg');

    // when rendering the image layer, we want the renderer to know that we'll place the image on top
    // of a canvas that has been scaled up/down to fit into the containing div; so we need to calculate
    // the scale required to go from the original PDF width, to the container width.
    let viewport = page.getViewport({ scale: 1 });
    const textScale = containerWidth / viewport.width;
    // this viewport will have the correct scale to render image to, to be placed directly over the canvas
    viewport = page.getViewport({ scale: textScale });

    image.style.left = `${canvas.offsetLeft}px`;
    image.style.top = `${canvas.offsetTop}px`;
    image.style.height = `${viewport.height}px`;
    image.style.width = `${viewport.width}px`;

    return image;
  }

  addPreviewPanel (canvas: HTMLCanvasElement, pageNum: number) {
    const panelPreview = document.createElement('button');
    panelPreview.dataset.page = String(pageNum);
    panelPreview.classList.add('preview-panel');
    panelPreview.addEventListener('click', (e) => this.handlePreviewPanelClick(e));

    const target = new Image();
    target.src = canvas.toDataURL('image/jpeg');

    const pageNumber = document.createElement('span');
    pageNumber.classList.add('preview-panel__page-number');
    pageNumber.innerText = String(pageNum);
    panelPreview.append(target, pageNumber);

    if (this.previewPanelsContainer) {
      this.previewPanelsContainer.appendChild(panelPreview);
    }
  }
}

export default PdfRenderer;

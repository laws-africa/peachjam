import debounce from 'lodash/debounce';
import items from '../items.json';
// @ts-ignore
import { markRange, rangeToTarget, targetToRange } from '../dom';
import { scrollToElement } from '../utils/function';

type GlobalWorkerOptionsType = {
  [key: string]: any,
  workerSrc: string
}

interface iPdfLib {
  [key: string]: any,
  GlobalWorkerOptions: GlobalWorkerOptionsType,
}

async function asyncForEach (array: any[], callback: (arg0: any, arg1: number, arg2: any[]) => any) {
  for (let index = 0; index < array.length; index++) {
    await callback(array[index], index, array);
  }
}

class PdfRenderer {
  protected pdfUrl: any;
  protected pdfContentWrapper: HTMLElement | null;
  protected root: HTMLElement;
  protected scrollListenerActive: boolean = true;
  protected pdfContentMarks: any[] = [];
  protected progressBarElement: HTMLElement | null;
  public onPreviewPanelClick: () => void = () => {};
  public onPdfLoaded: () => void = () => {};

  constructor (root: HTMLElement) {
    this.root = root;
    this.pdfUrl = root.dataset.pdf;
    this.pdfContentWrapper = root.querySelector('.pdf-content');
    this.progressBarElement = root.querySelector('.progress-bar');
    this.root.querySelector('button[data-load-doc-button]')?.addEventListener('click', () => {
      this.loadPdf();
    });
    if (!Object.keys(this.root.dataset).includes('largePdf')) {
      this.loadPdf();
    }
  }

  /**
   * Update loading progress bar
   * @param progress a percentage value between 0 and 100
   */
  setLoadingProgress (progress: number) {
  }

  loadPdf () {
    this.root.removeAttribute('data-large-pdf');
    this.setupPdfAndPreviewPanels().then(() => {
      this.setupPreviewPanels();
      this.onPdfLoaded();
    }).catch((e:ErrorEvent) => {
      this.root.innerText = e.message;
    });
  }

  setupPreviewPanels () {
    const pages: Array<HTMLElement> = Array.from(this.root.querySelectorAll('.pdf-content__page'));
    const previewPanels = Array.from(this.root.querySelectorAll('.preview-panel'));
    for (const previewPanel of previewPanels) {
      previewPanel.addEventListener('click', (e) => this.handlePreviewPanelClick(e));
    }

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

  async setupPdfAndPreviewPanels () {
    const pdfjsLib = (window as { [key: string]: any }).pdfjsLib as iPdfLib;
    if (!pdfjsLib) {
      throw new Error('Failed to load pdf.js');
    }
    pdfjsLib.GlobalWorkerOptions.workerSrc = '/static/lib/pdfjs/pdf.worker.js';

    this.root.removeAttribute('data-pdf-standby');
    this.root.setAttribute('data-pdf-loading', '');

    // load the PDF asynchronously
    const loadingTask = pdfjsLib.getDocument(this.pdfUrl);
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

      const numPages = pdf.numPages;
      const listOfGetPages = Array.from(Array(numPages), (_, index) => pdf.getPage(index + 1));
      const pages = await Promise.all(listOfGetPages);
      const previewPanelsContainer = this.root.querySelector('.pdf-previews');
      const docElement = document.querySelector('[data-document-element]');
      if (!docElement) return;
      const docElementWidth = docElement.clientWidth || 0;
      const scale = 2;

      await asyncForEach(pages, async (page, index) => {
        let viewport = page.getViewport({ scale });

        const canvas = document.createElement('canvas');
        canvas.style.display = 'block';
        // set the logical size of the canvas to match the scaled-up size of the viewport
        canvas.width = viewport.width;
        canvas.height = viewport.height;
        // force the canvas to be the width of the container in the dom
        canvas.style.width = `${docElementWidth}px`;

        const context = canvas.getContext('2d');
        const renderContext = {
          canvasContext: context,
          viewport
        };

        const elementRendered = document.createElement('div');
        elementRendered.setAttribute('id', `page-${index + 1}`);
        elementRendered.dataset.page = String(index + 1);
        elementRendered.classList.add('pdf-content__page');
        elementRendered.style.position = 'relative';
        elementRendered.appendChild(canvas);
        // Canvas must be mounted first so textLayer can get offset values
        if (this.pdfContentWrapper) {
          this.pdfContentWrapper.appendChild(elementRendered);
        }

        // render the page
        await page.render(renderContext).promise;

        const textLayer = document.createElement('div');
        textLayer.classList.add('textLayer');

        // when rendering the text layer, we want the renderer to know that we'll place the text on top
        // of a canvas that has been scaled up/down to fit into the containing div; so we need to calculate
        // the scale required to go from the original PDF width, to the container width.
        viewport = page.getViewport({ scale: 1 });
        const textScale = docElementWidth / viewport.width;
        // this viewport will have the correct scale to render text to, to be placed directly over the canvas
        viewport = page.getViewport({ scale: textScale });

        textLayer.style.left = `${canvas.offsetLeft}px`;
        textLayer.style.top = `${canvas.offsetTop}px`;
        textLayer.style.height = `${viewport.height}px`;
        textLayer.style.width = `${viewport.width}px`;

        pdfjsLib.renderTextLayer({
          textContent: await page.getTextContent(),
          container: textLayer,
          viewport,
          textDivs: []
        });
        elementRendered.appendChild(textLayer);

        // annotations
        const annotationData = await page.getAnnotations();
        if (annotationData.length) {
          elementRendered.appendChild(await this.addPdfAnnotations(pdfjsLib, page, viewport, annotationData));
        }

        // Image previews
        const panelPreview = document.createElement('button');
        panelPreview.dataset.page = String(index + 1);
        panelPreview.classList.add('preview-panel');
        const target = new Image();
        target.src = canvas.toDataURL('image/jpeg');
        const pageNumber = document.createElement('span');
        pageNumber.classList.add('preview-panel__page-number');
        pageNumber.innerText = String(index + 1);
        panelPreview.append(target, pageNumber);
        if (previewPanelsContainer) {
          previewPanelsContainer.appendChild(panelPreview);
        }
      });
    } catch (e) {
      console.log(e);
    }
  }

  /** Add PDF-sourced annotations, such as links
   */
  async addPdfAnnotations (pdfjsLib: iPdfLib, page: any, viewport: any, annotationData: any) {
    const annotationLayer = document.createElement('div');
    annotationLayer.classList.add('annotationLayer');
    pdfjsLib.AnnotationLayer.render({
      viewport: viewport.clone({ dontFlip: true }),
      div: annotationLayer,
      annotations: annotationData,
      page: page,
      linkService: {
        addLinkAttributes (a: HTMLAnchorElement, url: string, newWindow: boolean) {
          a.setAttribute('href', url);
          a.setAttribute('target', '_blank');
        },
        getDestinationHash (dst: any) {
          return '#' + dst;
        }
      }
    });

    // handle link clicks
    annotationLayer.querySelectorAll('.linkAnnotation').forEach((el) => {
      el.addEventListener('click', (e) => {
        const a = el.querySelector('a');
        if (a) {
          const url = a.getAttribute('href') || '';
          if (url.startsWith('#')) {
            document.location = url;
          } else {
            window.open(url, '_blank');
          }
        }
      });
    });
    return annotationLayer;
  }

  decoratePdf () {
    const marks: { style: { backgroundColor: string; }; setAttribute: (arg0: string, arg1: string) => void; }[] = [];

    for (const item of items) {
      const range = targetToRange(item.target, this.pdfContentWrapper);
      markRange(range, 'a', (element: { style: { backgroundColor: string; }; setAttribute: (arg0: string, arg1: string) => void; }) => {
        element.style.backgroundColor = 'red';
        element.setAttribute('href', '#');
        marks.push(element);
        return element;
      });
      this.pdfContentMarks.push({
        ...item,
        marks
      });
    }
  }
}

export default PdfRenderer;

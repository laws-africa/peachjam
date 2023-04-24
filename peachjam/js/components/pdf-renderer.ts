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
    this.pdfUrl = 'https://archive.gazettes.africa/archive/za/2023/za-government-gazette-regulation-gazette-dated-2023-01-31-no-47970.pdf'; // root.dataset.pdf;
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
    if (this.progressBarElement) {
      this.progressBarElement.style.width = `${progress}%`;
      this.progressBarElement.innerText = `${Math.ceil(progress)}%`;
    }
  }

  loadPdf () {
    this.root.removeAttribute('data-large-pdf');
    this.setupPdfAndPreviewPanels().then(() => {
      this.root.removeAttribute('data-pdf-loading');
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

    const asyncForEach = async (array: any[], callback: (arg0: any, arg1: number, arg2: any[]) => any) => {
      for (let index = 0; index < array.length; index++) {
        await callback(array[index], index, array);
      }
    };

    // load the PDF asynchronously
    const loadingTask = pdfjsLib.getDocument(this.pdfUrl);

    this.root.removeAttribute('data-pdf-standby');
    this.root.setAttribute('data-pdf-loading', '');
    loadingTask.onProgress = (data: { loaded: number, total: number }) => {
      if (data.total) {
        /*
        * The progress bar represents the progress of two processes
        *  1) loading the pdf data (first 50%)
        *  2) creating the pdf associating html and inserting it into the DOM (last 50%)
        * */
        this.setLoadingProgress(data.loaded / data.total / 2 * 100);
      }
    };

    try {
      const pdf = await loadingTask.promise;
      const numPages = pdf.numPages;
      const listOfGetPages = Array.from(Array(numPages), (_, index) => pdf.getPage(index + 1));
      const pages = await Promise.all(listOfGetPages);

      await asyncForEach(pages, async (page, index) => {
        const docElement = document.querySelector('[data-document-element]');
        if (!docElement) return;
        const docElementWidth = docElement.clientWidth || 0;
        const scale = 2;
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

        const renderTask = page.render(renderContext);
        elementRendered.appendChild(canvas);
        // Canvas must be mounted first so textLayer can get offset values
        if (this.pdfContentWrapper) {
          this.pdfContentWrapper.appendChild(elementRendered);
        }

        await renderTask.promise;

        const textContent = await page.getTextContent();
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
          textContent,
          container: textLayer,
          viewport,
          textDivs: []
        });
        elementRendered.appendChild(textLayer);

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
        const previewPanelsContainer = this.root.querySelector('.pdf-previews');
        if (previewPanelsContainer) {
          previewPanelsContainer.appendChild(panelPreview);
        }
        // first 50% is loading the file
        this.setLoadingProgress(50 + (index + 1) / numPages * 100 / 2);
      });
    } catch (e) {
      console.log(e);
    }
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

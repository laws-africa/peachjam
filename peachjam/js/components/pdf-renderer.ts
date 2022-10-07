import debounce from 'lodash/debounce';
import items from '../items.json';
// @ts-ignore
import { markRange, rangeToTarget, targetToRange } from '../dom';
import { scrollToElement } from '../utils/function';

type GlobalWorkerOptionsType = {
  [key: string]: any,
  workerSrc: string
}

type PageType = {
  [key: string]: any,
  view: [left: number, top: number, width: number, height: number]
}

interface iPdfLib {
  [key: string]: any,
  GlobalWorkerOptions: GlobalWorkerOptionsType,
}

class PdfRenderer {
  protected pdf: any;
  protected pdfContentWrapper: HTMLElement | null;
  protected root: HTMLElement;
  protected scrollListenerActive: boolean;
  protected pdfContentMarks: any[];
  public onPreviewPanelClick: () => void;
  public onPdfLoaded: () => void;
  constructor (root: HTMLElement) {
    this.root = root;
    this.pdf = root.dataset.pdf;
    this.pdfContentWrapper = root.querySelector('.pdf-content');
    this.scrollListenerActive = true;
    this.pdfContentMarks = [];
    this.onPreviewPanelClick = () => {};
    this.root.addEventListener('preview-panel-clicked', () => {
      this.onPreviewPanelClick();
    });
    this.onPdfLoaded = () => {};
    this.root.addEventListener('pdf-loaded', () => this.onPdfLoaded());

    const observer = new MutationObserver(() => {
      const progressBarElement: HTMLElement | null = root.querySelector('.progress-bar');
      const loadingProgress = root.getAttribute('data-loading-progress');
      if (progressBarElement && loadingProgress) {
        progressBarElement.style.width = `${parseFloat(loadingProgress) * 100}%`;
        progressBarElement.innerText = `${Math.ceil(parseFloat(loadingProgress) * 100)}%`;
      }
    });
    observer.observe(this.root, {
      attributeFilter: ['data-loading-progress']
    });

    this.root.querySelector('button[data-load-doc-button]')?.addEventListener('click', () => {
      this.loadPdf();
    });

    if (Object.keys(this.root.dataset).includes('largePdf')) return;
    this.loadPdf();
  }

  loadPdf () {
    this.root.removeAttribute('data-large-pdf');
    this.setupPdfAndPreviewPanels().then(() => {
      this.root.removeAttribute('data-loading-progress');
      this.root.removeAttribute('data-pdf-loading');
      this.root.dispatchEvent(new CustomEvent('pdf-loaded'));

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
          if (!current) return;
          this.activatePreviewPanel(current);
          const scrollableContainer = this.root.querySelector('[data-preview-scroll-container]');
          if (!scrollableContainer) return;
          scrollableContainer.scrollTop = (current.offsetTop + current.clientHeight) - (current.offsetHeight * 2);
        }
      }, 20));
    }).catch((e:ErrorEvent) => {
      this.root.innerText = e.message;
    });
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
    this.root.dispatchEvent(new CustomEvent('preview-panel-clicked'));
    if (!e.currentTarget) return;
    this.activatePreviewPanel(e.currentTarget);
    if (!(e.currentTarget instanceof HTMLElement)) return;
    this.scrollToPage(e.currentTarget.dataset.page);
  }

  scrollToPage (pageNumber: string | number | undefined) {
    const targetPage = this.root.querySelector(`.pdf-content__page[data-page="${pageNumber}"]`);
    if (!targetPage) return;
    this.scrollListenerActive = false;
    scrollToElement(targetPage as HTMLElement).then(() => {
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
    const asyncForEach = async (array: any[], callback: (arg0: any, arg1: number, arg2: any[]) => any) => {
      for (let index = 0; index < array.length; index++) {
        await callback(array[index], index, array);
      }
    };
    pdfjsLib.GlobalWorkerOptions.workerSrc = '/static/lib/pdfjs/pdf.worker.js';

    const loadingTask = pdfjsLib.getDocument(this.pdf);

    this.root.removeAttribute('data-pdf-standby');
    this.root.setAttribute('data-pdf-loading', '');
    loadingTask.onProgress = (data: { loaded: number }) => {
      if (this.root.dataset.pdfSize) {
        /*
        * The progress bar represents the progress of two processes
        *  1) loading the pdf data (first 50%)
        *  2) creating the pdf associating html and inserting it into the DOM (last 50%)
        * */
        this.root.setAttribute('data-loading-progress', `${data.loaded / parseInt(this.root.dataset.pdfSize) / 2}`);
      }
    };

    try {
      const pdf = await loadingTask.promise;
      const numPages = pdf.numPages;
      const listOfGetPages = Array.from(Array(numPages), (_, index) => pdf.getPage(index + 1));
      const pages = await Promise.all(listOfGetPages);
      await asyncForEach(pages, async (page: PageType, index) => {
        const docElement = document.querySelector('[data-document-element]');
        const docElementWidth = docElement?.clientWidth || 0;
        /*
        * Determine scale to fit document element width
        * page.view[2] is page width
        * */
        const scale = (docElementWidth / page.view[2]);

        const viewport = page.getViewport({ scale });

        const canvas = document.createElement('canvas');
        canvas.style.display = 'block';
        const context = canvas.getContext('2d');
        canvas.width = docElementWidth;
        // page.view[3] is height
        canvas.height = page.view[3] * scale;

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

        textLayer.style.left = `${canvas.offsetLeft}px`;
        textLayer.style.top = `${canvas.offsetTop}px`;
        textLayer.style.height = `${canvas.height}px`;
        textLayer.style.width = `${canvas.width}px`;

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
        const currentLoadingProgress = this.root.getAttribute('data-loading-progress');
        if (currentLoadingProgress) {
          const progressIncrement = 0.5 / pages.length;
          this.root.setAttribute('data-loading-progress', `${parseFloat(currentLoadingProgress) + progressIncrement}`);
        }
      });
    } catch (e) {
      console.log(e);
    }
  }

  decoratePdf () {
    const marks: { style: { backgroundColor: string; }; setAttribute: (arg0: string, arg1: string) => void; }[] = [];
    items.forEach(item => {
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
    });
  }
}

export default PdfRenderer;

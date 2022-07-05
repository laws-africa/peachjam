import debounce from 'lodash/debounce';
import items from '../items.json';
// @ts-ignore
import { markRange, rangeToTarget, targetToRange } from '../dom';

type GlobalWorkerOptionsType = {
  [key: string]: any,
  workerSrc: string
}

interface iPdfLib {
  [key: string]: any,
  GlobalWorkerOptions: GlobalWorkerOptionsType,
}

class PdfRenderer {
  protected pdf: any;
  protected pdfContentWrapper: HTMLElement | null;
  protected previewPanelsContainer: HTMLElement | null;
  protected root: HTMLElement;
  protected scrollListenerActive: boolean;
  protected pdfContentMarks: any[];
  private readonly pdfSize: string | undefined;
  private tabContent: HTMLElement | null;
  constructor (root: HTMLElement) {
    this.root = root;
    this.pdf = root.dataset.pdf;
    this.pdfSize = root.dataset.pdfSize;
    this.pdfContentWrapper = root.querySelector('.pdf-content');
    this.tabContent = root.querySelector('.pdf-tab-content');
    this.previewPanelsContainer = root.querySelector('.pdf-previews');
    this.scrollListenerActive = true;
    this.pdfContentMarks = [];

    const observer = new MutationObserver(() => {
      const progressBarElement: HTMLElement | null = root.querySelector('.progress-bar');
      const loadingProgress = root.getAttribute('data-loading-progress');
      if (progressBarElement && loadingProgress) {
        progressBarElement.style.width = `${parseFloat(loadingProgress) * 100}%`;
        progressBarElement.innerText = `${Math.ceil(parseFloat(loadingProgress) * 100)}%`;
      }
    });
    observer.observe(this.root, { attributes: true });
    this.setupPdfAndPreviewPanels().then(() => {
      this.root.removeAttribute('data-loading-progress');
      this.root.removeAttribute('data-is-loading');

      const pages: Array<HTMLElement> = Array.from(this.root.querySelectorAll('.pdf-content__page'));
      const previewPanels = Array.from(root.querySelectorAll('.preview-panel'));
      for (const previewPanel of previewPanels) {
        previewPanel.addEventListener('click', (e) => this.handlePreviewPanelClick(e));
      }

      window.addEventListener('scroll', debounce(() => {
        if (this.scrollListenerActive) {
          let current: HTMLElement | null;
          for (const page of pages) {
            if (window.scrollY >= page.offsetTop) {
              current = root.querySelector(`.preview-panel[data-page="${page.dataset.page}"]`);
              if (current) {
                this.activatePreviewPanel(current);
                if (this.tabContent) {
                  this.tabContent.scrollTop = (current.offsetTop + current.clientHeight) - (current.offsetHeight * 2);
                }
              }
            }
          }
        }
      }, 20));
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
    const targetPage = e.currentTarget && e.currentTarget instanceof HTMLElement
      ? this.root.querySelector(`.pdf-content__page[data-page="${e.currentTarget.dataset.page}"]`)
      : null;
    if (e.currentTarget) {
      this.activatePreviewPanel(e.currentTarget);
    }
    if (targetPage) {
      this.scrollListenerActive = false;
      let scrollTimeout:ReturnType<typeof setTimeout>;
      const windowScrollerListn = () => {
        clearTimeout(scrollTimeout);
        scrollTimeout = setTimeout(() => {
          window.removeEventListener('scroll', windowScrollerListn);
          this.scrollListenerActive = true;
        }, 100);
      };
      window.addEventListener('scroll', windowScrollerListn);
      targetPage.scrollIntoView({ behavior: 'smooth' });
    }
  }

  async setupPdfAndPreviewPanels () {
    const pdfjsLib = (window as { [key: string]: any })['pdfjs-dist/build/pdf'] as iPdfLib;
    const asyncForEach = async (array: any[], callback: (arg0: any, arg1: number, arg2: any[]) => any) => {
      for (let index = 0; index < array.length; index++) {
        await callback(array[index], index, array);
      }
    };
    pdfjsLib.GlobalWorkerOptions.workerSrc = '/static/lib/pdfjs/pdf.worker.js';

    const loadingTask = pdfjsLib.getDocument(this.pdf);

    loadingTask.onProgress = (data: { loaded: number }) => {
      if (this.pdfSize) {
        /*
        * The progress bar represents the progress of two processes
        *  1) loading the pdf data (first 50%)
        *  2) creating the pdf associating html and inserting it into the DOM (last 50%)
        * */
        this.root.setAttribute('data-loading-progress', `${data.loaded / parseInt(this.pdfSize) / 2}`);
      }
    };

    try {
      this.root.setAttribute('data-is-loading', '');
      const pdf = await loadingTask.promise;
      const numPages = pdf.numPages;
      const listOfGetPages = Array.from(Array(numPages), (_, index) => pdf.getPage(index + 1));
      const pages = await Promise.all(listOfGetPages);
      await asyncForEach(pages, async (page, index) => {
        const viewport = page.getViewport({ scale: 1 });
        const elementRendered = document.createElement('div');
        elementRendered.setAttribute('id', String(index + 1));
        elementRendered.dataset.page = String(index + 1);
        elementRendered.classList.add('pdf-content__page');
        elementRendered.style.position = 'relative';
        const canvas = document.createElement('canvas');
        canvas.style.display = 'block';
        const context = canvas.getContext('2d');
        canvas.height = viewport.height;
        canvas.width = viewport.width;

        const renderContext = {
          canvasContext: context,
          viewport
        };
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
        if (this.previewPanelsContainer) {
          this.previewPanelsContainer.appendChild(panelPreview);
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

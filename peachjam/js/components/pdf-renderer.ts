import debounce from 'lodash/debounce';

class PdfRenderer {
  protected pdf: any;
  protected pdfContentWrapper: HTMLElement | null;
  protected previewPanelsContainer: HTMLElement | null;
  private root: HTMLElement;
  protected scrollListenerActive: boolean;
  constructor (root: HTMLElement) {
    this.root = root;
    this.pdf = root.dataset.pdf;
    this.pdfContentWrapper = root.querySelector('.pdf-renderer__content');
    this.previewPanelsContainer = root.querySelector('.pdf-renderer__previews__inner');
    this.scrollListenerActive = true;

    this.setupPdfAndPreviewPanels().then(() => {
      const pages = Array.from(this.root.querySelectorAll('.pdf-renderer__content__page'));
      const previewPanels = Array.from(root.querySelectorAll('.preview-panel'));
      for (const previewPanel of previewPanels) {
        previewPanel.addEventListener('click', (e) => this.handlePreviewPanelClick(e));
      }

      window.addEventListener('scroll', debounce(() => {
        if (this.scrollListenerActive) {
          let current: HTMLElement;
          for (const page of pages) {
            // @ts-ignore
            if (window.scrollY >= page.offsetTop) {
              // @ts-ignore
              current = root.querySelector(`.preview-panel[data-page="${page.dataset.page}"]`);
              this.activatePreviewPanel(current);
              if (this.previewPanelsContainer) {
                this.previewPanelsContainer.scrollTop = current.offsetTop - (current.offsetHeight * 2);
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
    // @ts-ignore
    const targetPage = this.root.querySelector(`.pdf-renderer__content__page[data-page="${e.currentTarget.dataset.page}"]`);
    if (e.currentTarget) {
      this.activatePreviewPanel(e.currentTarget);
    }
    if (targetPage) {
      this.scrollListenerActive = false;
      // eslint-disable-next-line no-undef
      let scrollTimeout: NodeJS.Timeout;
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
    // @ts-ignore
    const pdfjsLib = window['pdfjs-dist/build/pdf'];
    const asyncForEach = async (array: any[], callback: (arg0: any, arg1: number, arg2: any[]) => any) => {
      for (let index = 0; index < array.length; index++) {
        await callback(array[index], index, array);
      }
    };
    pdfjsLib.GlobalWorkerOptions.workerSrc = '/static/lib/pdfjs/pdf.worker.js';
    const loadingTask = pdfjsLib.getDocument(this.pdf);
    try {
      const pdf = await loadingTask.promise;
      const numPages = pdf.numPages;
      const listOfGetPages = Array.from(Array(numPages), (_, index) => pdf.getPage(index + 1));
      const pages = await Promise.all(listOfGetPages);
      await asyncForEach(pages, async (page, index) => {
        const viewport = page.getViewport({ scale: 1 });

        const elementRendered = document.createElement('div');
        // @ts-ignore
        elementRendered.dataset.page = index + 1;
        elementRendered.classList.add('pdf-renderer__content__page');
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
      });
    } catch (e) {
      console.log(e);
    }
  }
}

export default PdfRenderer;

import { createApp } from 'vue';
import DocumentSearch from './DocumentSearch/index.vue';

class DocumentContent {
  protected root: HTMLElement;
  constructor (root: HTMLElement) {
    this.root = root;
    const aknDoc: HTMLElement | null = root.querySelector('la-akoma-ntoso');
    const htmlDoc: HTMLElement | null = root.querySelector('[data-html-doc]');
    const pdfDoc: HTMLElement| null = root.querySelector('[data-component="PdfRenderer"]');
    if (aknDoc) {
      this.renderDocSearch(aknDoc, 'akn', '#akn-doc-search');
    } else if (htmlDoc) {
      this.renderDocSearch(htmlDoc, 'html', '#html-doc-search');
    } else if (pdfDoc) {
      this.renderDocSearch(pdfDoc, 'pdf', '#pdf-doc-search');
    }
  }

  renderDocSearch (document: HTMLElement, docType: string, targetSelector: string) {
    const targetMountElement = this.root.querySelector(targetSelector);
    if (targetMountElement) {
      createApp(DocumentSearch, {
        document,
        docType: docType
      }).mount(targetMountElement);
    }
  }
}

export default DocumentContent;

import FindDocuments from './FindDocuments/index.vue';
import PdfRenderer from './pdf-renderer';
import DocumentList from './document-list';

const components: Record<string, any> = {
  // Data components
  PdfRenderer,
  DocumentList,
  // Vue components
  FindDocuments
};

export default components;

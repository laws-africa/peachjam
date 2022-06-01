import FindDocuments from './FindDocuments/index.vue';
import PdfRenderer from './pdf-renderer';
import DocumentList from './document-list';
import DocumentContent from './document-content';

const components: Record<string, any> = {
  // Data components
  PdfRenderer,
  DocumentList,
  DocumentContent,
  // Vue components
  FindDocuments
};

export default components;

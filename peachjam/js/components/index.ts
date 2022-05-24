import FindDocuments from './FindDocuments/index.vue';
import PdfRenderer from './pdf-renderer';
import { RelationshipEnrichments } from './RelationshipEnrichment';
import DocumentList from './document-list';

const components: Record<string, any> = {
  // Data components
  PdfRenderer,
  DocumentList,
  RelationshipEnrichments,
  // Vue components
  FindDocuments
};

export default components;

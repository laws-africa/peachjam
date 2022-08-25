import FindDocuments from './FindDocuments/index.vue';
import PdfRenderer from './pdf-renderer';
import { RelationshipEnrichments } from './RelationshipEnrichment';
import DocumentList from './document-list';
import DocumentContent from './document-content';
import NavigationSelect from './navigation-select';

const components: Record<string, any> = {
  // Data components
  PdfRenderer,
  DocumentList,
  RelationshipEnrichments,
  DocumentContent,
  NavigationSelect,
  // Vue components
  FindDocuments
};

export default components;

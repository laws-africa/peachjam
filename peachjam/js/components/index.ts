import { CopyToClipboard } from './clipboard';
import { RelationshipEnrichments } from './RelationshipEnrichment';
import DocumentFilterForm from './document-filter-form';
import DocumentTable from './document-table';
import DocumentContent from './DocumentContent/index';
import NavigationSelect from './navigation-select';
import { ToggleTab } from './tabs';
import TaxonomyTree from './taxonomy-tree';
import TermsOfUse from './terms-of-use';

import DocumentProblemModal from './DocumentProblemModal.vue';
import FindDocuments from './FindDocuments/index.vue';
import PocketLawDownload from './PocketLawDownload.vue';
import SaveDocumentModal from './SaveDocumentModal.vue';

const components: Record<string, any> = {
  // Data components
  CopyToClipboard,
  DocumentContent,
  DocumentFilterForm,
  DocumentTable,
  NavigationSelect,
  RelationshipEnrichments,
  ToggleTab,
  TaxonomyTree,
  TermsOfUse,

  // Vue components
  SaveDocumentModal,
  DocumentProblemModal,
  FindDocuments,
  PocketLawDownload
};

export default components;

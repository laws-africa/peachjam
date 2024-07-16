import { CopyToClipboard } from './clipboard';
import { RelationshipEnrichments } from './RelationshipEnrichment';
import DocumentList from './document-list';
import DocumentTable from './document-table';
import DocumentContent from './DocumentContent/index';
import NavigationSelect from './navigation-select';
import { ToggleTab } from './tabs';
import TaxonomyTree from './taxonomy-tree';
import TermsOfUse from './terms-of-use';

import DocumentProblemModal from './DocumentProblemModal.vue';
import FindDocuments from './FindDocuments/index.vue';
import PocketLawDownload from './PocketLawDownload.vue';

const components: Record<string, any> = {
  // Data components
  CopyToClipboard,
  DocumentContent,
  DocumentTable,
  DocumentList,
  NavigationSelect,
  RelationshipEnrichments,
  ToggleTab,
  TaxonomyTree,
  TermsOfUse,

  // Vue components
  DocumentProblemModal,
  FindDocuments,
  PocketLawDownload
};

export default components;

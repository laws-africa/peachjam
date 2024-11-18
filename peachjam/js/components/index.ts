import { CopyToClipboard } from './clipboard';
import { RelationshipEnrichments } from './RelationshipEnrichment';
import DocumentFilterForm from './document-filter-form';
import DocumentTable from './document-table';
import DocumentContent from './DocumentContent/index';
import NavigationSelect from './navigation-select';
import { ToggleTab } from './tabs';
import TaxonomyTree from './taxonomy-tree';
import TermsOfUse from './terms-of-use';
import SearchTypeahead from './search-typeahead';

import DocumentProblemModal from './DocumentProblemModal.vue';
import FindDocuments from './FindDocuments/index.vue';
import PocketLawDownload from './PocketLawDownload.vue';
import TaxonomyTopics from './TaxonomyTopics.vue';

const components: Record<string, any> = {
  // Data components
  CopyToClipboard,
  DocumentContent,
  DocumentFilterForm,
  DocumentTable,
  NavigationSelect,
  RelationshipEnrichments,
  SearchTypeahead,
  ToggleTab,
  TaxonomyTree,
  TermsOfUse,

  // Vue components
  DocumentProblemModal,
  FindDocuments,
  PocketLawDownload,
  TaxonomyTopics
};

export default components;

<template>
  <div id="search" ref="search-box">
    <div class="mb-4">
      <nav>
        <div
          id="nav-tab"
          class="nav nav-tabs mb-3"
          role="tablist"
        >
          <button
            id="search-tab"
            class="nav-link active"
            data-bs-toggle="tab"
            data-bs-target="#nav-search"
            type="button"
            role="tab"
            aria-controls="nav-search"
            aria-selected="true"
          >
            {{ $t('Search') }}
          </button>
          <button
            id="advanced-search-tab"
            class="nav-link"
            data-bs-toggle="tab"
            data-bs-target="#nav-advanced-search"
            type="button"
            role="tab"
            aria-controls="nav-advanced-search"
            aria-selected="false"
          >
            {{ $t('Advanced search') }}
          </button>
        </div>
      </nav>
      <div
        id="nav-tabContent"
        class="tab-content"
      >
        <div
          id="nav-search"
          class="tab-pane fade show active"
          role="tabpanel"
          aria-labelledby="search-tab"
        >
          <form
            class="d-flex align-items-center mb-2"
            @submit.prevent="simpleSearch"
          >
            <input
              v-model="q"
              type="text"
              class="form-control"
              :placeholder="searchPlaceholder"
              :aria-label="$t('Search documents')"
              aria-describedby="basic-addon2"
              required
            >
            <button
              type="submit"
              class="btn btn-primary ms-1"
              :disabled="loading"
            >
              <span
                v-if="loading"
                class="circle-loader--lt"
              />
              <span v-else>{{ $t("Search") }}</span>
            </button>
            <button
              v-if="searchInfo.count"
              type="button"
              class="btn btn-secondary ms-1 d-lg-none text-nowrap"
              @click="() => drawerOpen = true"
            >
              Filters <span v-if="selectedFacetsCount">({{ selectedFacetsCount }})</span>
            </button>
          </form>
          <div class="my-2">
            <HelpBtn page="search/" />
          </div>
        </div>
        <div
          id="nav-advanced-search"
          class="tab-pane fade"
          role="tabpanel"
          aria-labelledby="advanced-search-tab"
        >
          <AdvancedSearch
            v-model="advancedFields"
            :global-search-value="q"
            @global-search-change="value => q = value"
            @submit="submit"
          />
        </div>
      </div>

      <div
        v-if="error"
        class="mt-3 alert alert-warning"
      >
        {{ $t("Oops, something went wrong.") }} {{ error }}
      </div>
      <div
        v-if="searchInfo.count === 0"
        class="mt-3"
      >
        {{ $t("No documents match your search.") }}
      </div>
    </div>
    <div ref="filters-results-container">
      <FacetBadges v-model="facets" :facets="facets" />
      <div class="row">
        <div class="col col-lg-3">
          <MobileFacetsDrawer
            :open="drawerOpen"
            @outside-drawer-click="() => drawerOpen = false"
          >
            <FilterFacets
              v-if="searchInfo.count"
              v-model="facets"
              :loading="loading"
            >
              <template #header-title>
                <button
                  type="button"
                  class="btn-close d-lg-none"
                  :aria-label="$t('Close')"
                  @click="() => drawerOpen = false"
                />
                <strong class="filter-facet-title">{{ $t("Filters") }}</strong>
              </template>
            </FilterFacets>
          </MobileFacetsDrawer>
        </div>

        <div class="col-md-12 col-lg-9 search-pane position-relative">
          <div class="search-results">
            <div v-if="searchInfo.count">
              <div class="mb-3 sort-body row">
                <div class="col-md-3 order-md-2 mb-2 sort__inner d-flex align-items-center">
                  <div style="width: 65px;">
                    {{ $t('Sort by') }}
                  </div>
                  <select
                    v-model="ordering"
                    class="ms-2 form-select"
                  >
                    <option value="-score">
                      {{ $t('Relevance') }}
                    </option>
                    <option value="date">
                      {{ $t('Date (oldest first)') }}
                    </option>
                    <option value="-date">
                      {{ $t('Date (newest first)') }}
                    </option>
                  </select>
                </div>
                <div class="col-md order-md-1">
                  {{ $t('{document_count} documents found', { document_count: searchInfo.count }) }}
                </div>
              </div>

              <ul class="list-unstyled">
                <SearchResult
                  v-for="item in searchInfo.results"
                  :key="item.key"
                  :item="item"
                  :query="q"
                  :show-jurisdiction="showJurisdiction"
                  :document-labels="documentLabels"
                />
              </ul>

              <SearchPagination
                :search="searchInfo"
                :page="page"
                @changed="handlePageChange"
              />
            </div>
          </div>
          <div
            v-if="loading && searchInfo.count"
            class="overlay"
          />
        </div>
      </div>

      <a
        href="#search"
        class="to-the-top btn btn-secondary d-block d-lg-none"
      >
        ▲ {{ $t('To the top') }}
      </a>
    </div>

    <!-- DOM Hack for i18next to parse facet to locale json. i18next skips t functions in script element -->
    <div v-if="false">
      {{ $t('Document type') }}
      {{ $t('Author') }}
      {{ $t('Court') }}
      {{ $t('Court registry') }}
      {{ $t('Judges') }}
      {{ $t('Attorneys') }}
      {{ $t('Order') }}
      {{ $t('Jurisdiction') }}
      {{ $t('Locality') }}
      {{ $t('Matter type') }}
      {{ $t('Document nature') }}
      {{ $t('Language') }}
      {{ $t('Year') }}
    </div>
  </div>
</template>

<script>
import SearchResult from './SearchResult.vue';
import SearchPagination from './SearchPagination.vue';
import FilterFacets from '../FilterFacets/index.vue';
import MobileFacetsDrawer from './MobileSideDrawer.vue';
import AdvancedSearch from './AdvancedSearch.vue';
import HelpBtn from '../HelpBtn.vue';
import { scrollToElement } from '../../utils/function';
import FacetBadges from './FacetBadges.vue';

function resetAdvancedFields (fields) {
  const advanced = ['all', 'title', 'judges', 'case_summary', 'flynote', 'content'];
  for (const a of advanced) {
    fields[a] = {
      q: '',
      all: '',
      exact: '',
      any: '',
      none: ''
    };
  }

  fields.date = {
    date_to: null,
    date_from: null
  };
}

export default {
  name: 'FindDocuments',
  components: { FacetBadges, MobileFacetsDrawer, SearchResult, SearchPagination, FilterFacets, AdvancedSearch, HelpBtn },
  props: ['showJurisdiction'],
  data () {
    const getLabelOptionLabels = (labels) => {
      // the function name is a bit confusing but this gets labels for the options in Labels facet
      const labelOptions = {};
      for (const label of labels) {
        labelOptions[label.code] = label.name;
      }
      return labelOptions;
    };

    const data = {
      searchPlaceholder: JSON.parse(document.querySelector('#data-labels').textContent).searchPlaceholder,
      documentLabels: JSON.parse(document.querySelector('#data-labels').textContent).documentLabels,
      loadingCount: 0,
      error: null,
      searchInfo: {},
      page: 1,
      ordering: '-score',
      q: '',
      drawerOpen: false,
      advancedFields: {}
    };
    const facets = [
      {
        title: this.$t('Document type'),
        name: 'doc_type',
        type: 'checkboxes',
        value: [],
        options: []
      },
      {
        title: this.$t('Labels'),
        name: 'labels',
        type: 'checkboxes',
        value: [],
        options: [],
        optionLabels: getLabelOptionLabels(data.documentLabels)
      },
      {
        title: JSON.parse(document.querySelector('#data-labels').textContent).author,
        name: 'authors',
        type: 'checkboxes',
        value: [],
        options: []
      },
      {
        title: this.$t('Court'),
        name: 'court',
        type: 'checkboxes',
        value: [],
        options: []
      },
      {
        title: this.$t('Court registry'),
        name: 'registry',
        type: 'checkboxes',
        value: [],
        options: []
      },
      {
        title: this.$t('Judges'),
        name: 'judges',
        type: 'checkboxes',
        value: [],
        options: []
      },
      {
        title: this.$t('Attorneys'),
        name: 'attorneys',
        type: 'checkboxes',
        value: [],
        options: []
      },
      {
        title: this.$t('Order'),
        name: 'order_outcome',
        type: 'checkboxes',
        value: [],
        options: []
      },
      {
        title: this.$t('Locality'),
        name: 'locality',
        type: 'checkboxes',
        value: [],
        options: []
      },
      {
        title: this.$t('Matter type'),
        name: 'matter_type',
        type: 'checkboxes',
        value: [],
        options: []
      },
      {
        title: this.$t('Document nature'),
        name: 'nature',
        type: 'checkboxes',
        value: [],
        options: []
      },
      {
        title: this.$t('Language'),
        name: 'language',
        type: 'checkboxes',
        value: [],
        options: []
      },
      {
        title: this.$t('Year'),
        name: 'year',
        type: 'checkboxes',
        value: [],
        options: []
      }
    ];

    if (this.showJurisdiction) {
      facets.splice(0, 0, {
        title: this.$t('Jurisdiction'),
        name: 'jurisdiction',
        type: 'checkboxes',
        value: [],
        options: []
      });
    }

    data.facets = facets;
    resetAdvancedFields(data.advancedFields);
    return data;
  },

  computed: {
    selectedFacetsCount () {
      return this.facets.map(facet => facet.value.length).reduce((pv, cv) => pv + cv, 0);
    },
    loading () {
      return this.loadingCount > 0;
    }
  },

  watch: {
    ordering () {
      this.search();
    },

    facets: {
      handler () {
        this.page = 1;
        this.search();
      }
    }
  },

  mounted () {
    this.loadState();
    window.addEventListener('popstate', () => this.loadState());
  },

  methods: {
    sortGenericBuckets (items, reverse = false) {
      const buckets = [...items];
      buckets.sort((a, b) => a.key.localeCompare(b.key));
      if (reverse) {
        buckets.reverse();
      }
      return buckets;
    },

    getUrlParamValue (key, options) {
      const queryString = window.location.search;
      const urlParams = new URLSearchParams(queryString);
      const availableOptions = options.map(option => option.value);
      return urlParams.getAll(key).filter(value => availableOptions.includes(value));
    },

    handlePageChange (newPage) {
      this.page = newPage;
      this.search();
    },

    simpleSearch () {
      resetAdvancedFields(this.advancedFields);
      this.submit();
    },

    submit () {
      this.page = 1;
      this.search();
    },

    clearAllFilters () {
      this.facets.forEach((facet) => {
        if (facet.value.length) {
          facet.value = [];
        }
      });
    },

    serialiseState () {
      // save state to URL string
      const params = new URLSearchParams();

      if (this.q) params.set('q', this.q);
      if (this.page > 1) {
        params.set('page', this.page);
      }
      if (this.ordering !== '-score') {
        params.set('ordering', this.ordering);
      }

      this.facets.forEach((facet) => {
        facet.value.forEach((value) => {
          params.append(facet.name, value);
        });
      });

      // Set advanced fields to url
      Object.keys(this.advancedFields).forEach(key => {
        const value = this.advancedFields[key];
        if (!value) return;

        if (key === 'date') {
          if (value.date_from && value.date_to) {
            params.append('date_from', this.advancedFields.date.date_from);
            params.append('date_to', this.advancedFields.date.date_to);
          } else if (value.date_from) {
            params.append('date_from', this.advancedFields.date.date_from);
          } else if (value.date_to) {
            params.append('date_to', this.advancedFields.date.date_to);
          }
        } else {
          for (const mod of Object.keys(value)) {
            if (value[mod]) {
              params.append(`${key}_${mod}`, value[mod]);
            }
          }
        }
      });

      return params.toString();
    },

    loadState () {
      resetAdvancedFields(this.advancedFields);

      // load state from URL
      const params = new URLSearchParams(window.location.search);
      // skip the first event if there's a query, because the page load will already have sent it
      this.q = (params.get('q') || '').trim();
      this.page = parseInt(params.get('page')) || this.page;
      this.ordering = params.get('ordering') || this.ordering;

      this.facets.forEach((facet) => {
        if (params.has(facet.name)) {
          facet.value = params.getAll(facet.name);
        }
      });

      if (params.has('date_from')) this.advancedFields.date.date_from = params.get('date_from');
      if (params.has('date_to')) this.advancedFields.date.date_to = params.get('date_to');

      let showAdvanced = params.get('show-advanced-tab');
      for (const field of Object.keys(this.advancedFields)) {
        if (field !== 'date') {
          const values = this.advancedFields[field];

          for (const mod of Object.keys(values)) {
            const key = `${field}_${mod}`;
            if (params.get(key)) {
              values[mod] = params.get(key);
              showAdvanced = true;
            }
          }
        }
      }

      // if there are advance search fields or show-advanced-tab param, activate tab
      if (showAdvanced) {
        const tabTrigger = new window.bootstrap.Tab(this.$el.querySelector('#advanced-search-tab'));
        tabTrigger.show();
      }

      this.search(false);
    },

    suggest (q) {
      this.q = q;
      this.search();
    },

    formatFacets () {
      const generateOptions = (buckets, labels) => {
        return buckets.map((bucket) => ({
          label: labels ? labels[bucket.key] : bucket.key,
          count: bucket.doc_count,
          value: bucket.key
        }));
      };

      this.facets.forEach((facet) => {
        if (facet.name === 'year') {
          facet.options = generateOptions(
            this.sortGenericBuckets(
              this.searchInfo.facets[`_filter_${facet.name}`][facet.name]
                .buckets,
              true
            ),
            facet.optionLabels
          );
        } else {
          if (this.searchInfo.facets[`_filter_${facet.name}`]) {
            facet.options = generateOptions(
              this.sortGenericBuckets(
                this.searchInfo.facets[`_filter_${facet.name}`][facet.name]
                  .buckets
              ),
              facet.optionLabels
            );
          }
        }
        facet.value = this.getUrlParamValue(facet.name, facet.options);
      });
    },

    generateSearchUrl () {
      const params = new URLSearchParams();
      if (this.q) params.append('search', this.q);
      params.append('page', this.page);
      params.append('ordering', this.ordering);
      params.append('highlight', 'content');
      params.append('is_most_recent', 'true');

      this.facets.forEach((facet) => {
        facet.value.forEach((value) => {
          params.append(facet.name, value);
        });
      });

      // facets that we want the API to return
      this.facets.forEach((facet) => {
        params.append('facet', facet.name);
      });

      // advanced search fields, if any
      Object.keys(this.advancedFields).forEach(key => {
        const value = this.advancedFields[key];

        if (key === 'date') {
          if (value.date_from && value.date_to) {
            const dateFrom = value.date_from;
            const dateTo = value.date_to;
            params.append('date__range', `${dateFrom}__${dateTo}`);
          } else if (value.date_from) {
            params.append('date__gte', value.date_from);
          } else if (value.date_to) {
            params.append('date__lte', value.date_to);
          }
        } else if (value.q) {
          params.append(`search__${key}`, value.q);
        }
      });

      return `/search/api/documents/?${params.toString()}`;
    },

    async search (pushState = true) {
      // if one of the search fields is true perform search
      if (this.q || Object.values(this.advancedFields).some(f => f.q)) {
        this.loadingCount = this.loadingCount + 1;

        try {
          const url = this.generateSearchUrl();
          if (pushState) {
            window.history.pushState(
              null,
              '',
              document.location.pathname + '?' + this.serialiseState()
            );
          }
          const response = await fetch(url);

          // check that the search state hasn't changed since we sent the request
          if (url === this.generateSearchUrl()) {
            if (response.ok) {
              this.error = null;
              this.searchInfo = await response.json();
              if (this.searchInfo.count === 0) {
                this.clearAllFilters();
              }
              this.formatFacets();
            } else {
              this.error = response.statusText;
            }
          }
        } catch {
          this.error = 'Network unavailable.';
        }

        this.loadingCount = this.loadingCount - 1;
        this.drawerOpen = false;
        scrollToElement(this.$refs['search-box']);

        const tabTrigger = new window.bootstrap.Tab(this.$el.querySelector('#search-tab'));
        tabTrigger.show();
      }
    }
  }
};
</script>

<style scoped>
.search-pane {
  padding-top: 10px;
}

.overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.2);
  z-index: 9;
}

.sort-body {
  display: flex;
  justify-content: space-between;
}

@media screen and (max-width: 400px) {
  .sort-body {
    flex-direction: column;
  }
  .sort__inner {
    margin-top: 10px;
  }
}

@media screen and (max-width: 992px) {
   .filter-facet-title {
    position: absolute;
    margin: auto;
    left: 0;
    right: 0;
    width: 40px;
  }
}
</style>

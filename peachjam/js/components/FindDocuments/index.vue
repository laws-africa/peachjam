<template>
  <div id="search">
    <div class="search-input-container">
      <nav>
        <div
          id="nav-tab"
          class="nav nav-tabs mb-2"
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
            <div class="input-group">
              <input
                v-model="q"
                type="text"
                class="form-control"
                :placeholder="$t('Search documents')"
                :aria-label="$t('Search documents')"
                aria-describedby="basic-addon2"
                required
              >
              <div class="input-group-append">
                <button
                  type="submit"
                  class="btn btn-sm btn-primary"
                  style="
                border-top-right-radius: 0.2rem;
                border-bottom-right-radius: 0.2rem;
              "
                  :disabled="loading"
                >
                  <span
                    v-if="loading"
                    class="circle-loader--lt"
                  />
                  <span v-else>{{ $t("Search") }}</span>
                </button>
              </div>
              <button
                v-if="searchInfo.count"
                type="button"
                style="border-radius: 0.2rem"
                class="btn btn-sm btn-secondary ms-1 d-lg-none"
                @click="() => drawerOpen = true"
              >
                Filters <span v-if="selectedFacetsCount">({{ selectedFacetsCount }})</span>
              </button>
            </div>
          </form>
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
    <div
      ref="filters-results-container"
      class="container-fluid"
    >
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
              <div class="mb-3 sort-body">
                <div>{{ $t('{document_count} documents found', { document_count: searchInfo.count }) }}</div>
                <div class="sort__inner d-flex align-items-center">
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
              </div>

              <ul class="list-unstyled">
                <SearchResult
                  v-for="item in searchInfo.results"
                  :key="item.key"
                  :item="item"
                  :query="q"
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
import moment from 'moment';
import { scrollToElement } from '../../utils/function';

export default {
  name: 'FindDocuments',
  components: { MobileFacetsDrawer, SearchResult, SearchPagination, FilterFacets, AdvancedSearch },
  data () {
    return {
      loadingCount: 0,
      error: null,
      searchInfo: {},
      page: 1,
      ordering: '-score',
      q: '',
      drawerOpen: false,
      advancedFields: {
        title: '',
        judges: '',
        headnote_holding: '',
        flynote: '',
        content: '',
        date: {
          date_from: null,
          date_to: null
        }
      },
      facets: [
        {
          title: this.$t('Document type'),
          name: 'doc_type',
          type: 'checkboxes',
          value: [],
          options: []
        },
        {
          title: JSON.parse(document.querySelector('#data-labels').textContent).author,
          name: 'author',
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
          title: this.$t('Jurisdiction'),
          name: 'jurisdiction',
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
      ]
    };
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

    getUrlParamValue (key) {
      const queryString = window.location.search;
      const urlParams = new URLSearchParams(queryString);
      return urlParams.getAll(key);
    },

    handlePageChange (newPage) {
      this.page = newPage;
      this.search();
    },

    clearAdvancedFields () {
      this.advancedFields.title = '';
      this.advancedFields.judges = '';
      this.advancedFields.headnote_holding = '';
      this.advancedFields.flynote = '';
      this.advancedFields.content = '';
      this.advancedFields.date.date_to = null;
      this.advancedFields.date.date_from = null;
    },

    simpleSearch () {
      this.clearAdvancedFields();
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
        } else if (key !== 'date') {
          params.append(key, value);
        }
      });

      return params.toString();
    },

    loadState () {
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

      const advancedSearchFields = Object.keys(this.advancedFields).filter(key => key !== 'date');
      /**
      * if there are advance search fields url params (title, judges, flynote) or show-advanced-tab param, prefill
       * fields and activate advanced tab
      * */
      if (advancedSearchFields.some(key => params.has(key)) || params.get('show-advanced-tab')) {
        if (params.has('date_from')) this.advancedFields.date.date_from = params.get('date_from');
        if (params.has('date_to')) this.advancedFields.date.date_to = params.get('date_to');
        advancedSearchFields.forEach(key => {
          if (!params.has(key)) return;
          this.advancedFields[key] = params.get(key);
        });
        const tabTrigger = new window.bootstrap.Tab(this.$el.querySelector('#advanced-search-tab'));
        tabTrigger.show();
      }
      this.search();
    },

    suggest (q) {
      this.q = q;
      this.search();
    },

    formatFacets () {
      const generateOptions = (buckets) => {
        return buckets.map((bucket) => ({
          label: bucket.key,
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
            )
          );
        } else {
          facet.options = generateOptions(
            this.sortGenericBuckets(
              this.searchInfo.facets[`_filter_${facet.name}`][facet.name]
                .buckets
            )
          );
        }
        facet.value = this.getUrlParamValue(facet.name);
      });
    },

    async search () {
      // if one of the search fields is true perform search
      if (this.q || ['title', 'judges', 'headnote_holding', 'flynote', 'content'].some(key => this.advancedFields[key])) {
        const generateUrl = () => {
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
          Object.keys(this.advancedFields).forEach(key => {
            const value = this.advancedFields[key];
            if (!value) return;

            if (key === 'date') {
              if (value.date_from && value.date_to) {
                const dateFrom = moment(value.date_from).format('YYYY-MM-DD');
                const dateTo = moment(value.date_to).format('YYYY-MM-DD');
                params.append('date__range', `${dateFrom}__${dateTo}`);
              } else if (value.date_from) {
                params.append('date__gte', moment(value.date_from).format('YYYY-MM-DD'));
              } else if (value.date_to) {
                params.append('date__lte', moment(value.date_to).format('YYYY-MM-DD'));
              }
            } else if (key !== 'date') {
              params.append(`search__${key}`, value);
            }
          });
          return `${
              window.location.origin
          }/search/api/documents/?${params.toString()}`;
        };

        this.loadingCount = this.loadingCount + 1;
        try {
          const url = generateUrl();
          const response = await fetch(generateUrl());
          if (url === generateUrl()) {
            if (response.ok) {
              this.error = null;
              this.searchInfo = await response.json();
              if (this.searchInfo.count === 0) {
                this.clearAllFilters();
              }
              window.history.replaceState(
                null,
                '',
                document.location.pathname + '?' + this.serialiseState()
              );
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
        scrollToElement(this.$refs['filters-results-container']);
      }
    }
  }
};
</script>

<style scoped>
.search-input-container {
  background-color: white;
  width: 66%;
  margin-left: auto;
  margin-right: auto;
  padding-bottom: 1rem;
}

@media screen and (max-width: 992px) {
  .search-input-container {
    width: 100%;
  }
}

.search-input-container button[type="submit"] {
  height: 100%;
}

.search-facets {
  position: sticky;
  top: 0px;
  padding-top: 0;
  max-height: 100vh;
  height: 100%;
  overflow-y: auto;
  z-index: 99;
}

.search-facets .list-group-item {
  border-radius: 0px;
}

.search-facets__header {
  position: sticky;
  top: 0;
  left: 0;
  z-index: 99;
}

.search-pane {
  padding-top: 10px;
}

.search-facets .card-body {
  max-height: 25vh;
  overflow-y: auto;
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

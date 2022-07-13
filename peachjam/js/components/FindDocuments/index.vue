<template>
  <div id="search">
    <div class="search-input-container">
      <form
        class="d-flex align-items-center"
        @submit.prevent="handleSubmit"
      >
        <div class="input-group">
          <input
            ref="search-input"
            type="text"
            class="form-control"
            placeholder="Search documents"
            aria-label="Search documents"
            aria-describedby="basic-addon2"
            required
          >
          <div class="input-group-append">
            <button
              type="submit"
              class="btn btn-sm btn-primary"
              style="border-top-right-radius: 0.2rem; border-bottom-right-radius: 0.2rem"
              :disabled="loading"
            >
              <span
                v-if="loading"
                class="circle-loader--lt"
              />
              <span v-else>{{ $t('Search') }}</span>
            </button>
          </div>
        </div>
      </form>

      <div
        v-if="error"
        class="mt-3 alert alert-warning"
      >
        {{ $t('Oops, something went wrong.') }} {{ error }}
      </div>
      <div
        v-if="searchInfo.count === 0"
        class="mt-3"
      >
        {{ $t('No documents match your search.') }}
      </div>
      <div class="mt-3">
        <!--        <DidYouMean-->
        <!--          :q="q"-->
        <!--          @suggest="suggest"-->
        <!--        />-->
      </div>
    </div>
    <div class="container-fluid">
      <div class="row">
        <div class="col-md-12 col-lg-3">
          <div
            v-if="searchInfo.count"
            class="search-facets"
          >
            <ul class="list-group">
              <li class="list-group-item bg-light d-flex justify-content-between align-items-center search-facets__header">
                <a
                  href="#"
                  class="d-lg-none"
                  style="font-size: 24px"
                >
                  ×
                </a>
                <strong>{{ $t('Filters') }}</strong>
                <div>
                  <a
                    v-if="showClearAllFiltersBtn"
                    href="#"
                    @click.prevent="clearAllFilters"
                  >
                    {{ $t('Clear All') }}
                  </a>
                </div>
              </li>
              <li
                v-if="searchInfo.facets && searchInfo.facets._filter_doc_type"
                class="list-group-item"
              >
                <div class="d-flex justify-content-between mb-2">
                  <strong>{{ $t('Document type') }}</strong>
                  <a
                    v-if="filters.doc_type.length"
                    href="#"
                    @click.prevent="() => filters.doc_type = []"
                  >
                    {{ $t('Clear') }}
                  </a>
                </div>
                <TermFacet
                  :buckets="sortGenericBuckets(searchInfo.facets._filter_doc_type.doc_type.buckets)"
                  :selection="filters.doc_type"
                  :loading="loading"
                  @changed="(x) => filters.doc_type = x"
                />
              </li>
              <li
                v-if="searchInfo.facets && searchInfo.facets._filter_authoring_body"
                class="list-group-item"
              >
                <div class="d-flex justify-content-between mb-2">
                  <strong>{{ $t('Author') }}</strong>
                  <a
                    v-if="filters.authoring_body.length"
                    href="#"
                    @click.prevent="() => filters.authoring_body = []"
                  >
                    {{ $t('Clear') }}
                  </a>
                </div>
                <TermFacet
                  :buckets="sortGenericBuckets(searchInfo.facets._filter_authoring_body.authoring_body.buckets)"
                  :selection="filters.authoring_body"
                  :loading="loading"
                  @changed="(x) => filters.authoring_body = x"
                />
              </li>
              <li
                v-if="searchInfo.facets && searchInfo.facets._filter_jurisdiction"
                class="list-group-item"
              >
                <div class="d-flex justify-content-between mb-2">
                  <strong>{{ $t('Jurisdiction') }}</strong>
                  <a
                    v-if="filters.jurisdiction.length"
                    href="#"
                    @click.prevent="() => filters.jurisdiction = []"
                  >
                    {{ $t('Clear') }}
                  </a>
                </div>
                <TermFacet
                  :buckets="sortGenericBuckets(searchInfo.facets._filter_jurisdiction.jurisdiction.buckets)"
                  :selection="filters.jurisdiction"
                  :loading="loading"
                  @changed="(x) => filters.jurisdiction = x"
                />
              </li>
              <li
                v-if="searchInfo.facets && searchInfo.facets._filter_locality"
                class="list-group-item"
              >
                <div class="d-flex justify-content-between mb-2">
                  <strong>{{ $t('Locality') }}</strong>
                  <a
                    v-if="filters.locality.length"
                    href="#"
                    @click.prevent="() => filters.locality = []"
                  >
                    {{ $t('Clear') }}
                  </a>
                </div>
                <TermFacet
                  :buckets="sortGenericBuckets(searchInfo.facets._filter_locality.locality.buckets)"
                  :selection="filters.locality"
                  :loading="loading"
                  @changed="(x) => filters.locality = x"
                />
              </li>

              <li
                v-if="searchInfo.facets && searchInfo.facets._filter_matter_type"
                class="list-group-item"
              >
                <div class="d-flex justify-content-between mb-2">
                  <strong>{{ $t('Matter type') }}</strong>
                  <a
                    v-if="filters.matter_type.length"
                    href="#"
                    @click.prevent="() => filters.matter_type = []"
                  >
                    {{ $t('Clear') }}
                  </a>
                </div>
                <TermFacet
                  :buckets="sortGenericBuckets(searchInfo.facets._filter_matter_type.matter_type.buckets)"
                  :selection="filters.matter_type"
                  :loading="loading"
                  @changed="(x) => filters.matter_type = x"
                />
              </li>
              <li
                v-if="searchInfo.facets && searchInfo.facets._filter_nature"
                class="list-group-item"
              >
                <div class="d-flex justify-content-between mb-2">
                  <strong>{{ $t('Document nature') }}</strong>
                  <a
                    v-if="filters.nature.length"
                    href="#"
                    @click.prevent="() => filters.nature = []"
                  >
                    {{ $t('Clear') }}
                  </a>
                </div>
                <TermFacet
                  :buckets="sortGenericBuckets(searchInfo.facets._filter_nature.nature.buckets)"
                  :selection="filters.nature"
                  :loading="loading"
                  @changed="(x) => filters.nature = x"
                />
              </li>
              <li
                v-if="searchInfo.facets && searchInfo.facets._filter_language"
                class="list-group-item"
              >
                <div class="d-flex justify-content-between mb-2">
                  <strong>{{ $t('Language') }}</strong>
                  <a
                    v-if="filters.language.length"
                    href="#"
                    @click.prevent="() => filters.language = []"
                  >
                    {{ $t('Clear') }}
                  </a>
                </div>
                <TermFacet
                  :buckets="sortGenericBuckets(searchInfo.facets._filter_language.language.buckets)"
                  :selection="filters.language"
                  :loading="loading"
                  @changed="(x) => filters.language = x"
                />
              </li>
              <li
                v-if="searchInfo.facets && searchInfo.facets._filter_year"
                class="list-group-item"
              >
                <div class="d-flex justify-content-between mb-2">
                  <strong>{{ $t('Year') }}</strong>
                  <a
                    v-if="filters.year.length"
                    href="#"
                    @click.prevent="() => filters.year = []"
                  >
                    {{ $t('Clear') }}
                  </a>
                </div>
                <TermFacet
                  :buckets="sortGenericBuckets(searchInfo.facets._filter_year.year.buckets)"
                  :selection="filters.year"
                  :loading="loading"
                  @changed="(x) => filters.year = x"
                />
              </li>
            </ul>
          </div>
        </div>

        <div class="col-md-12 col-lg-9 search-pane position-relative">
          <div class="search-results">
            <div v-if="searchInfo.count">
              <div class="mb-3 d-flex justify-content-between">
                <div>
                  {{ searchInfo.count }}  documents found.
                </div>
              </div>

              <ul class="list-unstyled">
                <SearchResult
                  v-for="item in searchInfo.results"
                  :key="item.key"
                  :item="item"
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
    </div>
  </div>
</template>

<script>
import SearchResult from './SearchResult.vue';
import SearchPagination from './SearchPagination.vue';
import TermFacet from './TermFacet.vue';
import moment from 'moment';

export default {
  name: 'FindDocuments',
  components: { SearchResult, SearchPagination, TermFacet },
  data: () => {
    return {
      loadingCount: 0,
      error: null,
      searchInfo: {},
      page: 1,
      ordering: '-score',
      q: '',
      drawerOpen: false,
      filters: {
        doc_type: [],
        authoring_body: [],
        jurisdiction: [],
        locality: [],
        year: [],
        date: [],
        matter_type: [],
        nature: [],
        language: []
      }
    };
  },

  computed: {
    loading () {
      return this.loadingCount > 0;
    },
    showClearAllFiltersBtn () {
      return Object.keys(this.filters).some(key => this.filters[key].length);
    },

    selectedFiltersCount () {
      return Object.keys(this.filters).map(key => this.filters[key].length).reduce((pv, cv) => pv + cv, 0);
    }
  },

  watch: {
    ordering () {
      this.search();
    },

    filters: {
      deep: true,
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
    sortDateBuckets (items, ascending = false) {
      const buckets = [...items];
      if (ascending) {
        buckets.sort((a, b) =>
          moment(a).isBefore(moment(b)) ? -1 : 1
        );
      } else {
        buckets.sort((a, b) =>
          moment(a).isBefore(moment(b)) ? 1 : -1
        );
      }
      return buckets.map(bucket => ({
        ...bucket,
        key: moment(bucket.key).format('YYYY')
      }));
    },
    sortGenericBuckets (items, reverse = false) {
      const buckets = [...items];
      buckets.sort((a, b) => a.key.localeCompare(b.key));
      if (reverse) {
        buckets.reverse();
      }
      return buckets;
    },
    handlePageChange (newPage) {
      this.page = newPage;
      this.search();
      document.body.scrollTop = 0; // For Safari
      document.documentElement.scrollTop = 0; // For Chrome, Firefox, IE and Opera
    },
    handleSubmit () {
      this.page = 1;
      this.q = this.$refs['search-input'].value.trim();
      this.search();
    },
    clearAllFilters () {
      Object.keys(this.filters).forEach(key => {
        if (this.filters[key].length) {
          this.filters[key] = [];
        }
      });
    },

    serialiseState () {
      // save state to URL string
      const params = new URLSearchParams();
      params.set('q', this.q);
      if (this.page > 1) {
        params.set('page', this.page);
      }
      if (this.ordering !== '-score') {
        params.set('ordering', this.ordering);
      }

      for (const filter of Object.keys(this.filters)) {
        for (const f of this.filters[filter]) {
          params.append(filter, f);
        }
      }
      return params.toString();
    },

    loadState () {
      // load state from URL
      const params = new URLSearchParams(document.location.search);
      // skip the first event if there's a query, because the page load will already have sent it
      this.q = this.$refs['search-input'].value = (params.get('q') || '').trim();
      this.page = parseInt(params.get('page')) || this.page;
      this.ordering = params.get('ordering') || this.ordering;

      for (const filter of Object.keys(this.filters)) {
        if (params.has(filter)) {
          this.filters[filter] = params.getAll(filter);
        }
      }

      this.search();
    },

    suggest (q) {
      this.q = q;
      this.$refs['search-input'].value = q;
      this.search();
    },

    async search () {
      if (this.q !== '') {
        const generateUrl = () => {
          const params = new URLSearchParams();
          params.append('search', this.q);
          params.append('page', this.page);
          params.append('ordering', this.ordering);
          params.append('highlight', 'content');

          for (const key of Object.keys(this.filters)) {
            for (const x of this.filters[key]) {
              params.append(key, x);
            }
          }

          // facets that we want the API to return
          for (const facet of Object.keys(this.filters)) {
            params.append('facet', facet);
          }

          return `${window.location.origin}/search/api/documents/?${params.toString()}`;
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
              window.history.replaceState(null, '', document.location.pathname + '?' + this.serialiseState());
            } else {
              this.error = response.statusText;
            }
          }
        } catch {
          this.error = 'Network unavailable.';
        }

        this.loadingCount = this.loadingCount - 1;
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
</style>

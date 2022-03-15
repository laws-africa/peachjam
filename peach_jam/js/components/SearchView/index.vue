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
            placeholder="Search gazettes"
            aria-label="Search gazettes"
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
              <span v-else>Search</span>
            </button>

            <button
              v-if="searchInfo.count"
              type="button"
              style="border-radius: 0.2rem"
              class="btn  btn-sm btn-secondary ml-1 d-lg-none"
              @click="() => drawerOpen = true"
            >
              Filters <span v-if="selectedFiltersCount">({{ selectedFiltersCount }})</span>
            </button>
          </div>
        </div>
      </form>

      <div
        v-if="error"
        class="mt-3 alert alert-warning"
      >
        Oops, something went wrong. {{ error }}
      </div>
      <div
        v-if="searchInfo.count === 0"
        class="mt-3"
      >
        No gazettes match your search.
      </div>
      <div class="mt-3">
        <DidYouMean
          :q="q"
          @suggest="suggest"
        />
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
                <strong>Filters</strong>
                <div>
                  <a
                    v-if="showClearAllFiltersBtn"
                    href="#"
                    @click.prevent="clearAllFilters"
                  >
                    Clear All
                  </a>
                </div>
              </li>
              <li class="list-group-item">
                <div class="d-flex justify-content-between mb-2">
                  <strong>Jurisdiction</strong>
                  <a
                    v-if="filters.jurisdiction_name.length"
                    href="#"
                    @click.prevent="() => filters.jurisdiction_name = []"
                  >
                    Clear
                  </a>
                </div>
                <TermFacet
                  v-if="searchInfo.facets && searchInfo.facets._filter_jurisdiction_name"
                  :buckets="searchInfo.facets._filter_jurisdiction_name.jurisdiction_name.buckets"
                  :selection="filters.jurisdiction_name"
                  :loading="loading"
                  @changed="(x) => filters.jurisdiction_name = x"
                />
              </li>
              <li class="list-group-item">
                <div class="d-flex justify-content-between mb-2">
                  <strong>Year</strong>
                  <a
                    v-if="filters.year.length"
                    href="#"
                    @click.prevent="() => filters.year = []"
                  >
                    Clear
                  </a>
                </div>
                <TermFacet
                  v-if="searchInfo.facets && searchInfo.facets._filter_year"
                  :buckets="searchInfo.facets._filter_year.year.buckets"
                  :selection="filters.year"
                  :reverse="true"
                  :loading="loading"
                  @changed="(x) => filters.year = x"
                />
              </li>
              <li class="list-group-item">
                <div class="d-flex justify-content-between mb-2">
                  <strong>Publication</strong>
                  <a
                    v-if="filters.publication.length || filters.sub_publication.length"
                    href="#"
                    @click.prevent="() => { filters.publication = []; filters.sub_publication = []; }"
                  >
                    Clear
                  </a>
                </div>
                <TermFacet
                  v-if="searchInfo.facets && searchInfo.facets._filter_publication"
                  :buckets="searchInfo.facets._filter_publication.publication.buckets"
                  :selection="filters.publication"
                  :loading="loading"
                  @changed="(x) => filters.publication = x"
                />

                <hr v-if="searchInfo.facets && searchInfo.facets._filter_sub_publication && searchInfo.facets._filter_sub_publication.sub_publication.buckets.length">

                <TermFacet
                  v-if="searchInfo.facets && searchInfo.facets._filter_sub_publication"
                  :buckets="searchInfo.facets._filter_sub_publication.sub_publication.buckets"
                  :selection="filters.sub_publication"
                  :loading="loading"
                  @changed="(x) => filters.sub_publication = x"
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
                  {{ searchInfo.count }}  gazettes found.
                </div>

                <div>
                  Sort by
                  <select v-model="ordering">
                    <option value="-score">
                      Revelance
                    </option>
                    <option value="date">
                      Date (oldest first)
                    </option>
                    <option value="-date">
                      Date (newest first)
                    </option>
                  </select>
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

<script>import SearchResult from './SearchResult.vue';
import SearchPagination from './SearchPagination.vue';
import TermFacet from './TermFacet.vue';
import DidYouMean from './DidYouMean.vue';
// import MobileFacetsDrawer from './MobileSideDrawer';
import debounce from 'lodash.debounce';

export default {
  name: 'SearchView',
  components: { SearchResult, SearchPagination, TermFacet, DidYouMean },
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
        jurisdiction_name: [],
        year: [],
        publication: [],
        sub_publication: []
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
    // this.loadState();
    // window.addEventListener('resize', this.handleScreenResize);
  },

  methods: {
    // handleScreenResize: debounce(function () {
    //   this.drawerOpen = false;
    // }, 200),

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
      this.skipFirstGAEvent = !!(params.get('q'));
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

          for (const key of Object.keys(this.filters)) {
            for (const x of this.filters[key]) {
              params.append(key, x);
            }
          }

          // facets that we want the API to return
          for (const facet of ['jurisdiction_name', 'year', 'publication', 'sub_publication']) {
            params.append('facet', facet);
          }

          return '/api/search/?' + params.toString();
        };

        this.loadingCount = this.loadingCount + 1;
        try {
          const url = generateUrl();
          const response = await fetch('http://localhost:7000/api/search');
          if (url === generateUrl()) {
            if (response.ok) {
              this.error = null;
              this.searchInfo = await response.json();
              if (this.searchInfo.count === 0) {
                this.clearAllFilters();
              }
            } else {
              this.error = response.statusText;
            }
          }
        } catch {
          this.error = 'Network unavailable.';
        }

        this.loadingCount = this.loadingCount - 1;
        // this.drawerOpen = false;
      }
    },
    sendGAEvent () {
      if (this.skipFirstGAEvent) {
        this.skipFirstGAEvent = false;
        return;
      }

      // update page location
      window.history.replaceState(null, '', document.location.pathname + '?' + this.serialiseState());

      window.gtag('config', window.ga_id, {
        page_location: document.location.pathname + document.location.search
      });
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

@media only screen and (max-width: 992px) {
  .search-input-container {
    width: 100%;
    position: sticky;
    z-index: 99;
    top: 0;
    left: 0;
    padding: 1rem 1rem 0.25rem;
  }
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

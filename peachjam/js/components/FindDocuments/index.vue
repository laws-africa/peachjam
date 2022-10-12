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
    <div class="container-fluid">
      <div class="row">
        <div class="col col-lg-3">
          <MobileFacetsDrawer
            :open="drawerOpen"
            @outside-drawer-click="() => drawerOpen = false"
          >
            <FilterFacets
              v-model="facets"
              :loading="loading"
            />
          </MobileFacetsDrawer>
        </div>

        <div class="col-md-12 col-lg-9 search-pane position-relative">
          <div class="search-results">
            <div v-if="searchInfo.count">
              <div class="mb-3 sort-body">
                <div>{{ $t('{document_count} documents found', { document_count: searchInfo.count }) }}</div>
                <div class="sort__inner">
                  {{ $t('Sort by') }}
                  <select
                    v-model="ordering"
                    class="ms-2"
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
    </div>

    <!-- DOM Hack for i18next to parse facet to locale json. i18next skips t functions in script element -->
    <div v-if="false">
      {{ $t('Document type') }}
      {{ $t('Author') }}
      {{ $t('Court') }}
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

export default {
  name: 'FindDocuments',
  components: { MobileFacetsDrawer, SearchResult, SearchPagination, FilterFacets },
  data () {
    return {
      loadingCount: 0,
      error: null,
      searchInfo: {},
      page: 1,
      ordering: '-score',
      q: '',
      drawerOpen: false,
      facets: [
        {
          title: this.$t('Document type'),
          name: 'doc_type',
          type: 'checkboxes',
          value: [],
          options: []
        },
        {
          title: this.$t('Author'),
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

    handleSubmit () {
      this.page = 1;
      this.q = this.$refs['search-input'].value.trim();
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
      params.set('q', this.q);
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

      return params.toString();
    },

    loadState () {
      // load state from URL
      const params = new URLSearchParams(window.location.search);
      // skip the first event if there's a query, because the page load will already have sent it
      this.q = this.$refs['search-input'].value = (
        params.get('q') || ''
      ).trim();
      this.page = parseInt(params.get('page')) || this.page;
      this.ordering = params.get('ordering') || this.ordering;

      this.facets.forEach((facet) => {
        if (params.has(facet.name)) {
          facet.value = params.getAll(facet.name);
        }
      });

      this.search();
    },

    suggest (q) {
      this.q = q;
      this.$refs['search-input'].value = q;
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
      if (this.q !== '') {
        const generateUrl = () => {
          const params = new URLSearchParams();
          params.append('search', this.q);
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
        document.body.scrollTop = 0; // For Safari
        document.documentElement.scrollTop = 0; // For Chrome, Firefox, IE and Opera
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
    padding-top: 1rem;
    position: sticky;
    top: 0;
    left: 0;
    z-index: 9;
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
</style>

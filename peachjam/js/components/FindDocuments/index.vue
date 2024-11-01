<template>
  <div id="search" ref="search-box">
    <div class="mb-4">
      <nav>
        <div
          class="nav nav-tabs mb-3 border-bottom"
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
          <button
            v-if="showGoogle"
            id="google-search-tab"
            class="nav-link"
            data-bs-toggle="tab"
            data-bs-target="#nav-google-search"
            type="button"
            role="tab"
            aria-controls="nav-google-search"
            aria-selected="false"
          >
            {{ $t('Search with Google') }}
          </button>
        </div>
      </nav>
      <div class="tab-content">
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
              type="search"
              class="form-control"
              :placeholder="searchPlaceholder"
              :aria-label="$t('Search documents')"
              aria-describedby="basic-addon2"
              required
            >
            <button
              type="submit"
              class="btn btn-primary ms-2"
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
              {{ $t("Filters") }} <span v-if="selectedFacetsCount">({{ selectedFacetsCount }})</span>
            </button>
          </form>
          <div class="my-2 text-end">
            <HelpBtn page="search/" />
          </div>
          <div v-if="searchTip" class="my-2">
            <i class="bi bi-info-circle" />
            {{ searchTip.prompt }}
            <a href="#" @click.stop.prevent="useSearchTip()">{{ searchTip.q }}</a>
          </div>
        </div>
        <div
          id="nav-advanced-search"
          class="tab-pane fade"
          role="tabpanel"
          aria-labelledby="advanced-search-tab"
        >
          <AdvancedSearch
            v-model="advancedSearchCriteria"
            :advanced-search-date-criteria="advancedSearchDateCriteria"
            :global-search-value="q"
            :selected-facets-count="selectedFacetsCount"
            :search-info="searchInfo"
            @global-search-change="value => q = value"
            @date-change="value => advancedSearchDateCriteria = {...value}"
            @submit="advancedSearch"
            @show-facets="() => drawerOpen = true"
          />
        </div>
        <div
          v-if="showGoogle"
          id="nav-google-search"
          class="tab-pane fade"
          role="tabpanel"
          aria-labelledby="google-search-tab"
        >
          <div class="gcse-search" data-autoSearchOnLoad="false" />
        </div>
      </div>
    </div>
    <div class="mt-3" v-if="!googleActive">
      <FacetBadges v-model="facets" :permissive="searchInfo.count === 0" />
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
      <div ref="filters-results-container">
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

          <div class="col-md-12 col-lg-9 position-relative">
            <div class="search-results">
              <div v-if="searchInfo.count">
                <div class="mb-3 sort-body row">
                  <div class="col-md-4 order-md-2 mb-2 sort__inner d-flex align-items-center">
                    <div style="width: 6em">
                      {{ $t('Sort') }}
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
                  <div class="col-md order-md-1 align-self-center">
                    <span v-if="searchInfo.count > 9999">{{ $t('More than 10,000 documents found.') }}</span>
                    <span v-else>{{ $t('{document_count} documents found', { document_count: searchInfo.count }) }}</span>
                  </div>
                </div>

                <ul class="list-unstyled">
                  <SearchResult
                    v-for="item in searchInfo.results"
                    :key="item.key"
                    :item="item"
                    :query="q"
                    :debug="searchInfo.can_debug"
                    :show-jurisdiction="showJurisdiction"
                    :document-labels="documentLabels"
                    @explain="explain(item)"
                    @item-clicked="(e) => itemClicked(item, e)"
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
    </div>

    <!-- DOM Hack for i18next to parse facet to locale json. i18next skips t functions in script element -->
    <div v-if="false">
      {{ $t('Document type') }}
      {{ $t('Author') }}
      {{ $t('Court') }}
      {{ $t('Court registry') }}
      {{ $t('Judges') }}
      {{ $t('Attorneys') }}
      {{ $t('Outcome') }}
      {{ $t('Jurisdiction') }}
      {{ $t('Locality') }}
      {{ $t('Matter type') }}
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
import analytics from '../analytics';
import { authHeaders } from '../../api';

export default {
  name: 'FindDocuments',
  components: { FacetBadges, MobileFacetsDrawer, SearchResult, SearchPagination, FilterFacets, AdvancedSearch, HelpBtn },
  props: ['showJurisdiction', 'showGoogle'],
  data () {
    const getLabelOptionLabels = (labels) => {
      // the function name is a bit confusing but this gets labels for the options in Labels facet
      const labelOptions = {};
      for (const label of labels) {
        labelOptions[label.code] = label.name;
      }
      return labelOptions;
    };

    const getTitle = (title) => {
      return JSON.parse(document.querySelector('#data-labels').textContent)[title];
    };

    const data = {
      searchPlaceholder: JSON.parse(document.querySelector('#data-labels').textContent).searchPlaceholder,
      documentLabels: JSON.parse(document.querySelector('#data-labels').textContent).documentLabels,
      loadingCount: 0,
      error: null,
      searchInfo: {},
      page: 1,
      pageSize: 10,
      ordering: '-score',
      q: '',
      drawerOpen: false,
      searchTip: null,
      advancedSearchCriteria: [{
        text: '',
        fields: [],
        condition: '',
        exact: false
      },
      {
        text: '',
        fields: [],
        condition: 'AND',
        exact: false
      }],
      advancedSearchDateCriteria: {
        date_to: null,
        date_from: null
      },
      googleActive: false
    };
    const facets = [
      {
        title: this.$t('Document type'),
        name: 'nature',
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
        title: getTitle('author'),
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
        title: getTitle('registry'),
        name: 'registry',
        type: 'checkboxes',
        value: [],
        options: []
      },
      {
        title: getTitle('judge'),
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
        title: this.$t('Outcome'),
        name: 'outcome',
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
    this.$el.addEventListener('show.bs.tab', this.tabChanged);
  },

  methods: {
    tabChanged (e) {
      this.googleActive = e.target.id === 'google-search-tab';
    },

    sortBuckets (items, reverse = false, byCount = false) {
      const buckets = [...items];
      function keyFn (a, b) {
        if (byCount) {
          // sort by count, then by key
          return a.doc_count === b.doc_count ? a.key.localeCompare(b.key) : b.doc_count - a.doc_count;
        }
        return a.key.localeCompare(b.key);
      }
      buckets.sort(keyFn);
      if (reverse) {
        buckets.reverse();
      }
      return buckets;
    },

    getUrlParamValue (key, options) {
    },

    handlePageChange (newPage) {
      this.page = newPage;
      this.search();
    },

    simpleSearch () {
      this.resetAdvancedFields();
      this.submit();
    },

    advancedSearch () {
      this.q = '';
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

      if (this.advancedSearchDateCriteria.date_from && this.advancedSearchDateCriteria.date_to) {
        params.append('date_from', this.advancedSearchDateCriteria.date_from);
        params.append('date_to', this.advancedSearchDateCriteria.date_to);
      } else if (this.advancedSearchDateCriteria.date_from) {
        params.append('date_from', this.advancedSearchDateCriteria.date_from);
      } else if (this.advancedSearchDateCriteria.date_to) {
        params.append('date_to', this.advancedSearchDateCriteria.date_to);
      }

      const searchParams = this.advancedSearchCriteria.filter(criterion => criterion.text).map((criterion) => {
        const reducedCriterion = { text: criterion.text };
        if (criterion.fields.length) reducedCriterion.fields = criterion.fields;
        if (criterion.condition) reducedCriterion.condition = criterion.condition;
        if (criterion.exact) reducedCriterion.exact = criterion.exact;

        return reducedCriterion;
      });

      // Set advanced fields to url
      if (searchParams.length) params.append('a', JSON.stringify(searchParams));

      return params.toString();
    },

    loadState () {
      this.resetAdvancedFields();

      // load state from URL
      const params = new URLSearchParams(window.location.search);
      // skip the first event if there's a query, because the page load will already have sent it
      this.q = params.get('q') || '';
      this.page = parseInt(params.get('page')) || this.page;
      this.ordering = params.get('ordering') || this.ordering;

      this.facets.forEach((facet) => {
        if (params.has(facet.name)) {
          facet.value = params.getAll(facet.name);
        }
      });

      if (params.has('date_from')) this.advancedSearchDateCriteria.date_from = params.get('date_from');
      if (params.has('date_to')) this.advancedSearchDateCriteria.date_to = params.get('date_to');

      let showAdvanced = params.get('show-advanced-tab');
      if (params.has('a')) {
        const advancedSearchParams = JSON.parse(params.get('a'));
        advancedSearchParams.forEach((criterion, index) => {
          const fullCriterion = {
            text: criterion.text,
            fields: criterion.fields || [],
            condition: criterion.condition || '',
            exact: !!criterion.exact
          };
          if (index === 0 && !criterion.condition) this.advancedSearchCriteria.splice(0, 1, fullCriterion);
          else this.advancedSearchCriteria.splice(index, 0, fullCriterion);
        });
        showAdvanced = true;
      }

      // if there are advanced search fields or show-advanced-tab param, activate tab
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

    useSearchTip () {
      this.q = this.searchTip.q;
      this.search();
    },

    formatFacets () {
      const queryString = window.location.search;
      const urlParams = new URLSearchParams(queryString);

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
            this.sortBuckets(
              this.searchInfo.facets[`_filter_${facet.name}`][facet.name].buckets,
              true
            ),
            facet.optionLabels
          );
        } else {
          if (this.searchInfo.facets[`_filter_${facet.name}`]) {
            facet.options = generateOptions(
              this.sortBuckets(
                this.searchInfo.facets[`_filter_${facet.name}`][facet.name].buckets,
               false,
                // sort nature by descending count, everything else alphabetically
                facet.name === 'nature'
              ),
              facet.optionLabels
            );
          }
        }

        // If we have results, then sanity check chosen options against those that are available.
        // If there are no results, we trust any options given so that we can show the facet buttons
        // and allow the user to remove the facets to try to find results.
        if (this.searchInfo.count > 0) {
          const availableOptions = facet.options.map(option => option.value);
          facet.value = urlParams.getAll(facet.name).filter(value => availableOptions.includes(value));
        }
      });
    },

    formatResults () {
      for (let i = 0; i < this.searchInfo.results.length; i++) {
        // number items from 1 consistently across pages
        this.searchInfo.results[i].position = (this.page - 1) * this.pageSize + i + 1;
      }

      // determine best match: is the first result's score significantly better than the next?
      if (this.page === 1 && this.searchInfo.results.length > 1 &&
          this.searchInfo.results[0]._score / this.searchInfo.results[1]._score >= 1.2) {
        this.searchInfo.results[0].best_match = true;
      }
    },

    generateSearchParams () {
      const params = new URLSearchParams();
      if (this.q) params.append('search', this.q);
      params.append('page', this.page);
      params.append('ordering', this.ordering);

      this.facets.forEach((facet) => {
        facet.value.forEach((value) => {
          params.append(facet.name, value);
        });
      });

      // facets that we want the API to return
      this.facets.forEach((facet) => {
        params.append('facet', facet.name);
      });

      this.generateAdvancedSearchParams(params);

      return params;
    },

    generateAdvancedSearchParams (params) {
      // advanced search fields, if any
      if (this.advancedSearchDateCriteria.date_from && this.advancedSearchDateCriteria.date_to) {
        const dateFrom = this.advancedSearchDateCriteria.date_from;
        const dateTo = this.advancedSearchDateCriteria.date_to;
        params.append('date__range', `${dateFrom}__${dateTo}`);
      } else if (this.advancedSearchDateCriteria.date_from) {
        params.append('date__gte', this.advancedSearchDateCriteria.date_from);
      } else if (this.advancedSearchDateCriteria.date_to) {
        params.append('date__lte', this.advancedSearchDateCriteria.date_to);
      }

      // group criteria by fields and process each field separately
      const fields = new Map();
      for (const criterion of this.advancedSearchCriteria) {
        if (criterion.text) {
          for (const field of criterion.fields) {
            if (!fields.has(field)) fields.set(field, []);
            fields.get(field).push(criterion);
          }
        }
      }

      for (const [field, criteria] of fields) {
        params.set(`search__${field}`, this.generateAdvancedSearchQuery(criteria));
      }
    },

    generateAdvancedSearchQuery (criteria) {
      let q = '';

      for (const criterion of criteria) {
        const text = criterion.exact ? `"${criterion.text}"` : criterion.text;

        if (criterion.condition === 'AND') {
          q = q + ' & ';
        } else if (criterion.condition === 'OR') {
          q = q + ' | ';
        } else if (criterion.condition === 'NOT') {
          q = q + ' -';
        }

        q = q + `(${text})`;
      }

      return q.trim();
    },

    async search (pushState = true) {
      this.searchTip = null;

      // if one of the search fields is true perform search
      if (this.q || (Array.isArray(this.advancedSearchCriteria) && this.advancedSearchCriteria.some(f => f.text))) {
        this.loadingCount = this.loadingCount + 1;

        // scroll to put the search box at the top of the window
        scrollToElement(this.$refs['search-box']);

        // search tip
        if (this.q && this.q.indexOf('"') === -1 && this.q.indexOf(" ") > -1) {
          this.searchTip = {
            prompt: this.$t('Tip: Try using quotes to search for an exact phrase: '),
            q: `"${this.q}"`
          };
        }

        try {
          const params = this.generateSearchParams();
          const previousId = this.searchInfo.trace_id || '';
          const url = `/search/api/documents/?${params.toString()}&previous=${previousId}`;

          if (pushState) {
            window.history.pushState(
              null,
              '',
              document.location.pathname + '?' + this.serialiseState()
            );
          }
          const response = await fetch(url);

          // check that the search state hasn't changed since we sent the request
          if (params.toString() === this.generateSearchParams().toString()) {
            if (response.ok) {
              this.error = null;
              this.searchInfo = await response.json();
              this.formatFacets();
              this.formatResults();
              this.trackSearch(params);
            } else {
              this.error = response.statusText;
            }
          }
        } catch {
          this.error = 'Network unavailable.';
        }

        this.loadingCount = this.loadingCount - 1;
        this.drawerOpen = false;
      }
    },

    trackSearch (params) {
      const keywords = [];
      const facets = [];
      const fields = this.facets.map(facet => facet.name).concat(['date__range', 'date__gte', 'date__lte']);

      [...new Set(params.keys())].forEach((key) => {
        if (key.startsWith('search')) {
          const s = key === 'search' ? '' : (key.substring(8) + '=');
          keywords.push(s + params.get(key).trim());
        } else if (fields.includes(key)) {
          facets.push(`${key}=${params.getAll(key).join(',')}`);
        }
      });

      analytics.trackSiteSearch(keywords.join('; '), facets.join('; '), this.searchInfo.count);
    },

    async explain (item) {
      const params = this.generateSearchParams();
      params.set('index', item._index);
      const url = `/search/api/documents/${item.id}/explain/?${params.toString()}`;
      const resp = await fetch(url);
      const json = await resp.json();
      item.explanation = json;
    },

    async itemClicked (item, portion) {
      const params = new URLSearchParams();
      params.set('frbr_uri', item.expression_frbr_uri);
      params.set('portion', portion || '');
      params.set('position', item.position);
      params.set('search_trace', this.searchInfo.trace_id);
      try {
        fetch('/search/api/click/', {
          method: 'POST',
          headers: await authHeaders(),
          body: params
        });
      } catch (err) {
        console.log(err);
      }
    },

    resetAdvancedFields () {
      this.advancedSearchCriteria = [{
        text: '',
        fields: ['all'],
        condition: '',
        exact: false
      },
      {
        text: '',
        fields: ['all'],
        condition: 'AND',
        exact: false
      }];

      this.advancedSearchDateCriteria = {
        date_to: null,
        date_from: null
      };
    }

  }
};
</script>

<style scoped>
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

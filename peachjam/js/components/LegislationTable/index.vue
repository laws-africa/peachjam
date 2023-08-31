<template>
  <div>
    <div
      id="mobile-legislation-facets"
      ref="mobile-legislation-facets-ref"
      class="offcanvas offcanvas-start"
      tabindex="-1"
      aria-labelledby="mobile-legislation-facets"
    >
      <div class="offcanvas-header justify-content-end">
        <button
          type="button"
          class="btn-close text-reset"
          data-bs-dismiss="offcanvas"
          :aria-label="$t('Close')"
        />
      </div>
      <div class="offcanvas-body">
        <FilterFacets
          v-if="windowWith < 992"
          v-model="facets"
        />
      </div>
    </div>
    <div class="row">
      <div
        class="col col-lg-3 d-none d-lg-block"
      >
        <FilterFacets
          v-if="windowWith > 992"
          v-model="facets"
        />
      </div>
      <div class="col col-lg-9">
        <div class="d-block d-lg-none mb-2">
          <button
            class="btn btn-primary"
            type="button"
            data-bs-toggle="offcanvas"
            data-bs-target="#mobile-legislation-facets"
            aria-controls="mobile-legislation-facets"
          >
            Filters
          </button>
        </div>
        <div :class="`card legislation-table ${showDates ? 'with-dates' : ''}`">
          <div class="card-header">
            <input
              v-model="q"
              type="text"
              class="form-control"
              placeholder="Filter legislation"
            >
          </div>
          <div class="table-row legislation-table__row">
            <div class="indent" />
            <div>
              {{ filteredData.length }} of {{ tableData.length }} documents
            </div>
          </div>
          <div class="table-row legislation-table__row headings">
            <div class="indent" />
            <div class="table-row__content-col">
              <div class="content">
                <div
                  class="content__title align-items-center"
                  role="button"
                  @click="updateSort('title')"
                >
                  <strong>{{ $t('Title') }}</strong>
                  <i
                    v-if="sortableFields.title === 'asc'"
                    class="bi bi-sort-up ms-2"
                  />
                  <i
                    v-if="sortableFields.title === 'desc'"
                    class="bi bi-sort-down ms-2"
                  />
                </div>
                <div
                  v-if="!showDates"
                  class="content__secondary"
                  role="button"
                  @click="updateSort('citation')"
                >
                  <strong>{{ $t('Numbered title') }}</strong>
                  <i
                    v-if="sortableFields.citation === 'asc'"
                    class="bi bi-sort-up ms-2"
                  />
                  <i
                    v-if="sortableFields.citation === 'desc'"
                    class="bi bi-sort-down ms-2"
                  />
                </div>
                <div
                  v-if="showDates"
                  class="content__secondary"
                  role="button"
                  @click="updateSort('date')"
                >
                  <strong>{{ $t('Date') }}</strong>
                  <i
                    v-if="sortableFields.date === 'asc'"
                    class="bi bi-sort-up ms-2"
                  />
                  <i
                    v-if="sortableFields.date === 'desc'"
                    class="bi bi-sort-down ms-2"
                  />
                </div>
              </div>
            </div>
          </div>
          <template v-if="filteredData.length">
            <div
              v-for="(row, index) in filteredData"
              :key="index"
              :class="`table-row legislation-table__row ${
                row.children.length ? 'has-children' : ''
              }`"
              role="button"
              @click="handleRowClick"
            >
              <div
                v-if="row.children.length"
                class="column-caret indent"
              >
                <i class="bi bi-caret-right-fill" />
                <i class="bi bi-caret-down-fill" />
              </div>
              <div
                v-else
                class="indent"
              />
              <div class="table-row__content-col">
                <div class="content">
                  <div class="content__title">
                    <a :href="`${row.work_frbr_uri}`">{{ row.title }}</a>
                    <i
                      v-if="row.languages.length > 1"
                      class="bi bi-translate ps-2"
                      :title="$t('Multiple languages available')"
                    />
                  </div>
                  <div v-if="showDates" class="content__secondary">
                    {{ row.date }}
                  </div>
                  <div v-else class="content__secondary">
                    {{ row.citation }}
                  </div>
                  <div
                    v-if="row.children.length"
                    :id="`row-accordion-${index}`"
                    class="accordion-collapse collapse accordion content__children"
                    data-bs-parent=".legislation-table__row"
                  >
                    <div class="accordion-body p-0">
                      <div
                        v-for="(subleg, subleg_index) in row.children"
                        :key="subleg_index"
                        class="content mb-3"
                      >
                        <div class="content__title">
                          <a :href="`${subleg.work_frbr_uri}`">{{ subleg.title }}</a>
                        </div>
                        <div v-if="showDates" class="content__secondary">
                          {{ subleg.date }}
                        </div>
                        <div v-else class="content__secondary">
                          {{ subleg.citation }}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </template>
          <div
            v-else
            class="p-2 text-center"
          >
            {{ $t('No legislation found.') }}
            <a
              :href="`/search/?q=${encodeURIComponent(q)}`"
              target="_blank"
            >
              {{ $t('Try searching instead') }}
            </a>.
          </div>
        </div>
      </div>
    </div>
    <!-- DOM Hack for i18next to parse facet to locale json. i18next skips t functions in script element -->
    <div v-if="false">
      {{ $t('Years') }}
      {{ $t('Taxonomies') }}
    </div>
  </div>
</template>

<script>
import FilterFacets from '../FilterFacets/index.vue';
import debounce from 'lodash/debounce';

export default {
  name: 'LegislationTable',
  components: {
    FilterFacets
  },
  props: ['showDates'],
  data: () => ({
    offCanvasFacets: null,
    facets: [],
    tableData: [],
    filteredData: [],
    lockAccordion: false,
    q: '',
    windowWith: window.innerWidth,
    sortableFields: {
      title: 'asc',
      citation: '',
      date: ''
    }
  }),
  watch: {
    q () {
      this.filterData();
    },
    sortableFields () {
      this.filterData();
    },
    facets () {
      this.offCanvasFacets.hide();
      this.filterData();
    }
  },
  beforeUnmount () {
    window.removeEventListener('resize', this.setWindowWidth);
  },

  mounted () {
    this.offCanvasFacets = new window.bootstrap.Offcanvas(
      this.$refs['mobile-legislation-facets-ref']
    );
    window.addEventListener('resize', this.setWindowWidth);

    // To use this component json element #legislation-table-data must be in the dom
    const tableJsonElement = document.getElementById('legislation-table');
    this.tableData = JSON.parse(tableJsonElement.textContent);
    this.filterData();
    this.setFacets();
  },

  methods: {
    handleRowClick (e) {
      const parentRow = e.target.closest('.legislation-table__row');
      if (!parentRow.classList.contains('has-children')) return;
      if (
        Array.from(parentRow.querySelectorAll('a')).some(
          (a) => e.target === a || a.contains(e.target)
        )
      ) { return; }
      if (this.lockAccordion) return;
      const collapseElement = parentRow.querySelector('.collapse');
      collapseElement.addEventListener('shown.bs.collapse', () => {
        this.lockAccordion = false;
      });
      collapseElement.addEventListener('hidden.bs.collapse', () => {
        this.lockAccordion = false;
      });
      this.lockAccordion = true;
      // Async action
      parentRow.classList.toggle('expanded');
      return new window.bootstrap.Collapse(collapseElement);
    },
    setWindowWidth: debounce(function () {
      this.windowWith = window.innerWidth;
    }, 100),
    setFacets () {
      const yearsValuesCount = {};
      const resultsWithYears = this.filteredData.filter((item) => item.year);
      resultsWithYears.forEach((result) => {
        yearsValuesCount[result.year] =
          (yearsValuesCount[result.year] || 0) + 1;
      });

      const taxonomiesValuesCount = {};
      const resultsWithTaxonomies = this.filteredData.filter(
        (item) => item.taxonomies.length
      );
      resultsWithTaxonomies.forEach((item) => {
        item.taxonomies.forEach((taxonomy) => {
          taxonomiesValuesCount[taxonomy] =
            (taxonomiesValuesCount[taxonomy] || 0) + 1;
        });
      });

      const generateOptions = (count) => {
        return Object.keys(count).map((key) => ({
          label: key,
          count: count[key],
          value: key
        }));
      };
      const yearsOptions = generateOptions(yearsValuesCount);
      const taxonomyOptions = generateOptions(taxonomiesValuesCount);
      // Sort alphabetically
      taxonomyOptions.sort((a, b) => a.value.localeCompare(b.value));
      // Sort descending
      yearsOptions.sort((a, b) => b.value - a.value);

      this.facets = [
        {
          title: this.$t('Years'),
          name: 'year',
          type: 'radio',
          value: null,
          options: yearsOptions
        },
        {
          title: this.$t('Taxonomies'),
          name: 'taxonomies',
          type: 'checkboxes',
          value: [],
          options: taxonomyOptions
        }
      ];
    },
    updateSort (field) {
      let newSortValue;
      if (this.sortableFields[field] === '') {
        newSortValue = 'asc';
      } else if (this.sortableFields[field] === 'asc') {
        newSortValue = 'desc';
      } else if (this.sortableFields[field] === 'desc') {
        newSortValue = 'asc';
      }
      this.sortableFields = {
        ...{
          title: '',
          citation: '',
          date: ''
        },
        [field]: newSortValue
      };
    },
    filterData () {
      let data = [...this.tableData];
      if (this.q.trim()) {
        data = data.filter((item) => {
          return ['title', 'citation'].some((key) => {
            const value = item[key] || '';
            return value.toLowerCase().includes(this.q.toLowerCase());
          });
        });
      }

      const facetDict = {};
      this.facets.forEach((facet) => {
        if (
          !facet.value ||
          (Array.isArray(facet.value) && !facet.value.length)
        ) { return; }
        facetDict[facet.name] = facet.value;
      });
      Object.keys(facetDict).forEach((key) => {
        data = data.filter((item) => {
          if (Array.isArray(facetDict[key])) {
            const arr1 = facetDict[key].map((x) => String(x));
            const arr2 = item[key].map((x) => String(x));
            return arr1.some((item) => arr2.includes(item));
          } else {
            return String(item[key]) === String(facetDict[key]);
          }
        });
      });

      Object.keys(this.sortableFields).forEach((key) => {
        if (this.sortableFields[key]) {
          data.sort((a, b) => {
            const fa = a[key] ? a[key].toLowerCase() : '';
            const fb = b[key] ? b[key].toLowerCase() : '';
            if (this.sortableFields[key] === 'asc') {
              return fa.localeCompare(fb);
            } else if (this.sortableFields[key] === 'desc') {
              return fb.localeCompare(fa);
            }
          });
        }
      });
      this.filteredData = data;
    }
  }
};
</script>

<style scoped>
.legislation-table__row {
  padding: 0.25rem;
  border-bottom: 1px solid var(--bs-gray-200);
  cursor: default !important;
  transition: background-color 300ms ease-in-out;
}

.legislation-table__row.has-children {
  cursor: pointer !important;
}

.legislation-table__row.has-children:hover {
  background-color: var(--bs-light);
}

.legislation-table__row.headings {
  border-bottom: 1px solid var(--bs-primary);
}

.legislation-table__row.headings i {
  font-size: 18px;
}

.column-caret {
  text-align: center;
}

.legislation-table__row .column-caret .bi-caret-down-fill {
  display: none;
}

.legislation-table__row.expanded .column-caret .bi-caret-down-fill {
  display: block;
}

.legislation-table__row.expanded .column-caret .bi-caret-right-fill {
  display: none;
}

.indent {
  flex: 0 0 30px;
}

.table-row__content-col {
  flex: 1;
}

.table-row {
  display: flex;
  width: 100%;
  flex-wrap: wrap;
}

.table-row .content {
  display: grid;
  grid-gap: 1rem;
  grid-template-columns: repeat(12, 1fr);
}

.content__children {
  grid-column: span 12;
  margin-top: 10px;
}

.content__children .content__title {
  padding-left: 1rem;
}

.content__title {
  grid-column: span 8;
}

.content__secondary {
  grid-column: span 4;
}

.legislation-table.with-dates .content__title {
  grid-column: span 9;
}

.legislation-table.with-dates .content__secondary {
  grid-column: span 3;
}
</style>

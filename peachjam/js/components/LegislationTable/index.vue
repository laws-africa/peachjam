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
        <div class="mb-2">
          <input
            v-model="q"
            type="text"
            class="form-control"
            :placeholder="$t('Filter legislation')"
          >
        </div>
        <div class="mb-3">
          {{ filteredData.length }} of {{ tableData.length }} documents
        </div>
        <div v-if="filteredData.length" class="doc-table doc-table-title-subtitle-date">
          <div class="doc-table-row doc-table-header">
            <div class="doc-table-cell cell-title">
              <div class="indent" />
              <div
                class="title align-items-center"
                role="button"
                @click="updateSort('title')"
              >
                {{ $t('Title') }}
                <i
                  v-if="sortableFields.title === 'asc'"
                  class="bi bi-sort-up ms-2"
                />
                <i
                  v-if="sortableFields.title === 'desc'"
                  class="bi bi-sort-down ms-2"
                />
              </div>
            </div>
            <div class="doc-table-cell cell-subtitle">
              <div
                role="button"
                @click="updateSort('citation')"
              >
                {{ $t('Numbered title') }}
                <i
                  v-if="sortableFields.citation === 'asc'"
                  class="bi bi-sort-up ms-2"
                />
                <i
                  v-if="sortableFields.citation === 'desc'"
                  class="bi bi-sort-down ms-2"
                />
              </div>
            </div>
            <div class="doc-table-cell cell-date">
              <div
                role="button"
                @click="updateSort('year')"
              >
                {{ $t('Year') }}
                <i
                  v-if="sortableFields.year === 'asc'"
                  class="bi bi-sort-up ms-2"
                />
                <i
                  v-if="sortableFields.year === 'desc'"
                  class="bi bi-sort-down ms-2"
                />
              </div>
            </div>
          </div>
          <template
            v-for="(row, index) in rows"
            :key="index"
          >
            <template v-if="row.heading != null">
              <div class="doc-table-row">
                <div class="doc-table-cell cell-group">
                  {{ row.heading }}
                </div>
              </div>
            </template>
            <table-row
              v-else
              :id="`row-${index}`"
              :row="row"
              @toggle="toggleChildren(index)"
            />
            <template v-if="row.children && row.children.length">
              <div
                :id="`children-${index}`"
                class="doc-table-children collapse"
              >
                <table-row
                  v-for="(child, childIndex) in row.children"
                  :key="childIndex"
                  :row="child"
                />
              </div>
            </template>
          </template>
        </div>
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
    <!-- DOM Hack for i18next to parse facet to locale json. i18next skips t functions in script element -->
    <div v-if="false">
      {{ $t('Years') }}
      {{ $t('Taxonomies') }}
      {{ $t('Alphabetical') }}
    </div>
  </div>
</template>

<script>
import FilterFacets from '../FilterFacets/index.vue';
import TableRow from './TableRow.vue';
import debounce from 'lodash/debounce';

export default {
  name: 'LegislationTable',
  components: {
    FilterFacets,
    TableRow
  },
  props: ['showDates'],
  data: () => ({
    offCanvasFacets: null,
    facets: [],
    tableData: [],
    filteredData: [],
    rows: [],
    lockAccordion: false,
    q: '',
    windowWith: window.innerWidth,
    sortableFields: {
      title: 'asc',
      citation: '',
      year: ''
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
    toggleChildren (index) {
      const row = document.getElementById(`row-${index}`);
      const groupEl = document.getElementById(`children-${index}`);
      if (row && groupEl) {
        row.classList.toggle('expanded');
        return new window.bootstrap.Collapse(groupEl, { toggle: true });
      }
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
      const alphabet = 'abcdefghijklmnopqrstuvwxyz'.split('').map(letter => ({
        label: letter.toUpperCase(),
        value: letter
      }));
      this.facets = [
        {
          title: this.$t('Alphabetical'),
          name: 'alphabetical',
          type: 'letter-radio',
          value: [],
          options: alphabet
        },
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
          year: ''
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
          if (key === 'alphabetical') {
            return item.title.toLowerCase().startsWith(facetDict[key]);
          }
          if (Array.isArray(facetDict[key])) {
            const arr1 = facetDict[key].map((x) => String(x));
            const arr2 = item[key].map((x) => String(x));
            return arr1.some((item) => arr2.includes(item));
          } else {
            return String(item[key]) === String(facetDict[key]);
          }
        });
      });

      let sortKey = null;
      Object.keys(this.sortableFields).forEach((key) => {
        if (this.sortableFields[key]) {
          sortKey = key;
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

      this.rows = [];
      // group rows for headings
      function groupKey (record) {
        const val = record[sortKey] || '';
        if (sortKey === 'year') {
          // return year
          return val.substring(0, 4);
        } else {
          // letter
          return (val && val.length) ? val[0].toUpperCase() : '';
        }
      }

      let currentGroup = '';
      this.filteredData.forEach((record) => {
        const group = groupKey(record);
        if (group !== currentGroup) {
          currentGroup = group;
          this.rows.push({
            heading: group,
            children: []
          });
        }
        this.rows.push(record);
      });
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
  grid-column: span 6;
}

.legislation-table.with-dates .content__secondary {
  grid-column: span 3;
}
</style>

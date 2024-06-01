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
        <div class="mb-2 d-flex">
          <div class="flex-grow-1 me-2">
            <input
              v-model="q"
              type="text"
              class="form-control"
              :placeholder="$t('Filter legislation')"
            >
          </div>
          <div>
            <select class="form-control" v-model="sort">
              <option value="title">{{ $t('Title') }} (A - Z)</option>
              <option value="-title">{{ $t('Title') }} (Z - A)</option>
              <option value="year">{{ $t('Year') }} ({{ $t('Newest first') }})</option>
              <option value="-year">{{ $t('Year') }} ({{ $t('Oldest first') }})</option>
            </select>
          </div>
        </div>
        <div class="mb-3">
          {{ filteredData.length }} of {{ tableData.length }} documents
        </div>
        <table v-if="filteredData.length" class="doc-table doc-table--toggle">
          <thead>
            <tr>
              <th class="cell-toggle" />
              <th class="cell-title">
                <div
                  class="align-items-center"
                  role="button"
                  @click="updateSort('title')"
                >
                  {{ $t('Title') }}
                  <i v-if="sort === 'title'" class="bi bi-sort-up ms-2" />
                  <i v-if="sort === '-title'" class="bi bi-sort-down ms-2" />
                </div>
              </th>
              <th v-if="!hideCitations" class="cell-citation" />
              <th class="cell-date">
                <div
                  role="button"
                  @click="updateSort('year')"
                >
                  {{ $t('Year') }}
                  <i v-if="sort === 'year'" class="bi bi-sort-up ms-2" />
                  <i v-if="sort === '-year'" class="bi bi-sort-down ms-2" />
                </div>
              </th>
            </tr>
          </thead>
          <template
            v-for="(row, index) in rows"
            :key="index"
          >
            <template v-if="row.heading != null">
              <tr>
                <td class="cell-toggle" />
                <td class="cell-group" :colspan="hideCitations ? 2 : 3">
                  {{ row.heading }}
                </td>
              </tr>
            </template>
            <table-row
              v-else
              :id="`row-${index}`"
              :row="row"
              :hide-citation="hideCitations"
              @toggle="toggleChildren(index)"
            />
            <template v-if="row.children && row.children.length">
              <tbody
                :id="`children-${index}`"
                class="doc-table-children collapse"
              >
                <table-row
                  v-for="(child, childIndex) in row.children"
                  :key="childIndex"
                  :row="child"
                  :hide-citation="hideCitations"
                />
              </tbody>
            </template>
          </template>
        </table>
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
  props: ['hideCitations'],
  data: () => ({
    offCanvasFacets: null,
    facets: [],
    tableData: [],
    filteredData: [],
    rows: [],
    lockAccordion: false,
    q: '',
    windowWith: window.innerWidth,
    sort: 'title'
  }),
  watch: {
    q () {
      this.filterData();
    },
    sort () {
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
      if (this.sort === field) {
        this.sort = `-${field}`;
      } else {
        this.sort = field;
      }
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

      const sortAsc = this.sort[0] !== '-';
      const sortKey = sortAsc ? this.sort : this.sort.substring(1);
      this.sortRows(data, sortKey, sortAsc);
      for (const item of data) {
        this.sortRows(item.children, sortKey, sortAsc);
      }
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
    },
    sortRows (rows, sortKey, sortAsc) {
      rows.sort((a, b) => {
        const fa = a[sortKey] ? a[sortKey].toLowerCase() : '';
        const fb = b[sortKey] ? b[sortKey].toLowerCase() : '';
        // year is the exception that we want to sort desc by default
        return fa.localeCompare(fb) * (sortAsc ? 1 : -1) * (sortKey === 'year' ? -1 : 1);
      });
    }
  }
};
</script>

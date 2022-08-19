<template>
  <div class="row">
    <div
      v-if="showSideFilters"
      class="col col-lg-3"
    >
      <SecondaryFacets v-model="facets" />
    </div>
    <div
      class="col"
    >
      <div class="card legislation-table">
        <div class="card-header">
          <div class="input-group">
            <button
              class="btn btn-outline-secondary dropdown-toggle"
              type="button"
              data-bs-toggle="dropdown"
              aria-expanded="false"
            >
              Search by {{ filters[selectedFilterKey].label }}
            </button>
            <ul class="dropdown-menu">
              <li>
                <button
                  type="button"
                  class="dropdown-item"
                  @click="updateFilterBy('title')"
                >
                  Title
                </button>
              </li>
              <li>
                <button
                  type="button"
                  class="dropdown-item"
                  @click="updateFilterBy('citation')"
                >
                  Numbered title
                </button>
              </li>
            </ul>
            <input
              v-model="filters[selectedFilterKey].value"
              type="text"
              class="form-control"
              placeholder="Search documents"
            >
          </div>
        </div>
        <div
          class="legislation-table__row"
        >
          <div class="column-caret" />
          <div class="column">
            <strong>{{ tableData.length }} documents in total</strong>
          </div>
        </div>
        <div class="legislation-table__row headings">
          <div class="column-caret" />
          <div
            class="column d-flex align-items-center"
            role="button"
            @click="updateSort('title')"
          >
            <strong>Title</strong>
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
            class="column"
            role="button"
            @click="updateSort('citation')"
          >
            <strong>Numbered title</strong>
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
        <div
          v-for="(row, index) in filteredData"
          :key="index"
          class="legislation-table__row"
        >
          <div
            class="column-caret"
            data-bs-toggle="collapse"
            :data-bs-target="`#row-accordion-${index}`"
            aria-expanded="false"
            role="button"
            :aria-controls="`row-accordion-${index}`"
          >
            <i
              v-if="row.sublegs"
              class="bi bi-caret-right-fill"
            />
            <i
              v-if="row.sublegs"
              class="bi bi-caret-down-fill"
            />
          </div>
          <div class="column">
            <div>
              <a
                href="#"
                target="_blank"
              >{{ row.title }}</a>
            </div>
            <div class="column__subtitle">
              {{ row.frbr_uri }}
            </div>
          </div>
          <div class="column">
            {{ row.citation }}
          </div>
          <div
            v-if="row.sublegs"
            :id="`row-accordion-${index}`"
            class="accordion-collapse collapse column__accordion accordion"
            data-bs-parent=".legislation-table__row"
          >
            <div class="accordion-body">
              <div
                v-for="(leg, subleg_index) in row.sublegs"
                :key="subleg_index"
              >
                {{ leg.title }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import SecondaryFacets from './SecondaryFacets.vue';

export default {
  name: 'LegislationTable',
  components: {
    SecondaryFacets
  },
  data: () => ({
    facets: [],
    showSideFilters: false,
    tableData: [],
    filteredData: [],
    selectedFilterKey: 'title',
    filters: {
      title: {
        label: 'title',
        value: ''
      },
      citation: {
        label: 'numbered title',
        value: ''
      }

    },
    sortableFields: {
      title: 'asc',
      citation: ''
    }
  }),
  watch: {
    filters: {
      deep: true,
      handler () {
        this.filterData();
      }
    },
    sortableFields: {
      deep: true,
      handler () {
        this.filterData();
      }
    }
  },

  mounted () {
    const root = this.$el.closest('[data-vue-component="LegislationTable"]');
    if (Object.keys(root.dataset).includes('showSideFacets')) this.showSideFilters = true;

    // To use this component json element #legislation-table-data must be in the dom
    const tableJsonElement = document.getElementById('legislation-table');
    const facetDataElement = document.getElementById('facet-data');
    this.tableData = JSON.parse(tableJsonElement.textContent);
    const facetData = JSON.parse(facetDataElement.textContent);
    this.facets = [
      {
        title: 'Taxonomies',
        type: 'checkbox',
        name: 'taxonomies',
        value: [],
        options: facetData.taxonomies.map(taxonomy => ({
          label: taxonomy,
          value: taxonomy
        }))
      },

      {
        title: 'Years',
        type: 'radio',
        name: 'years',
        value: null,
        options: facetData.years.map(year => ({
          label: year,
          value: year
        }))
      }
    ];
    this.filterData();
  },

  methods: {
    updateFilterBy (field) {
      Object.keys(this.filters).forEach(key => { this.filters[key].value = ''; });
      this.selectedFilterKey = field;
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
          citation: ''
        },
        [field]: newSortValue
      };
    },
    filterData () {
      let data = [...this.tableData];
      data = data.filter(item => {
        const fieldValue = item[this.selectedFilterKey] || '';
        return fieldValue.toLowerCase().includes(this.filters[this.selectedFilterKey].value.toLowerCase());
      });
      Object.keys(this.sortableFields).forEach(key => {
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
.legislation-table__row.headings {
  border-bottom: 1px solid var(--bs-primary);
  margin-bottom: 0.5rem;
}

.legislation-table__row.headings i {
  font-size: 18px;
}

.legislation-table__row {
  display: flex;
  width: 100%;
  padding: 0.25rem;
  border-bottom: 1px solid var(--bs-gray-200);
  flex-wrap: wrap;
}

.column-caret[aria-expanded="false"] .bi-caret-down-fill {
  display: none;
}

.column-caret[aria-expanded="true"] .bi-caret-right-fill {
  display: none;
}

.legislation-table__row .column-caret {
  width: 30px;
  text-align: center;
}

.legislation-table__row .column {
  flex:1;
  width: 100%;
}

.legislation-table__row .column__subtitle {
  color: var(--bs-gray-500);
}

.legislation-table__row .accordion {
  width: 100%;
}
</style>

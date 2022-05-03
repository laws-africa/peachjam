<template>
  <div
    id="filtersAccordion"
    class="accordion"
  >
    <div class="accordion-item">
      <h2
        class="accordion-header"
      >
        <button
          class="accordion-button"
          type="button"
          data-bs-toggle="collapse"
          data-bs-target="#yearsCollapse"
          aria-expanded="true"
          aria-controls="yearsCollapse"
        >
          Years
        </button>
      </h2>
      <div
        id="yearsCollapse"
        class="accordion-collapse collapse show"
        data-bs-parent="#filtersAccordion"
      >
        <div class="accordion-body">
          <div
            v-for="(year, index) in years"
            :key="index"
            class="form-check"
          >
            <input
              :id="year"
              v-model="filters.years"
              class="form-check-input"
              type="checkbox"
              name="year"
            >
            <label
              class="form-check-label"
              :for="year"
            >
              {{ year }}
            </label>
          </div>
        </div>
      </div>
    </div>
    <div class="accordion-item">
      <h2
        class="accordion-header"
      >
        <button
          class="accordion-button"
          type="button"
          data-bs-toggle="collapse"
          data-bs-target="#alphabeticalCollapse"
          aria-expanded="true"
          aria-controls="alphabeticalCollapse"
        >
          Alphabetical
        </button>
      </h2>
      <div
        id="alphabeticalCollapse"
        class="accordion-collapse collapse show"
        data-bs-parent="#filtersAccordion"
      >
        <div class="accordion-body">
          <div class="letter-radiobox-container">
            <label
              v-for="(letter, key) in letters"
              :key="key"
              class="letter-radiobox"
            >
              <input
                :key="key"
                v-model="filters.letter"
                type="radio"
                name="letter"
              >
              <span class="letter-radiobox__text">
                {{ letter }}
              </span>
            </label>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'ListingFacets',
  data: () => ({
    page: 1,
    date: null,
    filters: {
      letter: '',
      years: []
    },
    letters: ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z'],
    years: [2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022]
  }),
  watch: {
    filters: {
      deep: true,
      handler () {

      }
    }
  },
  methods: {
    loadState () {
      // load state from URL
      const params = new URLSearchParams(document.location.search);
      // skip the first event if there's a query, because the page load will already have sent it
      this.page = parseInt(params.get('page')) || this.page;

      for (const filter of Object.keys(this.filters)) {
        if (params.has(filter)) {
          this.filters[filter] = params.getAll(filter);
        }
      }

      this.search();
    }
  }
};
</script>

<style scoped>
.letter-radiobox-container {
  display: flex;
  flex-flow: row wrap;
  justify-content: center;
}

.letter-radiobox {
  height: 40px;
  width: 40px;
  border-radius: 5px;
  cursor: pointer;
  overflow: hidden;
}
.letter-radiobox input {
  display: none;
}

.letter-radiobox__text {
  height: 100%;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 200ms ease-in-out, background-color 200ms ease-in-out;
  text-transform: uppercase;
}

.letter-radiobox:hover .letter-radiobox__text {
  background-color: rgba(238, 120, 69, 0.3);
}

.letter-radiobox input:checked + .letter-radiobox__text {
  background-color: #EE7845;
  color: white;
}

</style>

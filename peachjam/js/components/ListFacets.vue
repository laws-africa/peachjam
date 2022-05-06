<template>
  <form
    ref="form"
    method="get"
    @change="submit"
  >
    <ul class="list-group">
      <li class="list-group-item bg-light d-flex justify-content-between align-items-center">
        <strong>Filters</strong>
        <a
          v-if="showClearAllFilter"
          href="#"
          @click.prevent="clearAll"
        >
          Clear all
        </a>
      </li>
      <li class="list-group-item">
        <div class="d-flex justify-content-between mb-2">
          <strong>Year</strong>
          <a
            v-if="yearParam.length"
            href="#"
            @click.prevent="clearFacet('year')"
          >
            Clear
          </a>
        </div>
        <div
          v-for="(year, index) in years"
          :key="index"
          class="form-check"
        >
          <input
            :id="year"
            ref="yearInput"
            class="form-check-input"
            type="checkbox"
            name="year"
            :value="year"
            :checked="yearInputChecked(year)"
          >
          <label
            class="form-check-label"
            :for="year"
          >
            {{ year }}
          </label>
        </div>
      </li>
      <li class="list-group-item">
        <div class="d-flex justify-content-between mb-2">
          <strong>Alphabetical</strong>
          <a
            v-if="alphabetParam.length"
            href="#"
            @click.prevent="clearFacet('alphabet')"
          >
            Clear
          </a>
        </div>
        <div class="letter-radiobox-container">
          <label
            v-for="(letter, key) in alphabet"
            :key="key"
            class="letter-radiobox"
          >
            <input
              :key="key"
              ref="alphabetInput"
              :value="letter"
              :checked="alphabetInputChecked(letter)"
              type="radio"
              name="alphabet"
            >
            <span class="letter-radiobox__text">
              {{ letter }}
            </span>
          </label>
        </div>
      </li>
    </ul>
  </form>
</template>

<script>
export default {
  name: 'ListFacets',
  emits: ['form-changed'],
  data: () => ({
    page: 1,
    loading: false,
    alphabet: ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z'],
    years: ['2022', '2021', '2020', '2019', '2018', '2017', '2016', '2015', '2014', '2013', '2012', '2011']
  }),

  computed: {
    alphabetParam () {
      return this.getUrlParamValue('alphabet');
    },
    yearParam () {
      return this.getUrlParamValue('year');
    },
    showClearAllFilter () {
      return this.alphabetParam.length || this.yearParam.length;
    }
  },
  methods: {
    yearInputChecked (value) {
      return this.yearParam.includes(value);
    },
    alphabetInputChecked (value) {
      return this.alphabetParam.includes(value);
    },

    clearAll () {
      window.location.href = `${window.location.origin}${window.location.pathname}`;
    },

    clearFacet (key) {
      const queryString = window.location.search;
      const urlParams = new URLSearchParams(queryString);
      urlParams.delete(key);
      window.location.href = `${window.location.origin}${window.location.pathname}?${urlParams.toString()}`;
    },
    getUrlParamValue (key) {
      const queryString = window.location.search;
      const urlParams = new URLSearchParams(queryString);
      return urlParams.getAll(key);
    },
    submit () {
      this.$el.dispatchEvent(new CustomEvent('submitted', {
        bubbles: true
      }));
      this.$refs.form.submit();
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

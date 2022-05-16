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
      <li
        v-if="authors.length"
        class="list-group-item"
      >
        <div class="d-flex justify-content-between mb-2">
          <strong>Author</strong>
          <a
            v-if="author"
            href="#"
            @click.prevent="clearFacet('author')"
          >
            Clear
          </a>
        </div>
        <input
          v-if="author"
          name="author"
          :value="author"
          type="hidden"
        >
        <Multiselect
          v-model="author"
          name="author"
          :options="authors"
          :searchable="true"
          placeholder="Filter by author"
          :can-clear="false"
          class="author-select"
        />
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
          class="d-flex justify-content-between align-items-center"
        >
          <div class="form-check">
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
          <div
            v-if="loading"
            class="circle-loader"
          />
        </div>
      </li>
      <li class="list-group-item">
        <div class="d-flex justify-content-between mb-2">
          <strong>Alphabetical</strong>
          <div class="d-flex">
            <a
              v-if="alphabetParam.length"
              href="#"
              @click.prevent="clearFacet('alphabet')"
            >
              Clear
            </a>
            <span
              v-if="loading"
              class="circle-loader mx-2"
            />
          </div>
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
import { nextTick } from 'vue';
import Multiselect from '@vueform/multiselect';
import '@vueform/multiselect/themes/default.css';

export default {
  name: 'ListFacets',
  components: {
    Multiselect
  },
  props: {
    alphabet: {
      type: Array,
      default: () => []
    },
    authors: {
      type: Array,
      default: () => []
    },
    years: {
      type: Array,
      default: () => []
    }
  },
  data: () => {
    const queryString = window.location.search;
    const urlParams = new URLSearchParams(queryString);
    const author = urlParams.get('author');
    return {
      loading: false,
      author
    };
  },

  computed: {
    alphabetParam () {
      return this.getUrlParamValue('alphabet');
    },
    yearParam () {
      return this.getUrlParamValue('year');
    },
    showClearAllFilter () {
      return this.alphabetParam.length || this.yearParam.length || this.author;
    }
  },
  watch: {
    author () {
      nextTick().then(() => {
        this.submit();
      });
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
      this.loading = true;
      // On submit page refreshes
      this.$refs.form.submit();
    }
  }
};
</script>

<style scoped>
.author-select {
  --ms-font-size: 14px;
  --ms-option-font-size: 14px;
}

</style>

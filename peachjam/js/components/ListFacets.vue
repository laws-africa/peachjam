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
        v-if="years.length"
        class="list-group-item"
      >
        <div class="d-flex justify-content-between mb-2">
          <strong>Year</strong>
          <div class="d-flex align-items-center">
            <a
              v-if="yearParam.length"
              href="#"
              @click.prevent="clearFacet('year')"
            >
              Clear
            </a>
            <div
              v-if="loading"
              class="circle-loader ms-2"
            />
          </div>
        </div>
        <div
          v-for="(year, index) in orderedYears"
          :key="index"
          class="d-flex justify-content-between align-items-center"
        >
          <div class="form-check">
            <input
              :id="year"
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
        </div>
      </li>
      <li
        v-if="authors.length"
        class="list-group-item"
      >
        <div class="d-flex justify-content-between mb-2">
          <strong>Authors</strong>
          <div class="d-flex">
            <a
              v-if="authorParam.length"
              href="#"
              @click.prevent="clearFacet('author')"
            >
              Clear
            </a>
            <span
              v-if="loading"
              class="circle-loader mx-2"
            />
          </div>
        </div>
        <input
          ref="hidden-author-input"
          type="hidden"
          name="author"
        >
        <Multiselect
          v-model="author"
          :options="authorsOptions"
          :searchable="true"
          :can-clear="false"
          placeholder="Filter by author"
          class="author-select"
          @change="handleAuthorChange"
        />
      </li>
      <li
        v-if="alphabet.length"
        class="list-group-item"
      >
        <div class="d-flex justify-content-between mb-2">
          <strong>Alphabetical</strong>
          <div class="d-flex align-items-center">
            <a
              v-if="alphabetParam.length"
              href="#"
              @click.prevent="clearFacet('alphabet')"
            >
              Clear
            </a>
            <span
              v-if="loading"
              class="circle-loader ms-2"
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
    authors: {
      type: Array,
      default: () => []
    },
    alphabet: {
      type: Array,
      default: () => []
    },
    years: {
      type: Array,
      default: () => []
    }
  },
  data: () => {
    return {
      loading: false,
      author: null
    };
  },

  computed: {
    alphabetParam () {
      return this.getUrlParamValue('alphabet');
    },
    yearParam () {
      return this.getUrlParamValue('year');
    },
    authorParam () {
      return this.getUrlParamValue('author');
    },
    showClearAllFilter () {
      return this.alphabetParam.length || this.yearParam.length || this.authorParam.length;
    },
    authorsOptions () {
      return this.authors.map(author => ({
        label: author.name,
        value: author.id
      }));
      return this.alphabetParam.length || this.yearParam.length;
    },
    orderedYears () {
      const years = [...this.years];
      // largest to smallest
      return years.sort((a, b) => b - a);
    }
  },

  mounted () {
    if (this.authorParam.length) {
      this.$refs['hidden-author-input'].value = this.authorParam[0];
      this.author = this.authorParam[0];
    }
  },
  methods: {
    yearInputChecked (value) {
      return this.yearParam.includes(value.toString());
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
    handleAuthorChange (id) {
      this.$refs['hidden-author-input'].value = id;
      nextTick().then(() => this.submit());
    },
    submit () {
      this.loading = true;
      // On submit page refreshes
      // Prevention of empty query params
      for (const input of this.$refs.form.querySelectorAll('input')) {
        if (!input.value) input.setAttribute('disabled', '');
      }
      this.$refs.form.submit();
    }
  }
};
</script>

<style scoped>
.author-select {
  --ms-font-size: 14px;
  --ms-option-font-size: 14px;
  --ms-ring-color: none;
  --ms-option-bg-selected: var(--bs-primary);
  --ms-option-bg-selected-pointed: var(--bs-primary);
}
</style>

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
              v-if="getUrlParamValue('year').length"
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
              :checked="inputChecked('year', year)"
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
        v-if="authoringBodies.length"
        class="list-group-item"
      >
        <div class="d-flex justify-content-between mb-2">
          <strong>Authoring Body</strong>
          <div class="d-flex align-items-center">
            <a
              v-if="getUrlParamValue('authoring-body').length"
              href="#"
              @click.prevent="clearFacet('authoring-body')"
            >
              Clear
            </a>
            <span
              v-if="loading"
              class="circle-loader ms-2"
            />
          </div>
        </div>
        <div
          v-for="(authoringBody, index) in authoringBodies"
          :key="index"
          class="d-flex justify-content-between align-items-center"
        >
          <div class="form-check">
            <input
              :id="authoringBody"
              class="form-check-input"
              type="radio"
              name="authoring-body"
              :value="authoringBody"
              :checked="inputChecked('authoring-body', authoringBody)"
            >
            <label
              class="form-check-label"
              :for="authoringBody"
            >
              {{ authoringBody }}
            </label>
          </div>
        </div>
      </li>
      <li
        v-if="courts.length"
        class="list-group-item"
      >
        <div class="d-flex justify-content-between mb-2">
          <strong>Court</strong>
          <div class="d-flex align-items-center">
            <a
              v-if="getUrlParamValue('court').length"
              href="#"
              @click.prevent="clearFacet('court')"
            >
              Clear
            </a>
            <span
              v-if="loading"
              class="circle-loader ms-2"
            />
          </div>
        </div>
        <div
          v-for="(court, index) in courts"
          :key="index"
          class="d-flex justify-content-between align-items-center"
        >
          <div class="form-check">
            <input
              :id="court"
              class="form-check-input"
              type="radio"
              name="court"
              :value="court"
              :checked="inputChecked('court', court)"
            >
            <label
              class="form-check-label"
              :for="court"
            >
              {{ court }}
            </label>
          </div>
        </div>
      </li>
      <li
        v-if="alphabet.length"
        class="list-group-item"
      >
        <div class="d-flex justify-content-between mb-2">
          <strong>Alphabetical</strong>
          <div class="d-flex align-items-center">
            <a
              v-if="getUrlParamValue('alphabet').length"
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
              :value="letter"
              :checked="inputChecked('alphabet', letter)"
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
  props: {
    authoringBodies: {
      type: Array,
      default: () => []
    },
    courts: {
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
    showClearAllFilter () {
      return ['alphabet', 'year', 'authoring-body', 'court'].some(key => this.getUrlParamValue(key).length);
    },
    orderedYears () {
      const years = [...this.years];
      // largest to smallest
      return years.sort((a, b) => b - a);
    }
  },
  methods: {
    getUrlParamValue (key) {
      const queryString = window.location.search;
      const urlParams = new URLSearchParams(queryString);
      return urlParams.getAll(key);
    },
    inputChecked (key, value) {
      return this.getUrlParamValue(key).includes(value.toString());
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

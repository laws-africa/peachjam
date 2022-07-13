<template>
  <form
    ref="form"
    method="get"
    @change="submit"
  >
    <ul class="list-group">
      <li class="list-group-item bg-light d-flex justify-content-between align-items-center">
        <strong>{{ $t('Filters') }}</strong>
        <a
          v-if="showClearAllFilter"
          href="#"
          @click.prevent="clearAll"
        >
          {{ $t('Clear all') }}
        </a>
      </li>
      <li
        v-if="authors.length"
        class="list-group-item"
      >
        <div class="d-flex justify-content-between mb-2">
          <strong>{{ $t('Authoring Body') }}</strong>
          <div class="d-flex align-items-center">
            <a
              v-if="getUrlParamValue('author').length"
              href="#"
              @click.prevent="clearFacet('author')"
            >
              {{ $t('Clear') }}
            </a>
            <span
              v-if="loading"
              class="circle-loader ms-2"
            />
          </div>
        </div>
        <div class="facets-scrollable">
          <div
            v-for="(author, index) in sortAlphabetically(authors)"
            :key="index"
            class="d-flex justify-content-between align-items-center"
          >
            <div class="form-check">
              <input
                :id="author"
                class="form-check-input"
                type="radio"
                name="author"
                :value="author"
                :checked="inputChecked('author', author)"
              >
              <label
                class="form-check-label"
                :for="author"
              >
                {{ author }}
              </label>
            </div>
          </div>
        </div>
      </li>
      <li
        v-if="docTypes.length"
        class="list-group-item"
      >
        <div class="d-flex justify-content-between mb-2">
          <strong>{{ $t('Document type') }}</strong>
          <div class="d-flex align-items-center">
            <a
              v-if="getUrlParamValue('doc_type').length"
              href="#"
              @click.prevent="clearFacet('doc_type')"
            >
              {{ $t('Clear') }}
            </a>
            <span
              v-if="loading"
              class="circle-loader ms-2"
            />
          </div>
        </div>
        <div class="facets-scrollable">
          <div
            v-for="(docType, index) in sortAlphabetically(docTypes)"
            :key="index"
            class="d-flex justify-content-between align-items-center"
          >
            <div class="form-check">
              <input
                :id="docType"
                class="form-check-input"
                type="checkbox"
                name="doc_type"
                :value="docType"
                :checked="inputChecked('doc_type', docType)"
              >
              <label
                class="form-check-label"
                :for="docType"
              >
                {{ getDocTypeLabel(docType) }}
              </label>
            </div>
          </div>
        </div>
      </li>
      <li
        v-if="courts.length"
        class="list-group-item"
      >
        <div class="d-flex justify-content-between mb-2">
          <strong>{{ $t('Court') }}</strong>
          <div class="d-flex align-items-center">
            <a
              v-if="getUrlParamValue('court').length"
              href="#"
              @click.prevent="clearFacet('court')"
            >
              {{ $t('Clear') }}
            </a>
            <span
              v-if="loading"
              class="circle-loader ms-2"
            />
          </div>
        </div>
        <div class="facets-scrollable">
          <div
            v-for="(court, index) in sortAlphabetically(courts)"
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
        </div>
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
              {{ $t('Clear') }}
            </a>
            <div
              v-if="loading"
              class="circle-loader ms-2"
            />
          </div>
        </div>
        <div class="facets-scrollable">
          <div
            v-for="(year, index) in sortDescending(years)"
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
        </div>
      </li>
      <li
        v-if="alphabet.length"
        class="list-group-item"
      >
        <div class="d-flex justify-content-between mb-2">
          <strong>{{ $t("Alphabetical") }}</strong>
          <div class="d-flex align-items-center">
            <a
              v-if="getUrlParamValue('alphabet').length"
              href="#"
              @click.prevent="clearFacet('alphabet')"
            >
              {{ $t('Clear') }}
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
    authors: {
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
    },
    docTypes: {
      type: Array,
      default: () => []
    }
  },
  data: () => {
    return {
      loading: false
    };
  },
  computed: {
    showClearAllFilter () {
      return ['alphabet', 'year', 'author', 'court'].some(key => this.getUrlParamValue(key).length);
    }
  },
  methods: {
    getDocTypeLabel (value) {
      return value.split('_').map(word => `${word[0].toUpperCase()}${word.slice(1, word.length)}`).join(' ');
    },
    sortAlphabetically (items) {
      const sorted = [...items];
      return sorted.sort((a, b) => a.localeCompare(b));
    },
    sortDescending (items) {
      const sorted = [...items];
      return sorted.sort((a, b) => b - a);
    },
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

<style scoped>
.facets-scrollable {
  max-height: 25vh;
  overflow-y: auto;
}
</style>

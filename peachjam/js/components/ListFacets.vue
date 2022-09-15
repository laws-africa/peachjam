<template>
  <form
    ref="form"
    method="get"
    @change="submit"
  >
    <FilterFacets v-model="facets" />
  </form>
</template>

<script>
import FilterFacets from './FilterFacets/index.vue';
export default {
  name: 'ListFacets',
  components: { FilterFacets },
  props: {
    judges: {
      type: Array,
      default: () => []
    },
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
      loading: false,
      facets: []
    };
  },
  computed: {
    showClearAllFilter () {
      return ['alphabet', 'year', 'author', 'court'].some(
        (key) => this.getUrlParamValue(key).length
      );
    }
  },
  mounted () {
    this.loadFacets();
  },
  methods: {
    getDocTypeLabel (value) {
      return value
        .split('_')
        .map((word) => `${word[0].toUpperCase()}${word.slice(1, word.length)}`)
        .join(' ');
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
      window.location.href = `${window.location.origin}${
        window.location.pathname
      }?${urlParams.toString()}`;
    },
    submit () {
      this.loading = true;

      this.$refs.form.submit();
    },
    loadFacets () {
      const facetTitle = {
        alphabet: 'Alphabetical',
        authors: 'Regional Body',
        courts: 'Court',
        docTypes: 'Document type',
        judges: 'Judges',
        years: 'Year'
      };
      const formatOptions = (options) => {
        return options.map((option) => ({
          label: option,
          value: option
        }));
      };

      for (const key in this.$props) {
        if (this.$props[key].length && key !== 'alphabet') {
          if (key === 'years') {
            this.facets.push({
              title: facetTitle[key],
              name: key,
              type: 'checkboxes',
              value: this.getUrlParamValue(key),
              options: formatOptions(this.sortDescending(this.$props[key]))
            });
          } else {
            this.facets.push({
              title: facetTitle[key],
              name: key,
              type: 'radio',
              value: this.getUrlParamValue(key).length
                ? this.getUrlParamValue(key)[0]
                : null,
              options: formatOptions(this.sortAlphabetically(this.$props[key]))
            });
          }
        }
      }
      if (this.alphabet.length) {
        this.facets.push({
          title: facetTitle.alphabet,
          name: 'alphabet',
          type: 'letter-radio',
          value: this.getUrlParamValue('alphabet').length
            ? this.getUrlParamValue('alphabet')[0]
            : null,
          options: formatOptions(this.alphabet)
        });
      }
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

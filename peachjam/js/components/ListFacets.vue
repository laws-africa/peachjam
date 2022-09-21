<template>
  <form
    ref="form"
    method="get"
  >
    <FilterFacets
      v-model="facets"
      :loading="loading"
    />
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

  data () {
    return {
      loading: false,
      facets: this.getFacets()
    };
  },

  watch: {
    facets () {
      this.$nextTick(() => this.submit());
    }
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

    submit () {
      this.loading = true;
      this.$refs.form.submit();
    },

    getFacets () {
      const facetTitles = [
        { key: 'authors', value: 'Regional Body' },
        { key: 'courts', value: 'Court' },
        { key: 'docTypes', value: 'Document type' },
        { key: 'judges', value: 'Judges' },
        { key: 'years', value: 'Year' },
        { key: 'alphabet', value: 'Alphabetical' }
      ];

      const formatOptions = (options, key) => {
        return options.map((option) => {
          if (key === 'docTypes') {
            return {
              label: this.getDocTypeLabel(option),
              value: option
            };
          }
          return {
            label: option,
            value: option
          };
        });
      };

      return facetTitles.map(facet => {
        if (!this.$props[facet.key].length) return {};

        if (facet.key === 'alphabet') {
          return {
            title: facet.value,
            name: facet.key,
            type: 'letter-radio',
            value: this.getUrlParamValue(facet.key).length
              ? this.getUrlParamValue(facet.key)[0]
              : null,
            options: formatOptions(this.alphabet, facet.key)
          };
        } else if (facet.key === 'years') {
          return {
            title: facet.value,
            name: facet.key,
            type: 'checkboxes',
            value: this.getUrlParamValue(facet.key),
            options: formatOptions(this.sortDescending(this.years, facet.key))
          };
        } else {
          return {
            title: facet.value,
            name: facet.key,
            type: 'radio',
            value: this.getUrlParamValue(facet.key).length
              ? this.getUrlParamValue(facet.key)[0]
              : null,
            options: formatOptions(this.sortAlphabetically(this.$props[facet.key]), facet.key)
          };
        }
      });
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

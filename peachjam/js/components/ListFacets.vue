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
  <!-- DOM Hack for i18next to parse facet to locale json. i18next skips t functions in script element -->
  <div v-if="false">
    {{ $t('Alphabetical') }}
    {{ $t('Document type') }}
    {{ $t('Judges') }}
    {{ $t('Attorneys') }}
    {{ $t('Nature') }}
    {{ $t('Locality') }}
    {{ $t('Regional body') }}
    {{ $t('Year') }}
  </div>
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
    },
    natures: {
      type: Array,
      default: () => []
    },
    jurisdictions: {
      type: Array,
      default: () => []
    },
    localities: {
      type: Array,
      default: () => []
    },
    registries: {
      type: Array,
      default: () => []
    },
    attorneys: {
      type: Array,
      default: () => []
    },
    order_outcomes: {
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
    getDocNatureLabel (value) {
      return value.split();
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
      const facets = [
        {
          name: 'authors',
          type: 'radio',
          title: JSON.parse(document.querySelector('#data-labels').textContent).author
        },
        {
          name: 'docTypes',
          type: 'radio',
          title: this.$t('Document type')
        },
        {
          name: 'natures',
          type: 'checkboxes',
          title: this.$t('Nature')
        },
        {
          name: 'judges',
          type: 'radio',
          title: this.$t('Judges')
        },
        {
          name: 'order_outcomes',
          type: 'checkboxes',
          title: this.$t('Order')
        },
        {
          name: 'jurisdictions',
          type: 'checkboxes',
          title: this.$t('Jurisdiction')
        },
        {
          name: 'years',
          type: 'checkboxes',
          title: this.$t('Year')
        },
        {
          name: 'localities',
          type: 'checkboxes',
          title: this.$t('Locality')
        },
        {
          name: 'alphabet',
          type: 'letter-radio',
          title: this.$t('Alphabetical')
        },
        {
          name: 'attorneys',
          type: 'checkboxes',
          title: this.$t('Attorneys')
        }
      ];

      const formatOptions = (options, key) => {
        return options.map((option) => {
          return {
            label: key === 'docTypes' ? this.getDocTypeLabel(option) : option,
            value: option
          };
        });
      };

      for (const facet of facets) {
        if (facet.type === 'checkboxes') {
          facet.value = this.getUrlParamValue(facet.name);
        } else {
          facet.value = this.getUrlParamValue(facet.name).length ? this.getUrlParamValue(facet.name)[0] : null;
        }

        if (facet.name === 'alphabet') {
          facet.options = formatOptions(this.alphabet, facet.name);
        } else if (facet.name === 'years') {
          facet.options = formatOptions(this.sortDescending(this.years), facet.name);
        } else {
          facet.options = formatOptions(this.sortAlphabetically(this.$props[facet.name]), facet.name);
        }
      }

      return facets;
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

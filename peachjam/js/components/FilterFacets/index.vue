<template>
  <ul class="list-group">
    <li
      class="position-relative list-group-item bg-light d-flex justify-content-between align-items-center"
    >
      <slot name="header-title">
        <strong>{{ $t("Filters") }}</strong>
      </slot>
      <a
        v-if="showClearAllFilter"
        href="#"
        @click.prevent="clearAll"
      >
        {{ $t("Clear all") }}
      </a>
    </li>
    <li class="list-group-item d-flex d-lg-none">
      <label class="form-label align-self-center mb-0 me-2">{{ $t('Sort') }}</label>
      <select :value="ordering" class="ms-auto form-select select-narrow" @change="ordered">
        <option value="-score">
          {{ $t('Relevance') }}
        </option>
        <option value="date">
          {{ $t('Date (oldest first)') }}
        </option>
        <option value="-date">
          {{ $t('Date (newest first)') }}
        </option>
      </select>
    </li>
    <template
      v-for="(facet, index) in modelValue"
      :key="index"
    >
      <SingleFacet
        :facet="facet"
        :search-term="facetSearchTerms[facet.name] || ''"
        :loading="loading"
        @on-change="handleChange"
        @clear-facet="clearFacet"
        @facet-search-change="setFacetSearchTerm"
      />
    </template>
  </ul>
</template>

<script>
import SingleFacet from './SingleFacet.vue';
export default {
  name: 'FilterFacets',
  components: { SingleFacet },
  props: {
    modelValue: {
      type: Array,
      default: () => []
    },
    loading: {
      type: Boolean,
      default: false
    },
    ordering: {
      type: String,
      default: '-score'
    }
  },
  emits: ['update:modelValue', 'ordered'],
  data () {
    return {
      facetSearchTerms: {}
    };
  },
  computed: {
    showClearAllFilter () {
      return this.modelValue.some((item) => {
        if (item.type === 'checkboxes') {
          return item.value.length;
        } else {
          return item.value;
        }
      });
    }
  },
  methods: {
    setFacetSearchTerm ({ name, term }) {
      this.facetSearchTerms = {
        ...this.facetSearchTerms,
        [name]: term
      };
    },

    clearSingleFacet (data, fieldName) {
      const targetIndex = data.findIndex((facet) => facet.name === fieldName);
      if (data[targetIndex].type === 'checkboxes') {
        data[targetIndex].value = [];
      } else if (data[targetIndex.type === 'boolean']) {
        data[targetIndex].value = false;
      } else {
        data[targetIndex].value = null;
      }
      return data;
    },

    clearFacet (fieldName) {
      const data = this.clearSingleFacet(this.modelValue, fieldName);
      this.setFacetSearchTerm({ name: fieldName, term: '' });
      this.$emit('update:modelValue', [...data]);
    },

    clearAll () {
      let data = this.modelValue;
      this.modelValue.forEach((facet) => {
        data = this.clearSingleFacet(data, facet.name);
        this.setFacetSearchTerm({ name: facet.name, term: '' });
      });
      this.$emit('update:modelValue', [...data]);
    },

    handleChange (e, facet) {
      const targetIndex = this.modelValue.findIndex(
        (item) => item.name === facet.name
      );
      const data = [...this.modelValue];

      const getValue = () => {
        let newValue = e.target.value;
        if (facet.type === 'boolean') {
          newValue = e.target.checked;
        }
        if (facet.type === 'checkboxes') {
          if (e.target.checked) {
            newValue = [...data[targetIndex].value, e.target.value];
          } else {
            newValue = data[targetIndex].value.filter(
              (item) => String(item) !== String(e.target.value)
            );
          }
        }
        return newValue;
      };
      data[targetIndex] = {
        ...data[targetIndex],
        value: getValue()
      };
      this.$emit('update:modelValue', data);
    },

    ordered (e) {
      this.$emit('ordered', e.target.value);
    }
  }
};
</script>

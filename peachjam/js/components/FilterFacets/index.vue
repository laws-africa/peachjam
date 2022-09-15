<template>
  <ul class="list-group">
    <li
      class="list-group-item bg-light d-flex justify-content-between align-items-center"
    >
      <strong>{{ $t("Filters") }}</strong>
      <a
        v-if="showClearAllFilter"
        href="#"
        @click.prevent="clearAll"
      >
        {{ $t("Clear all") }}
      </a>
    </li>
    <template
      v-for="(facet, index) in modelValue"
      :key="index"
    >
      <SingleFacet
        :facet="facet"
        @on-change="handleChange"
        @clear-facet="clearFacet"
      />
    </template>
  </ul>
</template>

<script>
/**
 *  TODO: This will replace ListFacets. Testing for now in LegislationTable
 *  Sample data shape for v-model of this component
 * {
 *     type: 'radio',
 *     name: 'radio',
 *     title: 'Radio options',
 *     value: 'radio-option-one',
 *     options: [
 *       {
 *         label: 'Radio option 1',
 *         value: 'radio-option-one'
 *       },
 *       {
 *         label: 'Radio option 2',
 *         value: 'radio-option-two'
 *       }
 *     ]
 *   },
 *   {
 *     type: 'checkboxes',
 *     name: 'checkbox',
 *     title: 'Checkbox options',
 *     value: 'checkbox-option-one',
 *     options: [
 *       {
 *         label: 'Checkbox option 1',
 *         value: 'checkbox-option-one'
 *       },
 *       {
 *         label: 'Checkbox option 2',
 *         value: 'checkbox-option-two'
 *       }
 *     ]
 *   },
 *   {
 *     type: 'boolean',
 *     name: 'boolean',
 *     title: 'Boolean',
 *     value: false
 *   }
 * **/
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
      default: true
    }
  },
  emits: ['update:modelValue'],
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
      const queryString = window.location.search;

      if (queryString) {
        const urlParams = new URLSearchParams(queryString);
        urlParams.delete(fieldName);
        window.location.href = `${window.location.origin}${
          window.location.pathname
        }?${urlParams.toString()}`;
      }

      const data = this.clearSingleFacet(this.modelValue, fieldName);
      this.$emit('update:modelValue', [...data]);
    },
    clearAll () {
      const queryString = window.location.search;
      const urlParams = new URLSearchParams(queryString);

      let data = this.modelValue;
      this.modelValue.forEach((facet) => {
        if (urlParams.has(facet.name)) {
          urlParams.delete(facet.name);
          window.location.href = `${window.location.origin}${
            window.location.pathname
          }?${urlParams.toString()}`;
        }
        data = this.clearSingleFacet(data, facet.name);
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

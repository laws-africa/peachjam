<template>
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
    <template
      v-for="(facet, index) in facets"
      :key="index"
    >
      <li
        v-if="facet.options.length"
        class="list-group-item"
      >
        <div class="d-flex justify-content-between mb-2">
          <strong>{{ facet.title }}</strong>
          <div class="d-flex align-items-center">
            <a
              v-if="facet.type === 'checkbox' && facet.value.length"
              href="#"
              @click.prevent="clearFacet(facet.name)"
            >
              {{ $t('Clear') }}
            </a>

            <a
              v-if="facet.value && facet.type !== 'checkbox'"
              href="#"
              @click.prevent="clearFacet(facet.name)"
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
          <template v-if="facet.type === 'checkbox'">
            <div
              v-for="(option, optIndex) in facet.options"
              :key="optIndex"
              class="d-flex justify-content-between align-items-center"
            >
              <div
                class="form-check"
              >
                <input
                  :id="`${facet.name}_${optIndex}`"
                  v-model="facet.value"
                  :value="option.value"
                  class="form-check-input"
                  type="checkbox"
                  :name="facet.name"
                >
                <label
                  class="form-check-label"
                  :for="`${facet.name}_${optIndex}`"
                >
                  {{ option.label }}
                </label>
              </div>
            </div>
          </template>
          <template v-if="facet.type === 'radio'">
            <div
              v-for="(option, optIndex) in facet.options"
              :key="optIndex"
              class="d-flex justify-content-between align-items-center"
            >
              <div
                class="form-check"
              >
                <input
                  :id="`${facet.name}_${optIndex}`"
                  v-model="facet.value"
                  :value="option.value"
                  class="form-check-input"
                  type="radio"
                  :name="facet.name"
                >
                <label
                  class="form-check-label"
                  :for="`${facet.name}_${optIndex}`"
                >
                  {{ option.label }}
                </label>
              </div>
            </div>
          </template>
        </div>
      </li>
    </template>
  </ul>
</template>

<script>
// TODO: This will replace ListFacets. Testing for now in LegislationTable
export default {
  name: 'SecondaryFacets',
  props: {
    modelValue: {
      type: Array,
      default: () => []
    },
    loading: {
      type: Boolean,
      default: false
    }
  },
  emits: ['clear-all', 'clear-facet', 'update:modelValue'],
  data: () => ({
    facets: []
  }),
  computed: {
    showClearAllFilter () {
      return this.modelValue.some(item => {
        if (item.type === 'checkbox') {
          return item.value.length;
        } else {
          return item.value;
        }
      });
    }
  },
  watch: {
    value: {
      immediate: true,
      deep: true,
      handler () {
        this.facets = this.modelValue;
      }
    },
    facets: {
      deep: true,
      handler () {
        this.$emit('update:modelValue', this.facets);
      }
    }
  },
  methods: {
    clearFacet (fieldName) {
      const targetIndex = this.facets.findIndex(facet => facet.name === fieldName);
      this.facets[targetIndex].value = this.facets[targetIndex].type === 'checkbox' ? [] : null;
    },
    clearAll () {
      this.facets.forEach((facet, index) => {
        this.facets[index].value = facet.type === 'checkbox' ? [] : null;
      });
    }
    // sortAlphabetically (items) {
    //   const sorted = [...items];
    //   return sorted.sort((a, b) => a.localeCompare(b));
    // },
    // sortDescending (items) {
    //   const sorted = [...items];
    //   return sorted.sort((a, b) => b - a);
    // }
  }
};
</script>

<style scoped>
.facets-scrollable {
  max-height: 25vh;
  overflow-y: auto;
}
</style>

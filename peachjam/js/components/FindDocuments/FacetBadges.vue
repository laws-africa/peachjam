<template>
  <div v-if="activeOptions" class="d-none d-md-block mb-3">
    <button
      v-for="option in activeOptions"
      :key="option.value"
      class="btn btn-outline-primary me-2 btn-sm"
      type="button"
      :title="$t('Remove')"
      @click="updateModel(option.value)"
    >
      {{ option.label }}
      &nbsp;×
    </button>
  </div>
</template>

<script>
export default {
  name: 'FacetBadges',
  props: {
    modelValue: {
      type: Array,
      default: () => []
    },
    permissive: {
      // if this is true, then we don't sanity check facet values against options, which is only important
      // if there are no search results
      type: Boolean,
      default: false
    }
  },
  emits: ['update:modelValue'],
  computed: {
    activeOptions () {
      const activeFacets = this.modelValue.filter(facet => facet.value.length);
      const options = [];
      activeFacets.forEach(facet => {
        let activeOptions = [];
        if (this.permissive) {
          activeOptions = facet.value.map((v) => {
            return {
              value: v,
              label: v
            };
          });
        } else {
          activeOptions = facet.options.filter(option => facet.value.includes(option.value));
        }
        options.push(...activeOptions);
      });
      return options;
    }
  },
  methods: {
    updateModel (val) {
      // remove the clicked option from the facet.value array
      const updatedModel = [...this.modelValue].map(item => {
        item.value = item.value.filter(value => value !== val);
        return item;
      });
      this.$emit('update:modelValue', updatedModel);
    }
  }
};
</script>

<template>
  <div class="d-none d-md-block">
    <button
      v-for="option in activeOptions"
      :key="option.value"
      class="btn btn-outline-primary me-2 mb-2"
      :name="option.value"
      @click="updateModel"
      :title="$t('Remove')"
    >
      × {{ option.label }}
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
    }
  },
  emits: ['update:modelValue'],
  computed: {
    activeOptions () {
      const activeFacets = this.modelValue.filter(facet => facet.value.length);
      const options = [];
      activeFacets.forEach(facet => {
        const activeOptions = facet.options.filter(option => facet.value.includes(option.value));
        options.push(...activeOptions);
      });
      return options;
    }
  },
  methods: {
    updateModel (e) {
      // remove the clicked option from the facet.value array
      const updatedModel = [...this.modelValue].map(item => {
        item.value = item.value.filter(value => value !== e.target.name);
        return item;
      });
      this.$emit('update:modelValue', updatedModel);
    }
  }
};
</script>

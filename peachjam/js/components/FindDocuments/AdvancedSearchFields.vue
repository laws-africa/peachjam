<template>
  <div class="mb-3 d-md-flex">
    <div class="d-flex mb-2 flex-grow-1">
      <div v-if="criterion.condition" class="me-3">
        <select
          v-model="criterion.condition"
          class="form-control"
          @change="changed"
        >
          <option value="AND">AND</option>
          <option value="OR">OR</option>
          <option value="NOT">NOT</option>
        </select>
      </div>

      <div class="flex-grow-1 me-3">
        <input
          v-model="criterion.text"
          type="text"
          class="form-control"
          placeholder="Text to search for..."
          @input="changed"
        >
      </div>
    </div>

    <div class="d-flex mb-2">
      <div class="dropdown me-3">
        <button
          :id="`${criterion.condition}_${targetIndex}-dropdown_fields`"
          class="btn btn-secondary dropdown-toggle"
          data-bs-toggle="dropdown"
          data-bs-auto-close="outside"
          aria-expanded="false"
        >
          In these fields
        </button>

        <div class="dropdown-menu" :aria-labelledby="`${criterion.condition}_${targetIndex}-dropdown_fields`">
          <div
            v-for="field in ['title', 'judges', 'case_summary', 'flynote', 'content']"
            :key="field"
            class="form-check dropdown-item"
          >
            <input
              :id="`${criterion.condition}_${targetIndex}-${field}`"
              :name="`${criterion.condition}_${targetIndex}-${field}`"
              :checked="criterion.fields.indexOf(field) > -1"
              class="form-check-input"
              type="checkbox"
              @change="(e) => fieldChanged(field, e.target.checked)"
            >
            <label
              class="form-check-label"
              :for="`${criterion.condition}_${targetIndex}-${field}`"
            >
              {{ formatName(field) }}
            </label>
          </div>
        </div>
      </div>

      <div class="form-check">
        <input
          :id="`${criterion.condition}_${targetIndex}-exact`"
          v-model="criterion.exact"
          :name="`${criterion.condition}_${targetIndex}-exact`"
          type="checkbox"
          class="form-check-input"
          @change="changed"
        >
        <label
          class="form-check-label"
          :for="`${criterion.condition}_${targetIndex}-exact`"
        >
          Exact phrase
        </label>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'AdvancedSearchFields',
  props: {
    criterion: {
      type: Object,
      default: () => ({})
    },
    targetIndex: {
      type: Number,
      default: 0
    }
  },
  emits: ['on-change'],
  methods: {
    changed () {
      this.$emit('on-change');
    },
    fieldChanged (field, checked) {
      if (checked) {
        if (!this.criterion.fields.includes(field)) {
          this.criterion.fields.push(field);
        }
      } else {
        this.criterion.fields = this.criterion.fields.filter((f) => f !== field);
      }
      this.changed();
    },
    formatName (name) {
      let splitName = name.split('_');
      splitName = splitName.map((word) => word.charAt(0).toUpperCase() + word.slice(1));
      return splitName.join(' ');
    }
  }
};
</script>

<style scoped>
.dropdown-menu .dropdown-item {
  padding-left: 2.5rem;
  padding-right: 2.5rem;
}
</style>

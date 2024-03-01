<template>
  <div class="mb-3 row">
    <div v-if="criterion.condition" class="dropdown col-3">
      <span
        :id="`${criterion.condition}_${targetIndex}-dropdown`"
        class="btn btn-secondary dropdown-toggle"
        href="#"
        role="button"
        data-bs-toggle="dropdown"
        aria-expanded="false"
      >
        {{ criterion.condition }} these words
      </span>

      <div class="dropdown-menu p-2" :aria-labelledby="`${criterion.condition}_${targetIndex}-dropdown`">
        <button
          v-for="logicField in logicFields"
          :key="logicField"
          class="dropdown-item"
          type="button"
          @click="$emit('on-logic-change', logicField, targetIndex)"
        >
          {{ logicField }} these words
        </button>
      </div>
    </div>

    <div :class="`${criterion.condition ? 'col-9' : 'col-12'}`">
      <input
        :id="`${criterion.condition}_${targetIndex}-text`"
        :value="criterion.text"
        :name="`${criterion.condition}_${targetIndex}-text`"
        type="text"
        class="form-control"
        @input="(e) => $emit('on-change', e, targetIndex)"
      >

      <div class="d-flex justify-content-between">
        <div class="dropdown">
          <span
            :id="`${criterion.condition}_${targetIndex}-dropdown_fields`"
            class="dropdown-toggle"
            href="#"
            role="button"
            data-bs-toggle="dropdown"
            data-bs-auto-close="outside"
            aria-expanded="false"
          >
            Choose fields
          </span>

          <div class="dropdown-menu" :aria-labelledby="`${criterion.condition}_${targetIndex}-dropdown_fields`">
            <div
              v-for="field in ['title', 'judges', 'case_summary', 'flynote', 'content']"
              :key="field"
              class="form-check dropdown-item"
            >
              <input
                :id="`${criterion.condition}_${targetIndex}-${field}`"
                :checked="criterion.fields.includes(field)"
                :name="`${criterion.condition}_${targetIndex}-${field}`"
                :value="field"
                class="form-check-input"
                type="checkbox"
                @change="(e) => $emit('on-change', e)"
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
            :checked="criterion.exact"
            :name="`${criterion.condition}_${targetIndex}-exact`"
            type="checkbox"
            class="form-check-input"
            @change="(e) => $emit('on-exact-change', e)"
          >
          <label
            class="form-check-label"
            :for="`${criterion.condition}_${targetIndex}-exact`"
          >
            Exact Phrase
          </label>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'AdvancedSearchFields',
  props: {
    targetIndex: {
      type: Number,
      default: 0
    },
    criterion: {
      type: Object,
      default: () => ({})
    }
  },
  emits: ['on-change', 'on-logic-change', 'on-exact-change'],
  computed: {
    logicFields () {
      return ['AND', 'OR', 'NOT'].filter(logic => logic !== this.criterion.condition);
    }
  },
  methods: {
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

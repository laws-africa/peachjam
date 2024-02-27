<template>
  <div class="mb-3 row">
    <div v-if="inputField !== 'all'" class="dropdown col-3">
      <span
        :id="`${inputField}-dropdown`"
        class="btn btn-secondary dropdown-toggle"
        href="#"
        role="button"
        data-bs-toggle="dropdown"
        aria-expanded="false"
      >
        {{ inputField.split('_')[0].toUpperCase() }} of these words
      </span>

      <div class="dropdown-menu p-2" :aria-labelledby="`${inputField}-dropdown`">
        <button
          v-for="logicField in logicFields"
          :key="logicField"
          class="dropdown-item"
          type="button"
          @click="inputField=logicField"
        >
          {{ logicField.split('_')[0].toUpperCase() }} of these words
        </button>
      </div>
    </div>

    <div :class="`${inputField === 'all'? 'col-12' : 'col-9'}`">
      <input
        :id="`${inputField}-input`"
        :value="fieldValues.input"
        :name="`${inputField}-input`"
        type="text"
        class="form-control"
        @input="(e) => $emit('on-change', e, targetIndex)"
      >

      <div class="d-flex justify-content-between">
        <div class="dropdown">
          <span
            :id="`${inputField}-dropdown_fields`"
            class="dropdown-toggle"
            href="#"
            role="button"
            data-bs-toggle="dropdown"
            data-bs-auto-close="outside"
            aria-expanded="false"
          >
            Choose fields
          </span>

          <div class="dropdown-menu" :aria-labelledby="`${inputField}-dropdown_fields`">
            <div
              v-for="field in ['title', 'judges', 'case_summary', 'flynote', 'content']"
              :key="field"
              class="form-check dropdown-item"
            >
              <input
                :id="`${inputField}-${field}`"
                :checked="fieldValues.fields.includes(field)"
                :name="`${inputField}-${field}`"
                class="form-check-input"
                type="checkbox"
                @change="(e) => $emit('on-change', e)"
              >
              <label
                class="form-check-label"
                :for="`${inputField}-${field}`"
              >
                {{ formatName(field) }}
              </label>
            </div>
          </div>
        </div>

        <div class="form-check">
          <input
            :id="`${inputField}-exact`"
            :checked="fieldValues.exact"
            :name="`${inputField}-exact`"
            type="checkbox"
            class="form-check-input"
            @change="(e) => $emit('on-exact-change', e)"
          >
          <label
            class="form-check-label"
            :for="`${inputField}-exact`"
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
    inputName: {
      type: String,
      default: ''
    },
    fieldValues: {
      type: Object,
      default: () => ({})
    }
  },
  emits: ['on-change', 'on-logic-change', 'on-exact-change'],
  data () {
    return {
      inputField: this.inputName,
      targetIndex: Number(this.inputName.split('_')[1])
    };
  },
  computed: {
    logicFields () {
      return [`and_${this.targetIndex}`, `any_${this.targetIndex}`, `none_${this.targetIndex}`].filter(logic => logic !== this.inputField);
    }
  },
  watch: {
    inputField (newVal, oldVal) {
      this.$emit('on-logic-change', newVal, oldVal, this.targetIndex);
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

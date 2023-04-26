<template>
  <div class="">
    <hr>
    <h4>
      {{ $t(formTitle) }}...
    </h4>
    <div class="row mt-3">
      <label
        class="form-label col-sm-3"
        :for="`${inputName}-all`"
      >{{ $t("All these words") }}</label>
      <div class="col-sm-9">
        <input
          :id="`${inputName}-all`"
          :name="`${inputName}-all`"
          type="text"
          :value="fieldValues.all"
          class="form-control"
          :aria-describedby="$t(formTitle)"
          @input="e => updateSubfields(e, 'all')"
        >
      </div>
    </div>
    <div class="row mt-3">
      <label
        class="form-label col-sm-3"
        :for="`${inputName}-exact`"
      >{{ $t("This exact word or phrase") }}</label>
      <div class="col-sm-9">
        <input
          :id="`${inputName}-exact`"
          :name="`${inputName}-exact`"
          type="text"
          :value="fieldValues.exact"
          class="form-control"
          :aria-describedby="$t(formTitle)"
          @input="e => updateSubfields(e, 'exact')"
        >
      </div>
    </div>
    <div class="row mt-3">
      <label
        class="form-label col-sm-3"
        :for="`${inputName}-any`"
      >{{ $t("Any of these words") }}</label>
      <div class="col-sm-9">
        <input
          :id="`${inputName}-any`"
          :name="`${inputName}-any`"
          type="text"
          :value="fieldValues.any"
          class="form-control"
          :aria-describedby="$t(formTitle)"
          @input="e => updateSubfields(e, 'any')"
        >
      </div>
    </div>
    <div class="row mt-3">
      <label
        class="form-label col-sm-3"
        :for="`${inputName}-none`"
      >{{ $t("None of these words") }}</label>
      <div class="col-sm-9">
        <input
          :id="`${inputName}-none`"
          :name="`${inputName}-none`"
          type="text"
          :value="fieldValues.none"
          class="form-control"
          :aria-describedby="$t(formTitle)"
          @input="e => updateSubfields(e, 'none')"
        >
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'AdvancedSearchFields',
  props: {
    formTitle: {
      type: String,
      default: ''
    },
    inputName: {
      type: String,
      default: ''
    },
    fieldValues: {
      type: Object,
      default: () => ({})
    }
  },
  emits: ['update-field-values', 'update:fieldValues'],
  methods: {
    updateSubfields (e, subfield) {
      this.$emit('update:fieldValues', {
        ...this.fieldValues,
        [subfield]: e.target.value
      });
    //   this.$emit('update-field-values', this.inputName, subfield, e.target.value);
    }
  }
};
</script>

<style scoped>
hr {
    margin-top: 2rem;
}
</style>

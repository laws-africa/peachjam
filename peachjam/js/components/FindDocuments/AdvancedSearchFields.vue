<template>
  <div class="">
    <h4>
      {{ $t(formTitle) }}...
    </h4>
    <div class="row mt-3">
      <div class="col-sm-2">
        <label
          class="col-form-label"
          :for="`${inputName}-all`"
        >{{ $t("All these words") }}:</label>
      </div>
      <div class="col-sm-10">
        <input
          :id="`${inputName}-all`"
          :value="fieldValue.all"
          :name="`${inputName}-all`"
          type="text"
          placeholder="Type the important words: cross-examination law refugee"
          class="form-control"
          :aria-describedby="$t(formTitle)"
          @input="e => updateSubfields(e, 'all')"
        >
      </div>
    </div>
    <div class="row mt-3">
      <div class="col-sm-2">
        <label :for="`${inputName}-exact`">{{ $t("This exact word or phrase") }}:</label>
      </div>
      <div class="col-sm-10">
        <input
          :id="`${inputName}-exact`"
          :value="fieldValue.exact"
          :name="`${inputName}-exact`"
          type="text"
          placeholder="Put exact words in quotes: 'law refugee'"
          class="form-control"
          :aria-describedby="$t(formTitle)"
          @input="e => updateSubfields(e, 'exact')"
        >
      </div>
    </div>
    <div class="row mt-3">
      <div class="col-sm-2">
        <label :for="`${inputName}-any`">{{ $t("Any of these words") }}:</label>
      </div>
      <div class="col-sm-10">
        <input
          :id="`${inputName}-any`"
          :value="fieldValue.any"
          :name="`${inputName}-any`"
          type="text"
          placeholder="Type OR between all the words you want: law OR refugee"
          class="form-control"
          :aria-describedby="$t(formTitle)"
          @input="e => updateSubfields(e, 'any')"
        >
      </div>
    </div>
    <div class="row mt-3">
      <div class="col-sm-2">
        <label :for="`${inputName}-none`">{{ $t("None of these words:") }}:</label>
      </div>
      <div class="col-sm-10">
        <input
          :id="`${inputName}-none`"
          :value="fieldValue.none"
          :name="`${inputName}-none`"
          type="text"
          placeholder="Put a minus sign just before words that you don't want: -Myanmar -'Kibo Potts'"
          class="form-control"
          :aria-describedby="$t(formTitle)"
          @input="e => updateSubfields(e, 'none')"
        >
      </div>
    </div>
    <hr>
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
    fieldValue: {
      type: Object,
      default: () => ({})
    }
  },
  emits: ['update-field-values'],
  methods: {
    updateSubfields (e, subfield) {
      this.$emit('update-field-values', this.inputName, subfield, e.target.value);
    }
  }
};
</script>

<style scoped>
hr {
    margin-top: 2rem;
}
</style>

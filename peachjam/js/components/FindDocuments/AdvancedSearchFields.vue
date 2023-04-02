<template>
  <div class="">
    <div class="form-title">
      {{ $t(formTitle) }}...
    </div>
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
          v-model="subFields.all"
          :name="`${inputName}-all`"
          type="text"
          class="form-control"
          :aria-describedby="$t(formTitle)"
          @input="updateSubfields"
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
          v-model="subFields.exact"
          :name="`${inputName}-exact`"
          type="text"
          class="form-control"
          :aria-describedby="$t(formTitle)"
          @input="updateSubfields"
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
          v-model="subFields.any"
          :name="`${inputName}-any`"
          type="text"
          class="form-control"
          :aria-describedby="$t(formTitle)"
          @input="updateSubfields"
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
          v-model="subFields.none"
          :name="`${inputName}-none`"
          type="text"
          class="form-control"
          :aria-describedby="$t(formTitle)"
          @input="updateSubfields"
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
    fieldValues: {
      type: Object,
      default: () => ({})
    }
  },
  emits: ['update:fieldValues', 'update:modelValue', 'global-search-change'],
  data: function () {
    return {
      subFields: {
        all: '',
        exact: '',
        any: '',
        none: ''
      }
    };
  },
  methods: {
    updateSubfields () {
      this.$emit('update:fieldValues', {
        ...this.fieldValues,
        [this.inputName]: this.subFields
      });
      console.log(this.fieldValues);
    }
  }
};
</script>

<style scoped>
.form-title {
    font-size: larger;
    font-weight: bolder;
}

hr {
    margin-top: 2rem;
}
</style>

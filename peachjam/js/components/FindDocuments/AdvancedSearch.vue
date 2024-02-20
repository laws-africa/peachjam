<template>
  <form @submit.prevent="submitAdvancedForm">
    <div class="row mt-5">
      <div class="col-12">
        <div class="card mb-3">
          <h5 class="card-header">
            {{ $t("Search documents") }}
          </h5>
          <div class="card-body">
            <div>
              <input
                id="all-input"
                name="all-input"
                :value="modelValue.all.input"
                type="text"
                class="form-control"
                :aria-describedby="$t('Search available fields')"
                :placeholder="$t('Search documents')"
                @change="onChange"
              >

              <div class="d-flex justify-content-between">
                <div class="dropdown">
                  <span
                    id="all-dropdown_fields"
                    class="dropdown-toggle"
                    href="#"
                    role="button"
                    data-bs-toggle="dropdown"
                    data-bs-auto-close="outside"
                    aria-expanded="false"
                  >
                    Choose fields
                  </span>

                  <div class="dropdown-menu" aria-labelledby="all-dropdown_fields">
                    <div
                      v-for="field in fields"
                      :key="field"
                      class="form-check dropdown-item"
                    >
                      <input
                        :id="`all-${field}`"
                        v-model="modelValue.all.fields"
                        :name="`all-${field}`"
                        :value="field"
                        class="form-check-input"
                        type="checkbox"
                      >
                      <label
                        class="form-check-label"
                        :for="`all-${field}`"
                      >
                        {{ formatName(field) }}
                      </label>
                    </div>
                  </div>
                </div>

                <div class="form-check">
                  <input
                    id="all-exact"
                    :value="modelValue.all.exact"
                    name="all-exact"
                    type="checkbox"
                    class="form-check-input"
                    @change="onExactChange"
                  >
                  <label
                    class="form-check-label"
                    for="all-exact"
                  >
                    Exact Phrase
                  </label>
                </div>
              </div>
            </div>
            <div class="mt-3 row">
              <div v-if="!showAllOptions" class="dropdown col-3">
                <span
                  :id="`${firstLogic}-dropdown`"
                  class="btn btn-secondary dropdown-toggle"
                  href="#"
                  role="button"
                  data-bs-toggle="dropdown"
                  aria-expanded="false"
                >
                  {{ firstLogic.toUpperCase() }} of these words
                </span>

                <div class="dropdown-menu p-2" :aria-labelledby="`${firstLogic}-dropdown`">
                  <button
                    v-for="logicField in logicFields.slice(1)"
                    :key="logicField"
                    class="dropdown-item"
                    type="button"
                    @click="firstLogic=logicField"
                  >
                    {{ logicField.toUpperCase() }} of these words
                  </button>
                </div>
              </div>

              <div v-else class="col-3">
                <span
                  id=""
                  class="btn btn-secondary "
                  href="#"
                  role="button"
                  data-bs-toggle=""
                  aria-expanded="false"
                >
                  {{ firstLogic.toUpperCase() }} of these words
                </span>
              </div>
              <div class="col-9">
                <input
                  :id="`${firstLogic}-input`"
                  :name="`${firstLogic}-input`"
                  type="text"
                  :value="modelValue[firstLogic]?.input"
                  class="form-control"
                  @input="onChange"
                >
                <div class="d-flex justify-content-between">
                  <div class="dropdown">
                    <span
                      :id="`${firstLogic}-dropdown_fields`"
                      class="dropdown-toggle"
                      href="#"
                      role="button"
                      data-bs-toggle="dropdown"
                      data-bs-auto-close="outside"
                      aria-expanded="false"
                    >
                      Choose fields
                    </span>

                    <div class="dropdown-menu p-2" :aria-labelledby="`${firstLogic}-dropdown_fields`">
                      <div
                        v-for="field in fields"
                        :key="field"
                        class="form-check dropdown-item"
                      >
                        <input
                          :id="`${firstLogic}-${field}`"
                          :name="`${firstLogic}-${field}`"
                          :value="field"
                          class="form-check-input"
                          type="checkbox"
                          @change="onChange"
                        >
                        <label
                          class="form-check-label"
                          :for="`${firstLogic}-${field}`"
                        >
                          {{ formatName(field) }}
                        </label>
                      </div>
                    </div>
                  </div>

                  <div class="form-check">
                    <input
                      :value="modelValue[firstLogic]?.exact"
                      :name="`${firstLogic}-exact`"
                      type="checkbox"
                      class="form-check-input"
                      @change="onExactChange"
                    >
                    <label
                      class="form-check-label"
                      :for="`${firstLogic}-exact`"
                    >
                      Exact Phrase
                    </label>
                  </div>
                </div>
              </div>
            </div>
            <div v-if="modelValue[firstLogic].input || showAllOptions" class="mt-3 row">
              <div v-if="!showAllOptions" class="dropdown col-3">
                <span
                  :id="`${secondLogic}-dropdown`"
                  class="btn btn-secondary dropdown-toggle"
                  href="#"
                  role="button"
                  data-bs-toggle="dropdown"
                  aria-expanded="false"
                >
                  {{ secondLogic.toUpperCase() }} of these words
                </span>

                <div class="dropdown-menu p-2" :aria-labelledby="`${secondLogic}-dropdown`">
                  <button
                    v-for="logicField in logicFields.slice(1)"
                    :key="logicField"
                    class="dropdown-item"
                    type="button"
                    @click="secondLogic=logicField"
                  >
                    {{ logicField.toUpperCase() }} of these words
                  </button>
                </div>
              </div>

              <div v-else class="col-3">
                <span
                  id=""
                  class="btn btn-secondary "
                  href="#"
                  role="button"
                  data-bs-toggle=""
                  aria-expanded="false"
                >
                  {{ secondLogic.toUpperCase() }} of these words
                </span>
              </div>
              <div class="col-9">
                <input
                  :id="`${secondLogic}-input`"
                  :name="`${secondLogic}-input`"
                  type="text"
                  :value="modelValue[secondLogic]?.input"
                  class="form-control"
                  @input="onChange"
                >
                <div class="d-flex justify-content-between">
                  <div class="dropdown">
                    <span
                      :id="`${secondLogic}-dropdown_fields`"
                      class="dropdown-toggle"
                      href="#"
                      role="button"
                      data-bs-toggle="dropdown"
                      data-bs-auto-close="outside"
                      aria-expanded="false"
                    >
                      Choose fields
                    </span>

                    <div class="dropdown-menu p-2" :aria-labelledby="`${secondLogic}-dropdown_fields`">
                      <div
                        v-for="field in fields"
                        :key="field"
                        class="form-check dropdown-item"
                      >
                        <input
                          :id="`${secondLogic}-${field}`"
                          :name="`${secondLogic}-${field}`"
                          :value="field"
                          class="form-check-input"
                          type="checkbox"
                          @change="onChange"
                        >
                        <label
                          class="form-check-label"
                          :for="`${secondLogic}-${field}`"
                        >
                          {{ formatName(field) }}
                        </label>
                      </div>
                    </div>
                  </div>

                  <div class="form-check">
                    <input
                      :value="modelValue[secondLogic]?.exact"
                      :name="`${secondLogic}-exact`"
                      type="checkbox"
                      class="form-check-input"
                      @change="onExactChange"
                    >
                    <label
                      class="form-check-label"
                      :for="`${secondLogic}-exact`"
                    >
                      Exact Phrase
                    </label>
                  </div>
                </div>
              </div>
            </div>
            <div v-if="modelValue[secondLogic].input || showAllOptions" class="mt-3 row">
              <div class="col-3">
                <span
                  id=""
                  class="btn btn-secondary "
                  href="#"
                  role="button"
                  data-bs-toggle=""
                  aria-expanded="false"
                >
                  {{ thirdLogic.toUpperCase() }} of these words
                </span>
              </div>
              <div class="col-9">
                <input
                  :id="`${thirdLogic}-input`"
                  :name="`${thirdLogic}-input`"
                  type="text"
                  :value="modelValue[thirdLogic]?.input"
                  class="form-control"
                  @input="onChange"
                >
                <div class="d-flex justify-content-between">
                  <div class="dropdown">
                    <span
                      :id="`${thirdLogic}-dropdown_fields`"
                      class="dropdown-toggle"
                      href="#"
                      role="button"
                      data-bs-toggle="dropdown"
                      data-bs-auto-close="outside"
                      aria-expanded="false"
                    >
                      Choose fields
                    </span>

                    <div class="dropdown-menu p-2" :aria-labelledby="`${thirdLogic}-dropdown_fields`">
                      <div
                        v-for="field in fields"
                        :key="field"
                        class="form-check dropdown-item"
                      >
                        <input
                          :id="`${thirdLogic}-${field}`"
                          :name="`${thirdLogic}-${field}`"
                          :value="field"
                          class="form-check-input"
                          type="checkbox"
                          @change="onChange"
                        >
                        <label
                          class="form-check-labels"
                          :for="`${thirdLogic}-${field}`"
                        >
                          {{ formatName(field) }}
                        </label>
                      </div>
                    </div>
                  </div>

                  <div class="form-check">
                    <input
                      :value="modelValue[thirdLogic]?.exact"
                      :name="`${thirdLogic}-exact`"
                      type="checkbox"
                      class="form-check-input"
                      @change="onExactChange"
                    >
                    <label
                      class="form-check-label"
                      :for="`${thirdLogic}-exact`"
                    >
                      Exact Phrase
                    </label>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="col-lg">
        <div class="card mb-3">
          <h5 class="card-header">
            {{ $t("Date") }}
          </h5>
          <div class="card-body">
            <div class="row">
              <div class="col-6">
                <label class="form-label" for="date_from">{{
                  $t("Date from")
                }}</label>
                <input
                  id="date_from"
                  name="date_from"
                  type="date"
                  class="form-control"
                  :aria-describedby="$t('Date from')"
                  :placeholder="$t('Enter start date')"
                  :value="modelValue.date.date_from"
                  :disabled="disableDate"
                  @change="onDateChange"
                >
              </div>
              <div class="col-6">
                <label class="form-label" for="date_to">{{
                  $t("Date to")
                }}</label>
                <input
                  id="date_to"
                  name="date_to"
                  type="date"
                  class="form-control"
                  :aria-describedby="$t('Date to')"
                  :placeholder="$t('Enter end date')"
                  :value="modelValue.date.date_to"
                  :disabled="disableDate"
                  @change="onDateChange"
                >
              </div>
            </div>
            <div v-if="invalidDates" class="text-danger">
              {{ $t("The date range is invalid") }}.
            </div>
          </div>
        </div>
      </div>
    </div>
    <div class="d-flex justify-content-end">
      <div>
        <HelpBtn page="search/advanced-search" />
        <button type="submit" class="btn btn-primary">
          {{ $t('Search') }}
        </button>
      </div>
    </div>
  </form>
</template>

<script>
import HelpBtn from '../HelpBtn.vue';

export default {
  name: 'AdvancedSearch',
  components: { HelpBtn },

  props: {
    modelValue: {
      type: Object,
      default: () => ({})
    },
    globalSearchValue: {
      type: String,
      default: ''
    }
  },

  emits: ['submit', 'update:modelValue', 'global-search-change'],

  data: function () {
    return {
      showAllOptions: false,
      fields: ['title', 'judges', 'case_summary', 'flynote', 'content'],
      firstLogic: 'and',
      secondLogic: 'any',
      thirdLogic: 'none'
    };
  },

  computed: {
    invalidDates () {
      const datesStrings = [
        this.modelValue.date.date_from,
        this.modelValue.date.date_to
      ];

      if (datesStrings.every((date) => !date)) {
        return false;
      } else if (datesStrings.every((date) => date)) {
        const from = new Date(datesStrings[0]);
        const to = new Date(datesStrings[1]);
        return from > to;
      } else {
        return !datesStrings.some((string) => string);
      }
    },

    disableDate () {
      // Disable dates if there are no search values
      return !(
        ['title', 'case_summary', 'flynote', 'content'].some(
          (key) => this.modelValue[key]
        ) || this.globalSearchValue
      );
    },
    logicFields () {
      return ['and', 'any', 'none'].filter((field) => !this.modelValue[field].input);
    }
  },

  watch: {
    disableDate: {
      handler (newValue) {
        // When disabling calendar set date input values to null
        if (newValue) {
          this.$emit('update:modelValue', {
            ...this.modelValue,
            date: {
              date_from: null,
              date_to: null
            }
          });
        }
      }
    },

    logicFields: {
      handler (newValue, oldValue) {
        if (newValue.length < 2) this.showAllOptions = true;
        if (newValue.length < oldValue.length) {
          if (newValue.length === 1) {
            this.thirdLogic = newValue[0];
          } else if (newValue.length === 2) {
            this.secondLogic = newValue[0];
          }
        }
      }
    }
  },

  methods: {
    onChange (e) {
      const data = { ...this.modelValue };
      const splitInput = e.target.name.split('-');

      if (e.target.type === 'checkbox') {
        if (e.target.checked) data[splitInput[0]].fields.push(splitInput[1]);
      } else {
        data[splitInput[0]][splitInput[1]] = e.target.value;
      }

      this.$emit('update:modelValue', data);
    },

    onExactChange (e) {
      const data = { ...this.modelValue };
      const splitInput = e.target.name.split('-');
      if (e.target.checked) data[splitInput[0]][splitInput[1]] = e.target.checked;

      this.$emit('update:modelValue', data);
    },

    onDateChange (e) {
      this.$emit('update:modelValue', {
        ...this.modelValue,
        date: {
          ...this.modelValue.date,
          [e.target.name]: e.target.value
        }
      });
    },

    onGlobalSearch (e) {
      this.$emit('global-search-change', e.target.value);
    },

    /**
     * Build a single query string from the advanced values for a field.
     * @param field the name of the field
     * @param modifiers the advanced search modifiers object
     * @returns {string} a fully formatted search string
     */
    formatFieldValues () {
      const newValue = { ...this.modelValue };
      Object.keys(this.modelValue).forEach(field => {
        if (field !== 'date') {
          const fieldQuery = this.formatFieldQuery(field, this.modelValue[field]);
          newValue[field].q = fieldQuery;

          if (field === 'all') {
            this.$emit('global-search-change', fieldQuery);
          }
        }
      });
      this.$emit('update:modelValue', newValue);
    },

    formatFieldQuery (field, modifiers) {
      let q = '';
      const input = modifiers.exact ? '"' + modifiers.input.trim() + '"' : modifiers.input;
      if (!input) return '';
      let splitValue = input.match(/\w+|"[^"]+"/g);

      if (field === 'and') {
        // add quotes around runs of non-quoted tokens
        const tokens = [];

        splitValue.forEach((value) => {
          if (value.startsWith('"')) {
            tokens.push(value);
          } else {
            tokens.push('"' + value + '"');
          }
        });

        splitValue = tokens.join('+');
      } else if (field === 'any') {
        splitValue = `(|${splitValue.join('|')})`;
      } else if (field === 'none') {
        splitValue = splitValue.map((value) => `-${value}`).join(' ');
      } else splitValue = splitValue.join(' ');

      q = q + ' ' + splitValue.trim();

      return q.trim();
    },

    submitAdvancedForm () {
      this.formatFieldValues();
      this.$emit('submit');
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

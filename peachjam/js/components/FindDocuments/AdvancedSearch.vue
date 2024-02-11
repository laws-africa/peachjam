<template>
  <form @submit.prevent="submitAdvancedForm">
    <div class="mb-4">
      <div>
        <label for="global">{{ $t("Search available fields") }}:</label>
        <input
          id="global"
          name="global"
          type="text"
          class="form-control"
          :value="globalSearchValue"
          :aria-describedby="$t('Search available fields')"
          :placeholder="$t('Search documents')"
          @input="onGlobalSearch"
        >
      </div>
      <div class="form-check d-flex justify-content-end mt-2">
        <input
          :value="modelValue.exact"
          name="exact"
          type="checkbox"
          class="form-check-input me-2"
          @change="onChange"
        >
        <label
          class="form-check-label"
          for="exact_checkbox"
        >
          Exact Phrase
        </label>
      </div>
    </div>

    <div class="row">
      <div class="col-lg">
        <div class="card mb-3">
          <h5 class="card-header">
            {{ $t("Fields to search") }}
          </h5>
          <div class="card-body">
            <div
              v-for="field in Object.keys(modelValue.fields)"
              :key="field"
              class="form-check"
            >
              <input
                :id="`${field}_checkbox`"
                :name="`field-${field}`"
                :checked="modelValue.fields[field]"
                class="form-check-input"
                type="checkbox"
                @change="onChange"
              >
              <label
                class="form-check-label"
                :for="`${field}_checkbox`"
              >
                {{ formatName(field) }}
              </label>
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

    <div class="row">
      <div class="col-lg">
        <div class="card mb-3">
          <h5 class="card-header">
            {{ $t("Additional filters") }}
          </h5>
          <div class="card-body">
            <div>
              <div class="row">
                <label class="form-label col-sm-3" for="and-words">{{ $t("AND these words") }}</label>
                <div class="col-sm-9">
                  <input
                    id="and-words"
                    name="and"
                    type="text"
                    :value="modelValue.and"
                    class="form-control"
                    @input="onChange"
                  >
                </div>
              </div>

              <div class="row mt-3">
                <label class="form-label col-sm-3" for="or-words">{{ $t("OR these words") }}</label>
                <div class="col-sm-9">
                  <input
                    id="or-words"
                    name="any"
                    type="text"
                    :value="modelValue.any"
                    class="form-control"
                    @input="onChange"
                  >
                </div>
              </div>

              <div class="row mt-3">
                <label class="form-label col-sm-3" for="not-words">{{ $t("NOT these words") }}</label>
                <div class="col-sm-9">
                  <input
                    id="not-words"
                    name="none"
                    type="text"
                    :value="modelValue.none"
                    class="form-control"
                    @input="onChange"
                  >
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="d-flex justify-content-end">
      <div>
        <HelpBtn page="search/advanced-search" />
        <button type="submit" class="btn btn-primary">
          {{ $t("Search") }}
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
    }
  },

  methods: {
    onChange (e) {
      const data = { ...this.modelValue };
      const name = e.target.name;
      if (name.startsWith('field')) {
        const field = name.split('-')[1];
        data.fields[field] = e.target.checked;
      } else {
        data[name] = e.target.value;
      }
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

    formatFieldQuery () {
      const newValue = { ...this.modelValue };
      let q = this.modelValue.exact ? '"' + this.globalSearchValue + '"' : this.globalSearchValue;

      if (this.modelValue.and) {
        let splitValue = this.modelValue.and.match(/\w+|"[^"]+"/g);
        // add quotes around runs of non-quoted tokens
        const tokens = [];
        let unquoted = [];

        splitValue.forEach((value) => {
          if (value.startsWith('"')) {
            if (unquoted.length) {
              tokens.push('"' + unquoted.join(' ') + '"');
              unquoted = [];
            }
            tokens.push(value);
          } else {
            unquoted.push(value);
          }
        });

        if (unquoted.length) {
          tokens.push('"' + unquoted.join(' ') + '"');
        }
        splitValue = tokens.join(' ');

        // special case for the "and" modifier - we want to update the input box to reflect the quoted string
        newValue.and = splitValue;

        q = q + ' ' + splitValue.trim();
      }

      if (this.modelValue.any) {
        let splitValue = this.modelValue.any.match(/\w+|"[^"]+"/g);
        splitValue = `(${splitValue.join('|')})`;
        q = q + ' ' + splitValue.trim();
      }

      if (this.modelValue.none) {
        let splitValue = this.modelValue.none.match(/\w+|"[^"]+"/g);
        splitValue = splitValue.map((value) => `-${value}`).join(' ');
        q = q + ' ' + splitValue.trim();
      }

      newValue.search = q;
      this.$emit('update:modelValue', newValue);
    },

    submitAdvancedForm () {
      this.formatFieldQuery();
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

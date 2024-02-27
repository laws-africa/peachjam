<template>
  <form @submit.prevent="submitAdvancedForm">
    <div class="row mt-5">
      <div class="col-12">
        <div class="card mb-3">
          <h5 class="card-header">
            {{ $t("Search documents") }}
          </h5>
          <div class="card-body">
            <AdvancedSearchFields
              v-for="(inputName) in Object.keys(modelValue).filter(key => key !== 'date')"
              :key="inputName"
              :field-values="modelValue[inputName]"
              :input-name="inputName"
              @on-change="onChange"
              @on-logic-change="onLogicChange"
              @on-exact-change="onExactChange"
            />
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
import AdvancedSearchFields from './AdvancedSearchFields.vue';

export default {
  name: 'AdvancedSearch',
  components: { HelpBtn, AdvancedSearchFields },

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
    onChange (e, index = 0) {
      const data = { ...this.modelValue };
      const splitInput = e.target.name.split('-');

      if (e.target.type === 'checkbox') {
        if (e.target.checked) data[splitInput[0]].fields.push(splitInput[1]);
      } else {
        data[splitInput[0]][splitInput[1]] = e.target.value;

        if (index && index === Object.keys(data).length - 2 && e.target.value) {
          data[`and_${index + 1}`] = {
            q: '',
            input: '',
            fields: [],
            exact: false
          };
        }
      }

      this.$emit('update:modelValue', data);
    },

    onExactChange (e) {
      const data = { ...this.modelValue };
      const splitInput = e.target.name.split('-');
      data[splitInput[0]][splitInput[1]] = e.target.checked;

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

    onLogicChange (logicName, oldName, index) {
      let data = { ...this.modelValue };
      const keyValues = Object.entries(data);
      keyValues.splice(index, 0, [logicName, data[oldName]]);
      data = Object.fromEntries(keyValues);
      delete data[oldName];

      this.$emit('update:modelValue', data);
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
          const fieldQuery = this.formatFieldQuery(field.split('_')[0], this.modelValue[field]);
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

        splitValue = tokens.join(' ');
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
    }
  }
};
</script>

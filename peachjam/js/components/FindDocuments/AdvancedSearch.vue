<template>
  <form @submit.prevent="submitAdvancedForm">
    <div class="row">
      <div class="col-lg">
        <div class="card mb-3">
          <h5 class="card-header">{{ $t("Anywhere") }}</h5>
          <div class="card-body">
            <AdvancedSearchFields v-model:fieldValues="modelValue.all" input-name="all" />
          </div>
        </div>
      </div>

      <div class="col-lg">
        <div class="card mb-3">
          <h5 class="card-header">{{ $t("Date") }}</h5>
          <div class="card-body">
            <div class="row">
              <div class="col-6">
                <label class="form-label" for="date_from">{{ $t("Date from") }}</label>
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
                <label class="form-label" for="date_to">{{ $t("Date to") }}</label>
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
              {{ $t('The date range is invalid') }}.
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="row">
      <div class="col-lg">
        <div class="card mb-3">
          <h5 class="card-header">{{ $t("Title") }}</h5>
          <div class="card-body">
            <AdvancedSearchFields v-model:fieldValues="modelValue.title" input-name="title" />
          </div>
        </div>
      </div>

      <div class="col-lg">
        <div class="card mb-3">
          <h5 class="card-header">{{ $t("Content") }}</h5>
          <div class="card-body">
            <AdvancedSearchFields v-model:fieldValues="modelValue.content" input-name="content" />
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
import AdvancedSearchFields from './AdvancedSearchFields.vue';
import HelpBtn from '../HelpBtn.vue';

export default {
  name: 'AdvancedSearch',

  components: { AdvancedSearchFields, HelpBtn },

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
      showAdditionalOptions: false
    };
  },

  computed: {
    invalidDates () {
      const datesStrings = [this.modelValue.date.date_from, this.modelValue.date.date_to];

      if (datesStrings.every(date => !date)) {
        return false;
      } else if (datesStrings.every(date => date)) {
        const from = new Date(datesStrings[0]);
        const to = new Date(datesStrings[1]);
        return from > to;
      } else { return !datesStrings.some(string => string); }
    },

    disableDate () {
      // Disable dates if there are no search values
      return !(['title', 'case_summary', 'flynote', 'content'].some(key => this.modelValue[key]) || this.globalSearchValue);
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
      data[e.target.name].q = e.target.value;
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

    formatFieldValues () {
      Object.keys(this.modelValue).forEach(field => {
        if (field !== 'date') {
          const newValue = { ...this.modelValue };
          const fieldQuery = this.formatFieldQuery(field, this.modelValue[field]);
          if (fieldQuery) {
            if (field === 'all') {
              this.$emit('global-search-change', fieldQuery.trim());
            } else {
              newValue[field].q = fieldQuery.trim();
            }
          } else {
            if (field === 'all') {
              this.$emit('global-search-change', '');
            } else newValue[field].q = '';
          }
          this.$emit('update:modelValue', newValue);
        }
      });
    },

    /**
     * Build a single query string from the advanced values for a field.
     * @param field the name of the field
     * @param modifiers the advanced search modifiers object
     * @returns {string} a fully formatted search string
     */
    formatFieldQuery (field, modifiers) {
      let q = '';

      for (const mod of Object.keys(modifiers)) {
        // mod is "all", "exact", "none" etc.
        if (mod === 'q') continue;
        const value = modifiers[mod];
        if (!value) continue;

        // split into components; either single words or "phrases"
        let splitValue = value.match(/\w+|"[^"]+"/g);
        if (mod === 'all') {
          splitValue = splitValue.join(' ');
        } else if (mod === 'exact') {
          // add quotes around runs of non-quoted tokens
          const tokens = [];
          let unquoted = [];

          splitValue.forEach(value => {
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

          // special case for the "exact" modifier - we want to update the input box to reflect the quoted string
          modifiers[mod] = splitValue;
        } else if (mod === 'any') {
          splitValue = `(${splitValue.join('|')})`;
        } else if (mod === 'none') {
          splitValue = splitValue.map(value => `-${value}`).join(' ');
        }

        q = q + ' ' + splitValue.trim();
      }

      return q;
    },

    submitAdvancedForm () {
      this.formatFieldValues();
      this.showAdditionalOptions = false;
      this.$emit('submit');
    }
  }
};
</script>

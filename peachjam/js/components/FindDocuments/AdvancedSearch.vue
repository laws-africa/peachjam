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
              v-for="(criterion, index) in modelValue"
              :key="index"
              :criterion="criterion"
              :target-index="index"
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
                  :value="advancedSearchDateCriteria.date_from"
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
                  :value="advancedSearchDateCriteria.date_to"
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
      type: Array,
      default: () => []
    },
    advancedSearchDateCriteria: {
      type: Object,
      default: () => ({})
    },
    globalSearchValue: {
      type: String,
      default: ''
    }
  },

  emits: ['submit', 'update:modelValue', 'global-search-change', 'date-change'],

  computed: {
    invalidDates () {
      const datesStrings = [
        this.advancedSearchDateCriteria.date_from,
        this.advancedSearchDateCriteria.date_to
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
        this.modelValue.some(
          (criterion) => criterion.text
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
      const data = [...this.modelValue];

      if (e.target.type === 'checkbox') {
        if (e.target.checked) data[index].fields.push(e.target.value);
      } else {
        data[index] = { ...data[index], text: e.target.value };

        if (index && index === data.length - 1 && e.target.value) {
          data.push({
            text: '',
            fields: [],
            condition: 'AND',
            exact: false
          });
        }

        if (index === 0) this.$emit('global-search-change', e.target.value);
      }

      this.$emit('update:modelValue', data);
    },

    onExactChange (e, index) {
      const data = [...this.modelValue];
      data[index] = { ...data[index], exact: e.target.checked };

      this.$emit('update:modelValue', data);
    },

    onDateChange (e) {
      this.$emit('date-change', {
        ...this.advancedSearchDateCriteria,
        [e.target.name]: e.target.value
      });
    },

    onLogicChange (logicName, index) {
      const data = [...this.modelValue];
      data[index] = { ...data[index], condition: logicName };

      this.$emit('update:modelValue', data);
    },

    submitAdvancedForm () {
      this.$emit('submit');
    }
  }
};
</script>

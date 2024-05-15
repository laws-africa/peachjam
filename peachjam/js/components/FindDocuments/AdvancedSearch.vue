<template>
  <form @submit.prevent="submitAdvancedForm">
    <div class="card">
      <div class="card-body">
        <AdvancedSearchFields
          v-for="(criterion, index) in modelValue"
          :key="index"
          :criterion="criterion"
          :target-index="index"
          @on-change="onChange"
        />

        <div class="row mt-5">
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
      <div class="card-footer d-flex justify-content-end">
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
          this.$emit('date-change', {
            ...this.advancedSearchDateCriteria,
            date_from: null,
            date_to: null
          });
        }
      }
    }
  },

  methods: {
    onChange () {
      this.cleanupCriteria(false);
    },

    onDateChange (e) {
      this.$emit('date-change', {
        ...this.advancedSearchDateCriteria,
        [e.target.name]: e.target.value
      });
    },

    cleanupCriteria (removeEmpty) {
      let data = [...this.modelValue];

      if (removeEmpty) {
        data = data.filter((criterion) => criterion.condition === '' || criterion.text);
      }

      // ensure there's an empty entry at the end
      if (data[data.length - 1].text) {
        data.push({ text: '', fields: ['all'], exact: false, condition: 'AND' });
      }

      this.$emit('update:modelValue', data);
    },

    submitAdvancedForm () {
      // remove empty criteria
      this.cleanupCriteria(true);
      this.$emit('submit');
    }
  }
};
</script>

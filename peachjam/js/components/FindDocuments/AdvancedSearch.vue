<template>
  <div class="">
    <div class="">
      <form @submit.prevent="$emit('submit')">
        <div class="">
          <AdvancedSearchFields
            :field-value="modelValue.q"
            form-title="Search all fields"
            input-name="q"
            @update-field-values="updateFieldValues"
          />
          <AdvancedSearchFields
            :field-value="modelValue.title"
            form-title="Title"
            input-name="title"
            @update-field-values="updateFieldValues"
          />
          <AdvancedSearchFields
            :field-value="modelValue.judges"
            form-title="Judges"
            input-name="judges"
            @update-field-values="updateFieldValues"
          />
          <AdvancedSearchFields
            :field-value="modelValue.headnote_holding"
            form-title="Headnote holding"
            input-name="headnote_holding"
            @update-field-values="updateFieldValues"
          />
          <AdvancedSearchFields
            :field-value="modelValue.flynote"
            form-title="Flynote"
            input-name="flynote"
            @update-field-values="updateFieldValues"
          />
          <AdvancedSearchFields
            :field-value="modelValue.content"
            form-title="Content"
            input-name="content"
            @update-field-values="updateFieldValues"
          />

          <div class="row mb-3">
            <div class="col-lg-6 form-group">
              <label for="date_from">{{ $t("Date from") }}:</label>
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
            <div class="col-lg-6 form-group">
              <label for="date_to">{{ $t("Date to") }}:</label>
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
          <div
            v-if="invalidDates"
            class="col-12 mb-3 text-danger"
          >
            {{ $t('The date range you have selected is invalid') }}. {{ $t('Please choose a correct date range') }}.
          </div>
        </div>
        <div class="text-end">
          <button
            type="submit"
            class="btn btn-primary"
          >
            {{ $t('Search') }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script>
import AdvancedSearchFields from './AdvancedSearchFields.vue';

export default {
  name: 'AdvancedSearch',
  components: { AdvancedSearchFields },
  props: {
    modelValue: {
      type: Object,
      default: () => ({})
    }
  },
  emits: ['submit', 'update:modelValue'],
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
      return !(['q', 'title', 'judges', 'headnote_holding', 'flynote', 'content'].some(key => Object.values(this.modelValue[key]).join('')));
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
    updateFieldValues (inputName, key, value) {
      this.$emit('update:modelValue', {
        ...this.modelValue,
        [inputName]: { ...this.modelValue[inputName], [key]: value }
      });
    },
    onDateChange (e) {
      this.$emit('update:modelValue', {
        ...this.modelValue,
        date: {
          ...this.modelValue.date,
          [e.target.name]: e.target.value
        }
      });
    }
  }
};
</script>

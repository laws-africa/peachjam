<template>
  <div class="">
    <div class="">
      <form @submit.prevent="formatFieldValues">
        <div class="">
          <!-- <AdvancedSearchFields
            form-title="Search all fields"
            input-name="global"
          /> -->
          <AdvancedSearchFields
            v-model:fieldValues="fieldValues"
            form-title="Title"
            input-name="title"
          />
          <AdvancedSearchFields
            v-model:fieldValues="fieldValues"
            form-title="Judges"
            input-name="judges"
          />
          <AdvancedSearchFields
            v-model:fieldValues="fieldValues"
            form-title="Headnote holding"
            input-name="headnote_holding"
          />
          <AdvancedSearchFields
            v-model:fieldValues="fieldValues"
            form-title="Flynote"
            input-name="flynote"
          />
          <AdvancedSearchFields
            v-model:fieldValues="fieldValues"
            form-title="Content"
            input-name="content"
          />

          <!-- <div class="col-12 mb-3">
            <div class="form-group">
              <label for="content">{{ $t('Content') }}:</label>
              <input
                id="content"
                type="text"
                name="content"
                class="form-control"
                :aria-describedby="$t('Content')"
                :placeholder="$t('Search documents by content')"
                :value="modelValue.content"
                @input="onChange"
              >
            </div>
          </div> -->

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
    },
    globalSearchValue: {
      type: String,
      default: ''
    }
  },
  emits: ['submit', 'update:modelValue', 'global-search-change'],
  data: function () {
    return {
      fieldValues: {
        title: {
          all: '',
          exact: '',
          any: '',
          none: ''
        },
        judges: {
          all: '',
          exact: '',
          any: '',
          none: ''
        },
        headnote_holding: {
          all: '',
          exact: '',
          any: '',
          none: ''
        },
        flynote: {
          all: '',
          exact: '',
          any: '',
          none: ''
        },
        content: {
          all: '',
          exact: '',
          any: '',
          none: ''
        }
      }
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
      return !(['title', 'judges', 'headnote_holding', 'flynote', 'content'].some(key => this.modelValue[key]) || this.globalSearchValue);
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
    modelValue () {
      this.$nextTick(this.loadFieldValues());
    }
  },
  methods: {
    onChange (e) {
      this.$emit('update:modelValue', {
        ...this.modelValue,
        [e.target.name]: e.target.value
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
    },
    onGlobalSearch (e) {
      this.$emit('global-search-change', e.target.value);
    },
    formatFieldValues () {
      Object.keys(this.fieldValues).forEach(key => {
        let formattedSearchString = '';
        Object.keys(this.fieldValues[key]).forEach(fieldKey => {
          let formattedFieldValue = this.fieldValues[key][fieldKey];
          if (formattedFieldValue) {
            if (fieldKey === 'any') {
              formattedFieldValue = formattedFieldValue.replace('OR', '|');
            }

            formattedSearchString = formattedSearchString + ' ' + formattedFieldValue;
          }
        });
        if (formattedSearchString) {
          this.$emit('update:modelValue', {
            ...this.modelValue,
            [key]: formattedSearchString.trim()
          });
        }
      });
      this.$emit('submit');
    },
    loadFieldValues () {
      Object.keys(this.modelValue).forEach(key => {
        if (key === 'date') return;
        const fieldValue = this.modelValue[key];
        if (fieldValue) {
          console.log(fieldValue, this.modelValue);
          const splitValue = fieldValue.match(/[^\s"']+|['"][^'"]*["']+/g);

          splitValue.forEach((value, index) => {
            if (value.startsWith('-')) {
              this.fieldValues[key].none = (this.fieldValues[key].none + ' ' + value).trim();
            } else if (value.startsWith('"') || value.startsWith("'")) {
              this.fieldValues[key].exact = (this.fieldValues[key].exact + ' ' + value).trim();
            } else if (value === '|') {
              this.fieldValues[key].any = this.fieldValues[key].any || splitValue[index - 1] + ' OR ' + splitValue[index + 1];
            } else if (splitValue[index + 1] !== '|' && splitValue[index + 1] !== '|') {
              this.fieldValues[key].all = (this.fieldValues[key].all + ' ' + value).trim();
            }
          });
        }
      });
    }
  }
};
</script>

<style scoped>
.form-title {
  font-weight: bold;
}
</style>

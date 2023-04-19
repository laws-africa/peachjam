<template>
  <div class="card">
    <div class="card-body">
      <form @submit.prevent="submitAdvancedForm">
        <div class="row">
          <div class="col-12 mb-3">
            <label for="global">{{ $t("Search all fields") }}:</label>
            <input
              id="global"
              name="global"
              type="text"
              class="form-control"
              :value="globalSearchValue"
              :aria-describedby="$t('Search all fields')"
              :placeholder="$t('Search documents by all fields')"
              @input="onGlobalSearch"
            >
          </div>
          <div class="col-12 col-lg-6 mb-3">
            <div class="form-group">
              <label for="title">{{ $t("Title") }}:</label>
              <input
                id="title"
                name="title"
                type="text"
                class="form-control"
                :aria-describedby="$t('Title')"
                :placeholder="$t('Search documents by title')"
                :value="modelValue.title"
                @input="onChange"
              >
            </div>
          </div>
          <div class="col-12 col-lg-6 mb-3">
            <div class="form-group">
              <label for="judges">{{ $t("Judges") }}:</label>
              <input
                id="judges"
                name="judges"
                type="text"
                class="form-control"
                :aria-describedby="$t('Judges')"
                :placeholder="$t('Search documents by judges')"
                :value="modelValue.judges"
                @input="onChange"
              >
            </div>
          </div>

          <div class="col-12 col-lg-6 mb-3">
            <div class="form-group">
              <label for="headnote_holding">{{ $t("Headnote holding") }}:</label>
              <input
                id="headnote_holding"
                type="text"
                name="headnote_holding"
                class="form-control"
                :aria-describedby="$t('Headnote holding')"
                :placeholder="$t('Search documents by headnote holding')"
                :value="modelValue.headnote_holding"
                @input="onChange"
              >
            </div>
          </div>

          <div class="col-12 col-lg-6 mb-3">
            <div class="form-group">
              <label for="flynote">{{ $t("Flynote") }}:</label>
              <input
                id="flynote"
                name="flynote"
                type="text"
                class="form-control"
                :aria-describedby="$t('Flynote')"
                :placeholder="$t('Search documents by flynote')"
                :value="modelValue.flynote"
                @input="onChange"
              >
            </div>
          </div>

          <div class="col-12 mb-3">
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
          </div>

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

        <div class="col-6">
          <label>
            <input
              v-model="showAdditionalOptions"
              type="checkbox"
            >
            {{ $t('Show additional options') }}
          </label>
        </div>

        <div v-if="showAdditionalOptions">
          <AdvancedSearchFields
            v-model:fieldValues="fieldValues"
            form-title="Search all fields"
            input-name="q"
          />
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
        q: {
          all: '',
          exact: '',
          any: '',
          none: ''
        },
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
      },
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
          const formattedFieldValue = this.fieldValues[key][fieldKey];
          if (!formattedFieldValue) return;
          let splitValue = formattedFieldValue.match(/\w+|"[^"]+"/g);
          if (fieldKey === 'all') {
            splitValue = splitValue.join(' ');
          } else if (fieldKey === 'exact') {
            let exactPhrase = '';
            let splitPhrase = '';
            splitValue.forEach(value => {
              if (value.startsWith('"')) {
                splitPhrase = splitPhrase + ' ' + `"${exactPhrase.trim()}"` + ' ' + value;
                exactPhrase = '';
              } else exactPhrase = exactPhrase + ' ' + value;
            });
            splitValue = exactPhrase ? splitPhrase + ' ' + `"${exactPhrase.trim()}"` : splitPhrase;
          } else if (fieldKey === 'any') {
            splitValue = `(${splitValue.join('|')})`;
          } else if (fieldKey === 'none') {
            splitValue = splitValue.map(value => {
              return `-${value}`;
            });
            splitValue = splitValue.join('');
          }

          formattedSearchString = formattedSearchString + ' ' + splitValue.trim();
        });
        if (formattedSearchString) {
          if (key === 'q') {
            this.$emit('global-search-change', formattedSearchString.trim());
          } else {
            this.$emit('update:modelValue', {
              ...this.modelValue,
              [key]: formattedSearchString.trim()
            });
          }
        }
      });
    },
    submitAdvancedForm () {
      this.formatFieldValues();
      this.showAdditionalOptions = false;
      this.$emit('submit');
    }
    // loadFieldValues () {
    //   Object.keys(this.modelValue).forEach(key => {
    //     if (this.modelValue[key]) {
    //       const splitValue = this.modelValue[key].match(/[^\s"']+|['"][^'"]*["']+/g);

    //       splitValue.forEach((value, index) => {
    //         if (value.startsWith('-')) {
    //           this.fieldValues[key].none = (this.fieldValues[key].none + ' ' + value).trim();
    //         } else if (value.startsWith('"') || value.startsWith("'")) {
    //           this.fieldValues[key].exact = (this.fieldValues[key].exact + ' ' + value).trim();
    //         } else if (value === '|') {
    //           this.fieldValues[key].any = this.fieldValues[key].any || splitValue[index - 1] + ' OR ' + splitValue[index + 1];
    //         } else if (splitValue[index + 1] !== '|' && splitValue[index + 1] !== '|') {
    //           this.fieldValues[key].all = (this.fieldValues[key].all + ' ' + value).trim();
    //         }
    //       });
    //     }
    //   });
    // }
  }
};
</script>

<style scoped>
.form-title {
  font-weight: bold;
}
</style>

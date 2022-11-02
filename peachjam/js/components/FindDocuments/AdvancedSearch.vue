<template>
  <div class="card">
    <div class="card-body">
      <form @submit.prevent="$emit('submit')">
        <div class="row">
          <div class="col-12 mb-3">
            <label for="global">{{ $t("Search all documents:") }}</label>
            <input
              id="global"
              name="global"
              type="text"
              class="form-control"
              :value="globalSearchValue"
              :aria-describedby="$t('Search all documents:')"
              :placeholder="$t('Search documents by all fields')"
              @input="onGlobalSearch"
            >
          </div>
          <div class="col-6 mb-3">
            <div class="form-group">
              <label for="title">{{ $t("Title:") }}</label>
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
          <div class="col-6 mb-3">
            <div class="form-group">
              <label for="judges">{{ $t("Judges:") }}</label>
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

          <div class="col-6 mb-3">
            <div class="form-group">
              <label for="headnote_holding">{{ $t("Headnote holding:") }}</label>
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

          <div class="col-6 mb-3">
            <div class="form-group">
              <label for="flynote">{{ $t("Flynote:") }}</label>
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
              <label for="content">{{ $t('Content:') }}</label>
              <textarea
                id="content"
                name="content"
                class="form-control"
                :aria-describedby="$t('Content')"
                :placeholder="$t('Search documents by content')"
                :value="modelValue.content"
                @input="onChange"
              />
            </div>
          </div>
          <div class="col-6 mb-3">
            <div class="form-group">
              <label for="date_from">{{ $t("Date from:") }}</label>
              <input
                id="date_from"
                name="date_from"
                type="date"
                class="form-control"
                :aria-describedby="$t('Date from:')"
                :placeholder="$t('Enter start date')"
                :value="modelValue.date.date_from"
                :disabled="disableDate"
                @change="onDateChange"
              >
            </div>
          </div>
          <div class="col-6 mb-3">
            <div class="form-group">
              <label for="date_to">{{ $t("Date to:") }}</label>
              <input
                id="date_to"
                name="date_to"
                type="date"
                class="form-control"
                :aria-describedby="$t('Date to:')"
                :placeholder="$t('Enter end date')"
                :value="modelValue.date.date_to"
                :disabled="disableDate"
                @change="onDateChange"
              >
            </div>
          </div>
          <div
            v-if="invalidDateRange"
            class="col-12 mb-3 text-danger"
          >
            {{ $t('The date range you have selected is invalid. Please choose a correct date range.') }}
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

export default {
  name: 'AdvancedSearch',
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
    invalidDateRange () {
      if (!this.modelValue.date.date_from && !this.modelValue.date.date_to) {
        return false;
      }
      const from = new Date(this.modelValue.date.date_from);
      const to = new Date(this.modelValue.date.date_to);
      return from > to;
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
    }
  }
};
</script>

<style scoped>
label {
  font-weight: bold;
}
</style>

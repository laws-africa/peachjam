<template>
  <div class="card">
    <div class="card-body">
      <form @submit.prevent="$emit('submit')">
        <div class="row">
          <div class="col-12 mb-3">
            <label for="global">{{ $t("Search all documents") }}</label>
            <input
              id="global"
              name="global"
              type="text"
              class="form-control"
              :value="globalSearchValue"
              :aria-describedby="$t('Search all documents')"
              :placeholder="$t('Lorem all document search')"
              @input="onGlobalSearch"
            >
          </div>
          <div class="col-6 mb-3">
            <div class="form-group">
              <label for="title">{{ $t("Title") }}</label>
              <input
                id="title"
                name="title"
                type="text"
                class="form-control"
                :aria-describedby="$t('Title')"
                :placeholder="$t('Enter document title')"
                :value="modelValue.title"
                @input="onChange"
              >
            </div>
          </div>
          <div class="col-6 mb-3">
            <div class="form-group">
              <label for="judges">{{ $t("Judges") }}</label>
              <input
                id="judges"
                name="judges"
                type="text"
                class="form-control"
                :aria-describedby="$t('Judges')"
                :placeholder="$t('Enter document judges')"
                :value="modelValue.judges"
                @input="onChange"
              >
            </div>
          </div>

          <div class="col-6 mb-3">
            <div class="form-group">
              <label for="headnote_holding">{{ $t("Headnote holding") }}</label>
              <input
                id="headnote_holding"
                type="text"
                name="headnote_holding"
                class="form-control"
                :aria-describedby="$t('Headnote holding')"
                :placeholder="$t('Enter document headnote holding')"
                :value="modelValue.headnote_holding"
                @input="onChange"
              >
            </div>
          </div>

          <div class="col-6 mb-3">
            <div class="form-group">
              <label for="flynote">{{ $t("Flynote") }}</label>
              <input
                id="flynote"
                name="flynote"
                type="text"
                class="form-control"
                :aria-describedby="$t('Flynote')"
                :placeholder="$t('Enter document flynote')"
                :value="modelValue.flynote"
                @input="onChange"
              >
            </div>
          </div>

          <div class="col-12 mb-3">
            <div class="form-group">
              <label for="content">{{ $t('Content') }}</label>
              <textarea
                id="content"
                name="content"
                class="form-control"
                :aria-describedby="$t('Content')"
                :placeholder="$t('Enter document content')"
                :value="modelValue.content"
                @input="onChange"
              />
            </div>
          </div>
          <div class="col-12">
            <strong>Filter by date</strong>
          </div>
          <div class="col-6 mb-3">
            <div class="form-group">
              <label for="date_from">{{ $t("Date from") }}</label>
              <input
                id="date_from"
                name="date_from"
                type="date"
                class="form-control"
                :aria-describedby="$t('Date from')"
                :placeholder="$t('Enter document date from')"
                :value="modelValue.date.date_from"
                :disabled="disableDate"
                @change="onDateChange"
              >
            </div>
          </div>
          <div class="col-6 mb-3">
            <div class="form-group">
              <label for="date_to">{{ $t("Date to") }}</label>
              <input
                id="date_to"
                name="date_to"
                type="date"
                class="form-control"
                :aria-describedby="$t('Date to')"
                :placeholder="$t('Enter document date to')"
                :value="modelValue.date.date_to"
                :disabled="disableDate"
                @change="onDateChange"
              >
            </div>
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
  data: () => ({
    validationMessage: false
  }),
  computed: {
    disableDate () {
      // Disable dates if there are no search values
      return !(['title', 'judges', 'headnote_holding', 'flynote', 'content'].some(key => this.modelValue[key]) || this.globalSearchValue);
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

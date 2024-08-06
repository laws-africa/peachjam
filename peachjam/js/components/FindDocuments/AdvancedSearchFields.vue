<template>
  <div class="mb-3 d-md-flex">
    <div class="d-flex mb-2 flex-grow-1">
      <div v-if="criterion.condition" class="me-3">
        <select
          v-model="criterion.condition"
          class="form-control"
          @change="changed"
        >
          <option value="AND">
            {{ $t('AND') }}
          </option>
          <option value="OR">
            {{ $t('OR') }}
          </option>
          <option value="NOT">
            {{ $t('NOT') }}
          </option>
        </select>
      </div>

      <div class="flex-grow-1 me-3">
        <input
          v-model="criterion.text"
          type="text"
          class="form-control"
          placeholder="Text to search for..."
          @input="changed"
        >
      </div>
    </div>

    <div class="d-flex mb-2">
      <div class="dropdown me-3">
        <button
          :id="`advanced-${targetIndex}-fields-btn`"
          class="btn btn-secondary dropdown-toggle"
          data-bs-toggle="dropdown"
          data-bs-auto-close="outside"
          aria-expanded="false"
        >
          {{ $t('In these fields') }}
        </button>

        <div class="dropdown-menu" :aria-labelledby="`advanced-${targetIndex}-fields-btn`">
          <div
            v-for="field in fields"
            :key="field.field"
            class="form-check dropdown-item"
          >
            <input
              :id="`advanced-${targetIndex}-fields-${field.field}`"
              :checked="this.criterion.fields.includes(field.field)"
              :disabled="field.field === 'all' && this.criterion.fields.includes(field.field)"
              class="form-check-input"
              type="checkbox"
              @change="(e) => fieldChanged(field.field, e.target.checked)"
            >
            <label
              class="form-check-label"
              :for="`advanced-${targetIndex}-fields-${field.field}`"
            >
              {{ field.label }}
            </label>
          </div>
        </div>
      </div>

      <div class="form-check">
        <input
          :id="`advanced-${targetIndex}-exact`"
          v-model="criterion.exact"
          type="checkbox"
          class="form-check-input"
          @change="changed"
        >
        <label
          class="form-check-label"
          :for="`advanced-${targetIndex}-exact`"
        >
          {{ $t('Exact phrase') }}
        </label>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'AdvancedSearchFields',
  props: {
    criterion: {
      type: Object,
      default: () => ({})
    },
    targetIndex: {
      type: Number,
      default: 0
    }
  },
  emits: ['on-change'],
  data: (self) => {
    return {
      fields: [{
        field: 'all',
        label: self.$t('Any field')
      }, {
        field: 'title',
        label: self.$t('Title')
      }, {
        field: 'citation',
        label: self.$t('Citation')
      }, {
        field: 'judges_text',
        label: self.$t('Judicial officers')
      }, {
        field: 'case_number',
        label: self.$t('Case number')
      }, {
        field: 'case_name',
        label: self.$t('Case parties')
      }, {
        field: 'case_summary',
        label: self.$t('Case summary')
      }, {
        field: 'flynote',
        label: self.$t('Flynote')
      }, {
        field: 'content',
        label: self.$t('Content')
      }]
    };
  },
  methods: {
    changed () {
      this.$emit('on-change');
    },
    fieldChanged (field, checked) {
      if (field === 'all') {
        if (checked) {
          // only 'all'
          this.criterion.fields.splice(0, this.criterion.fields.length);
          this.criterion.fields.push(field);
        } else if (this.criterion.fields.includes(field) && this.criterion.fields.length > 1) {
          // remove it
          this.criterion.fields.splice(this.criterion.fields.indexOf(field), 1);
        }
      } else if (checked) {
        // add it
        if (!this.criterion.fields.includes(field)) {
          this.criterion.fields.push(field);
        }
        if (this.criterion.fields.includes('all')) {
          this.criterion.fields.splice(this.criterion.fields.indexOf('all'), 1);
        }
      } else if (this.criterion.fields.includes(field)) {
        // remove it
        this.criterion.fields.splice(this.criterion.fields.indexOf(field), 1);
        if (this.criterion.fields.length === 0) {
          this.criterion.fields.push('all');
        }
      }
      this.changed();
    }
  }
};
</script>

<style scoped>
.dropdown-menu .dropdown-item {
  padding-left: 2.5rem;
  padding-right: 2.5rem;
}
</style>

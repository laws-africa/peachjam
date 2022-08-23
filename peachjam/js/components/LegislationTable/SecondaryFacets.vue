<template>
  <ul class="list-group">
    <li class="list-group-item bg-light d-flex justify-content-between align-items-center">
      <strong>{{ $t('Filters') }}</strong>
      <a
        v-if="showClearAllFilter"
        href="#"
        @click.prevent="clearAll"
      >
        {{ $t('Clear all') }}
      </a>
    </li>
    <template
      v-for="(facet, index) in modelValue"
      :key="index"
    >
      <!-- Facets with options are type radio or checkboxes -->
      <template v-if="facet.options && facet.options.length">
        <li
          class="list-group-item"
        >
          <div class="d-flex justify-content-between mb-2">
            <strong>{{ facet.title }}</strong>
            <div class="d-flex align-items-center">
              <a
                v-if="facet.type === 'checkboxes' && facet.value.length"
                href="#"
                @click.prevent="clearFacet(facet.name)"
              >
                {{ $t('Clear') }}
              </a>

              <a
                v-if="facet.value && facet.type !== 'checkboxes'"
                href="#"
                @click.prevent="clearFacet(facet.name)"
              >
                {{ $t('Clear') }}
              </a>
              <span
                v-if="loading"
                class="circle-loader ms-2"
              />
            </div>
          </div>
          <div class="facets-scrollable">
            <template v-if="facet.type === 'checkboxes'">
              <div
                v-for="(option, optIndex) in facet.options"
                :key="optIndex"
                class="d-flex justify-content-between align-items-center"
              >
                <div
                  class="form-check flex-grow-1"
                >
                  <input
                    :id="`${facet.name}_${optIndex}`"
                    :value="option.value"
                    class="form-check-input"
                    type="checkbox"
                    :name="facet.name"
                    :checked="facet.value.some(value => String(value) === String(option.value))"
                    @input="(e) => handleChange(e, facet)"
                  >
                  <label
                    class="form-check-label"
                    :for="`${facet.name}_${optIndex}`"
                  >
                    {{ option.label }}
                  </label>
                </div>
                <div>
                  <span
                    class="badge bg-light text-dark"
                  >{{ option.count }}</span>
                </div>
              </div>
            </template>
            <template v-if="facet.type === 'radio'">
              <div
                v-for="(option, optIndex) in facet.options"
                :key="optIndex"
                class="d-flex justify-content-between align-items-center"
              >
                <div
                  class="form-check flex-grow-1"
                >
                  <input
                    :id="`${facet.name}_${optIndex}`"
                    :checked="String(facet.value) === String(option.value)"
                    :value="option.value"
                    class="form-check-input"
                    type="radio"
                    :name="facet.name"
                    @input="(e) => handleChange(e, facet)"
                  >
                  <label
                    class="form-check-label"
                    :for="`${facet.name}_${optIndex}`"
                  >
                    {{ option.label }}
                  </label>
                </div>
                <div>
                  <span
                    class="badge bg-light text-dark"
                  >
                    {{ option.count }}
                  </span>
                </div>
              </div>
            </template>
          </div>
        </li>
      </template>
      <template v-if="facet.type === 'boolean'">
        <div class="list-group-item d-flex justify-content-between">
          <div
            class="d-flex justify-content-between align-items-center"
          >
            <div
              class="form-check"
            >
              <input
                :id="facet.name"
                :checked="facet.value"
                class="form-check-input"
                type="checkbox"
                :name="facet.name"
                @input="(e) => handleChange(e, facet)"
              >
              <label
                class="form-check-label"
                :for="facet.name"
              >
                <strong>{{ facet.title }}</strong>
              </label>
            </div>
          </div>
          <div class="d-flex align-items-center">
            <span
              class="badge bg-light text-dark"
            >
              {{ facet.count }}
            </span>
            <span
              v-if="loading"
              class="circle-loader ms-2"
            />
          </div>
        </div>
      </template>
    </template>
  </ul>
</template>

<script>
// TODO: This will replace ListFacets. Testing for now in LegislationTable
export default {
  name: 'SecondaryFacets',
  props: {
    modelValue: {
      type: Array,
      default: () => []
    },
    loading: {
      type: Boolean,
      default: false
    }
  },
  emits: ['update:modelValue'],
  computed: {
    showClearAllFilter () {
      return this.modelValue.some(item => {
        if (item.type === 'checkboxes') {
          return item.value.length;
        } else {
          return item.value;
        }
      });
    }
  },
  methods: {
    clearSingleFacet (data, fieldName) {
      const targetIndex = data.findIndex(facet => facet.name === fieldName);
      if (data[targetIndex].type === 'checkboxes') {
        data[targetIndex].value = [];
      } else if (data[targetIndex.type === 'boolean']) {
        data[targetIndex].value = false;
      } else {
        data[targetIndex].value = null;
      }
      return data;
    },
    clearFacet (fieldName) {
      const data = this.clearSingleFacet(this.modelValue, fieldName);
      this.$emit('update:modelValue', [...data]);
    },
    clearAll () {
      let data = this.modelValue;
      this.modelValue.forEach((facet) => {
        data = this.clearSingleFacet(data, facet.name);
      });
      this.$emit('update:modelValue', [...data]);
    },
    handleChange (e, facet) {
      const targetIndex = this.modelValue.findIndex(item => item.name === facet.name);
      const data = [...this.modelValue];

      const getValue = () => {
        let newValue = e.target.value;
        if (facet.type === 'boolean') {
          newValue = e.target.checked;
        }
        if (facet.type === 'checkboxes') {
          if (e.target.checked) {
            newValue = [...data[targetIndex].value, e.target.value];
          } else {
            newValue = data[targetIndex].value.filter(item => String(item) !== String(e.target.value));
          }
        }
        return newValue;
      };
      data[targetIndex] = {
        ...data[targetIndex],
        value: getValue()
      };
      this.$emit('update:modelValue', data);
    }
  }
};
</script>

<style scoped>
.facets-scrollable {
  max-height: 25vh;
  overflow-y: auto;
}
</style>

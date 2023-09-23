<template>
  <template v-if="facet.options && facet.options.length">
    <li class="list-group-item">
      <div class="d-flex justify-content-between mb-2">
        <strong>{{ facet.title }}</strong>
        <div class="d-flex align-items-center">
          <a
            v-if="showClearFilter"
            href="#"
            @click.prevent="$emit('clear-facet', facet.name)"
          >
            {{ $t('Clear') }}
          </a>

          <span
            v-if="loading"
            class="circle-loader ms-2"
          />
        </div>
      </div>
      <div :class="`${facet.type === 'letter-radio' ? '' : 'facets-scrollable'}`">
        <template v-if="facet.type === 'checkboxes'">
          <div
            v-for="(option, optIndex) in facet.options"
            :key="optIndex"
            class="d-flex justify-content-between align-items-center"
          >
            <div class="form-check flex-grow-1">
              <input
                :id="`${facet.name}_${optIndex}`"
                :value="option.value"
                class="form-check-input"
                type="checkbox"
                :name="facet.name"
                :checked="facet.value.some(value => String(value) === String(option.value))"
                @input="(e) => $emit('on-change', e, facet)"
              >
              <label
                class="form-check-label"
                :for="`${facet.name}_${optIndex}`"
              >
                {{ option.label }}
              </label>
            </div>
            <div>
              <span class="badge bg-light text-dark">{{ option.count }}</span>
            </div>
          </div>
        </template>
        <template v-if="facet.type === 'radio'">
          <div
            v-for="(option, optIndex) in facet.options"
            :key="optIndex"
            class="d-flex justify-content-between align-items-center"
          >
            <div class="form-check flex-grow-1">
              <input
                :id="`${facet.name}_${optIndex}`"
                :checked="String(facet.value) === String(option.value)"
                :value="option.value"
                class="form-check-input"
                type="radio"
                :name="facet.name"
                @input="(e) => $emit('on-change',e, facet)"
              >
              <label
                class="form-check-label"
                :for="`${facet.name}_${optIndex}`"
              >
                {{ option.label }}
              </label>
            </div>
            <div>
              <span class="badge bg-light text-dark">
                {{ option.count }}
              </span>
            </div>
          </div>
        </template>
        <template v-if="facet.type === 'letter-radio'">
          <div class="letter-radiobox-container">
            <label
              v-for="(option, optIndex) in facet.options"
              :key="optIndex"
              class="letter-radiobox"
            >
              <input
                :key="optIndex"
                :value="option.value"
                :checked="String(facet.value) === String(option.value)"
                type="radio"
                :name="facet.name"
                @input="(e) => $emit('on-change',e, facet)"
              >
              <span class="letter-radiobox__text">
                {{ option.label }}
              </span>
            </label>
          </div>
        </template>
      </div>
    </li>
  </template>
  <template v-if="facet.type === 'boolean'">
    <div class="list-group-item d-flex justify-content-between">
      <div class="d-flex justify-content-between align-items-center">
        <div class="form-check">
          <input
            :id="facet.name"
            :checked="facet.value"
            class="form-check-input"
            type="checkbox"
            :name="facet.name"
            @input="(e) => $emit('on-change', e, facet)"
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
        <span class="badge bg-light text-dark">
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

<script>
export default {
  name: 'SingleFacet',
  props: {
    facet: {
      type: Object,
      required: true
    },
    loading: {
      type: Boolean,
      required: false,
      default: false
    }
  },
  emits: ['clear-facet', 'on-change'],
  computed: {
    showClearFilter () {
      if (this.facet.type === 'checkboxes') {
        return this.facet.value.length;
      } else {
        return this.facet.value;
      }
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

<template>
  <ul class="list-unstyled mb-0">
    <li
      v-for="bucket in buckets"
      :key="bucket.key"
    >
      <label
        v-if="bucket.key"
        class="mb-0 d-flex"
      >
        <div class="flex-grow-1">
          <input
            v-model="items"
            type="checkbox"
            :value="bucket.key"
          >
          {{ bucket.key }}
        </div>
        <div>
          <span
            v-if="loading"
            class="circle-loader count-loader"
          />
          <span
            v-else
            class="badge bg-light text-dark"
          >{{ bucket.doc_count }}</span>
        </div>
      </label>
    </li>
  </ul>
</template>

<script>
export default {
  name: 'TermFacet',
  props: {
    buckets: {
      type: Array,
      default: () => []
    },
    reverse: {
      type: Boolean,
      default: false
    },
    selection: {
      type: Array,
      default: () => []
    },
    loading: {
      type: Boolean,
      default: false
    }
  },
  emits: ['changed'],
  data: () => {
    return {
      items: []
    };
  },
  watch: {
    selection: {
      immediate: true,
      handler () {
        this.items = this.selection;
      }
    },
    items () {
      this.$emit('changed', this.items);
    },
    buckets () {
      // when the buckets change, ensure that our selection only includes valid entries
      const keys = this.buckets.map(b => b.key);
      const filtered = this.items.filter(x => keys.includes(x));
      if (filtered.length !== this.items.length) {
        this.items = filtered;
      }
    }
  }
};
</script>

<style scoped>
label {
  cursor: pointer;
}

.circle-loader.count-loader {
  width: 18px;
  height: 18px;
}
</style>

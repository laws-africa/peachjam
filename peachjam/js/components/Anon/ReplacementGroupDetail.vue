<template>
  <div class="card">
    <div class="card-header d-flex">
      <h6 @click="toggle">
        <span v-if="collapsed" class="toggle">▶</span>
        <span v-if="!collapsed" class="toggle">▼</span>
        {{ group.title }}
        <span class="ms-2 badge text-bg-secondary">{{nApplied}} / {{group.replacements.length + group.suggestions.length}}</span>
      </h6>
      <button
        class="btn btn-success ms-auto"
        @click="apply"
        :disabled="!canApply"
        :title="$t('Apply')"
      ><i class="bi bi-check"></i></button>
      <button
        class="btn btn-warning ms-2"
        @click="unapply"
        :disabled="!canUnapply"
        title="$t('Undo')"
      ><i class="bi bi-arrow-counterclockwise"></i></button>
      <button
        class="btn btn-danger ms-2"
        @click="remove"
        title="$t('Remove')"
      ><i class="bi bi-trash"></i></button>
    </div>
    <ul :class="`list-group list-group-flush replacement-group-items ${collapsed ? 'd-none' : ''}`">
      <template v-for="replacement of group.replacements" :key="replacement.id">
        <ReplacementDetail
          :replacement="replacement"
          :active="replacement === modelValue"
          @applied="applied"
          @activated="$emit('update:modelValue', replacement)"
        />
      </template>
      <template v-for="replacement of group.suggestions" :key="replacement.id">
        <ReplacementDetail
          :replacement="replacement"
          :active="replacement === modelValue"
          @applied="applied"
          @activated="$emit('update:modelValue', replacement)"
        />
      </template>
    </ul>
  </div>
</template>

<script>
import ReplacementDetail from './ReplacementDetail.vue';

export default {
  props: ['group', 'modelValue'],
  components: { ReplacementDetail },
  emits: ['remove', 'applied', 'unapplied', 'update:modelValue'],
  data () {
    return {
      collapsed: false,
    };
  },
  computed: {
    canApply () {
      return (this.group.replacements[0].oldText !== this.group.replacements[0].newText) && (this.group.replacements.some(r => !r.applied) || this.group.suggestions.length > 0);
    },
    canUnapply () {
      return this.group.replacements.some(r => r.applied);
    },
    nApplied () {
      return this.group.replacements.filter(r => r.applied).length;
    }
  },
  methods: {
    apply () {
      const replacements = this.group.replacements.concat(this.group.suggestions);
      for (const replacement of replacements) {
        if (!replacement.applied) {
          replacement.apply();
          replacement.mark();
        }
      }
      this.$emit('applied', replacements);
    },
    unapply () {
      const replacements = this.group.replacements.concat(this.group.suggestions);
      for (const replacement of replacements) {
        replacement.unapply();
        replacement.mark();
      }
      this.$emit('unapplied', replacements);
    },
    applied (replacement) {
      this.$emit('applied', [replacement]);
    },
    remove () {
      if (this.group.replacements.some(r => r.applied) && !confirm("Are you sure?")) {
        return;
      }

      const replacements = this.group.replacements.concat(this.group.suggestions);
      for (const replacement of replacements) {
        replacement.unmark();
        replacement.unapply();
        this.$emit('unapplied', replacement);
      }
      this.$emit('remove', this.group);
    },
    toggle () {
      this.collapsed = !this.collapsed;
    }
  }
}
</script>

<style scoped>
.replacement-group-items {
  max-height: 50vh;
  overflow-y: auto;
}

.toggle {
  cursor: pointer;
}
</style>

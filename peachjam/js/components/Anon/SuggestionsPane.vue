<template>
  <div class="card mb-3">
    <div class="card-header d-flex">
      <h6 @click="toggle">
        <span v-if="collapsed" class="toggle">▶</span>
        <span v-if="!collapsed" class="toggle">▼</span>
        {{ $t('Suggested replacements') }}
      </h6>
      <button
        class="btn btn-outline-primary ms-auto"
        :disabled="loading"
        @click="load"
      >
        <span v-if="!loading">{{ $t('Make suggestions') }}</span>
        <span v-else>{{ $t('Thinking') }}...</span>
      </button>
    </div>
    <div :class="`card-body ${collapsed ? 'd-none': ''}`" v-if="suggestions.length">
      <ul class="list-unstyled mb-0 suggestion-list">
        <li v-for="suggestion of suggestions" :key="suggestion.id" class="d-flex">
          <div>
            <div>{{ suggestion.old_text }} → {{ suggestion.new_text }}</div>
            <div class="text-muted ms-3">{{ suggestion.reasoning }}</div>
          </div>
          <button class="btn btn-primary ms-auto" @click="apply(suggestion)">{{ $t('Use') }}</button>
        </li>
      </ul>
    </div>
  </div>
</template>

<script>
import { findText, Replacement } from './replacements';
import { rangeToTarget } from '@lawsafrica/indigo-akn/dist/ranges';

export default {
  props: ['documentId'],
  emits: ['apply'],
  data () {
    return {
      collapsed: false,
      loading: false,
      counter: 0,
      suggestions: []
    };
  },
  methods: {
    async load () {
      this.loading = true;
      try {
        const resp = await fetch(`/admin/anon/${this.documentId}/suggestions`, {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('input[name=csrfmiddlewaretoken]').value
          }
        });
        if (!resp.ok) {
          alert(`Failed: ${resp.statusText}`);
        } else {
          const info = await resp.json();
          this.suggestions = info.suggestions;
          for (const suggestion of this.suggestions) {
            suggestion.id = this.counter++;
          }
        }
      } finally {
        this.loading = false;
      }
    },
    toggle () {
      this.collapsed = !this.collapsed;
    },
    apply (suggestion) {
      // find the first occurrence of the old text
      const root = document.getElementById('content-root');
      const ranges = findText(root, suggestion.old_text, 1);
      if (ranges.length) {
        const target = rangeToTarget(ranges[0], root);
        if (target) {
          this.$emit('apply', new Replacement(root, suggestion.old_text, suggestion.new_text, target, false, false));
          this.suggestions.splice(this.suggestions.indexOf(suggestion), 1);
        }
      }
    }
  }
};
</script>

<style scoped>
.suggestion-list {
  max-height: 25vh;
  overflow-y: auto;
}
</style>

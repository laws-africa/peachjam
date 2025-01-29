<template>
  <div class="card mb-3">
    <div class="card-header d-flex">
      <h6>Suggestions</h6>
      <button
        class="btn btn-primary ms-auto"
        :disabled="loading"
        @click="load"
      >
        Refresh
      </button>
    </div>
    <div class="card-body" v-if="suggestions.length">
      <ul class="list-unstyled mb-0 suggestion-list">
        <li v-for="suggestion of suggestions" :key="suggestion.id" class="d-flex">
          <div>
            {{ suggestion.oldText }}
            ->
            {{ suggestion.newText }}
          </div>
          <button class="btn btn-success ms-auto" @click="apply(suggestion)">Use</button>
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
    apply (suggestion) {
      // find the first occurrence of the old text
      const root = document.getElementById('content-root');
      const ranges = findText(root, suggestion.oldText, 1);
      if (ranges.length) {
        const target = rangeToTarget(ranges[0], root);
        if (target) {
          this.$emit('apply', new Replacement(root, suggestion.oldText, suggestion.newText, target));
          this.suggestions.splice(this.suggestions.indexOf(suggestion), 1);
        }
      }
    }
  }
};
</script>

<style>
.suggestion-list {
  max-height: 25vh;
  overflow-y: auto;
}
</style>

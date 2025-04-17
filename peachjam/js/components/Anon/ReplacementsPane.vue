<template>
  <div>
    <SuggestionsPane @apply="add" :document-id="documentId" />
    <div class="d-flex">
      <button class="btn btn-primary" @click="newReplacement">Replace...</button>
      <div class="dropdown ms-auto">
        <button class="btn btn-outline-secondary dropdown-toggle" type="button" data-bs-toggle="dropdown">
          Anonymisation notice
        </button>
        <ul class="dropdown-menu">
          <li><button class="dropdown-item" @click="$emit('insertNotice')">Insert</button></li>
          <li><button class="dropdown-item" @click="$emit('removeNotice')">Remove</button></li>
        </ul>
      </div>
    </div>
    <div v-for="group of groups.values()" :key="group.key" class="mt-3">
      <ReplacementGroupDetail
        v-model="activeReplacement"
        :group="group"
        @remove="remove"
        @applied="applied"
      />
    </div>
  </div>
</template>

<script>
import { Replacement, ReplacementGroup } from './replacements.js';
import { rangeToTarget } from '@lawsafrica/indigo-akn/dist/ranges';
import ReplacementGroupDetail from './ReplacementGroupDetail.vue';
import SuggestionsPane from './SuggestionsPane.vue';

export default {
  components: { ReplacementGroupDetail, SuggestionsPane },
  props: {
    replacements: Array,
    documentId: String
  },
  emits: ['insertNotice', 'removeNotice', 'applied'],
  data () {
    return {
      activeReplacement: null,
      groups: new Map()
    };
  },
  mounted () {
    const data = JSON.parse(document.getElementById('replacements').innerText);
    const contentRoot = this.getContentRoot();
    this.replacements.push(...data.map(r => new Replacement(contentRoot, r.old_text, r.new_text, r.target, false, true)));
    this.updateGroups();
  },
  methods: {
    add (replacement) {
      this.replacements.push(replacement);
      // ensure there are marks before new suggestions are searched
      replacement.mark();
      this.updateGroups();
      this.activeReplacement = replacement;
    },
    newReplacement () {
      const selection = window.getSelection();
      const contentRoot = this.getContentRoot();

      if (selection.rangeCount > 0) {
        const range = selection.getRangeAt(0);
        if (!range.collapsed && contentRoot.contains(range.commonAncestorContainer)) {
          const replacement = new Replacement(contentRoot, range.toString(), range.toString(), rangeToTarget(range, contentRoot));
          this.add(replacement);
          selection.empty();
        }
      }
    },
    applied (replacements) {
      for (const replacement of replacements) {
        if (replacement.suggestion) {
          replacement.suggestion = false;
          this.replacements.push(replacement);
        }
      }
      this.$nextTick(() => this.updateGroups());
      this.$emit('applied');
    },
    remove (group) {
      for (const replacement of group.replacements) {
        const ix = this.replacements.indexOf(replacement);
        if (ix > -1) {
          this.replacements.splice(ix, 1);
        }
      }
      this.$nextTick(() => this.updateGroups());
    },
    updateGroups () {
      const newGroups = new Map();

      // group by the grouping function
      for (const replacement of this.replacements) {
        if (!newGroups.has(replacement.grouping())) {
          newGroups.set(replacement.grouping(), []);
        }
        newGroups.get(replacement.grouping()).push(replacement);
      }

      // map into group objects
      for (const [key, replacements] of newGroups) {
        if (this.groups.has(key)) {
          const group = this.groups.get(key);
          group.replacements = replacements;
        } else {
          this.groups.set(key, new ReplacementGroup(replacements));
        }
      }

      // delete groups that are all suggestions or deleted
      for (const [key, group] of this.groups) {
        if (!newGroups.has(key) || group.replacements.length === 0) {
          for (const replacement of group.suggestions) {
            replacement.unmark();
          }
          this.groups.delete(key);
        }
      }

      for (const group of this.groups.values()) {
        group.populateSuggestions();
      }
    },
    getContentRoot () {
      return document.querySelector('#content-root');
    }
  }
}
</script>

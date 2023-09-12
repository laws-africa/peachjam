<template>
  <div class="doc-search">
    <form
      class="doc-search__form mb-2"
      @submit.prevent="() => (q = $refs.q.value)"
    >
      <div class="input-group">
        <input
          ref="q"
          type="text"
          required
          class="form-control"
          :placeholder="$t('Search document content')"
          :aria-label="$t('Search document content')"
          aria-describedby="search-content-button"
          minlength="3"
        >
        <button
          class="btn btn-secondary"
          type="submit"
        >
          {{ $t("Search") }}
        </button>
      </div>
      <div class="text-end mt-2">
        <HelpBtn page="search/search-inside-a-document" />
        <a
          v-if="marks.length"
          href="#"
          @click.prevent="clear"
        >{{ $t("Clear") }}</a>
      </div>
      <div
        v-if="!marks.length && q"
        class="mt-2"
      >
        {{ $t("No results") }}
      </div>
    </form>
    <div class="doc-search__results">
      <div v-if="marks.length">
        <AknSnippets
          v-if="docType === 'akn'"
          :nodes="marks"
          @go-to-snippet="goToSnippet"
        />
        <HTMLSnippets
          v-if="docType === 'html'"
          :nodes="marks"
          @go-to-snippet="goToSnippet"
        />

        <PdfSnippets
          v-if="docType === 'pdf'"
          :nodes="marks"
          @go-to-snippet="goToSnippet"
        />
      </div>
    </div>
  </div>
</template>

<script>
import Mark from 'mark.js';
import HTMLSnippets from './HTMLSnippets.vue';
import PdfSnippets from './PdfSnippets.vue';
import AknSnippets from './AknSnippets.vue';
import { scrollToElement } from '../../utils/function';
import HelpBtn from "../HelpBtn.vue";

export default {
  name: 'DocumentSearch',
  components: {HelpBtn, AknSnippets, PdfSnippets, HTMLSnippets },
  props: {
    docType: {
      type: String,
      required: true,
      validator (value) {
        // The value must match one of these strings
        return ['akn', 'pdf', 'html'].includes(value);
      }
    },
    document: {
      type: HTMLElement,
      required: true
    },
    mountElement: {
      type: HTMLElement,
      required: true
    }
  },
  data: () => ({
    q: '',
    marks: [],
    markInstance: null
  }),
  watch: {
    q (newValue) {
      // Unmark when search if mark instance exists already
      if (this.markInstance) {
        this.markInstance.unmark();
        this.marks = [];
      }
      this.searchDoc(newValue);
    }
  },
  methods: {
    clear () {
      this.$refs.q.value = '';
      this.q = '';
    },
    searchDoc (q) {
      if (!this.markInstance) {
        this.markInstance = new Mark(this.document);
      }
      this.markInstance.mark(q, {
        separateWordSearch: false
      });
      this.marks = [...this.document.querySelectorAll('[data-markjs]')];
    },

    goToSnippet (node) {
      this.mountElement.dispatchEvent(new CustomEvent('going-to-snippet'));
      // Wait for offset canvas to close then scroll
      window.setTimeout(() => {
        scrollToElement(node, () => {
          node.style.outline = '2px solid transparent';
          node.style.transition = 'outline-color 400ms ease-in-out';
          node.style.outlineColor = 'var(--bs-primary)';
          window.setTimeout(() => {
            node.style.outlineColor = 'transparent';
          }, 400);
        }, 60);
      }, 300);
    }
  }
};
</script>

<style>
.doc-search {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 1rem;
}

.doc-search__results {
  flex: 1 1 auto;
  overflow-y: auto;
  height: 0;
}

.doc-search__results .snippet-card:focus {
  border-color: var(--bs-primary);
}
</style>

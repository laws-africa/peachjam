<template>
  <div class="doc-search">
    <form
      class="doc-search__form mb-4"
      @submit.prevent="() => q = $refs.q.value"
    >
      <div class="input-group">
        <input
          ref="q"
          type="text"
          required
          class="form-control"
          placeholder="Search document content"
          aria-label="Search document content"
          aria-describedby="search-content-button"
          minlength="3"
        >
        <button
          class="btn btn-secondary"
          type="submit"
        >
          Search
        </button>
      </div>
    </form>
    <div class="doc-search__results">
      <div v-if="!marks.length && q">
        No results
      </div>
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

export default {
  name: 'DocumentSearch',
  components: { AknSnippets, PdfSnippets, HTMLSnippets },
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
      const decorateNode = () => {
        node.style.outline = '2px solid transparent';
        node.style.transition = 'outline-color 300ms ease-in-out';
        node.style.outlineColor = 'var(--bs-primary)';
        window.setTimeout(() => {
          node.style.outlineColor = 'transparent';
        }, 400);
      };
      let isScrolling;
      const onScroll = () => {
        window.clearTimeout(isScrolling);
        isScrolling = window.setTimeout(() => {
          // On scroll stop decorate node
          decorateNode();
          window.removeEventListener('scroll', onScroll);
        }, 66);
      };

      const top = window.pageYOffset + node.getBoundingClientRect().top - 70;

      window.addEventListener('scroll', onScroll, false);
      window.scrollTo({
        top,
        behavior: 'smooth'
      });
      // If did not scroll decorate node
      if (!isScrolling) decorateNode();
    }
  }

};
</script>

<style scoped>
.doc-search {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 1rem;
  background-color: #f8f9fa;
}

.doc-search__results {
  flex: 1 1 auto;
  overflow-y: auto;
  height: 0;
}
</style>

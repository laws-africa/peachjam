<template>
  <div class="doc-search">
    <div class="inner">
      <div class="section">
        <div class="mb-4">
          <form @submit.prevent="() => q = $refs.q.value">
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
        </div>
        <div v-if="!marks.length && q">
          No results
        </div>
        <div
          v-if="marks.length"
          class="scrollable-content"
        >
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
      node.style.transition = 'background-color 400ms ease-in-out';
      const top =
        window.pageYOffset +
        node.getBoundingClientRect().top - 70;
      window.scrollTo({
        top,
        behavior: 'smooth'
      });
      node.style.backgroundColor = 'yellow';
      window.setTimeout(() => {
        node.style.backgroundColor = 'initial';
      }, 400);
    }
  }

};
</script>

<style scoped>
.doc-search {
  position: relative;
  height: 100%;
  background-color: #f8f9fa;
}

.doc-search .inner {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 0;
  display: flex;
  flex-direction: column;
  width: 100%;
}

.doc-search .section {
  margin: 10px;
  flex-grow: 1;

  display: flex;
  flex-direction: column;

  /* for Firefox */
  min-height: 0;
}

.doc-search .section .scrollable-content {
  flex-grow: 1;
  overflow: auto;
  /* for Firefox */
  min-height: 0;
}

</style>

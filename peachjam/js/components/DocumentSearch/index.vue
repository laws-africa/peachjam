<template>
  <div class="doc-search">
    <form
      class="doc-search__form mb-2"
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
      <div
        v-if="marks.length"
        class="text-end mt-2"
      >
        <a
          href="#"
          @click.prevent="clear"
        >Clear</a>
      </div>
      <div
        v-if="!marks.length && q"
        class="mt-2"
      >
        No results
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
      scrollToElement(node, 60).then(() => {
        node.style.outline = '2px solid transparent';
        node.style.transition = 'outline-color 400ms ease-in-out';
        node.style.outlineColor = 'var(--bs-primary)';
        window.setTimeout(() => {
          node.style.outlineColor = 'transparent';
        }, 400);
      });

      function scrollToElement (elem, offset = 0) {
        const rect = elem.getBoundingClientRect();
        const targetPosition = Math.floor(rect.top + self.pageYOffset - offset);
        window.scrollTo({
          top: targetPosition,
          behavior: 'smooth'
        });

        return new Promise((resolve, reject) => {
          const failed = setTimeout(() => {
            // eslint-disable-next-line prefer-promise-reject-errors
            reject();
          }, 2000);
          const scrollHandler = () => {
            if (self.pageYOffset === targetPosition) {
              window.removeEventListener('scroll', scrollHandler);
              clearTimeout(failed);
              resolve();
            }
          };
          if (self.pageYOffset === targetPosition) {
            clearTimeout(failed);
            resolve();
          } else {
            window.addEventListener('scroll', scrollHandler);
            elem.getBoundingClientRect();
          }
        });
      }
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

<template>
  <div class="doc-search">
    <div class="inner">
      <div class="section">
        <div class="mb-4">
          <form @submit="handleSubmit">
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
        <div v-if="!results.length && q">
          No results
        </div>
        <div
          v-if="results.length"
          class="scrollable-content"
        >
          <div v-if="docType === 'akn'">
            <div
              v-for="result in results"
              :key="result.id"
              class="mb-4"
            >
              <AknResult
                :result="result"
                :q="q"
                :block-element-names="aknBlockElNames"
                @go-to-result="goToResult"
              />
            </div>
          </div>
          <HTMLResults
            v-if="docType === 'html'"
            :q="q"
            :results="results"
            @go-to-result="goToResult"
          />

          <PdfResults
            v-if="docType === 'pdf'"
            :results="results"
            :q="q"
            @go-to-result="goToResult"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import Mark from 'mark.js';
import AknResult from './AknResult.vue';
import HTMLResults from './HTMLResults.vue';
import PdfResults from './PdfResults.vue';

export default {
  name: 'DocumentSearch',
  components: { PdfResults, HTMLResults, AknResult },
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
    results: [],
    markInstance: null,
    aknBlockElNames: [
      'blockContainer',
      'block',
      'blockList',
      'conclusions',
      'foreign',
      'item',
      'ol',
      'p',
      'preface',
      'tblock',
      'toc',
      'ul']
  }),
  watch: {
    q (newValue) {
      // Unmark when search if mark instance exists already
      if (this.markInstance) {
        this.markInstance.unmark();
        this.results = [];
      }
      switch (this.docType) {
        case 'akn':
          this.searchAknDoc(newValue);
          break;
        case 'pdf':
          this.searchHTMLDoc(newValue, this.document.querySelectorAll('.pdf-renderer__content__page .textLayer'));
          break;
        case 'html':
          this.searchHTMLDoc(newValue, this.document);
          break;
        default:
          break;
      }
    }
  },
  methods: {
    handleSubmit (e) {
      e.preventDefault();
      this.q = this.$refs.q.value;
    },
    searchPdf (q) {
      // Still tweaking this
      const textLayers = this.document.querySelectorAll('.pdf-renderer__content__page .textLayer');
      const sentences = [];
      textLayers.forEach(element => {
        const sentence = [];
        for (const child of element.childNodes) {
          sentence.push(child);
          if (child.nodeName === 'BR') {
            break;
          }
        }
        sentences.push(sentence);
      });
    },
    searchHTMLDoc (q, markContext) {
      if (!this.markInstance) {
        this.markInstance = new Mark(markContext);
      }
      // Mark content
      this.markInstance.unmark();
      this.markInstance.mark(q, {
        element: 'span',
        className: 'doc-mark',
        separateWordSearch: false
      });
      this.results = [...this.document.querySelectorAll('[data-markjs]')];
    },

    searchAknDoc (q) {
      const selector = this.aknBlockElNames.map(item => `.akn-section .akn-${item}, .akn-preamble .akn-${item}`).join(', ');
      if (!this.markInstance) {
        // Monitor block level element for each section in akn document
        this.markInstance = new Mark(this.document.querySelectorAll(selector));
      }
      if (q) {
        // Mark content
        this.markInstance.unmark();
        this.markInstance.mark(q, {
          separateWordSearch: false
        });

        const searchData = [];
        this.document.querySelectorAll('.akn-section, .akn-preamble').forEach((section) => {
          const titleSelector = section.querySelector('h3');
          const title = (titleSelector ? titleSelector.textContent : '') || '';
          const text = [];
          const contentNodes = section.querySelectorAll(selector);
          contentNodes.forEach((elem) => {
            text.push(elem.textContent);
          });
          searchData.push({
            id: section.id,
            title,
            contentNodes,
            text: text.join(' ').toLocaleLowerCase()
          });
        });

        this.results = searchData.filter(item => item.text.includes(this.q.toLocaleLowerCase()));
      }
    },

    goToResult (node) {
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

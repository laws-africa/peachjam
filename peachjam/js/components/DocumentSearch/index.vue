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
        <div v-if="!aknResults.length && q">
          No results
        </div>
        <div
          v-if="aknResults.length"
          class="scrollable-content"
        >
          <div
            v-for="result in aknResults"
            :key="result.id"
            class="mb-4"
          >
            <AknResult
              :q="q"
              :result="result"
              @mark-clicked="handleMarkClick"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import Mark from 'mark.js';
import AknResult from './AknResult.vue';

export default {
  name: 'DocumentSearch',
  components: { AknResult },
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
    aknResults: [],
    htmlResults: [],
    markInstance: null
  }),
  watch: {
    q (newValue) {
      switch (this.docType) {
        case 'akn':
        case 'document':
          this.searchAknDoc(newValue);
          break;
        case 'pdf':
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
    searchAknDoc () {
      if (!this.markInstance) {
        this.markInstance = new Mark(this.document.querySelectorAll('.akn-p, .akn-listIntroduction, .akn-intro, .akn-wrapUp'));
      }
      if (this.q) {
        const clonedDoc = this.document.cloneNode(true);
        const searchData = [];
        clonedDoc.querySelectorAll('.akn-section').forEach((section) => {
          const titleSelector = section.querySelector('h3');
          const title = (titleSelector ? titleSelector.textContent : '') || '';
          const selector = '.akn-p, .akn-listIntroduction, .akn-intro, .akn-wrapUp';
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

        this.aknResults = searchData.filter(item => item.text.includes(this.q.toLocaleLowerCase()));
        // Mark content
        this.markInstance.unmark();
        this.markInstance.mark(this.q, {
          separateWordSearch: false
        });
      } else {
        this.markInstance.unmark();
        this.aknResults = [];
      }
    },

    handleMarkClick (targetSelector) {
      const targetElement = this.document.querySelector(targetSelector);
      targetElement.style.transition = 'background-color 400ms ease-in-out';
      const top =
        window.pageYOffset +
        targetElement.getBoundingClientRect().top - 70;
      window.scrollTo({
        top,
        behavior: 'smooth'
      });
      targetElement.style.backgroundColor = 'yellow';
      window.setTimeout(() => {
        targetElement.style.backgroundColor = 'initial';
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

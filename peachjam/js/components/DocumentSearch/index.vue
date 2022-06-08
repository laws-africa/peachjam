<template>
  <div class="doc-search">
    <div class="inner">
      <div class="section">
        <div class="mb-4">
          <input
            v-model="q"
            type="text"
            required
            class="form-control"
            placeholder="Search document content"
            aria-label="Search document content"
            aria-describedby="search-content-button"
          >
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
import debounce from 'lodash/debounce';
import AknResult from './AknResult.vue';

export default {
  name: 'DocumentSearch',
  components: { AknResult },
  props: {
    document: {
      type: HTMLElement,
      required: true
    }
  },
  data: () => ({
    q: '',
    aknResults: [],
    markInstance: null
  }),
  watch: {
    q (newValue) {
      this.searchAknDoc(newValue);
    }
  },
  methods: {
    searchAknDoc: debounce(function (q) {
      if (!this.markInstance) {
        this.markInstance = new Mark(this.document.querySelectorAll('.akn-section'));
      }
      if (q) {
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

        if (this.q.length > 3) {
          this.aknResults = searchData.filter(item => item.text.includes(q.toLocaleLowerCase()));

          // Mark content
          this.markInstance.unmark();
          this.markInstance.mark(q, {
            separateWordSearch: false
          });
        }
      } else {
        this.markInstance.unmark();
        this.aknResults = [];
      }
    }, 300),

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

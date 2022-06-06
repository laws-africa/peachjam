<template>
  <div class="doc-search toc">
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
        <div v-if="!results.length && q">
          No results
        </div>
        <div
          v-if="results.length"
          class="scrollable-content"
        >
          <ResultCard
            v-for="result in results"
            :key="result.id"
            :q="q"
            :result="result"
            @mark-clicked="handleMarkClick"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import ResultCard from './ResultCard.vue';
import Mark from 'mark.js';
import debounce from 'lodash/debounce';

export default {
  name: 'DocumentSearch',
  components: { ResultCard },
  props: {
    document: {
      type: HTMLElement,
      required: true
    }
  },
  data: () => ({
    q: '',
    results: []
  }),
  watch: {
    q (newValue) {
      this.searchAknDoc(newValue);
    }
  },
  methods: {
    searchAknDoc: debounce(function (q) {
      const markInstance = new Mark(this.document.querySelectorAll('.akn-p, .akn-listIntroduction, .akn-intro, .akn-wrapUp'));
      if (q) {
        const searchData = [];
        const selector = '.akn-p, .akn-listIntroduction, .akn-intro, .akn-wrapUp';
        this.document.querySelectorAll('.akn-section').forEach((section) => {
          // TODO: This query has cases of duplicate textNodes. Need to investigate why. (For now use Set to remove duplicates)
          // const text = [];
          const text = new Set();
          section.querySelectorAll(selector).forEach((elem) => {
            // text.push(elem.textContent);
            text.add(elem.textContent);
          });
          const titleSelector = section.querySelector('h3');
          const title = (titleSelector ? titleSelector.textContent : '') || '';
          searchData.push({
            id: section.id,
            title,
            content: [...text].join(' ')
          });
        });

        // WIP lunr logic
        // const lunrSearchData = lunr(function () {
        //   this.field('id');
        //   this.field('title');
        //   this.field('content');
        //   searchData.forEach((item) => {
        //     this.add(item);
        //   });
        // });
        // const result = lunrSearchData.search(q);
        // this.results = result.map(x => {
        //   return searchData.find((y) => x.ref === y.id);
        // });
        // Hack to get it working for now
        if (this.q.length > 3) {
          this.results = searchData.filter(item => item.content.toLowerCase().includes(q.toLowerCase()));

          // Mark content
          markInstance.unmark();
          markInstance.mark(q, {
            separateWordSearch: false
          });
        }
      } else {
        markInstance.unmark();
        this.results = [];
      }
    }, 300),

    handleMarkClick (data) {
      const marks = [...this.document.querySelectorAll(`#${data.sectionId} mark`)];
      const targetElement = marks[data.nthMark - 1];
      const top =
        window.pageYOffset +
        targetElement.getBoundingClientRect().top;
      window.scrollTo({
        top,
        behavior: 'smooth'
      });
    }
  }

};
</script>

<style scoped>
.doc-search {
  position: relative;
  height: 100%;
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

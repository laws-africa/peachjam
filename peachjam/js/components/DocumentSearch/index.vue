<template>
  <div class="doc-search">
    <div class="inner">
      <div class="section">
        <form @submit="handleSubmit">
          <div class="input-group my-2">
            <input
              v-model="q"
              type="text"
              required
              class="form-control"
              placeholder="Search document content"
              aria-label="Search document content"
              aria-describedby="search-content-button"
            >
            <button
              id="search-content-button"
              class="btn btn-secondary"
              type="submit"
            >
              Search
            </button>
          </div>
        </form>
        <div class="scrollable-content">
          <ResultCard
            v-for="result in results"
            :q="q"
            :key="result.id"
            :result="result"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import lunr from 'lunr';
import ResultCard from './ResultCard.vue';

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
  methods: {
    searchAknDoc (query) {
      const searchData = [];
      const selector = '.akn-p, .akn-listIntroduction, .akn-intro, .akn-wrapUp';
      this.document.querySelectorAll('.akn-section').forEach((section) => {
        const text = [];
        section.querySelectorAll(selector).forEach((elem) => {
          text.push(elem.textContent);
        });
        const titleSelector = section.querySelector('h3');
        const title = (titleSelector ? titleSelector.textContent : '') || '';
        searchData.push({
          id: section.id,
          title,
          content: text.join(' ').toLocaleLowerCase()
        });
      });
      const learnSearchData = lunr(function () {
        this.field('id');
        this.field('title');
        this.field('content');
        searchData.forEach((item) => {
          this.add(item);
        });
      });
      const result = learnSearchData.search(query);
      this.results = result.map(x => {
        return searchData.find((y) => x.ref === y.id);
      });
      // const instance = new Mark(this.root);
      // instance.mark('famous');
    },
    handleSubmit (e) {
      e.preventDefault();
      this.searchAknDoc(this.q);
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

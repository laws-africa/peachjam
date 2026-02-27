<template>
  <div>
    <search-box
      ref="searchBox"
      v-model="query"
      :history="history"
      :suggestions="suggestions"
      @search="search"
      @cancel="cancel"
    />
  </div>
</template>

<script>
import SearchBox from './SearchBox.vue';

export default {
  name: 'SearchBoxWrapper',
  components: {
    SearchBox
  },
  data: () => {
    return {
      inputEl: null,
      query: '',
      history: [
        { type: 'history', text: 'Previous Search 1' },
        { type: 'history', text: 'Previous Search 2' },
        { type: 'history', text: 'Previous Search 3' }
      ],
      suggestions: []
    };
  },
  methods: {
    show (inputEl) {
      this.inputEl = inputEl;
      this.query = inputEl.value;
      this.$refs.searchBox.show(inputEl);
    },
    search (query) {
      this.$refs.searchBox.hide();
      this.inputEl.value = query;
      // TODO: trigger search
    },
    cancel () {
      this.$refs.searchBox.hide();
    }
  }
};
</script>

<template>
  <SearchBox
    ref="searchBox"
    v-model="query"
    :groups="groups"
    :remove-history="removeHistory"
    @search="search"
    @shortcut="openShortcut"
    @close="cancel"
  />
</template>

<script>
import SearchBox from './SearchBox.vue';
import SearchSuggestions from '../../utils/search-suggestions';

export default {
  name: 'SearchBoxWrapper',
  components: { SearchBox },
  data () {
    return { query: '', groups: [], config: {}, isOpen: false };
  },
  watch: {
    query () {
      if (this.isOpen) this.suggestionSource.update(this.query, this.config.showSuggestions);
    }
  },
  mounted () {
    this.suggestionSource = new SearchSuggestions(groups => { this.groups = groups; });
  },
  beforeUnmount () {
    this.suggestionSource.dispose();
  },
  methods: {
    show (input, config) {
      if (!this.$refs.searchBox.show(input)) return;
      this.config = config;
      this.query = input.value;
      this.isOpen = true;
      this.suggestionSource.update(this.query, config.showSuggestions);
    },
    cancel () {
      this.isOpen = false;
      this.suggestionSource.cancel();
      this.config = {};
    },
    search (query, suggestion) {
      const callback = this.config.onSearch;
      this.$refs.searchBox.close();
      callback(query, suggestion);
    },
    openShortcut (event, item) {
      this.suggestionSource.recordAccess(item);
      if (!event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) this.$refs.searchBox.close();
    },
    removeHistory (item) {
      return this.suggestionSource.removeHistory(item);
    }
  }
};
</script>

<template>
  <SearchBox
    ref="searchBox"
    v-model="query"
    :groups="groups"
    :user-id="shortcuts.user_id"
    :loading="loading"
    :shortcuts-error="shortcutsError"
    :suggestions-loading="suggestionsLoading"
    :suggestions-error="suggestionsError"
    @search="search"
    @shortcut="openShortcut"
    @close="cancel"
  />
</template>

<script>
import SearchBox from './SearchBox.vue';
import SearchSuggestions from '../../utils/search-suggestions';
import OmniboxHistory from '../../utils/omnibox-history';

export default {
  name: 'SearchBoxWrapper',
  components: { SearchBox },
  data () {
    return {
      query: '',
      config: {},
      shortcuts: { user_id: null, recent_searches: [], saved_items: [] },
      recentIds: [],
      recentSearches: [],
      suggestions: [],
      loading: false,
      shortcutsError: false,
      suggestionsLoading: false,
      suggestionsError: false,
      isOpen: false
    };
  },
  computed: {
    groups () {
      const term = this.query.trim().toLocaleLowerCase();
      const matches = item => item.text.toLocaleLowerCase().includes(term);
      const saved = this.shortcuts.saved_items.filter(matches);
      const groups = [];
      if (term) {
        const matchRank = item => {
          const text = item.text.toLocaleLowerCase();
          return text === term ? 0 : (text.startsWith(term) ? 1 : 2);
        };
        saved.sort((a, b) => matchRank(a) - matchRank(b) || this.recency(a) - this.recency(b));
        if (saved.length) groups.push({ key: 'saved', label: this.$t('Saved items'), items: saved.slice(0, 8) });
        if (this.suggestions.length) groups.push({ key: 'suggestions', label: this.$t('Search suggestions'), items: this.suggestions });
        return groups;
      }
      if (this.recentSearches.length) {
        groups.push({ key: 'history', label: this.$t('Recent searches'), items: this.recentSearches.slice(0, 5) });
      }
      const definitions = [
        ['document', this.$t('Saved documents')],
        ['folder', this.$t('Saved folders')],
        ['saved_search', this.$t('Saved searches')]
      ];
      for (const [type, label] of definitions) {
        const items = saved.filter(item => item.type === type);
        // Browser recency takes priority; the server's newest-saved order is the fallback.
        items.sort((a, b) => this.recency(a) - this.recency(b));
        if (items.length) groups.push({ key: type, label, items: items.slice(0, 4) });
      }
      return groups;
    }
  },
  watch: {
    query () { this.loadSuggestions(); }
  },
  mounted () {
    this.shortcutRequests = new Map();
    this.suggestionSource = new SearchSuggestions();
    this.pendingSearches = [];
    window.addEventListener('peachjam.search-completed', this.recordSearch);
    window.addEventListener('hashchange', this.recordCurrentPage);
    document.addEventListener('htmx:afterSwap', this.recordCurrentPage);
  },
  beforeUnmount () {
    this.cancel();
    window.removeEventListener('peachjam.search-completed', this.recordSearch);
    window.removeEventListener('hashchange', this.recordCurrentPage);
    document.removeEventListener('htmx:afterSwap', this.recordCurrentPage);
  },
  methods: {
    preload (url) {
      // Deduplicate concurrent loads, but refresh on every open so saves and searches appear immediately.
      this.shortcutsUrl = url;
      if (this.shortcutRequests.has(url)) return this.shortcutRequests.get(url);
      this.loading = true;
      this.shortcutsError = false;
      const promise = fetch(url, { cache: 'no-store', credentials: 'same-origin' })
        .then(async response => {
          if (!response.ok) throw new Error('Unable to load shortcuts');
          const data = await response.json();
          if (this.shortcutsUrl === url) {
            this.shortcuts = data;
            if (!this.history || this.history.userId !== data.user_id) this.history = new OmniboxHistory(data.user_id);
            for (const search of this.pendingSearches) this.history.remember(search.query, search.url);
            this.pendingSearches = [];
            this.recentSearches = this.history.recent(data.recent_searches);
            this.readRecency();
            this.recordCurrentPage();
          }
          return data;
        })
        .catch(() => {
          if (this.shortcutsUrl === url) {
            this.shortcutsError = true;
            this.shortcuts = { user_id: null, recent_searches: [], saved_items: [] };
            this.history = null;
            this.pendingSearches = [];
            this.recentSearches = [];
          }
          return null;
        })
        .finally(() => {
          this.shortcutRequests.delete(url);
          if (this.shortcutsUrl === url) this.loading = false;
        });
      this.shortcutRequests.set(url, promise);
      return promise;
    },
    show (input, config) {
      if (!this.$refs.searchBox.show(input)) return;
      this.config = config;
      this.query = input.value;
      this.isOpen = true;
      this.loadSuggestions();
      this.preload(config.shortcutsUrl);
    },
    cancel () {
      this.isOpen = false;
      clearTimeout(this.suggestionTimer);
      this.suggestionController?.abort();
      this.suggestions = [];
      this.config = {};
    },
    search (query, suggestion) {
      const callback = this.config.onSearch;
      this.$refs.searchBox.close();
      callback(query, suggestion);
    },
    openShortcut (event, item) {
      if (item.type !== 'history') this.remember(item.id);
      if (!event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) this.$refs.searchBox.close();
    },
    readRecency () {
      try {
        const stored = JSON.parse(localStorage.getItem(`peachjam.omnibox.${this.shortcuts.user_id}`) || '[]');
        this.recentIds = Array.isArray(stored) ? stored.filter(id => typeof id === 'string').slice(0, 30) : [];
      } catch (_) { this.recentIds = []; }
    },
    remember (id) {
      if (this.shortcuts.user_id === null || this.recentIds[0] === id) return;
      this.recentIds = [id, ...this.recentIds.filter(value => value !== id)].slice(0, 30);
      try {
        // Store only IDs, scoped to the signed-in user, rather than private titles or search queries.
        localStorage.setItem(`peachjam.omnibox.${this.shortcuts.user_id}`, JSON.stringify(this.recentIds));
      } catch (_) { /* Browsing still works when storage is unavailable. */ }
    },
    recency (item) {
      const index = this.recentIds.indexOf(item.id);
      return index < 0 ? this.recentIds.length : index;
    },
    recordCurrentPage () {
      if (this.shortcuts.user_id === null) return;
      // The existing document DOM identifies the work, regardless of which expression was opened.
      const workId = document.querySelector('#document-content[data-work-id]')?.dataset.workId;
      const documentItem = this.shortcuts.saved_items.find(item => item.type === 'document' && String(item.work_id) === workId);
      if (documentItem && this.lastVisitedWork !== documentItem.id) {
        this.remember(documentItem.id);
        this.lastVisitedWork = documentItem.id;
      }
      const folderItem = this.shortcuts.saved_items.find(item => {
        if (item.type !== 'folder') return false;
        const url = new URL(item.url, window.location.origin);
        return url.pathname === window.location.pathname && url.hash === window.location.hash;
      });
      if (folderItem && this.lastVisitedFolder !== folderItem.id) this.remember(folderItem.id);
      this.lastVisitedFolder = folderItem?.id;
    },
    recordSearch (event) {
      if (this.shortcutsError) return;
      const search = event.detail;
      if (!this.history || this.loading) {
        this.pendingSearches.push(search);
        return;
      }
      this.history.remember(search.query, search.url);
      this.recentSearches = this.history.recent(this.shortcuts.recent_searches);
    },
    loadSuggestions () {
      clearTimeout(this.suggestionTimer);
      this.suggestionController?.abort();
      this.suggestions = [];
      this.suggestionsLoading = false;
      this.suggestionsError = false;
      const term = this.query.trim();
      if (!this.isOpen || !this.config.showSuggestions || term.length < 3 || !this.suggestionSource.shouldLoad(term)) return;
      this.suggestionsLoading = true;
      this.suggestionTimer = setTimeout(async () => {
        const controller = new AbortController();
        this.suggestionController = controller;
        try {
          const items = await this.suggestionSource.load(term, this.config.suggestionsUrl, controller.signal);
          if (controller.signal.aborted || !this.isOpen || this.query.trim() !== term) return;
          this.suggestions = items.map((item, index) => ({
            id: `suggestion-${index}`, text: item.value, meta: item.typeLabel, suggestionType: item.type
          }));
        } catch (_) {
          if (!controller.signal.aborted) this.suggestionsError = true;
        } finally {
          if (!controller.signal.aborted) this.suggestionsLoading = false;
        }
      }, 200);
    }
  }
};
</script>

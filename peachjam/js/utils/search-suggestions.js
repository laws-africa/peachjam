import i18n from 'i18next';
import peachJam from '../peachjam';
import OmniboxHistory from './omnibox-history';

/** Provide search suggestions, personal shortcuts and history, keeping them current as the user navigates. */
export default class SearchSuggestions {
  constructor (onChange) {
    this.onChange = onChange;
    this.query = '';
    this.active = false;
    this.shortcuts = { user_id: null, recent_searches: [], saved_items: [] };
    this.recentIds = [];
    this.pendingSearches = [];
    this.suggestions = [];
    this.noSuggestions = new Map();
    this.noSuggestionsTtlMs = 30 * 60 * 1000;
    this.maxValueLength = 100;
    this.listeners = [
      [window, 'peachjam.user-loaded', () => this.loadShortcuts()],
      [window, 'peachjam.search-completed', event => this.recordSearch(event.detail)],
      [window, 'hashchange', () => this.recordCurrentPage()],
      [document, 'htmx:afterSwap', () => this.recordCurrentPage()],
      [document, 'htmx:afterRequest', event => this.savedItemsChanged(event)]
    ];
    for (const [target, event, handler] of this.listeners) target.addEventListener(event, handler);
    this.loadShortcuts();
  }

  dispose () {
    this.cancel();
    for (const [target, event, handler] of this.listeners) target.removeEventListener(event, handler);
  }

  changed () {
    this.onChange(this.getGroups());
  }

  getGroups () {
    const term = this.query.trim().toLocaleLowerCase();
    const saved = this.shortcuts.saved_items.filter(item => item.text.toLocaleLowerCase().includes(term));
    const groups = [];
    if (term) {
      const matchRank = item => {
        const text = item.text.toLocaleLowerCase();
        return text === term ? 0 : (text.startsWith(term) ? 1 : 2);
      };
      saved.sort((a, b) => matchRank(a) - matchRank(b) || this.recency(a) - this.recency(b));
      if (saved.length) groups.push({ key: 'saved', label: i18n.t('Saved items'), items: saved.slice(0, 8), showTypes: true });
      if (this.suggestions.length) groups.push({ key: 'suggestions', label: i18n.t('Search suggestions'), items: this.suggestions, showTypes: true });
      return groups;
    }
    const recent = this.history?.recent(this.shortcuts.recent_searches) || [];
    if (recent.length) groups.push({ key: 'history', label: i18n.t('Recent searches'), items: recent.slice(0, 5) });
    for (const [type, label] of [
      ['document', i18n.t('Saved documents')],
      ['folder', i18n.t('Saved folders')],
      ['saved_search', i18n.t('Saved searches')]
    ]) {
      const items = saved.filter(item => item.type === type);
      // Browser recency takes priority; newest-saved order is the fallback.
      items.sort((a, b) => this.recency(a) - this.recency(b));
      if (items.length) groups.push({ key: type, label, items: items.slice(0, 4) });
    }
    return groups;
  }

  loadShortcuts () {
    const data = peachJam.user.omnibox;
    if (!data) return;
    this.shortcuts = data;
    if (!this.history || this.history.userId !== data.user_id) this.history = new OmniboxHistory(data.user_id);
    for (const search of this.pendingSearches) this.history.remember(search.query, search.url);
    this.pendingSearches = [];
    this.readRecency();
    this.recordCurrentPage();
    this.changed();
  }

  savedItemsChanged (event) {
    const { successful, requestConfig } = event.detail;
    if (!successful || requestConfig.verb.toLowerCase() !== 'post') return;
    const path = new URL(requestConfig.path, window.location.origin).pathname;
    const prefix = peachJam.config.urlLangPrefix;
    if ([`${prefix}/user/saved-documents/`, `${prefix}/my/folders/`, `${prefix}/search/saved-searches/`].some(url => path.startsWith(url))) {
      peachJam.loaded();
    }
  }

  recordAccess (item) {
    if (item.type !== 'history') {
      this.remember(item.id);
      this.changed();
    }
  }

  readRecency () {
    try {
      const stored = JSON.parse(localStorage.getItem(`peachjam.omnibox.${this.shortcuts.user_id}`) || '[]');
      this.recentIds = Array.isArray(stored) ? stored.filter(id => typeof id === 'string').slice(0, 30) : [];
    } catch (_) { this.recentIds = []; }
  }

  remember (id) {
    if (this.shortcuts.user_id === null || this.recentIds[0] === id) return;
    this.recentIds = [id, ...this.recentIds.filter(value => value !== id)].slice(0, 30);
    try {
      // Access recency stores only saved-item IDs, scoped to the current user.
      localStorage.setItem(`peachjam.omnibox.${this.shortcuts.user_id}`, JSON.stringify(this.recentIds));
    } catch (_) { /* Browsing still works when storage is unavailable. */ }
  }

  recency (item) {
    const index = this.recentIds.indexOf(item.id);
    return index < 0 ? this.recentIds.length : index;
  }

  recordCurrentPage () {
    if (this.shortcuts.user_id === null) return;
    // Match work IDs; shortcut IDs below identify SavedDocument records, not document expressions.
    const workId = document.querySelector('#document-content[data-work-id]')?.dataset.workId;
    const savedDocument = this.shortcuts.saved_items.find(item => item.type === 'document' && String(item.work_id) === workId);
    let changed = false;
    if (savedDocument && this.lastVisitedSavedDocumentId !== savedDocument.id) {
      this.remember(savedDocument.id);
      this.lastVisitedSavedDocumentId = savedDocument.id;
      changed = true;
    }
    const folder = this.shortcuts.saved_items.find(item => {
      if (item.type !== 'folder') return false;
      const url = new URL(item.url, window.location.origin);
      return url.pathname === window.location.pathname && url.hash === window.location.hash;
    });
    if (folder && this.lastVisitedFolderId !== folder.id) {
      this.remember(folder.id);
      changed = true;
    }
    this.lastVisitedFolderId = folder?.id;
    if (changed) this.changed();
  }

  recordSearch (search) {
    if (!this.history) {
      this.pendingSearches.push(search);
      return;
    }
    this.history.remember(search.query, search.url);
    this.changed();
  }

  removeHistory (item) {
    this.history.remove(item.url);
    this.changed();
  }

  update (query, showSuggestions = true) {
    this.active = true;
    this.query = query;
    this.loadSuggestions(showSuggestions);
    this.changed();
  }

  cancel () {
    this.active = false;
    clearTimeout(this.suggestionTimer);
    this.suggestionController?.abort();
    this.suggestions = [];
  }

  loadSuggestions (showSuggestions) {
    clearTimeout(this.suggestionTimer);
    this.suggestionController?.abort();
    this.suggestions = [];
    const term = this.query.trim();
    if (!showSuggestions || term.length < 3 || !this.shouldLoad(term)) return;
    this.suggestionTimer = setTimeout(async () => {
      const controller = new AbortController();
      this.suggestionController = controller;
      try {
        const items = await this.load(term, controller.signal);
        if (controller.signal.aborted || !this.active || this.query.trim() !== term) return;
        this.suggestions = items;
        this.changed();
      } catch (_) { /* Search remains available when suggestions cannot be loaded. */ }
    }, 200);
  }

  shouldLoad (query) {
    const value = query.toLowerCase();
    if (value.length > this.maxValueLength) return false;
    for (const [prefix, expiresAt] of this.noSuggestions) {
      if (expiresAt <= Date.now()) this.noSuggestions.delete(prefix);
      else if (value.startsWith(prefix)) return false;
    }
    return true;
  }

  async readResponse (response, query) {
    if (!response.ok) throw new Error('Unable to load search suggestions');
    const data = await response.json();
    const suggestions = data.suggestions.map((item, index) => ({
      id: `suggestion-${index}`, text: item.value, meta: item.type_label, suggestionType: item.type
    }));
    if (!suggestions.length) {
      const maxAge = (response.headers.get('Cache-Control') || '').match(/(?:^|,)\s*max-age=(\d+)/i);
      const ttl = maxAge ? Number(maxAge[1]) * 1000 : this.noSuggestionsTtlMs;
      this.noSuggestions.set(query.toLowerCase(), Date.now() + ttl);
    }
    return suggestions;
  }

  async load (query, signal) {
    const url = new URL(`${peachJam.config.urlLangPrefix}/search/api/documents/suggest/`, window.location.origin);
    url.searchParams.set('q', query);
    const response = await fetch(url, { signal });
    if (signal.aborted) return [];
    return this.readResponse(response, query);
  }
}

/** Keep personal search history independent of publicly cached search responses. */
export default class OmniboxHistory {
  constructor (userId) {
    this.userId = userId;
    this.storageKey = `peachjam.omnibox.searches.${userId}`;
    this.items = [];
    this.removed = new Set();
    if (userId === null) return;
    try {
      const stored = JSON.parse(localStorage.getItem(this.storageKey) || '[]');
      if (Array.isArray(stored)) {
        this.items = stored.filter(item => item && typeof item.text === 'string' && typeof item.url === 'string').slice(0, 12);
      }
      const removed = JSON.parse(localStorage.getItem(`${this.storageKey}.removed`) || '[]');
      if (Array.isArray(removed)) this.removed = new Set(removed.filter(url => typeof url === 'string'));
    } catch (_) { /* History also works when browser storage is unavailable. */ }
  }

  canonicalUrl (value) {
    const url = new URL(value, window.location.origin);
    if (url.origin !== window.location.origin) return null;
    // Explicit defaults and suggestion analytics do not change the saved search.
    url.searchParams.delete('suggestion');
    if (url.searchParams.get('page') === '1') url.searchParams.delete('page');
    if (url.searchParams.get('ordering') === '-score') url.searchParams.delete('ordering');
    if (url.searchParams.get('mode') === 'text') url.searchParams.delete('mode');
    url.searchParams.sort();
    return url.pathname + (url.searchParams.size ? '?' + url.searchParams.toString() : '');
  }

  recent (serverItems = []) {
    const seen = new Set();
    return [...this.items, ...serverItems].filter(item => {
      let url;
      try { url = this.canonicalUrl(item.url); } catch (_) { return false; }
      if (!url || this.removed.has(url) || seen.has(url)) return false;
      seen.add(url);
      return true;
    }).slice(0, 12);
  }

  remember (query, value) {
    if (this.userId === null || !query.trim()) return;
    const url = this.canonicalUrl(value);
    if (!url) return;
    this.removed.delete(url);
    this.items = [{ id: `history-${url}`, type: 'history', text: query.trim(), url }, ...this.recent()]
      .filter((item, index) => index === 0 || this.canonicalUrl(item.url) !== url).slice(0, 12);
    this.persist();
  }

  remove (value) {
    if (this.userId === null) return;
    const url = this.canonicalUrl(value);
    if (!url) return;
    // Suppress server-trace fallbacks too, so a removed search stays hidden after a reload.
    this.removed.add(url);
    this.items = this.recent();
    this.persist();
  }

  persist () {
    try {
      localStorage.setItem(this.storageKey, JSON.stringify(this.items));
      localStorage.setItem(`${this.storageKey}.removed`, JSON.stringify([...this.removed]));
    } catch (_) { /* Retain history in memory for this page if storage is blocked. */ }
  }
}

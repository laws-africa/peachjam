/** Share suggestion parsing and empty-prefix expiry across both search interfaces. */
export default class SearchSuggestions {
  constructor () {
    this.noSuggestions = new Map();
    this.noSuggestionsTtlMs = 30 * 60 * 1000;
    this.maxValueLength = 100;
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

  async readResponse (response, query = null) {
    if (!response.ok) throw new Error('Unable to load search suggestions');
    const data = await response.json();
    const suggestions = data.suggestions.map(item => ({
      value: item.value, label: item.value, type: item.type, typeLabel: item.type_label
    }));
    if (!suggestions.length) {
      const maxAge = (response.headers.get('Cache-Control') || '').match(/(?:^|,)\s*max-age=(\d+)/i);
      const ttl = maxAge ? Number(maxAge[1]) * 1000 : this.noSuggestionsTtlMs;
      query = query || new URL(response.url).searchParams.get('q');
      if (query) this.noSuggestions.set(query.toLowerCase(), Date.now() + ttl);
    }
    return suggestions;
  }

  async load (query, endpoint, signal) {
    if (!this.shouldLoad(query)) return [];
    const url = new URL(endpoint, window.location.origin);
    url.searchParams.set('q', query);
    const response = await fetch(url, { signal });
    if (signal.aborted) return [];
    return this.readResponse(response, query);
  }
}

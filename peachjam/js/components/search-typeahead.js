import Autocomplete from 'bootstrap5-autocomplete/autocomplete.js';
import SearchSuggestions from '../utils/search-suggestions';

class CustomAutocomplete extends Autocomplete {
  constructor (input, options) {
    super(input, options);

    this.shouldLoadFromServer = options.shouldLoadFromServer;
  }

  _loadFromServer (show) {
    if (this.shouldLoadFromServer && !this.shouldLoadFromServer()) {
      // hide any existing suggestion
      this.setData([]);
      this.hideSuggestions();
      return false;
    }
    super._loadFromServer(show);
  }
}

export default class SearchTypeahead {
  constructor (input, forVue) {
    this.forVue = forVue;
    this.input = input;
    this.suggestions = new SearchSuggestions();

    this.autocomplete = CustomAutocomplete.getOrCreateInstance(this.input, {
      liveServer: true,
      server: '/search/api/documents/suggest/',
      queryParam: 'q',
      fixed: true,
      fullWidth: true,
      showAllSuggestions: true,
      ignoreEnter: true,
      // 3 chars before suggestions are shown
      suggestionsThreshold: 3,
      noCache: false,
      autoselectFirst: false,
      highlightTyped: false,
      shouldLoadFromServer: this.shouldLoadFromServer.bind(this),
      onServerError: (error, signal) => {
        if (error.name !== 'AbortError' && !signal.aborted) {
          console.warn('Unable to load search suggestions', error);
        }
      },
      onServerResponse: response => this.suggestions.readResponse(response),
      onRenderItem: (item) => {
        const label = this.highlightLabel(item.label);
        const typeLabel = this.escapeHtml(item.typeLabel);
        return `${label} <span class="badge text-bg-secondary float-end ms-2">${typeLabel}</span>`;
      },
      onSelectItem: (item) => {
        if (this.forVue) {
          this.input.dispatchEvent(new CustomEvent('typeahead', { detail: { suggestion: item } }));
        } else {
          if (this.input.form.suggestion) {
            // record the type of suggestion
            this.input.form.suggestion.value = item.type;
          }
          this.input.form.submit();
        }
      }
    });
  }

  shouldLoadFromServer () {
    return this.suggestions.shouldLoad(this.input.value);
  }

  escapeHtml (value) {
    const element = document.createElement('span');
    element.textContent = value;
    return element.innerHTML;
  }

  highlightLabel (label) {
    const query = this.input.value.toLowerCase();
    const matchAt = label.toLowerCase().indexOf(query);
    if (matchAt < 0) return this.escapeHtml(label);

    const before = this.escapeHtml(label.substring(0, matchAt));
    const match = this.escapeHtml(label.substring(matchAt, matchAt + query.length));
    const after = this.escapeHtml(label.substring(matchAt + query.length));
    return `${before}<mark>${match}</mark>${after}`;
  }
}

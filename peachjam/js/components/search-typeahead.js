import Autocomplete from 'bootstrap5-autocomplete/autocomplete.js';

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
    // searches without suggestions; if the input has one of these as a prefix, we know we don't want to
    // call the server again
    this.noSuggestions = new Map();
    this.noSuggestionsTtlMs = 30 * 60 * 1000;
    // don't call the server if the value is longer than this
    this.maxValueLength = 100;

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
      onServerError: (_ignored, signal) => {
        // do nothing to avoid noisey errors
      },
      onServerResponse: async (response) => {
        const data = await response.json();
        const suggestions = data.suggestions.map((suggestion) => {
          return {
            value: suggestion.value,
            label: suggestion.value,
            type: suggestion.type,
            typeLabel: suggestion.type_label,
            targetId: suggestion.target_id
          };
        });
        if (!suggestions.length) {
          this.noSuggestions.set(this.input.value.toLowerCase(), Date.now() + this.noSuggestionsTtlMs);
        }
        return suggestions;
      },
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
          if (this.input.form.suggestion_id) {
            this.input.form.suggestion_id.value = item.targetId || '';
          }
          this.input.form.submit();
        }
      }
    });
  }

  shouldLoadFromServer () {
    const value = this.input.value.toLowerCase();

    if (value.length > this.maxValueLength) {
      return false;
    }

    if (value.length) {
      for (const [prefix, expiresAt] of this.noSuggestions) {
        if (expiresAt <= Date.now()) {
          this.noSuggestions.delete(prefix);
          continue;
        }
        if (value.startsWith(prefix) || value === prefix) {
          return false;
        }
      }
    }
    return true;
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

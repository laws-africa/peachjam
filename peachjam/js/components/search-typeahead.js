import Autocomplete from 'bootstrap5-autocomplete/autocomplete.js';

class CustomAutocomplete extends Autocomplete {
  constructor (input, options) {
    super(input, options);

    this.shouldLoadFromServer = options.shouldLoadFromServer;
  }

  _loadFromServer (show) {
    if (this.shouldLoadFromServer && !this.shouldLoadFromServer()) {
      // TODO: hide suggestions?
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
    this.noSuggestions = new Set();

    this.autocomplete = CustomAutocomplete.getOrCreateInstance(this.input, {
      liveServer: true,
      server: '/search/api/documents/suggest/',
      queryParam: 'q',
      fixed: true,
      fullWidth: true,
      // 3 chars before suggestions are shown
      suggestionsThreshold: 3,
      noCache: false,
      autoselectFirst: false,
      highlightTyped: true,
      shouldLoadFromServer: this.shouldLoadFromServer.bind(this),
      onServerResponse: async (response) => {
        const data = await response.json();
        const suggestions = data.suggestions.prefix.options.map((option) => {
          return {
            value: option.text,
            label: option.text,
            type: 'prefix'
          };
        });
        if (!suggestions.length) {
          this.noSuggestions.add(this.input.value.toLowerCase());
        }
        return suggestions;
      },
      onSelectItem: (item) => {
        if (this.forVue) {
          this.input._typeaheadItem = item;
          this.input.dispatchEvent(new Event('typeahead'));
        } else {
          this.input.form.submit();
        }
      }
    });
  }

  shouldLoadFromServer () {
    const value = this.input.value.toLowerCase();
    if (value.length) {
      for (const prefix of this.noSuggestions) {
        if (value.startsWith(prefix) || value === prefix) {
          return false;
        }
      }
    }
    return true;
  }
}

import Autocomplete from 'bootstrap5-autocomplete/autocomplete.js';

export default class SearchTypeahead {
  constructor (input, forVue) {
    this.forVue = forVue;
    this.input = input;

    Autocomplete.getOrCreateInstance(this.input, {
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
      onServerResponse: async (response) => {
        const data = await response.json();
        const suggestions = data.suggestions.prefix.options.map((option) => {
          return {
            value: option.text,
            label: option.text,
            type: "prefix"
          };
        });
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
}

import { createAndMountApp } from '../utils/vue-utils';
import { vueI18n } from '../i18n';
import SearchBoxWrapper from './FindDocuments/SearchBoxWrapper.vue';

interface SearchInputOptions {
  showSuggestions?: boolean;
  onSearch?: (query: string, suggestion: string | null) => void;
}

interface Omnibox {
  show: (input: HTMLInputElement, options: SearchInputOptions) => void;
}

let omnibox: Omnibox | null = null;
const boundInputs = new WeakSet<HTMLInputElement>();

/** Bind search inputs to a single shared overlay, including inputs inserted by HTMX. */
export default class SearchInput {
  constructor (root: HTMLInputElement, options: SearchInputOptions = {}) {
    if (boundInputs.has(root)) return;
    boundInputs.add(root);
    if (!omnibox) {
      const mountTarget = document.createElement('div');
      document.body.append(mountTarget);
      omnibox = createAndMountApp({
        component: SearchBoxWrapper,
        use: [vueI18n],
        mountTarget
      }) as unknown as Omnibox;
    }
    const wrapper = omnibox;
    const config = {
      showSuggestions: root.dataset.showSuggestions !== 'false',
      onSearch: (query: string, suggestion: string | null) => {
        root.value = query;
        root.dispatchEvent(new Event('input', { bubbles: true }));
        const field = root.form?.elements.namedItem('suggestion') as HTMLInputElement | null;
        if (field) field.value = suggestion || '';
        root.form?.requestSubmit();
      },
      ...options
    };
    root.addEventListener('focus', () => wrapper.show(root, config));
    root.addEventListener('click', () => wrapper.show(root, config));
  }
}

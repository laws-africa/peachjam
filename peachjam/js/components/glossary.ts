export default class GlossaryFilter {
  tabPane: Element | null = null;

  constructor (input: HTMLInputElement) {
    this.tabPane = input.closest('.tab-pane');
    input.addEventListener('input', () => {
      this.filterGlossary(input.value.trim().toLowerCase());
    });
  }

  filterGlossary (needle: string) {
    if (this.tabPane) {
      const glossary = this.tabPane.querySelector('.glossary-list');

      if (glossary) {
        const terms = glossary.querySelectorAll(':scope > li.term');
        terms.forEach((li) => {
          const term = li.getAttribute('data-term');
          li.classList.toggle('d-none', !term || !term.toLowerCase().includes(needle));
        });
      }
    }
  }
}

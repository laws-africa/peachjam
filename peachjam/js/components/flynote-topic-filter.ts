export default class FlynoteTopicFilter {
  constructor (input: HTMLInputElement) {
    const container = input.closest('.card');
    if (!container) return;

    input.addEventListener('input', () => {
      this.filterTopics(container, input.value.trim().toLowerCase());
    });
  }

  filterTopics (container: Element, query: string) {
    const items = container.querySelectorAll('.topic-item');
    items.forEach((item) => {
      const name = item.getAttribute('data-name') ?? '';
      const matches = !query || name.includes(query);
      item.classList.toggle('d-none', !matches);
      item.classList.toggle('d-flex', matches);
    });
  }
}

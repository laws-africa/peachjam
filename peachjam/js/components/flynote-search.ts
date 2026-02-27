class FlynoteSearch {
  constructor (root: HTMLElement) {
    const input = root.querySelector('#flynote-search') as HTMLInputElement | null;
    const list = root.querySelector('#flynote-all-list') as HTMLElement | null;
    const noResults = root.querySelector('#flynote-no-results') as HTMLElement | null;
    if (!input || !list) return;

    input.addEventListener('input', function () {
      const query = input.value.trim().toLowerCase();
      const items = list.querySelectorAll('[data-name]');
      let visible = 0;

      items.forEach(function (item) {
        const match = !query || (item.getAttribute('data-name') || '').indexOf(query) !== -1;
        item.classList.toggle('d-none', !match);
        if (match) visible++;
      });

      if (noResults) {
        noResults.classList.toggle('d-none', visible > 0);
      }
    });
  }
}

export default FlynoteSearch;

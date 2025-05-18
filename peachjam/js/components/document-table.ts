class DocumentTable {
  public root: HTMLElement;

  constructor (root: HTMLElement) {
    this.root = root;
    this.setupSorting();
  }

  setupSorting () {
    this.root.querySelectorAll('[data-sort]').forEach((el) => {
      el.addEventListener('click', (e: Event) => {
        this.setSort(el.getAttribute('data-sort') || '');
      });
    });
  }

  setSort (value: string) {
    // find the enclosing form element and set the value of the name=sort input
    const form = this.root.closest('form');
    if (form && form.sort) {
      form.sort.value = value;
      form.sort.dispatchEvent(new Event('change'));
    }
  }
}

export default DocumentTable;

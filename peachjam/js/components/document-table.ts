import htmx from 'htmx.org';

class DocumentTable {
  public root: HTMLElement;

  constructor (root: HTMLElement) {
    this.root = root;
    this.setupSorting();
    this.loadSavedDocuments();
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

  loadSavedDocuments () {
    // use htmx to load and inject save-document details
    // get document ids
    const ids = Array.from(this.root.querySelectorAll('tr[data-document-id]')).map((el) => {
      return el.getAttribute('data-document-id');
    });
    if (ids.length) {
      const el = document.createElement('div');
      const query = ids.map(id => `doc_id=${id}`).join('&');
      htmx.ajax('get', '/saved-documents/fragments?' + query, el);
    }
  }
}

export default DocumentTable;

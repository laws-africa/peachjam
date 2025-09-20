export class SavedDocumentModal {
  root: HTMLElement;
  placeholder = '';

  constructor (root: HTMLElement) {
    this.root = root;
    this.root.addEventListener('show.bs.modal', this.onShow.bind(this));
    const content = document.getElementById('saved-document-modal-content');
    if (content) {
      this.placeholder = content.innerHTML;
    }
  }

  onShow () {
    // clear modal content
    const content = document.getElementById('saved-document-modal-content');
    if (content) {
      content.innerHTML = this.placeholder;
    }
  }
}

/**
 * Loads and injects HTML fragments for saved documents for the page (or the provided root element).
 */
export function loadSavedDocuments (root: HTMLElement | null = null) {
  root = root || document.documentElement;

  // get document ids
  const ids = new Set(Array.from(root.querySelectorAll('[data-document-id]')).map((el) => {
    return el.getAttribute('data-document-id');
  }));

  // also check root
  if (root.hasAttribute('data-document-id')) {
    ids.add(root.getAttribute('data-document-id'));
  }

  if (ids.size) {
    // off-page element to load fragments into. Actual fragments will be swapped with hx-swap-oob
    const el = document.createElement('div');
    const query = Array.from(ids).map(id => `doc_id=${id}`).join('&');
    // @ts-ignore
    window.htmx.ajax('get', '/user/saved-documents/fragments?' + query, el);
  }
}

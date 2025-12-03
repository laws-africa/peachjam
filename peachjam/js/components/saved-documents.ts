import { htmxAjax } from '../utils/function';

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
    const seachParams = new URLSearchParams();

    seachParams.set('doc_ids', Array.from(ids).join(','));

    // @ts-ignore
    htmxAjax('get', `${peachjam.config.urlLangPrefix}/user/saved-documents/fragments?${searchParams.toString()}`);
  }
}

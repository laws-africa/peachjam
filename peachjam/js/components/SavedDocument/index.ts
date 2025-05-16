export class SavedDocumentModal {
  root: HTMLElement;

  constructor (root: HTMLElement) {
    this.root = root;
    this.root.addEventListener('show.bs.modal', () => {
      // clear modal content
      const content = document.getElementById('saved-document-modal-content');
      if (content) {
        content.innerHTML = '<div class="modal-body spinner-when-empty"></div>';
      }
    });
  }
}

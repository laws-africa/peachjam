export default class DocumentFilterForm {
  public root: HTMLElement;

  constructor (root: HTMLElement) {
    this.root = root;
    // on small displays, move the filters into the offcanvas element
    if (window.innerWidth < 992) {
      this.moveFiltersToOffcanvas();
    }
  }

  moveFiltersToOffcanvas () {
    const offcanvas = this.root.querySelector('.offcanvas-body');
    const content = this.root.querySelector('.document-list-facets');
    if (offcanvas && content) {
      offcanvas.appendChild(content);
    }
  }
}

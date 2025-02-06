export default class DocumentFilterForm {
  public root: HTMLElement;
  public offCanvasUsed: boolean = false;

  constructor (root: HTMLElement) {
    this.root = root;

    // setup a resize observer to move the filters when the window is resized
    const observer = new ResizeObserver(() => this.moveFilters());
    observer.observe(this.root);
    this.moveFilters();
  }

  moveFilters () {
    // on small displays, move the filters into the offcanvas element
    if (window.innerWidth < 992) {
      this.moveFiltersToOffcanvas();
    } else {
      this.moveFiltersToMainContent();
    }
  }

  moveFiltersToOffcanvas () {
    if (!this.offCanvasUsed) {
      const offcanvas = this.root.querySelector('.offcanvas-body');
      const content = this.root.querySelector('.document-list-facets');
      if (offcanvas && content) {
        requestAnimationFrame(() => {
          offcanvas.appendChild(content);
          this.offCanvasUsed = true;
        });
      }
    }
  }

  moveFiltersToMainContent () {
    if (this.offCanvasUsed) {
      const wrapper = this.root.querySelector('.document-list-facets-wrapper');
      const content = this.root.querySelector('.document-list-facets');
      if (wrapper && content) {
        requestAnimationFrame(() => {
          wrapper.appendChild(content);
          this.offCanvasUsed = false;
        });
      }
    }
  }
}

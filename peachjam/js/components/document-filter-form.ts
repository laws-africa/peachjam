export default class DocumentFilterForm {
  public root: HTMLElement;
  public offCanvasUsed: boolean = false;

  constructor (root: HTMLElement) {
    this.root = root;

    // ensure the bootstrap offcanvas element is closed before htmx swaps the content, otherwise it can end up in a
    // broken state
    this.root.addEventListener('htmx:beforeSwap', () => this.cleanupOffcanvas());

    // setup a resize observer to move the filters when the window is resized
    const observer = new ResizeObserver(() => this.moveFilters());
    observer.observe(this.root);
    this.moveFilters();
    this.setupFacetSearch();
    this.setupSkipLinks();
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

  cleanupOffcanvas () {
    const offcanvasElement = this.root.querySelector('[data-document-table-offcanvas]') as HTMLElement | null;
    if (!offcanvasElement) {
      return;
    }

    const offcanvas = window.bootstrap?.Offcanvas?.getInstance(offcanvasElement);
    offcanvas?.hide();
  }

  setupFacetSearch () {
    this.root.querySelectorAll('[data-facet-search]').forEach((facet) => {
      const facetEl = facet as HTMLElement;
      const input = facetEl.querySelector('[data-facet-search-input]') as HTMLInputElement | null;
      if (!input) {
        return;
      }

      const filterOptions = () => {
        this.filterFacetOptions(facetEl, input.value);
      };

      input.addEventListener('input', filterOptions);
      filterOptions();
    });
  }

  filterFacetOptions (facet: HTMLElement, term: string) {
    const searchTerm = term.trim().toLowerCase();
    facet.querySelectorAll('[data-facet-option]').forEach((option) => {
      const optionEl = option as HTMLElement;
      const labelText = optionEl.querySelector('[data-facet-option-label]')?.textContent?.toLowerCase() || '';
      const isVisible = !searchTerm || labelText.includes(searchTerm);

      optionEl.classList.toggle('d-none', !isVisible);
      optionEl.hidden = !isVisible;
      optionEl.setAttribute('aria-hidden', String(!isVisible));
    });
  }

  setupSkipLinks () {
    this.root.querySelectorAll('[data-skip-link]').forEach((link) => {
      link.addEventListener('click', (event: Event) => {
        const currentTarget = event.currentTarget as HTMLAnchorElement | null;
        const href = currentTarget?.getAttribute('href') || '';
        if (!href.startsWith('#')) {
          return;
        }

        const target = document.querySelector(href) as HTMLElement | null;
        if (!target) {
          return;
        }

        event.preventDefault();
        if (currentTarget?.hasAttribute('data-close-offcanvas')) {
          this.cleanupOffcanvas();
        }
        window.history.replaceState(null, '', href);
        requestAnimationFrame(() => this.focusTarget(target));
      });
    });
  }

  focusTarget (target: HTMLElement) {
    target.focus({ preventScroll: true });
    target.scrollIntoView({ block: 'start' });
  }
}

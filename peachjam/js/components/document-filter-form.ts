export default class DocumentFilterForm {
  public root: HTMLElement;
  public offCanvasUsed: boolean = false;

  constructor (root: HTMLElement) {
    this.root = root;

    // setup a resize observer to move the filters when the window is resized
    const observer = new ResizeObserver(() => this.moveFilters());
    observer.observe(this.root);
    this.moveFilters();
    this.setupFacetOptionOrdering();
    this.setupFacetSearch();
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

  setupFacetOptionOrdering () {
    this.root.querySelectorAll('.facets-scrollable').forEach((facet) => {
      const facetEl = facet as HTMLElement;
      facetEl.addEventListener('change', (e: Event) => {
        const target = e.target as HTMLElement | null;
        if (target && target.matches('input[type="checkbox"], input[type="radio"]')) {
          this.reorderFacetOptions(facetEl);
        }
      });
      this.reorderFacetOptions(facetEl);
    });
  }

  filterFacetOptions (facet: HTMLElement, term: string) {
    const searchTerm = term.trim().toLowerCase();
    facet.querySelectorAll('[data-facet-option]').forEach((option) => {
      const optionEl = option as HTMLElement;
      const labelText = optionEl.querySelector('[data-facet-option-label]')?.textContent?.toLowerCase() || '';
      const isVisible = !searchTerm || labelText.includes(searchTerm);

      optionEl.classList.toggle('d-none', !isVisible);
    });
  }

  reorderFacetOptions (facet: HTMLElement) {
    const options = (Array.from(facet.querySelectorAll('[data-facet-option]')) as HTMLElement[]).map((option) => {
      return {
        option,
        selected: this.optionIsSelected(option),
        order: Number(option.dataset.facetOptionOrder || 0)
      };
    });

    options.sort((a, b) => {
      const aSelected = a.selected ? 0 : 1;
      const bSelected = b.selected ? 0 : 1;
      if (aSelected !== bSelected) {
        return aSelected - bSelected;
      }

      return a.order - b.order;
    });

    options.forEach(({ option }) => {
      facet.appendChild(option);
    });
  }

  optionIsSelected (option: HTMLElement) {
    return !!option.querySelector<HTMLInputElement>('input:checked');
  }
}

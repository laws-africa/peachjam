/** Fill the mobile pagination row with as many nearby page links as fit. */
export default class ResponsivePagination {
  private root: HTMLElement;
  private currentPage: number;
  private pageCount: number;
  private baseUrl: URL;
  private pageLabel: string;
  private currentPageLabel: string;
  private ellipsis: string;
  private observer?: ResizeObserver;

  constructor (root: HTMLElement) {
    this.root = root;
    this.currentPage = Number(root.dataset.currentPage);
    this.pageCount = Number(root.dataset.pageCount);
    this.baseUrl = new URL(root.dataset.baseUrl || window.location.href, window.location.origin);
    this.pageLabel = root.dataset.pageLabel || 'Go to page __PAGE__';
    this.currentPageLabel = root.dataset.currentPageLabel || 'Current page, page __PAGE__';
    this.ellipsis = root.dataset.ellipsis || '…';

    if (!Number.isInteger(this.currentPage) || !Number.isInteger(this.pageCount)) return;

    this.observer = new ResizeObserver(() => this.update());
    this.observer.observe(root);
    this.update();
  }

  private update (): void {
    if (!this.root.clientWidth) return;

    const pages = new Set<number>([this.currentPage]);
    if (this.currentPage > 1) pages.add(this.currentPage - 1);
    if (this.currentPage < this.pageCount) pages.add(this.currentPage + 1);
    pages.add(this.pageCount);
    const omittedEnds = new Set<number>();
    this.render(pages);

    // Nearby pages take priority over a distant last-page shortcut.
    if (this.root.scrollWidth > this.root.clientWidth &&
      this.pageCount > this.currentPage + 1) {
      pages.delete(this.pageCount);
      omittedEnds.add(this.pageCount);
      this.render(pages);
    }

    // Move the numbered window forward as the current page advances.
    for (let page = this.currentPage + 2; page <= this.pageCount; page++) {
      if (pages.has(page) || omittedEnds.has(page)) continue;
      if (!this.addIfFits(pages, page)) return;
    }

    // At the end of the list, use any remaining room for earlier pages.
    for (let page = this.currentPage - 2; page >= 1; page--) {
      if (pages.has(page)) continue;
      if (!this.addIfFits(pages, page)) break;
    }
  }

  private addIfFits (pages: Set<number>, page: number): boolean {
    pages.add(page);
    this.render(pages);
    if (this.root.scrollWidth <= this.root.clientWidth) return true;

    pages.delete(page);
    this.render(pages);
    return false;
  }

  private render (pages: Set<number>): void {
    const items: HTMLElement[] = [];
    if (this.currentPage > 1) items.push(this.pageLink(this.currentPage - 1, '‹'));

    let previousPage = 0;
    for (const page of Array.from(pages).sort((a, b) => a - b)) {
      if (previousPage && page - previousPage === 2) items.push(this.pageLink(previousPage + 1));
      if (previousPage && page - previousPage > 2) items.push(this.ellipsisItem());
      items.push(page === this.currentPage ? this.currentItem() : this.pageLink(page));
      previousPage = page;
    }

    if (this.currentPage < this.pageCount) items.push(this.pageLink(this.currentPage + 1, '›'));
    this.root.replaceChildren(...items);
  }

  private pageLink (page: number, arrow?: string): HTMLElement {
    const item = document.createElement('li');
    item.className = 'page-item flex-fill';

    const link = document.createElement('a');
    link.className = 'page-link text-center';
    const url = new URL(this.baseUrl);
    url.searchParams.set('page', String(page));
    link.href = url.pathname + url.search + url.hash;
    link.setAttribute('aria-label', this.pageLabel.replace('__PAGE__', String(page)));

    if (arrow) {
      const symbol = document.createElement('span');
      symbol.setAttribute('aria-hidden', 'true');
      symbol.textContent = arrow;
      link.append(symbol);
    } else {
      link.textContent = String(page);
    }

    item.append(link);
    return item;
  }

  private currentItem (): HTMLElement {
    const item = document.createElement('li');
    item.className = 'page-item active flex-fill';
    item.setAttribute('aria-current', 'page');

    const label = document.createElement('span');
    label.className = 'page-link text-center';
    label.append(String(this.currentPage));

    const hidden = document.createElement('span');
    hidden.className = 'visually-hidden';
    hidden.textContent = this.currentPageLabel.replace('__PAGE__', String(this.currentPage));
    label.append(hidden);
    item.append(label);
    return item;
  }

  private ellipsisItem (): HTMLElement {
    const item = document.createElement('li');
    item.className = 'page-item flex-fill';

    const label = document.createElement('span');
    label.className = 'page-link text-center';
    label.setAttribute('aria-hidden', 'true');
    label.textContent = this.ellipsis;
    item.append(label);
    return item;
  }
}

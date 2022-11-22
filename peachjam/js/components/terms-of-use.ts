import { generateHtmlTocItems } from '../utils/function';

class TermsOfUse {
  constructor (root: HTMLElement) {
    const content: HTMLElement | null = root.querySelector('[data-terms-of-use-content]');
    const tocContainer: HTMLElement | null = root.querySelector('[data-table-of-contents]');
    if (!content || !tocContainer) return;
    const tableOfContents = document.createElement('la-table-of-contents');
    tableOfContents.items = generateHtmlTocItems(content);
    tocContainer.appendChild(tableOfContents);
  }
}

export default TermsOfUse;

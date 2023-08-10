import { generateHtmlTocItems } from '../utils/function';

class TermsOfUse {
  constructor (root: HTMLElement) {
    const content: HTMLElement | null = root.querySelector('.terms-of-use-content');
    const tocContainers: HTMLElement[] = Array.from(root.querySelectorAll('.navigation-toc'));
    if (!content || !tocContainers.length) return;
    const items = generateHtmlTocItems(content);
    const nav: HTMLElement | null = document.getElementById('side-nav');
    const offCanvas = new window.bootstrap.Offcanvas(nav);

    tocContainers.forEach(element => {
      const tableOfContents = document.createElement('la-table-of-contents');
      tableOfContents.items = items;
      element.appendChild(tableOfContents);
      tableOfContents.addEventListener('itemTitleClicked', (e) => {
        offCanvas?.hide();
      });
    });
  }
}

export default TermsOfUse;

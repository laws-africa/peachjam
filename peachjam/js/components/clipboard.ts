export class CopyToClipboard {
  root: HTMLElement;
  buttonHTML: string;

  constructor (root: HTMLElement) {
    this.root = root;
    this.buttonHTML = root.innerHTML;
    root.addEventListener('click', () => this.copy());
  }

  async copy () {
    try {
      const text = this.root.dataset.value;
      const html = this.root.dataset.valueHtml;

      if (navigator && navigator.clipboard) {
        const items: Record<string, Blob> = {};

        if (text) {
          const type = 'text/plain';
          items[type] = new Blob([text], { type });
        }

        if (html) {
          const type = 'text/html';
          items[type] = new Blob([html], { type });
        }

        await navigator.clipboard.write([new ClipboardItem(items)]);

        this.root.innerText = this.root.dataset.confirmation || 'Copied!';
        setTimeout(() => {
          this.root.innerHTML = this.buttonHTML;
        }, 1500);
      }
    } catch {
      this.root.innerText = 'Copy failed!';
      setTimeout(() => {
        this.root.innerHTML = this.buttonHTML;
      }, 1500);
    }
  }
}

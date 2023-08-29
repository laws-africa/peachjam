export class CopyToClipboard {
  root: HTMLElement;
  text: string;

  constructor (root: HTMLElement) {
    this.root = root;
    this.text = root.innerText;
    root.addEventListener('click', () => this.copy());
  }

  async copy () {
    try {
      if (navigator && navigator.clipboard) {
        await navigator.clipboard.writeText(this.root.dataset.value || '');

        this.root.innerText = this.root.dataset.confirmation || 'Copied!';
        setTimeout(() => {
          this.root.innerText = this.text;
        }, 1500);
      }
    } catch {
      this.root.innerText = 'Copy failed!';
      setTimeout(() => {
        this.root.innerText = this.text;
      }, 1500);
    }
  }
}

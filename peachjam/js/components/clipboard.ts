export class CopyToClipboard {
  root: HTMLElement;
  text: string;

  constructor (root: HTMLElement) {
    this.root = root;
    this.text = root.innerText;
    root.addEventListener('click', () => this.copy());
  }

  copy () {
    if (navigator && navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(this.root.dataset.value || '')
        .then(() => {
          this.root.innerText = this.root.dataset.confirmation || 'Copied!';
          setTimeout(() => {
            this.root.innerText = this.text;
          }, 1500);
        })
        .catch(() => {
          this.root.innerText = 'Copy failed!';
          setTimeout(() => {
            this.root.innerText = this.text;
          }, 1500);
        });
    }
  }
}

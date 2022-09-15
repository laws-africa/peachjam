export class CopyToClipboard {
  root: HTMLElement;
  text: string;

  constructor (root: HTMLElement) {
    this.root = root;
    this.text = root.innerText;
    root.addEventListener('click', () => this.copy());
  }

  copy () {
    navigator.clipboard.writeText(this.root.dataset.value || '').then(() => {
      this.root.innerText = this.root.dataset.confirmation || 'Copied!';
      setTimeout(() => {
        this.root.innerText = this.text;
      }, 1500);
    });
  }
}

import debounce from 'lodash/debounce';

export default class FloatingHeader {
  public root: HTMLElement;
  public documentContent: HTMLElement;

  constructor(root: HTMLElement) {
    this.root = root;
    this.documentContent = document.querySelector('.document-detail-toolbar') as HTMLElement;
    this.init();
  }

  init () {
    window.addEventListener('scroll', debounce(this.onScroll.bind(this), 200));
  }

  onScroll () {
    const contentTop = this.documentContent.getBoundingClientRect().top;
    if (contentTop <= -10) {
      this.root.classList.add('visible');
    } else {
      this.root.classList.remove('visible');
    }
  }
}

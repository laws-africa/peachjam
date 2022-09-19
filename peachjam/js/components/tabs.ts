export class ToggleTab {
  anchor: HTMLElement;

  constructor (anchor: HTMLAnchorElement) {
    this.anchor = anchor;
    this.anchor.addEventListener('click', (e) => this.clicked(e));
  }

  clicked (e: Event) {
    e.preventDefault();
    const href = this.anchor.getAttribute('href');
    if (href) {
      const trigger = document.querySelector(`[data-bs-target="${href}"]`);
      if (trigger) {
        // @ts-ignore
        const tab = new window.bootstrap.Tab(trigger);
        tab.show();
      }
    }
  }
}

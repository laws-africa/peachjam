export class ToggleTab {
  btn: HTMLElement;

  constructor (btn: HTMLElement) {
    this.btn = btn;
    this.btn.addEventListener('click', (e) => this.clicked(e));
  }

  clicked (e: Event) {
    e.preventDefault();
    const href = this.btn.getAttribute('href');
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

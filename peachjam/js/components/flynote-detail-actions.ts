import peachJam from '../peachjam';

export default class FlynoteDetailActions {
  root: HTMLElement;
  manageUrl: string;

  constructor (root: HTMLElement) {
    this.root = root;
    this.manageUrl = root.dataset.manageUrl || '';

    peachJam.whenUserLoaded().then((user) => {
      if (user.is_staff && this.manageUrl) {
        this.render();
      }
    });
  }

  render () {
    const wrapper = document.createElement('div');
    wrapper.className = 'dropdown';

    const button = document.createElement('button');
    button.className = 'btn btn-outline-secondary btn-sm';
    button.type = 'button';
    button.setAttribute('data-bs-toggle', 'dropdown');
    button.setAttribute('aria-expanded', 'false');
    button.setAttribute('aria-label', 'Flynote actions');
    button.innerHTML = '<i class="bi bi-three-dots" aria-hidden="true"></i>';

    const menu = document.createElement('ul');
    menu.className = 'dropdown-menu dropdown-menu-end';

    const item = document.createElement('li');
    const link = document.createElement('a');
    link.className = 'dropdown-item';
    link.href = this.manageUrl;
    link.innerText = 'Manage flynote';

    item.appendChild(link);
    menu.appendChild(item);
    wrapper.appendChild(button);
    wrapper.appendChild(menu);
    this.root.replaceChildren(wrapper);
  }
}

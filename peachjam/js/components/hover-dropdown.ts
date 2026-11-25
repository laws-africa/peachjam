import { Dropdown } from 'bootstrap';

/** Add desktop hover to Bootstrap dropdowns while preserving native button controls. */
export default class HoverDropdown {
  constructor (root: HTMLElement) {
    if (root.dataset.hoverDropdownInitialized) return;
    const toggle = root.querySelector<HTMLElement>('[data-bs-toggle="dropdown"]');
    if (!toggle) return;
    root.dataset.hoverDropdownInitialized = 'true';
    const dropdown = Dropdown.getOrCreateInstance(toggle);
    const desktopHover = window.matchMedia('(min-width: 992px) and (hover: hover) and (pointer: fine)');
    let closeTimer: ReturnType<typeof setTimeout>;
    root.addEventListener('mouseenter', () => {
      clearTimeout(closeTimer);
      if (desktopHover.matches) dropdown.show();
    });
    root.addEventListener('mouseleave', () => {
      // Allow the pointer to cross Bootstrap's small gap above the dropdown.
      closeTimer = setTimeout(() => {
        if (desktopHover.matches && !root.contains(document.activeElement)) dropdown.hide();
      }, 150);
    });
    root.addEventListener('focusout', (event: FocusEvent) => {
      if (!root.contains(event.relatedTarget as Node | null)) dropdown.hide();
    });
  }
}

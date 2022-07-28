class NavigationSelect {
  constructor (root: HTMLSelectElement) {
    root.addEventListener('change', e => {
      window.location.href = root.options[root.selectedIndex].value;
    });
  }
}

export default NavigationSelect;

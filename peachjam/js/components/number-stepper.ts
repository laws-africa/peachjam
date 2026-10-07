export default class NumberStepper {
  root: HTMLElement;

  constructor (root: HTMLElement) {
    this.root = root;
    this.root.querySelectorAll<HTMLButtonElement>('[data-step]').forEach((button) => {
      button.addEventListener('click', () => this.step(button));
    });
    this.root.querySelectorAll<HTMLInputElement>('[data-number-stepper-input]').forEach((input) => {
      input.addEventListener('input', () => this.updateButtons(input));
      this.updateButtons(input);
    });
  }

  step (button: HTMLButtonElement) {
    const group = button.closest('.input-group');
    const input = group?.querySelector<HTMLInputElement>('[data-number-stepper-input]');
    if (!input) return;
    if (Number(button.dataset.step) < 0) input.stepDown();
    else input.stepUp();
    input.dispatchEvent(new Event('input', { bubbles: true }));
  }

  updateButtons (input: HTMLInputElement) {
    const group = input.closest('.input-group');
    const value = Number(input.value);
    const minimum = Number(input.min || 0);
    const maximum = input.max ? Number(input.max) : null;
    const decrement = group?.querySelector<HTMLButtonElement>('[data-step="-1"]');
    const increment = group?.querySelector<HTMLButtonElement>('[data-step="1"]');
    if (decrement) decrement.disabled = value <= minimum;
    if (increment) increment.disabled = maximum !== null && value >= maximum;
  }
}

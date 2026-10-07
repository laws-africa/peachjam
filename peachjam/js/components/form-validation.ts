interface HtmxValidationError {
  elt: HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement;
}

interface HtmxValidationHaltedEvent extends Event {
  detail: {
    errors: HtmxValidationError[];
  };
}

/** Shows native browser validation feedback for an HTMX form submission. */
export default class FormValidation {
  public root: HTMLFormElement;

  constructor (root: HTMLElement) {
    this.root = root as HTMLFormElement;
    this.root.addEventListener('htmx:validation:halted', (event) => this.reportFirstError(event));
  }

  reportFirstError (event: Event) {
    const errors = (event as HtmxValidationHaltedEvent).detail.errors;
    errors[0]?.elt.reportValidity();
  }
}

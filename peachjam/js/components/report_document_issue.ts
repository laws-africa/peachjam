export class ReportDocumentIssue {
  root: HTMLElement;
  form: HTMLFormElement | null;

  constructor (root: HTMLElement) {
    this.root = root;
    this.form = this.root.querySelector('form');
    if (this.form) {
      this.form.addEventListener('submit', (e: SubmitEvent) => this.submit(e));
    }
  }

  submit (e: SubmitEvent) {
    e.preventDefault();

    const form = new FormData(this.form || undefined);

    fetch('/api/document-problem/', {
      method: 'post',
      body: form
    }).then(response => {
      if (response.ok) {
        return response.text();
      } else {
        throw new Error('Something went wrong');
      }
    }).then(data => {
      this.handleResponse(data);
    }).catch(error => {
      console.log(error);
    });
  }

  handleResponse (response: string) {
    if (this.form) {
      this.form.innerHTML = response;
    }
  }
}

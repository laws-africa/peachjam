export default class DocumentUploader {
  extractorUrl: string;
  fileUpload: HTMLInputElement;
  notices: HTMLElement;

  constructor (root: HTMLElement) {
    this.extractorUrl = root.dataset.extractorUrl || '';
    this.notices = document.createElement('div');
    this.fileUpload = document.getElementById('id_upload_file') as HTMLInputElement;

    if (this.fileUpload) {
      this.fileUpload.insertAdjacentElement('afterend', this.notices);
      this.fileUpload?.addEventListener('change', this.onFileChanged.bind(this));
    }
  }

  async onFileChanged (event: Event) {
    const file = this.fileUpload.files?.[0];
    if (file) {
      this.notices.innerHTML = '';
      const result = document.createElement('div');
      this.notices.appendChild(result);

      // get a digest of the file and check with the server if it's a duplicate
      const digest = await calculateDigest(file);
      if (digest) {
        // ask server if the file is a duplicate
        // @ts-ignore
        window.htmx.ajax('GET', `/admin/check-duplicate-file?sha256=${digest}`, result);
      }

      if (this.extractorUrl) {
        this.useExtractor(file);
      }
    }
  }

  async useExtractor (file: File) {
    const status = document.createElement('div');
    status.innerText = 'Extracting...';
    this.notices.appendChild(status);

    const csrfToken = document.querySelector('input[name="csrfmiddlewaretoken"]')?.getAttribute('value');
    const formData = new FormData();
    formData.append('file', file);
    formData.append('csrfmiddlewaretoken', csrfToken || '');

    try {
      const resp = await fetch(this.extractorUrl, {
        method: 'POST',
        body: formData
      });
      if (resp.ok) {
        // parse the html into a DOM
        const html = await resp.text();
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');

        this.replaceFormElements(doc);

        const result = doc.querySelector('#extraction-result');
        if (result) {
          status.replaceWith(result);
        }
      } else {
        status.innerText = 'Error: ' + (await resp.text()) || resp.statusText;
      }
    } catch (e) {
      status.innerText = 'Error: ' + e;
    }
  }

  replaceFormElements (doc: Document) {
    // insert the elements into the form
    doc.querySelectorAll('select[id], input[id]').forEach((input) => {
      const el = document.getElementById(input.id);
      if (el) {
        // SELECT elements need special handling for select2
        if (el.tagName === 'SELECT' && el.nextElementSibling?.classList.contains('select2')) {
          el.nextElementSibling.remove();
        }
        el.replaceWith(input);
        if (el.tagName === 'SELECT') {
          // @ts-ignore
          window.django.jQuery(input).select2({ width: 'element' });
        }
      }
    });
  }
}

/* Calculate SHA-256 hash of an ArrayBuffer */
async function sha256 (data: ArrayBuffer): Promise<string> {
  const hashBuffer = await crypto.subtle.digest('SHA-256', data); // hash the message
  const hashArray = Array.from(new Uint8Array(hashBuffer)); // convert buffer to byte array
  return hashArray.map(b => b.toString(16).padStart(2, '0')).join(''); // convert bytes to hex string
}

async function calculateDigest (file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = async function (event) {
      const arrayBuffer = event.target?.result as ArrayBuffer;
      const digest = await sha256(arrayBuffer);
      resolve(digest);
    };
    reader.onerror = function (event) {
      reject(event);
    };
    reader.readAsArrayBuffer(file);
  });
}

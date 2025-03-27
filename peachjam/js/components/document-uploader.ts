export default class DocumentUploader {
  model: string;
  fileUpload: HTMLInputElement;

  constructor (root: HTMLElement) {
    this.model = root.dataset.model || '';
    this.fileUpload = document.getElementById('id_upload_file') as HTMLInputElement;
    this.fileUpload?.addEventListener('change', this.onFileChanged.bind(this));
  }

  async onFileChanged (event: Event) {
    const file = this.fileUpload.files?.[0];
    if (file) {
      const notices = document.createElement('div');
      const result = document.createElement('div');
      notices.appendChild(result);
      this.fileUpload.insertAdjacentElement('afterend', notices);

      // get a digest of the file and check with the server if it's a duplicate
      const digest = await calculateDigest(file);
      if (digest) {
        // ask server if the file is a duplicate
        // @ts-ignore
        window.htmx.ajax('GET', `/admin/check-duplicate-file?sha256=${digest}`, result);
      }

      if (this.model === 'peachjam.judgment') {
        this.useExtractor(file, notices);
      }
    }
  }

  async useExtractor (file: File, notices: HTMLElement) {
    const status = document.createElement('div');
    status.innerText = 'Extracting...';
    notices.appendChild(status);

    const csrfToken = document.querySelector('input[name="csrfmiddlewaretoken"]')?.getAttribute('value');
    const formData = new FormData();
    formData.append('file', file);
    formData.append('csrfmiddlewaretoken', csrfToken || '');

    try {
      const resp = await fetch('/admin/peachjam/judgment/extract/', {
        method: 'POST',
        body: formData
      });
      if (resp.ok) {
        const html = await resp.text();
        // parse the html into a DOM
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');

        // insert the elements into the form
        doc.querySelectorAll('select[id], input[id]').forEach((input) => {
          const el = document.getElementById(input.id);
          if (el) {
            if (el.tagName === 'SELECT' && el.nextElementSibling?.classList.contains('select2')) {
              el.nextElementSibling.remove();
            }
            el.replaceWith(input);
            // @ts-ignore
            window.django.jQuery(input).select2({width: 'element'});
          }
        });

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

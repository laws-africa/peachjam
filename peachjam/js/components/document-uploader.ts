export default class DocumentUploader {
  fileUpload: HTMLInputElement;

  constructor (root: HTMLElement) {
    this.fileUpload = document.getElementById('id_upload_file') as HTMLInputElement;
    this.fileUpload?.addEventListener('change', this.onFileChanged.bind(this));
  }

  async onFileChanged (event: Event) {
    const file = this.fileUpload.files?.[0];
    if (file) {
      const container = document.createElement('div');
      this.fileUpload.insertAdjacentElement('beforebegin', container);
      // get a digest of the file and check with the server if it's a duplicate
      const digest = await this.calculateDigest(file);
      if (digest) {
        // ask server if the file is a duplicate
        // @ts-ignore
        window.htmx.ajax('GET', `/admin/check-duplicate-file?sha256=${digest}`, container);
      }
    }

    // TODO: use extractor
  }

  async calculateDigest (file: File): Promise<string> {
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
}

/* Calculate SHA-256 hash of an ArrayBuffer */
async function sha256 (data: ArrayBuffer): Promise<string> {
  const hashBuffer = await crypto.subtle.digest('SHA-256', data); // hash the message
  const hashArray = Array.from(new Uint8Array(hashBuffer)); // convert buffer to byte array
  return hashArray.map(b => b.toString(16).padStart(2, '0')).join(''); // convert bytes to hex string
}

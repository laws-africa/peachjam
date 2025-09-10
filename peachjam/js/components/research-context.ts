export default class ResearchContext {
  root: HTMLElement;
  documentContent: HTMLElement;

  constructor (root: HTMLElement) {
    this.root = root;
    this.documentContent = document.querySelector('#document-content .content') as HTMLElement;
    console.log(this.documentContent);

    // HACK
    window.setTimeout(() => this.decorateCitations(), 100);
  }

  decorateCitations () {
    const citations = this.documentContent.querySelectorAll('a');
    let i = 1;

    citations.forEach(citation => {
      if (citation.getAttribute('href')?.startsWith('/akn/') &&
        citation.parentElement?.tagName !== 'A') {

        // get the target
        const uri = citation.getAttribute('href');
        const target = this.root.querySelector('[data-frbr-uri="' + uri + '"]');

        if (target) {
          // append a number
          let a = document.createElement('span');
          a.className = 'citation-link';
          a.innerText = `${i}`;
          a.addEventListener('click', (e) => {
            e.preventDefault();
            target.scrollIntoView({behavior: 'smooth'});
          });
          citation.insertAdjacentElement('afterend', a);

          a = document.createElement('span');
          a.className = 'citation-link';
          a.innerText = `${i}`;
          a.addEventListener('click', (e) => {
            e.preventDefault();
            citation.scrollIntoView({behavior: 'smooth'});
          });
          target.querySelector('.title')?.insertAdjacentElement('beforeend', a);

          i++;
        }
      }
    });
  }
}

function setupLawReaderComparison () {
  const template = document.getElementById('law-reader-template');
  const tocElement = document.getElementById('akn_toc_json');

  function addComparisonButton (wrapper, item) {
    const heading = wrapper.querySelector('h1, h2, h3, h4, h5, h6');
    if (heading) {
      const html = template.innerHTML.replace('PORTION', 'portion-a=' + item.id + '&portion-b=' + item.id);
      // add it after element
      heading.insertAdjacentHTML('afterend', html);
    }
  }

  if (template && tocElement) {
    const toc = JSON.parse(tocElement.textContent) || [];

    for (let i = 0; i < toc.length; i++) {
      const el = document.getElementById(toc[i].id);
      if (el) {
        addComparisonButton(el, toc[i]);
      }
    }
  }
}

window.addEventListener('peachjam.before-setup', setupLawReaderComparison);

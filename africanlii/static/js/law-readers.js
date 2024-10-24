function setupLawReaderComparison () {
  function addComparisonButton (wrapper) {
    const heading = wrapper.querySelector('h1, h2, h3, h4, h5, h6');
    if (heading) {
      const a = document.createElement('a');
      a.textContent = 'Compare';
      a.href = '/foo';
      // add it after element
      heading.insertAdjacentElement('afterend', a);
    }
  }

  const tocElement = document.getElementById('akn_toc_json');
  if (tocElement) {
    const toc = JSON.parse(tocElement.textContent) || [];
    for (let i = 0; i < toc.length; i++) {
      const el = document.getElementById(toc[i].id);
      if (el) {
        addComparisonButton(el, toc[i].id);
      }
    }
  }
}

window.addEventListener('peachjam.before-setup', setupLawReaderComparison);

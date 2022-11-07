class TaxonomyTree {
  constructor (root: HTMLSelectElement) {
    const tableOfContents = document.createElement('la-table-of-contents');
    // TODO: Add logic to sort taxonomy data for laTableOfContents to ingest
    const jsonElement: HTMLElement | null = root.querySelector('#taxonomy-tree');
    tableOfContents.items = jsonElement ? JSON.parse(jsonElement.textContent as string) : [];
    root.appendChild(tableOfContents);
  }
}

export default TaxonomyTree;

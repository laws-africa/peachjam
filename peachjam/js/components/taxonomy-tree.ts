type ItemType = {
  [key: string] : any,
  title: string,
  id: string,
  children: ItemType[]
}

class TaxonomyTree {
  constructor (root: HTMLElement) {
    const tableOfContents = document.createElement('la-table-of-contents');
    const jsonElement: HTMLElement | null = document.getElementById('taxonomy_tree');
    const data = jsonElement && jsonElement.textContent ? JSON.parse(jsonElement.textContent as string) : [];
    const urlParts: string[] = window.location.href.split('/');
    const currentTaxonomy = urlParts[urlParts.length - 1];

    const slugRoot: string = root.dataset.rootSlug || '';

    tableOfContents.items = data.map((item: ItemType) => {
      const formatItem = (x: ItemType, ancestors: string[]) => {
        const newAncestors = [...ancestors, x.data.slug];
        const formatted: ItemType = {
          title: x.data.name,
          id: newAncestors.join('/'),
          children: []
        };
        if (Object.keys(x).includes('children')) {
          formatted.children = x.children.map(y => formatItem(y, newAncestors));
        }
        return formatted;
      };
      return formatItem(item, ['taxonomy', slugRoot]);
    });

    root.appendChild(tableOfContents);

    // data-slug-root should always have a value. Contractual dom agreement.
    tableOfContents.addEventListener('itemRendered', (e) => {
      const tocItem = e.target as HTMLElement | null;
      if (!tocItem) return;
      const hrefElement = tocItem.querySelector('.content__action__title') as HTMLAnchorElement | null;
      if (!hrefElement) return;

      const taxonomies: string[] = hrefElement.href.split('/');
      if (!taxonomies.length) return;
      const taxonomy = taxonomies[taxonomies.length - 1];
      if (taxonomy === currentTaxonomy) {
        hrefElement.removeAttribute('href');
        hrefElement.classList.add('active');
      } else {
        const url = new URL(hrefElement.href);
        hrefElement.href = url.hash.replace('#', '/');
      }
    });
  }
}

export default TaxonomyTree;

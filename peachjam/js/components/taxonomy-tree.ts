type ItemType = {
  [key: string] : any,
  title: string,
  id: string,
  children: ItemType[]
}

class TaxonomyTree {
  constructor (root: HTMLElement) {
    const tableOfContents = document.createElement('la-table-of-contents');
    const jsonElement: HTMLElement | null = root.querySelector('#annotated-taxonomy-tree');
    const data = jsonElement && jsonElement.textContent ? JSON.parse(jsonElement.textContent as string) : [];
    const urlParts: string[] = window.location.href.split('/');
    const currentTaxonomy = urlParts[urlParts.length - 1];

    const slugRoot: string | undefined = root.dataset.rootSlug;

    tableOfContents.items = data.map((item: ItemType) => {
      // there should always be slugRoot. Contractual dom agreement
      const slugPath: string[] = [...slugRoot ? [slugRoot] : []];
      const formatItem = (x: ItemType) => {
        const hasChildren = Object.keys(x).includes('children');
        let id;
        if (hasChildren) {
          slugPath.push(x.data.slug);
          id = `/taxonomy/${slugPath.join('/')}`;
        } else {
          id = `/taxonomy/${x.data.slug}`;
        }

        const formatted: ItemType = {
          title: x.data.name,
          id,
          slug: x.data.slug,
          children: []
        };
        if (hasChildren) {
          formatted.children = x.children.map(formatItem);
        }
        return formatted;
      };
      return formatItem(item);
    });

    // replace hashes with proper links
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
        hrefElement.href = hrefElement.href.replace('#', '');
      }
    });

    root.appendChild(tableOfContents);
  }
}

export default TaxonomyTree;

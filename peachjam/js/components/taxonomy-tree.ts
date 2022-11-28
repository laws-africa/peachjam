import { createTocController } from '../utils/function';
import i18next from 'i18next';
import { TOCItemType } from '../utils/types-and-interfaces';

class TaxonomyTree {
  constructor (root: HTMLElement) {
    const tocController = createTocController();
    const jsonElement: HTMLElement | null = document.getElementById('taxonomy_tree');
    const data = jsonElement && jsonElement.textContent ? JSON.parse(jsonElement.textContent as string) : [];
    const urlParts: string[] = window.location.pathname.split('/');
    const currentTaxonomy = urlParts[urlParts.length - 1];

    const slugRoot: string = root.dataset.rootSlug || '';

    tocController.items = data[0].children.map((item: TOCItemType) => {
      const formatItem = (x: TOCItemType, ancestors: string[]) => {
        const newAncestors = [...ancestors, x.data.slug];
        const formatted: TOCItemType = {
          title: x.data.name,
          id: newAncestors.join('/'),
          children: []
        };
        if (Object.keys(x).includes('children')) {
          formatted.children = x.children.map(y => formatItem(y, newAncestors));
        }
        return formatted;
      };
      // data-slug-root should always have a value. Contractual dom agreement.
      return formatItem(item, ['taxonomy', slugRoot]);
    });

    tocController.expandAllBtnText = i18next.t('Expand all');
    tocController.collapseAllBtnText = i18next.t('Collapse all');
    tocController.titleFilterPlaceholder = i18next.t('Search');

    root.appendChild(tocController);

    /*
    * Logic to handle rendering items. Two main things happen here:
    * 1) If la-toc-item's anchor element contains #, remove # so it is a proper link
    * 2) If the currentTaxonomy is the same as the la-toc-item's anchor element taxonomy, then apply an active css class
    * */
    tocController.addEventListener('itemRendered', (e) => {
      const tocItem = e.target as HTMLElement | null;
      if (!tocItem) return;
      const hrefElement = tocItem.querySelector('.content__action__title') as HTMLAnchorElement | null;
      if (!hrefElement) return;
      const taxonomies: string[] = hrefElement.href.split('/');
      if (!taxonomies.length) return;
      const taxonomy = taxonomies[taxonomies.length - 1];
      if (taxonomy === currentTaxonomy) {
        hrefElement.href = 'javascript:void(0)';
        hrefElement.classList.add('active');
      } else if (hrefElement.href.includes('#')) {
        const url = new URL(hrefElement.href);
        hrefElement.href = url.hash.replace('#', '/');
      }
    });
  }
}

export default TaxonomyTree;

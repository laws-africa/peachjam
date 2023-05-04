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

    // data-slug-root should always have a value. Contractual dom agreement.
    const slugRoot: string = root.dataset.rootSlug || '';
    const prefix: string = root.dataset.prefix || 'taxonomy';

    function formatItem (x: TOCItemType): TOCItemType {
      return {
        title: x.data.name,
        url: `/${prefix}/${slugRoot}/${x.data.slug}`,
        children: (x.children || []).map(y => formatItem(y))
      };
    }

    tocController.items = data[0].children.map((item: TOCItemType) => formatItem(item));
    tocController.expandAllBtnText = i18next.t('Expand all');
    tocController.collapseAllBtnText = i18next.t('Collapse all');
    tocController.titleFilterPlaceholder = i18next.t('Search');
    // collapse by default
    tocController.expanded = false;
    root.appendChild(tocController);

    // If the currentTaxonomy is the same as the la-toc-item's anchor element taxonomy, then apply an active css class
    tocController.addEventListener('itemRendered', (e) => {
      const tocItem = e.target as HTMLElement | null;
      if (!tocItem) return;
      const hrefElement = tocItem.querySelector('.content__action__title') as HTMLAnchorElement | null;
      if (!hrefElement) return;
      const taxonomies: string[] = hrefElement.href.split('/');
      if (!taxonomies.length) return;
      const taxonomy = taxonomies[taxonomies.length - 1];
      if (taxonomy === currentTaxonomy) {
        hrefElement.classList.add('active');
      }
    });
  }
}

export default TaxonomyTree;

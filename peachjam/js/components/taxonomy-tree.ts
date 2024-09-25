import { createTocController } from '../utils/function';
import i18next from 'i18next';
import { TOCItemType } from '../utils/types-and-interfaces';

class TaxonomyTree {
  constructor (root: HTMLElement) {
    const tocController = createTocController();
    const jsonElement: HTMLElement | null = document.getElementById('taxonomy_tree');
    const data = jsonElement && jsonElement.textContent ? JSON.parse(jsonElement.textContent as string) : [];
    const urlParts: string[] = window.location.pathname.split('/');
    const currentItem = urlParts[urlParts.length - 1];
    // collapsed by default
    const expanded = false;
    // data-slug-root should always have a value. Contractual dom agreement.
    const slugRoot: string = root.dataset.rootSlug || '';
    const prefix: string = root.dataset.prefix || 'taxonomy';

    function formatItem (x: TOCItemType): TOCItemType {
      const children = (x.children || []).map(y => formatItem(y));
      return {
        title: x.data.name,
        slug: x.data.slug,
        href: `/${prefix}/${slugRoot}/${x.data.slug}`,
        expanded: expanded || x.data.slug === currentItem || children.some(y => y.expanded),
        children
      };
    }

    tocController.expanded = expanded;
    tocController.items = data.length ? data[0].children.map((item: TOCItemType) => formatItem(item)) : [];
    tocController.expandAllBtnText = i18next.t('Expand all');
    tocController.collapseAllBtnText = i18next.t('Collapse all');
    tocController.titleFilterPlaceholder = i18next.t('Search');

    // If the currentItem is the same as the la-toc-item's anchor element taxonomy, then apply an active css class
    tocController.addEventListener('itemRendered', (e) => {
      const tocItem = e.target as HTMLElement | null;
      if (!tocItem) return;
      const hrefElement = tocItem.querySelector('.content__action__title') as HTMLAnchorElement | null;
      if (!hrefElement) return;
      // @ts-ignore
      if (tocItem.item && tocItem.item.slug === currentItem) {
        hrefElement.classList.add('active');
      }
    });

    root.appendChild(tocController);
  }
}

export default TaxonomyTree;

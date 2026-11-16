import peachJam from '../peachjam';
import { htmxAjax } from '../utils/function';

const placeholderSelector = '[data-leading-authority-document-id]';

/**
 * Loads subscription-gated leading-authority fragments for the page (or the
 * provided root element).
 */
export function loadLeadingAuthorities (root: HTMLElement | null = null) {
  root = root || document.documentElement;

  const placeholders = Array.from(root.querySelectorAll(placeholderSelector));
  if (root.matches(placeholderSelector)) {
    placeholders.push(root);
  }

  const listingIds = new Set<string>();
  const detailIds = new Set<string>();

  for (const placeholder of placeholders) {
    const documentId = placeholder.getAttribute('data-leading-authority-document-id');
    if (!documentId) continue;

    if (placeholder.getAttribute('data-leading-authority-layout') === 'detail') {
      detailIds.add(documentId);
    } else {
      listingIds.add(documentId);
    }
  }

  if (!listingIds.size && !detailIds.size) return;

  const searchParams = new URLSearchParams();
  if (listingIds.size) {
    searchParams.set('listing_doc_ids', Array.from(listingIds).join(','));
  }
  if (detailIds.size) {
    searchParams.set('detail_doc_ids', Array.from(detailIds).join(','));
  }

  htmxAjax('get', `${peachJam.config.urlLangPrefix}/leading-authorities/fragments?${searchParams.toString()}`);
}

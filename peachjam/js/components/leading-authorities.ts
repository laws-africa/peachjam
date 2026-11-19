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

    if (placeholder.getAttribute('data-leading-authority-presentation') === 'detail') {
      detailIds.add(documentId);
    } else {
      listingIds.add(documentId);
    }
  }

  loadPresentation('listing', listingIds);
  loadPresentation('detail', detailIds);
}

function loadPresentation (presentation: 'listing' | 'detail', documentIds: Set<string>) {
  if (!documentIds.size) return;

  const searchParams = new URLSearchParams();
  searchParams.set('doc_ids', Array.from(documentIds).join(','));
  htmxAjax(
    'get',
    `${peachJam.config.urlLangPrefix}/leading-authorities/fragments/${presentation}?${searchParams.toString()}`
  );
}

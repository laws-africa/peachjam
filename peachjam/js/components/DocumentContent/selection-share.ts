import { IRangeTarget } from '@lawsafrica/indigo-akn/dist/ranges';
import { GutterEnrichmentManager, IGutterEnrichmentProvider } from '@lawsafrica/indigo-akn/dist/enrichments';
import ShareSelectionModal from './ShareSelectionModal.vue';
import i18next from 'i18next';
import { createAndMountApp } from '../../utils/vue-utils';
import { vueI18n } from '../../i18n';

/**
 * Adds a popup to share the selection provision or text.
 */
export default class SelectionShare implements IGutterEnrichmentProvider {
  protected manager: GutterEnrichmentManager;
  protected documentTitle: string;

  constructor (manager: GutterEnrichmentManager) {
    this.manager = manager;
    this.manager.addProvider(this);
    // @ts-ignore
    this.documentTitle = document.querySelector('.document-content')?.dataset?.title || '';
  }

  getButton (target: IRangeTarget): HTMLButtonElement | null {
    const btn = document.createElement('button');
    btn.className = 'btn btn-outline-secondary';
    btn.type = 'button';
    btn.title = i18next.t('Share');
    btn.innerHTML = '<i class="bi bi-share"></i>';
    return btn;
  }

  addEnrichment (target: IRangeTarget): void {
    if (target.selectors) {
      // get the selected text
      const quoteSelector = target.selectors.find((x) => x.type === 'TextQuoteSelector');
      if (quoteSelector && quoteSelector.exact) {
        const url = new URL(window.location.toString());
        url.hash = target.anchor_id;

        // open the share dialog
        createAndMountApp({
          component: ShareSelectionModal,
          props: {
            url: url.toString(),
            text: `${quoteSelector.exact} - ${this.documentTitle}`
          },
          use: [vueI18n],
          mountTarget: document.createElement('div')
        });
      }
    }
  }
}

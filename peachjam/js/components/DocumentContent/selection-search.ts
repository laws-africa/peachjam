import { IRangeTarget } from '@lawsafrica/indigo-akn/dist/ranges';
import { GutterEnrichmentManager, IGutterEnrichmentProvider } from '@lawsafrica/indigo-akn/dist/enrichments';
import peachJam from '../../peachjam';
import i18next from 'i18next';

/**
 * Adds a popup to search the site based on selected document text.
 */
export default class SelectionSearch implements IGutterEnrichmentProvider {
  protected manager: GutterEnrichmentManager;

  constructor (manager: GutterEnrichmentManager) {
    this.manager = manager;
    this.manager.addProvider(this);
  }

  getButton (target: IRangeTarget): HTMLButtonElement | null {
    const btn = document.createElement('button');
    btn.className = 'btn btn-outline-secondary';
    btn.type = 'button';
    btn.innerText = i18next.t('Search {{appName}}...', { appName: peachJam.config.appName });
    return btn;
  }

  addEnrichment (target: IRangeTarget): void {
    if (target.selectors) {
      // get the selected text
      const quoteSelector = target.selectors.find((x) => x.type === 'TextQuoteSelector');
      if (quoteSelector && quoteSelector.exact) {
        document.location = '/search/?q=' + encodeURIComponent(quoteSelector.exact);
      }
    }
  }
}

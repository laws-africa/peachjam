import { GutterEnrichmentManager, IGutterEnrichmentProvider } from '@lawsafrica/indigo-akn/dist/enrichments';
import { IRangeTarget } from '@lawsafrica/indigo-akn/dist/ranges';
import { createAndMountApp } from '../../utils/vue-utils';
import { vueI18n } from '../../i18n';
import ShareSelectionModal from './ShareSelectionModal.vue';
import i18next from 'i18next';
import peachJam from '../../peachjam';

/**
 * Adds a popup to search the site based on selected document text.
 */
export class SelectionSearch implements IGutterEnrichmentProvider {
  protected manager: GutterEnrichmentManager;

  constructor (manager: GutterEnrichmentManager) {
    this.manager = manager;
    this.manager.addProvider(this);
  }

  getButton (target: IRangeTarget): HTMLButtonElement | null {
    const btn = document.createElement('button');
    btn.className = 'btn btn-outline-secondary';
    btn.type = 'button';
    btn.title = i18next.t('Search');
    btn.innerHTML = '<i class="bi bi-search"></i> ' + btn.title;
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

/**
 * Adds a popup to share the selection provision or text.
 */
export class SelectionShare implements IGutterEnrichmentProvider {
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
    btn.innerHTML = '<i class="bi bi-share"></i> ' + btn.title;
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

abstract class ProvisionEidProvider implements IGutterEnrichmentProvider {
  protected getProvisionEid (target: IRangeTarget): string | null {
    if (!peachJam.config.documentEmbeddings) return null;
    return target.anchor_id || null;
  }

  protected createButton (icon: string, label: string): HTMLButtonElement {
    const btn = document.createElement('button');
    btn.className = 'btn btn-outline-secondary';
    btn.type = 'button';
    btn.title = label;
    btn.innerHTML = `<i class="${icon}"></i> ${label}`;
    return btn;
  }

  abstract getButton(target: IRangeTarget): HTMLButtonElement | null;
  abstract addEnrichment(target: IRangeTarget): void;
}

/**
 * Button to link to the "compare" view for a provision.
 */
export class CompareProvisionProvider extends ProvisionEidProvider {
  protected expressionFrbrUri: string;

  constructor (expressionFrbrUri: string) {
    super();
    this.expressionFrbrUri = expressionFrbrUri;
  }

  getButton (target: IRangeTarget): HTMLButtonElement | null {
    if (!this.expressionFrbrUri || !this.getProvisionEid(target)) return null;
    return this.createButton('bi bi-book', i18next.t('Compare'));
  }

  addEnrichment (target: IRangeTarget): void {
    const provisionEid = this.getProvisionEid(target);
    if (!this.expressionFrbrUri || !provisionEid) return;

    const params = new URLSearchParams({
      'uri-a': `${this.expressionFrbrUri}/~${provisionEid}`
    });
    document.location.href = `${peachJam.config.urlLangPrefix}/compare?${params.toString()}`;
  }
}

/**
 * Button to link to the "similar provisions" view for a provision.
 */
export class SimilarProvisionsProvider extends ProvisionEidProvider {
  protected expressionFrbrUri: string;

  constructor (expressionFrbrUri: string) {
    super();
    this.expressionFrbrUri = expressionFrbrUri;
  }

  getButton (target: IRangeTarget): HTMLButtonElement | null {
    if (!this.getProvisionEid(target)) return null;
    return this.createButton('bi bi-intersect', i18next.t('Find similar'));
  }

  addEnrichment (target: IRangeTarget): void {
    const provisionEid = this.getProvisionEid(target);
    if (!provisionEid) return;

    document.location.href = `${peachJam.config.urlLangPrefix}${this.expressionFrbrUri}/provision/${provisionEid}/similar`;
  }
}

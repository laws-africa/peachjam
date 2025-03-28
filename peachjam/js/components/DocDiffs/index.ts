import ProvisionChangedGutterItem from './ProvisionChangedGutterItem.vue';
import ProvisionDiffInline from './ProvisionDiffInline.vue';
import { createAndMountApp } from '../../utils/vue-utils';
import { vueI18n } from '../../i18n';
import analytics from '../analytics';

class DocDiffsManager {
  private gutter: HTMLElement;
  private inlineDiff: any;
  private serviceUrl: string;
  private readonly frbrExpressionUri: string;

  constructor (frbrExpressionUri: string, gutter: HTMLElement, serviceBaseUrl: string) {
    this.frbrExpressionUri = frbrExpressionUri;
    this.gutter = gutter;
    this.serviceUrl = this.getServiceUrl(serviceBaseUrl);
    this.loadProvisions();
  }

  getServiceUrl (baseUrl: string): string {
    const hostname = window.location.hostname;
    // if localhost use laws.africa otherwise default to domain name of site
    const partner = hostname === 'localhost' || hostname === '127.0.0.1' ? 'laws.africa' : window.location.hostname;
    return `${baseUrl}/v1/p/${partner}`;
  }

  async loadProvisions () {
    const url = `${this.serviceUrl}/e/changed-provisions${this.frbrExpressionUri}`;
    let response = null;
    try {
      response = await fetch(url);
    } catch (e) {
      // don't bubble the exception up
    }

    if (response && response.ok) {
      const { provisions = [] } = await response.json();
      this.decorateChangedProvisions(provisions);
    }
  }

  decorateChangedProvisions (provisions: any[]) {
    provisions.forEach(provision => {
      const item = createAndMountApp({
        component: ProvisionChangedGutterItem,
        props: {
          provision
        },
        use: [vueI18n],
        mountTarget: document.createElement('div')
      });
      this.gutter.appendChild(item.$el);
      item.$el.addEventListener('show-changes', (e: CustomEvent) => this.showProvisionChangesInline(e.detail.provision));
    });
  }

  closeInlineDiff () {
    if (!this.inlineDiff) return;
    this.inlineDiff.close();
  }

  showProvisionChangesInline (provision: any) {
    // Prevents reinitializing the same inlineDiff if it is the same provision
    if (this.inlineDiff && this.inlineDiff.provision.id === provision.id) {
      return;
    }
    if (this.inlineDiff) this.inlineDiff.close();
    this.inlineDiff = createAndMountApp({
      component: ProvisionDiffInline,
      props: {
        documentId: provision.id,
        provision: provision,
        frbrExpressionUri: this.frbrExpressionUri,
        serviceUrl: this.serviceUrl
      },
      use: [vueI18n],
      mountTarget: document.createElement('div')
    });
    this.inlineDiff.$el.addEventListener('close', () => {
      this.inlineDiff = null;
    });
    analytics.trackEvent('Document', 'What changed');
  }
}

export default DocDiffsManager;

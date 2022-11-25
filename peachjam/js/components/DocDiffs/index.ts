import ProvisionChangedGutterItem from './ProvisionChangedGutterItem.vue';
import ProvisionDiffInline from './ProvisionDiffInline.vue';
import { createAndMountApp } from '../../utils/vue-utils';
import { i18n } from '../../i18n';

export const getBaseUrl = () => {
  const hostname = window.location.hostname;
  // if localhost use laws.africa otherwise default to domain name of site
  const partner = hostname === 'localhost' || hostname === '127.0.0.1' ? 'laws.africa' : window.location.hostname;
  return `https://services.lawsafrica.com/v1/p/${partner}`;
};

class DocDiffsManager {
  private gutter: HTMLElement;
  private inlineDiff: any;
  private readonly frbrExpressionUri: string;
  constructor (frbrExpressionUri: string, gutter: HTMLElement) {
    this.frbrExpressionUri = frbrExpressionUri;
    this.gutter = gutter;
    this.loadProvisions();
  }

  async loadProvisions () {
    const url = `${getBaseUrl()}/e/changed-provisions${this.frbrExpressionUri}`;
    const response = await fetch(url);
    if (response.ok) {
      const { provisions = [] } = await response.json();
      this.decorateChangedProvisions(provisions);
    } else {
      throw new Error(response.statusText);
    }
  }

  decorateChangedProvisions (provisions: any[]) {
    provisions.forEach(provision => {
      const item = createAndMountApp({
        component: ProvisionChangedGutterItem,
        props: {
          provision
        },
        use: [i18n],
        mountTarget: document.createElement('div')
      });
      this.gutter.appendChild(item.$el);
      item.$el.addEventListener('show-changes', (e: CustomEvent) => this.showProvisionChangesInline(e.detail.provision));
    });
  }

  showProvisionChangesInline (provision: any) {
    // Prevents reinitializing the same inlineDiff if it is the same provision
    if (this.inlineDiff && this.inlineDiff.provision.id === provision.id) {
      return;
    }
    if (this.inlineDiff) {
      this.inlineDiff.close();
    }
    this.inlineDiff = createAndMountApp({
      component: ProvisionDiffInline,
      props: {
        documentId: provision.id,
        provision: provision,
        frbrExpressionUri: this.frbrExpressionUri
      },
      use: [i18n],
      mountTarget: document.createElement('div')
    });
    this.inlineDiff.$el.addEventListener('close', () => {
      this.inlineDiff = null;
    });
  }
}

export default DocDiffsManager;

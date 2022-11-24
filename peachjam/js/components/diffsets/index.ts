import ProvisionChangedGutterItem from './ProvisionChangedGutterItem.vue';
import ProvisionDiffInline from './ProvisionDiffInline.vue';
import { createAndMountApp } from '../../utils/vue-utils';
import { i18n } from '../../i18n';

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
    const url = `https://services.lawsafrica.com/v1/p/laws.africa/e/changed-provisions${this.frbrExpressionUri}`;
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
  }
}

export default DocDiffsManager;

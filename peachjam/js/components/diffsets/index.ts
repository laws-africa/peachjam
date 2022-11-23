import ProvisionChangedGutterItem from './ProvisionChangedGutterItem.vue';
import ProvisionDiffInline from './ProvisionDiffInline.vue';
import { createAndMountApp } from '../../utils/vue-utils';
import { i18n } from '../../i18n';

class DocDiffsets {
  private akn: HTMLElement;
  private gutter: HTMLElement;
  private inlineDiff: any;
  constructor (akn: HTMLElement, gutter: HTMLElement) {
    this.akn = akn;
    this.gutter = gutter;
    this.loadProvisions();
  }

  async loadProvisions () {
    const frbrExpressionUri = this.akn.getAttribute('expression-frbr-uri');
    if (!frbrExpressionUri) return;
    const url = `https://services.lawsafrica.com/v1/p/laws.africa/e/changed-provisions${frbrExpressionUri}`;
    const response = await fetch(url);
    if (response.ok) {
      const { provisions = [] } = await response.json();
      this.decorateChangedProvisions(provisions);
    } else {
      throw new Error(response.statusText);
    }
  }

  decorateChangedProvisions (provisions: any[]) {
    console.log(provisions);
    provisions.forEach(provision => {
      const element = document.createElement('div');
      const item = createAndMountApp({
        component: ProvisionChangedGutterItem,
        props: {
          provision
        },
        use: [i18n],
        mountTarget: element
      });
      this.gutter.appendChild(item.$el);
      item.$el.addEventListener('show-changes', (e: CustomEvent) => this.showProvisionChangesInline(e.detail.provision));
    });
  }

  showProvisionChangesInline (provision: any) {
    if (this.inlineDiff) {
      this.inlineDiff.close();
    }
    const target = document.createElement('div');
    this.inlineDiff = createAndMountApp({
      component: ProvisionDiffInline,
      props: {
        documentId: provision.id,
        provision: provision
      },
      use: [i18n],
      mountTarget: target
    });

    this.inlineDiff.$mount();
  }
}

export default DocDiffsets;

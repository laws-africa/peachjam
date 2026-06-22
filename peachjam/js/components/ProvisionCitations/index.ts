import { createAndMountApp } from "../../utils/vue-utils";
import ProvisionCitationCount from "./ProvisionCitationCount.vue";
import { vueI18n } from "../../i18n";
import { readJsonScript } from "../../utils/json-script";

interface ProvisionCitation {
  provision_eid: string;
  citations: number;
}

export class ProvisionCitations {
  root: HTMLElement;
  gutter: HTMLElement | null;
  citations: ProvisionCitation[];
  expressionFrbrUri: string;

  constructor (root: HTMLElement) {
    this.root = root;
    this.gutter = root.querySelector('la-gutter');
    this.expressionFrbrUri = root.querySelector('la-akoma-ntoso')?.frbrExpressionUri || '';

    this.citations = readJsonScript<ProvisionCitation[]>('incoming-citations-json', []);

    this.createGutterItems();
  }

  createGutterItems () {
    if (this.gutter && this.citations) {
      for (const info of this.citations) {
        createAndMountApp({
          component: ProvisionCitationCount,
          props: {
            gutter: this.gutter,
            provision_eid: info.provision_eid,
            citations: info.citations,
            expressionFrbrUri: this.expressionFrbrUri
          },
          use: [vueI18n],
          mountTarget: document.createElement('div')
        });
      }
    }
  }
}

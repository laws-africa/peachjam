import components from './components';
import '@lawsafrica/web-components/dist/components/la-akoma-ntoso';
import '@lawsafrica/web-components/dist/components/la-gutter';
import '@lawsafrica/web-components/dist/components/la-gutter-item';
import '@lawsafrica/web-components/dist/components/la-table-of-contents-controller';
import '@lawsafrica/web-components/dist/components/la-decorate-internal-refs';
import '@lawsafrica/web-components/dist/components/la-decorate-terms';
// @ts-ignore
import { i18n } from './i18n';
import { createAndMountApp } from './utils/vue-utils';

class PeachJam {
  private components: any[];
  constructor () {
    this.components = [];
  }

  setup () {
    this.createComponents();
  }

  createComponents () {
    document.querySelectorAll('[data-component]').forEach((el) => {
      const name: string | null = el.getAttribute('data-component');
      if (name && components[name]) {
        // create the component and attached it to the HTML element
        (el as any).component = new components[name](el);
        this.components.push((el as any).component);
      }
    });

    // create vue-based components
    document.querySelectorAll('[data-vue-component]').forEach((el) => {
      const name = el.getAttribute('data-vue-component');
      if (name && components[name]) {
        const vueComp = components[name];
        createAndMountApp({
          component: vueComp,
          use: [i18n],
          mountTarget: el as HTMLElement
        });
        (el as any).component = vueComp;
        this.components.push(vueComp);
      }
    });
  }
}

const peachJam = new PeachJam();
export default peachJam;

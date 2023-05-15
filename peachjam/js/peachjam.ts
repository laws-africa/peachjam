import components from './components';

// @ts-ignore
import { vueI18n } from './i18n';
import { createAndMountApp } from './utils/vue-utils';

import {
  LaAkomaNtoso,
  LaGutter,
  LaGutterItem,
  LaTableOfContentsController,
  LaTableOfContents,
  LaTocItem,
  LaDecorateInternalRefs,
  LaDecorateExternalRefs,
  LaDecorateTerms
} from '@lawsafrica/law-widgets/dist/components';

customElements.define('la-akoma-ntoso', LaAkomaNtoso as any);
customElements.define('la-gutter', LaGutter as any);
customElements.define('la-gutter-item', LaGutterItem as any);
customElements.define('la-decorate-internal-refs', LaDecorateInternalRefs as any);
customElements.define('la-decorate-external-refs', LaDecorateExternalRefs as any);
customElements.define('la-decorate-terms', LaDecorateTerms as any);
customElements.define('la-table-of-contents-controller', LaTableOfContentsController as any);
customElements.define('la-table-of-contents', LaTableOfContents as any);
customElements.define('la-toc-item', LaTocItem as any);

class PeachJam {
  private components: any[];
  constructor () {
    this.components = [];
  }

  setup () {
    this.setupSentry();
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
          // pass in the element's data attributes as props
          props: { ...(el as HTMLElement).dataset },
          use: [vueI18n],
          mountTarget: el as HTMLElement
        });
        (el as any).component = vueComp;
        this.components.push(vueComp);
      }
    });
  }

  private setupSentry () {
    const el = document.getElementById('sentry-config');
    const config = el ? JSON.parse(el.innerHTML) : null;
    // @ts-ignore
    if (config && window.Sentry) {
      // @ts-ignore
      window.Sentry.init({
        dsn: config.dsn,
        environment: config.environment,
        allowUrls: [
          new RegExp(window.location.host.replace('.', '\\.') + '/static/')
        ],
        denyUrls: [
          new RegExp(window.location.host.replace('.', '\\.') + '/static/lib/pdfjs/')
        ]
      });
    }
  }
}

const peachJam = new PeachJam();
export default peachJam;

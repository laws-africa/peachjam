import components from './components';

import {
  LaAkomaNtoso, LaGutter, LaGutterItem, LaTableOfContentsController, LaDecorateInternalRefs, LaDecorateTerms
} from '@lawsafrica/law-widgets-vue';

// @ts-ignore
import { i18n } from './i18n';
import { createAndMountApp } from './utils/vue-utils';
import { defineComponent } from 'vue';

/*
* This will register web components for vanilla or vue usage
* */
defineComponent({
  components: {
    LaAkomaNtoso,
    LaDecorateInternalRefs,
    LaDecorateTerms,
    LaGutter,
    LaGutterItem,
    LaTableOfContentsController
  }
});

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

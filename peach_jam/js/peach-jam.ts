import components from './components';
import { defineComponent, createApp } from 'vue';

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
        const vueComp = defineComponent(components[name]);
        createApp(vueComp).mount(el);
        (el as any).component = vueComp;
        this.components.push(vueComp);
      }
    });
  }
}

const peachJam = new PeachJam();
export default peachJam;

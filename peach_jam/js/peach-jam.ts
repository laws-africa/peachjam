// @ts-ignore
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
        this.components.push(el);
      }
    });

    // create vue-based components
    document.querySelectorAll('[data-vue-component]').forEach((el) => {
      const name = el.getAttribute('data-vue-component');
      if (name && components[name]) {
        const component = defineComponent(components[name]);
        createApp(component).mount(el);
      }
    });
  }
}

const peachJam = new PeachJam();
export default peachJam;

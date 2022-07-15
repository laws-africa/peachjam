import { createApp, defineComponent, Plugin } from 'vue';

/* Util file holding helper functions for vue related operations  */

type CreateAndMountAppType = {
    component: any,
    props?: { [key:string]: any },
    use?: Plugin[],
    mountTarget: HTMLElement
}

export const createAndMountApp = ({
  component,
  props = {},
  use = [],
  mountTarget
} : CreateAndMountAppType) => {
  const definedComponent = defineComponent(component);
  const app = createApp(definedComponent, props);
  use?.forEach(plugin => {
    app.use(plugin);
  });
  app.mount(mountTarget);
  return app;
};

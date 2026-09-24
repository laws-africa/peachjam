import { createAndMountApp } from '../utils/vue-utils';
import SearchBoxWrapper from './FindDocuments/SearchBoxWrapper.vue';
import { vueI18n } from '../i18n';

export default class SearchInput {
  constructor (root: HTMLInputElement) {
    const div = document.createElement('div');
    document.body.append(div);

    // @ts-ignore
    const wrapper = createAndMountApp({
      component: SearchBoxWrapper,
      use: [vueI18n],
      mountTarget: div
    });

    root.addEventListener('click', () => {
      // @ts-ignore
      wrapper.show(root);
    });
  }
}

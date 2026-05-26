import type { App, Plugin } from 'vue';
import i18n from 'i18next';
import I18NextVue from 'i18next-vue';

// Load language data from html, we can't use peachJam.config because it's loaded after this file
const data = document.getElementById('peachjam-config')?.innerText;
let config = {
  language: 'en',
  languages: ['en']
};

if (data) {
  config = JSON.parse(data);
}

const loadJSONFile = (url = '') => {
  try {
    return require(`./locale/${url}`);
  } catch (e) {
    return null;
  }
};

export function setUpI8n () {
  const resources: {
  [key: string] : any
} = {};

  config.languages.forEach(key => {
    resources[key] = {
      translation: loadJSONFile(`${key}/translation.json`)
    };
  });

  i18n.init({
    fallbackLng: 'en',
    lng: config.language,
    resources,
    interpolation: {
      prefix: '{',
      suffix: '}'
    },
    returnEmptyString: false
  });
}

// Setup i8next for js files
setUpI8n();

// Provide a Vue plugin that wires i18next-vue to the shared i18next instance.
export const vueI18n: Plugin = {
  install (app: App) {
    app.use(I18NextVue, { i18next: i18n });
  }
};

import { createI18n } from 'vue-i18n';
import i18n from 'i18next';

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
    resources
  });
};

// Setup Vue i18next for vue files
const setupVueI8n = () => {
  const messages: {
  [key: string] : any
} = {};

  config.languages.forEach(key => {
    messages[key] = loadJSONFile(`${key}/translation.json`);
  });

  const vueOptions = {
    fallbackLocale: 'en',
    locale: config.language,
    messages
  };
  return createI18n(vueOptions);
};

// Setup i8next for js files
setUpI8n();
// Setup Vue i18next for vue files
export const vueI18n = setupVueI8n();

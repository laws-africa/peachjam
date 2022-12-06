import { createI18n } from 'vue-i18n';
import i18n from 'i18next';

const languageSelect: HTMLSelectElement | null = document.getElementById('language') as HTMLSelectElement;
const langs = languageSelect ? Array.from(languageSelect.querySelectorAll('option'))
  .map(option => option.value) : ['en'];
const selectedLang = languageSelect ? languageSelect.options[languageSelect.selectedIndex].value : 'en';

const loadJSONFile = (url = '') => {
  try {
    return require(`./locale/${url}`);
  } catch (e) {
    return null;
  }
};

const setUpI8n = () => {
  const resources: {
  [key: string] : any
} = {};

  langs.forEach(key => {
    resources[key] = {
      translation: loadJSONFile(`${key}/translation.json`)
    };
  });

  i18n.init({
    fallbackLng: 'en',
    lng: selectedLang,
    resources
  });
};

// Setup Vue i18next for vue files
const setupVueI8n = () => {
  const messages: {
  [key: string] : any
} = {};

  langs.forEach(key => {
    messages[key] = loadJSONFile(`${key}/translation.json`);
  });

  const vueOptions = {
    fallbackLocale: 'en',
    locale: selectedLang,
    messages
  };
  return createI18n(vueOptions);
};

// Setup i8next for js files
setUpI8n();
// Setup Vue i18next for vue files
export const vueI18n = setupVueI8n();

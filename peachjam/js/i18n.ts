import { createI18n } from 'vue-i18n';

const languageSelect: HTMLSelectElement | null = document.getElementById('language') as HTMLSelectElement;
const langs = languageSelect ? Array.from(languageSelect.querySelectorAll('option'))
  .map(option => option.value) : [];
const selectedLang = languageSelect ? languageSelect.options[languageSelect.selectedIndex].value : 'en';

const loadJSONFile = (url = '') => {
  try {
    return require(`./locale/${url}`);
  } catch (e) {
    return null;
  }
};

const messages: {
  [key: string] : any
} = {};

langs.forEach(key => {
  messages[key] = loadJSONFile(`${key}/translation.json`);
});

const options = {
  fallbackLocale: 'en',
  locale: selectedLang,
  messages
};
export const i18n = createI18n(options);

import { createI18n } from 'vue-i18n';

const languageSelect = document.getElementById('language');
const langs = languageSelect ? Array.from(languageSelect.querySelectorAll('option'))
  .map(option => option.value) : [];
const selectedLang = languageSelect ? languageSelect.options[languageSelect.selectedIndex].value : 'en';

const loadJSONFile = (url = '') => {
  try {
    return require(`./peachjam/js/locale/${url}`);
  } catch (e) {
    return null;
  }
};

const messages = {};

langs.forEach(key => {
  messages[key] = loadJSONFile(`${key}/translation.json`);
});

const options = {
  fallbackLocale: 'en',
  locale: selectedLang,
  messages
};
export const i18n = createI18n(options);

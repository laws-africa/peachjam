import { defineConfig, type ExtractedKeysMap, type Plugin } from 'i18next-cli';
import { readdir, readFile } from 'node:fs/promises';
import { join } from 'node:path';
import i18nextVuePlugin from 'i18next-cli-vue';

const findVueFiles = async (dir: string): Promise<string[]> => {
  const entries = await readdir(dir, { withFileTypes: true });
  const files: string[] = [];

  for (const entry of entries) {
    const fullPath = join(dir, entry.name);

    if (entry.isDirectory()) {
      files.push(...await findVueFiles(fullPath));
    } else if (entry.isFile() && fullPath.endsWith('.vue')) {
      files.push(fullPath);
    }
  }

  return files;
};

const vueTemplateExtractionPlugin = (): Plugin => ({
  name: 'vue-template-extraction',

  async onEnd (keys: ExtractedKeysMap) {
    const vueFiles = await findVueFiles('peachjam/js');
    const keyPattern = /(?:this\.)?(?:\bi18next\.t|\$t|\bt)\(\s*(['"`])(.*?)\1/g;
    const countPattern = /(?:this\.)?(?:\bi18next\.t|\$t|\bt)\(\s*(['"`])(.*?)\1\s*,\s*\{[^}]*\bcount\s*:/g;
    const countPluralSuffixes = ['_one', '_many', '_other'];
    const pluralSuffixes = ['_zero', '_one', '_two', '_few', '_many', '_other'];

    for (const file of vueFiles) {
      const content = await readFile(file, 'utf8');
      let match;

      while ((match = countPattern.exec(content)) !== null) {
        const key = match[2] || '';
        if (!key.trim()) {
          continue;
        }

        for (const suffix of countPluralSuffixes) {
          const pluralKey = `translation:${key}${suffix}`;
          if (keys.has(pluralKey)) {
            continue;
          }

          keys.set(pluralKey, {
            key: `${key}${suffix}`,
             ns: 'translation'
          });
        }
      }

      while ((match = keyPattern.exec(content)) !== null) {
        const key = match[2] || '';
        if (!key.trim()) {
          continue;
        }

        const uniqueKey = `translation:${key}`;
        const hasPluralVariants = pluralSuffixes.some((suffix) => keys.has(`${uniqueKey}${suffix}`));

        if (hasPluralVariants) {
          continue;
        }

        if (!keys.has(uniqueKey)) {
          keys.set(uniqueKey, {
            key,
            ns: 'translation',
            defaultValue: key
          });
        }
      }
    }
  }
});

export default defineConfig({
  locales: ['en', 'fr', 'sw', 'pt'],
  extract: {
    input: './peachjam/js/**/*.{js,ts,vue}',
    output: './peachjam/js/locale/{{language}}/{{namespace}}.json',
    functions: ['t', '*.t', '$t', '*.$t', 'i18next.t'],
    defaultNS: 'translation',
    contextSeparator: '_',
    pluralSeparator: '_',
    nsSeparator: false,
    keySeparator: false
  },
  plugins: [
    i18nextVuePlugin({ vueVersion: 3 }),
    vueTemplateExtractionPlugin()
  ]
});

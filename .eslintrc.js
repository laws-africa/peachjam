module.exports = {
  env: {
    browser: true,
    es2020: true,
    jquery: true
  },
  root: true,
  plugins: ['@typescript-eslint'],
  parserOptions: {
    ecmaVersion: 11,
    sourceType: 'module',
    parser: require.resolve('@typescript-eslint/parser'),
    extraFileExtensions: ['.vue']
  },
  extends: [
    'eslint:recommended',
    'plugin:@typescript-eslint/eslint-recommended',
    'standard',
    'plugin:vue/vue3-recommended'
  ],
  overrides: [{
    files: ['*.ts', '*.tsx'],
    rules: {
      // The core 'no-unused-vars' rules (in the eslint:recommeded ruleset)
      // does not work with type definitions
      'no-unused-vars': 'off'
    }
  }],
  rules: {
    semi: ['error', 'always']
  }
};

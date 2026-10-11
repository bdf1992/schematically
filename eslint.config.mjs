import globals from 'globals';
import fs from 'node:fs';
const architecture = JSON.parse(fs.readFileSync(new URL('./arch.config.json', import.meta.url), 'utf8'));

// Runtime globals shared by classic browser scripts are supplied by arch_scan's
// scope overlay; no-undef remains enabled rather than ignoring that concern.
const rules = {
  'no-undef': 'error',
  'no-dupe-args': 'error',
  'no-dupe-keys': 'error',
  'no-duplicate-case': 'error',
  'no-unreachable': 'error',
  'no-unsafe-finally': 'error',
  'no-constant-condition': ['error', { checkLoops: false }],
  'valid-typeof': 'error',
  'no-self-assign': 'error',
  'no-async-promise-executor': 'error',
  'constructor-super': 'error',
  'no-this-before-super': 'error',
  'no-unused-vars': ['warn', { args: 'none', caughtErrors: 'none' }],
  complexity: ['warn', 30]
};

export default [
  { files: ['src/*.js'], languageOptions: {
    ecmaVersion: 'latest', sourceType: 'script',
    globals: globals.browser
  }, rules },
  { files: [...architecture.domFreeCores, ...architecture.environmentAdapters], languageOptions: { globals: globals.node } },
  { files: ['mcp/*.mjs'], languageOptions: {
    ecmaVersion: 'latest', sourceType: 'module', globals: globals.node
  }, rules }
];

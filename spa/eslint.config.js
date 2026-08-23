import js from '@eslint/js'
import prettier from 'eslint-config-prettier'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import globals from 'globals'
import testingLibrary from 'eslint-plugin-testing-library'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  { ignores: ['dist', '.omc', 'src/api/generated'] },
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      // strictTypeChecked, not recommendedTypeChecked: these run the compiler,
      // and they are the only rules that can see a floating promise or an
      // `any` leaking through a boundary.
      ...tseslint.configs.strictTypeChecked,
      ...tseslint.configs.stylisticTypeChecked,
      reactHooks.configs.flat['recommended-latest'],
      reactRefresh.configs.vite,
      // Last: it switches off every rule Prettier already decides.
      prettier,
    ],
    languageOptions: {
      globals: globals.browser,
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
    rules: {
      // Nothing may be dropped on the floor. `ignoreVoid: false` means even
      // `void somePromise` is rejected: rejection must be handled, not muted.
      '@typescript-eslint/no-floating-promises': [
        'error',
        { ignoreVoid: false },
      ],
      // An empty catch is the purest form of swallowing.
      'no-empty': ['error', { allowEmptyCatch: false }],
      // Only Errors carry a stack; a thrown string loses the trace.
      '@typescript-eslint/only-throw-error': 'error',
      '@typescript-eslint/prefer-promise-reject-errors': 'error',
      // A new union member must break the build, not fall through silently.
      '@typescript-eslint/switch-exhaustiveness-check': 'error',
      // The assertion that hides a real null.
      '@typescript-eslint/no-non-null-assertion': 'error',
      '@typescript-eslint/consistent-type-imports': 'error',
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
      ],
      'no-console': ['error', { allow: ['warn', 'error'] }],
    },
  },
  {
    files: ['**/*.test.{ts,tsx}', 'vitest.setup.ts'],
    extends: [testingLibrary.configs['flat/react']],
  },
)

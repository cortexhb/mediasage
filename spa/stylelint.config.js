/**
 * Stylelint 15 dropped its formatting rules to Prettier, so what is left in
 * the standard config is correctness: unknown properties, invalid values,
 * malformed selectors, duplicate declarations.
 */

// Kebab-case, optionally with a BEM modifier: `.setup-step--done` is the
// project's convention, not a naming defect.
const BEM_CLASS =
  '^[a-z][a-z0-9]*(?:-[a-z0-9]+)*(?:--[a-z0-9]+(?:-[a-z0-9]+)*)?$'

// Notation and naming preferences only. Silenced on the ported stylesheet
// because fixing them rewrites 3650 lines and destroys the diff against
// `frontend/style.css` that the React port is verified with. Correctness
// rules stay on.
// TODO: Delete this override once the old frontend is gone.
const NOTATIONAL = [
  'alpha-value-notation',
  'color-function-alias-notation',
  'color-function-notation',
  'color-hex-length',
  'comment-empty-line-before',
  'declaration-block-no-redundant-longhand-properties',
  'declaration-block-single-line-max-declarations',
  'keyframes-name-pattern',
  'media-feature-range-notation',
  'no-descending-specificity',
  'property-no-vendor-prefix',
  'rule-empty-line-before',
  'value-keyword-case',
]

export default {
  extends: ['stylelint-config-standard'],
  ignoreFiles: ['dist/**', 'node_modules/**', '.omc/**'],
  rules: {
    'selector-class-pattern': [
      BEM_CLASS,
      { message: 'Expected kebab-case, optionally with a BEM --modifier' },
    ],
  },
  overrides: [
    {
      files: ['src/style.css'],
      rules: Object.fromEntries(NOTATIONAL.map((rule) => [rule, null])),
    },
  ],
}

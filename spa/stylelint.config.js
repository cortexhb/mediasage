/**
 * Stylelint 15 dropped its formatting rules to Prettier, so what is left in
 * the standard config is correctness: unknown properties, invalid values,
 * malformed selectors, duplicate declarations.
 */

// camelCase block, optional `__element`, optional `--modifier`. camelCase
// because CSS Module classes are read as JavaScript properties, so
// `styles.trackRow__title` resolves where a kebab-case name needs brackets.
// Mixins and Sass variables are not read from JavaScript, so kebab stays.
const BEM_CLASS =
  '^[a-z][a-zA-Z0-9]*(?:__[a-z][a-zA-Z0-9]*)?(?:--[a-z][a-zA-Z0-9]*)?$'

export default {
  // The `-scss` config supplies the SCSS parser and swaps the rules that
  // cannot see through `@use`, `@mixin`, or interpolation.
  extends: ['stylelint-config-standard-scss'],
  ignoreFiles: ['dist/**', 'node_modules/**', '.omc/**'],
  rules: {
    'selector-class-pattern': [
      BEM_CLASS,
      {
        message:
          'Expected a camelCase block with an optional __element and --modifier',
      },
    ],
  },
}

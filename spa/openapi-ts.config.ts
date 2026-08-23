import { defineConfig } from '@hey-api/openapi-ts'

/**
 * Generates the API boundary from FastAPI's schema.
 *
 * `input` is the running dev server: the schema is derived from the route
 * models, so there is no checked-in copy to drift. Output is committed, so a
 * backend field rename shows up as a compile error in review.
 */
export default defineConfig({
  input: `${process.env.MEDIASAGE_API_URL ?? 'http://localhost:5765'}/openapi.json`,
  output: {
    path: 'src/api/generated',
    // Formatted so the committed diff is reviewable, but not linted: ESLint
    // ignores this directory, and `strictTypeChecked` on generated code would
    // only ever report defects nobody here can fix.
    postProcess: ['prettier'],
  },
  // No runtime: the client is ours, and hey-api's fails
  // `exactOptionalPropertyTypes`.
  plugins: ['@hey-api/typescript'],
})

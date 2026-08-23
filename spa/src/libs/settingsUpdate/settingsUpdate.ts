/**
 * The submitted settings form, as a partial configuration update.
 *
 * Pure, so the rules are testable without a form: what is left out, what is
 * coerced to a number, and which field fills two.
 */
import type { ConfigUpdateWritable } from '../../api/generated/types.gen.ts'

/** The fields the API types as a boolean; a form carries only strings. */
const BOOLEAN = new Set(['smart_generation'])

/** The fields the API types as a number rather than a string. */
const NUMERIC = new Set([
  'context_window',
  'cost_analysis_input',
  'cost_analysis_output',
  'cost_generation_input',
  'cost_generation_output',
])

/**
 * An empty field is left out entirely.
 *
 * The backend treats a present key as a change, so an untouched credential
 * field has to disappear rather than blank the stored one. A number that is
 * present is kept even at zero: `ConfigUpdate.changes()` filters on presence,
 * not truthiness, so a zero cost survives.
 */
export function settingsUpdate(form: FormData): ConfigUpdateWritable {
  const update: Record<string, string | number | boolean> = {}

  for (const [name, value] of form.entries()) {
    if (typeof value !== 'string') continue
    const trimmed = value.trim()
    if (trimmed === '') continue
    if (BOOLEAN.has(name)) {
      update[name] = trimmed === 'true'
      continue
    }
    update[name] = NUMERIC.has(name) ? Number(trimmed) : trimmed
  }

  // A custom server exposes one model, which fills both roles.
  const model = update.model_analysis
  if (update.llm_provider === 'custom' && model !== undefined) {
    update.model_generation = model
  }

  return update
}

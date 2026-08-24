/**
 * The submitted settings form, as a partial configuration update.
 *
 * Every field is named `section.field`, and that name is the whole mapping:
 * `ConfigUpdate` is shaped like `MediasageConfig`, so a name says which patch
 * its value belongs in. What each one coerces to comes from the API's schema
 * by way of `libs/patchFields`, so no table of field names here can fall out
 * of step with the backend.
 *
 * Pure, so the rules are testable without a form: what is left out, what is
 * coerced, and which field fills two.
 */
import type { ConfigUpdateWritable } from '../../api/generated/types.gen.ts'
import type { PatchKind } from '../patchFields/patchFields.ts'

/** One section's changes, before the API's type is claimed for them. */
type Patch = Record<string, unknown>

/** One value in the type its field declares; a list keeps its items as text. */
function coerced(value: string, kind: PatchKind | undefined): unknown {
  if (kind === 'boolean') return value === 'true'
  if (kind === 'number') return Number(value)
  if (kind === 'list') {
    return value
      .split(',')
      .map((item) => item.trim())
      .filter((item) => item !== '')
  }
  return value
}

/**
 * An empty field is left out entirely.
 *
 * The backend treats a present key as a change, so an untouched credential
 * field has to disappear rather than blank the stored one. A number that is
 * present is kept even at zero: `ConfigUpdate.changes()` filters on presence,
 * not truthiness, so a zero cost survives.
 */
export function settingsUpdate(
  form: FormData,
  kinds: ReadonlyMap<string, PatchKind>,
): ConfigUpdateWritable {
  const update: Record<string, Patch> = {}

  for (const [name, value] of form.entries()) {
    if (typeof value !== 'string') continue
    const trimmed = value.trim()
    if (trimmed === '') continue

    const [section, field] = name.split('.')
    // An unqualified name names no section to put it in.
    if (section === undefined || field === undefined) continue

    const patch = (update[section] ??= {})
    patch[field] = coerced(trimmed, kinds.get(name))
  }

  // A custom server exposes one model, which fills both roles.
  const llm = update.llm
  if (llm?.provider === 'custom' && llm.model_analysis !== undefined) {
    llm.model_generation = llm.model_analysis
  }

  return update
}

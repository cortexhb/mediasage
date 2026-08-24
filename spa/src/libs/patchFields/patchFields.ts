/**
 * The settings form, read out of the API's own schema.
 *
 * `MediasageConfig` has ten sections and 74 editable fields, and `CLAUDE.md`
 * says which settings exist lives in `backend/config/models.py` and is not
 * restated. So the form is not written by hand: every `*Patch` model in
 * `/openapi.json` carries its fields' types, bounds and descriptions, which is
 * everything an input needs. A setting added to a section appears here with no
 * change to the SPA.
 *
 * Pure, so the mapping from a JSON Schema property to an input is testable
 * without a network or a form.
 */

/** Which control a field gets, and how its value is coerced back. */
export type PatchKind = 'text' | 'password' | 'number' | 'boolean' | 'list'

export interface PatchField {
  readonly section: string
  readonly field: string
  /** `section.field` — the input's name, and how `settingsUpdate` groups it. */
  readonly name: string
  readonly label: string
  readonly kind: PatchKind
  readonly hint?: string | undefined
  readonly min?: number | undefined
  readonly max?: number | undefined
  /** `any` where the value is a float, so a browser accepts decimals. */
  readonly step?: number | 'any' | undefined
}

/** One `anyOf` member, as FastAPI writes an optional field. */
interface Member {
  readonly type?: string
  readonly format?: string
  readonly minimum?: number
  readonly maximum?: number
  readonly exclusiveMinimum?: number
  readonly exclusiveMaximum?: number
}

interface Property {
  readonly anyOf?: readonly Member[]
  readonly title?: string
  readonly description?: string
  readonly type?: string
  readonly format?: string
}

interface Schema {
  readonly properties?: Record<string, Property>
}

/** `LLMPatch` writes `llm`; the suffix is how a model names its section. */
const SUFFIX = 'Patch'

/** Section names as `ConfigUpdate` spells them, keyed by schema name. */
const SECTIONS: Record<string, string> = { LLM: 'llm', Langfuse: 'langfuse' }

export const PatchFields = {
  /**
   * Every editable field in every section, in the order the models declare.
   *
   * Takes `components.schemas` whole: which of them are patches is decided by
   * the name, so a section added to `ConfigUpdate` needs no entry here.
   */
  of(schemas: Record<string, Schema>): PatchField[] {
    const found: PatchField[] = []
    for (const [name, schema] of Object.entries(schemas)) {
      if (!name.endsWith(SUFFIX)) continue
      const section = PatchFields.sectionOf(name)
      for (const [field, property] of Object.entries(schema.properties ?? {})) {
        found.push(PatchFields.one(section, field, property))
      }
    }
    return found
  },

  /** `BudgetPatch` is `budget`; the two acronyms are spelt out in `SECTIONS`. */
  sectionOf(name: string): string {
    const stem = name.slice(0, -SUFFIX.length)
    return SECTIONS[stem] ?? stem.toLowerCase()
  },

  one(section: string, field: string, property: Property): PatchField {
    // The null member is what makes it optional.
    const member =
      property.anyOf?.find((one) => one.type !== 'null') ?? property
    const kind = PatchFields.kindOf(member)

    return {
      section,
      field,
      name: `${section}.${field}`,
      label: property.title ?? field,
      kind,
      hint: property.description,
      ...(kind === 'number' ? PatchFields.bounds(member) : {}),
    }
  },

  kindOf(member: Member): PatchKind {
    if (member.type === 'boolean') return 'boolean'
    if (member.type === 'array') return 'list'
    if (member.type === 'integer' || member.type === 'number') return 'number'
    return member.format === 'password' ? 'password' : 'text'
  },

  /**
   * The bounds an input can enforce, from the ones the schema declares.
   *
   * An exclusive bound is only representable on an integer, where the next
   * whole number is the real limit. On a float it is dropped and the server
   * refuses the value instead — a wrong `min` would refuse a legal one.
   */
  bounds(member: Member): Pick<PatchField, 'min' | 'max' | 'step'> {
    const whole = member.type === 'integer'
    const min =
      member.minimum ??
      (whole && member.exclusiveMinimum !== undefined
        ? member.exclusiveMinimum + 1
        : undefined)
    const max =
      member.maximum ??
      (whole && member.exclusiveMaximum !== undefined
        ? member.exclusiveMaximum - 1
        : undefined)

    return { min, max, step: whole ? 1 : 'any' }
  },

  /** What each name coerces to, which is all `settingsUpdate` needs. */
  kinds(fields: readonly PatchField[]): ReadonlyMap<string, PatchKind> {
    return new Map(fields.map((one) => [one.name, one.kind]))
  },
}

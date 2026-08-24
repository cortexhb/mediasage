import { describe, expect, it } from 'vitest'

import { PatchFields } from './patchFields.ts'

/** One optional field, shaped as FastAPI writes it into the schema. */
function optional(member: Record<string, unknown>, extra = {}) {
  return { anyOf: [member, { type: 'null' }], ...extra }
}

const SCHEMAS = {
  BudgetPatch: {
    properties: {
      tokens_per_track: optional(
        { type: 'integer', exclusiveMinimum: 0 },
        { title: 'Tokens Per Track', description: 'Measured average.' },
      ),
      context_buffer_fraction: optional(
        { type: 'number', minimum: 0, exclusiveMaximum: 1 },
        { title: 'Context Buffer Fraction' },
      ),
    },
  },
  LLMPatch: {
    properties: {
      api_key: optional(
        { type: 'string', format: 'password' },
        { title: 'Api Key' },
      ),
      smart_generation: optional(
        { type: 'boolean' },
        { title: 'Smart Generation' },
      ),
      max_retries: optional(
        { type: 'integer', minimum: 1, maximum: 10 },
        { title: 'Max Retries' },
      ),
    },
  },
  LibraryPatch: {
    properties: {
      live_keywords: optional(
        { type: 'array', items: { type: 'string' } },
        { title: 'Live Keywords' },
      ),
    },
  },
  // Not a patch: proves the sweep goes by suffix, not by presence.
  Track: { properties: { title: { type: 'string' } } },
}

/** One field out of the fixture, by the name a form would give it. */
function field(name: string) {
  return PatchFields.of(SCHEMAS).find((one) => one.name === name)
}

describe('PatchFields.of', () => {
  it('reads only the patch models, so other schemas are not settings', () => {
    const sections = new Set(PatchFields.of(SCHEMAS).map((one) => one.section))

    expect(sections).toEqual(new Set(['budget', 'llm', 'library']))
  })

  it('names each field the way the form submits it', () => {
    expect(field('budget.tokens_per_track')).toMatchObject({
      section: 'budget',
      field: 'tokens_per_track',
      label: 'Tokens Per Track',
    })
  })

  it('carries the description across as the hint', () => {
    expect(field('budget.tokens_per_track')?.hint).toBe('Measured average.')
  })

  it('leaves the hint absent where the schema declares none', () => {
    expect(field('budget.context_buffer_fraction')?.hint).toBeUndefined()
  })
})

describe('PatchFields.sectionOf', () => {
  it.each([
    ['BudgetPatch', 'budget'],
    ['LibraryPatch', 'library'],
    // Lowercasing alone would answer `llmpatch` and `langfusepatch`.
    ['LLMPatch', 'llm'],
    ['LangfusePatch', 'langfuse'],
  ])('reads %s as the %s section', (name, section) => {
    expect(PatchFields.sectionOf(name)).toBe(section)
  })
})

describe('the control a field gets', () => {
  it.each([
    ['budget.tokens_per_track', 'number'],
    ['llm.api_key', 'password'],
    ['llm.smart_generation', 'boolean'],
    ['library.live_keywords', 'list'],
  ])('draws %s as a %s', (name, kind) => {
    expect(field(name)?.kind).toBe(kind)
  })
})

describe('the bounds an input enforces', () => {
  it('keeps an inclusive bound as it stands', () => {
    expect(field('llm.max_retries')).toMatchObject({ min: 1, max: 10, step: 1 })
  })

  it('turns an exclusive bound on a whole number into the next one', () => {
    // `gt=0` on an integer means 1 is the smallest legal value.
    expect(field('budget.tokens_per_track')?.min).toBe(1)
  })

  it('drops an exclusive bound on a float, which no input can express', () => {
    // `lt=1.0` is not `max=0`; a wrong max would refuse a legal 0.5.
    expect(field('budget.context_buffer_fraction')?.max).toBeUndefined()
  })

  it('lets a float take decimals', () => {
    expect(field('budget.context_buffer_fraction')?.step).toBe('any')
  })

  it('leaves a field that is not a number without bounds', () => {
    expect(field('llm.api_key')?.step).toBeUndefined()
  })
})

describe('PatchFields.kinds', () => {
  it('maps every name to what it coerces to, for `settingsUpdate`', () => {
    const kinds = PatchFields.kinds(PatchFields.of(SCHEMAS))

    expect(kinds.get('llm.smart_generation')).toBe('boolean')
    expect(kinds.get('budget.tokens_per_track')).toBe('number')
  })
})

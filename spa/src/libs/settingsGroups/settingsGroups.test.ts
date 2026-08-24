import { describe, expect, it } from 'vitest'

import { SETTINGS_GROUPS, groupBySlug } from './settingsGroups.ts'

describe('SETTINGS_GROUPS', () => {
  it('gives every group its own slug, since the slug is the route', () => {
    const slugs = SETTINGS_GROUPS.map((group) => group.slug)

    expect(new Set(slugs).size).toBe(slugs.length)
  })

  it('claims each section once, so no field is drawn on two pages', () => {
    const sections = SETTINGS_GROUPS.flatMap((group) => group.sections)

    expect(new Set(sections).size).toBe(sections.length)
  })

  it('skips only fields of sections the group itself draws', () => {
    // A `bespoke` name outside them would silently hide nothing.
    for (const group of SETTINGS_GROUPS) {
      for (const name of group.bespoke) {
        expect(group.sections).toContain(name.split('.')[0])
      }
    }
  })

  it('qualifies every bespoke name, which is how the form addresses one', () => {
    for (const group of SETTINGS_GROUPS) {
      for (const name of group.bespoke) {
        expect(name).toMatch(/^\w+\.\w+$/)
      }
    }
  })
})

describe('groupBySlug', () => {
  it('finds the group a path names', () => {
    expect(groupBySlug('ai')?.title).toBe('AI Provider')
  })

  it('answers nothing for a slug that is not one of ours', () => {
    expect(groupBySlug('nonesuch')).toBeUndefined()
  })

  it('answers nothing when the path carries no slug at all', () => {
    expect(groupBySlug(undefined)).toBeUndefined()
  })
})

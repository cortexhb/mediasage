import { beforeEach, describe, expect, it } from 'vitest'

import { keepFamiliarity, readFamiliarity } from './familiarityPref.ts'

describe('the familiarity preference', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('is `any` until one has been chosen', () => {
    expect(readFamiliarity()).toBe('any')
  })

  it('reads back what was kept', () => {
    keepFamiliarity('hidden_gems')

    expect(readFamiliarity()).toBe('hidden_gems')
  })

  it('keeps the key `frontend/app.js:4791` reads', () => {
    keepFamiliarity('comfort')

    expect(localStorage.getItem('mediasage-familiarity-pref')).toBe('comfort')
  })

  it('falls back to `any` for a value it does not know', () => {
    localStorage.setItem('mediasage-familiarity-pref', 'whatever')

    expect(readFamiliarity()).toBe('any')
  })
})

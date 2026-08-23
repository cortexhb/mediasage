import { describe, expect, it } from 'vitest'

import { tracksThatFit } from './tracksThatFit.ts'

describe('tracksThatFit', () => {
  it.each([
    [32768, 569],
    [40960, 717],
    [128000, 2284],
    [200000, 3580],
  ])('fits %i tokens of context to %i tracks', (window, tracks) => {
    expect(tracksThatFit(window)).toBe(tracks)
  })

  it('reports the legacy figure for a 32k window', () => {
    // `frontend/app.js:1903` hardcodes "(~556 tracks)" as its fallback.
    expect(tracksThatFit(32000)).toBe(556)
  })

  it('floors at a hundred rather than reporting a negative count', () => {
    // Below ~1111 tokens the instructions alone exceed the window.
    expect(tracksThatFit(512)).toBe(100)
    expect(tracksThatFit(0)).toBe(100)
  })

  it('rounds down, so the count never overstates what fits', () => {
    expect(tracksThatFit(2000)).toBe(100)
    expect(tracksThatFit(10000)).toBe(160)
  })
})

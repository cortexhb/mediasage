import { describe, expect, it } from 'vitest'

import { albumFrame } from './albumFrames.ts'

describe('albumFrame', () => {
  it('keeps the three frames this stream declares', () => {
    expect(
      albumFrame({ event: 'progress', data: { step: 'writing' } }),
    ).toEqual({ event: 'progress', data: { step: 'writing' } })
    expect(
      albumFrame({ event: 'result', data: { recommendations: [] } }),
    ).toBeDefined()
    expect(
      albumFrame({ event: 'error', data: { message: 'no' } }),
    ).toBeDefined()
  })

  it('skips a frame this build does not know', () => {
    // `complete` is the playlist stream's terminator, not this one's.
    expect(albumFrame({ event: 'complete', data: {} })).toBeUndefined()
  })

  it('skips a payload that is not an object', () => {
    expect(albumFrame({ event: 'result', data: 'nope' })).toBeUndefined()
    expect(albumFrame({ event: 'result', data: null })).toBeUndefined()
  })
})

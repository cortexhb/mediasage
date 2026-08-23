import { describe, expect, it } from 'vitest'

import { syncProgress } from './syncProgress.ts'

describe('syncProgress', () => {
  it('reports nothing measurable before a phase is set', () => {
    expect(syncProgress(null)).toEqual({ percent: null, text: 'Syncing…' })
  })

  it.each([
    ['fetching_albums', 'Reading albums from Plex: 40 / 200 albums'],
    ['fetching_genres', 'Enriching albums with genres: 40 / 200 genres'],
    ['fetching', 'Reading tracks from Plex: 40 / 200 tracks'],
    ['processing', 'Saving tracks: 40 / 200 tracks'],
  ] as const)('measures %s and names its unit', (phase, text) => {
    expect(syncProgress({ phase, current: 40, total: 200 })).toEqual({
      percent: 20,
      text,
    })
  })

  it('groups thousands, since a library runs to five figures', () => {
    expect(
      syncProgress({ phase: 'processing', current: 1250, total: 80058 }).text,
    ).toBe('Saving tracks: 1,250 / 80,058 tracks')
  })

  it.each([
    ['fetching_albums', 'Reading albums from Plex…'],
    ['processing', 'Saving tracks…'],
  ] as const)('says what %s is doing when it has no total', (phase, text) => {
    // Indeterminate, not zero: a zero bar reads as a stalled sync.
    expect(syncProgress({ phase, current: 0, total: 0 })).toEqual({
      percent: null,
      text,
    })
  })

  it('treats missing counts as no total rather than failing', () => {
    expect(syncProgress({ phase: 'processing' })).toEqual({
      percent: null,
      text: 'Saving tracks…',
    })
  })
})

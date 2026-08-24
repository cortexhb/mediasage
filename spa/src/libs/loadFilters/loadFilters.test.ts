import { http, HttpResponse } from 'msw'
import { beforeEach, describe, expect, it } from 'vitest'

import { server } from '@test'
import type { PlaylistFlow } from '../flowStore/flowStore.ts'
import {
  forgetPlaylistFlow,
  writePlaylistFlow,
} from '../flowStore/flowStore.ts'
import type { FiltersData } from './loadFilters.ts'
import { loadFilters } from './loadFilters.ts'

const ANALYSIS = {
  suggested_genres: ['Jazz'],
  suggested_decades: ['1960s'],
  available_genres: [
    { name: 'Jazz', count: 400 },
    { name: 'Rock', count: 900 },
  ],
  available_decades: [
    { name: '1960s', count: 100 },
    { name: '1970s', count: 200 },
  ],
  reasoning: '',
}

const PROMPT: PlaylistFlow = {
  mode: 'prompt',
  id: 'f-1',
  prompt: 'moody jazz',
  questions: [],
  analysis: ANALYSIS,
}

const SEED: PlaylistFlow = {
  mode: 'seed',
  id: 'f-2',
  track: {
    rating_key: '99',
    title: 'Fake Plastic Trees',
    artist: 'Radiohead',
    album: 'The Bends',
    duration_ms: 290_000,
  },
  dimensions: [],
}

/** The loader as the router calls it, with the mode from the path. */
function asked(mode: string): {
  params: { mode: string }
  request: Request
} {
  return {
    params: { mode },
    request: new Request(`http://localhost/playlist/${mode}/filters`),
  }
}

/** A configuration read, so the ceiling is not the fallback. */
function configured(ceiling = 3000): void {
  server.use(
    http.get('/api/config', () =>
      HttpResponse.json({ max_tracks_to_ai: ceiling }),
    ),
  )
}

/** What Plex reports, holding one genre and one decade. */
function stocked(): void {
  server.use(
    http.get('/api/library/stats', () =>
      HttpResponse.json({
        total_tracks: 5000,
        genres: [{ name: 'Shoegaze', count: 12 }],
        decades: [{ name: '1990s', count: 30 }],
      }),
    ),
  )
}

describe('loadFilters', () => {
  beforeEach(forgetPlaylistFlow)

  it('sends a deep link with no record behind it back to step one', async () => {
    const answer = await loadFilters(asked('prompt'))

    expect((answer as Response).headers.get('Location')).toBe(
      '/playlist/prompt',
    )
  })

  it('sends a seed flow reached under the prompt path to its own start', async () => {
    writePlaylistFlow(SEED)

    const answer = await loadFilters(asked('prompt'))

    expect((answer as Response).headers.get('Location')).toBe('/playlist/seed')
  })

  describe('a prompt flow', () => {
    it('draws the lists the analysis bought', async () => {
      configured()
      writePlaylistFlow(PROMPT)

      const data = (await loadFilters(asked('prompt'))) as FiltersData

      expect(data.mode).toBe('prompt')
      expect(data.availableGenres).toEqual(ANALYSIS.available_genres)
      expect(data.suggestedGenres).toEqual(['Jazz'])
      expect(data.ceiling).toBe(3000)
    })

    it('sends one with no analysis back to the refine step', async () => {
      writePlaylistFlow({ ...PROMPT, analysis: undefined })

      const answer = await loadFilters(asked('prompt'))

      expect((answer as Response).headers.get('Location')).toBe(
        '/playlist/prompt/refine',
      )
    })
  })

  describe('a seed flow', () => {
    it('starts with everything selected, as `app.js:3046` did', async () => {
      configured()
      stocked()
      writePlaylistFlow(SEED)

      const data = (await loadFilters(asked('seed'))) as FiltersData

      expect(data.mode).toBe('seed')
      expect(data.availableGenres).toEqual([{ name: 'Shoegaze', count: 12 }])
      expect(data.suggestedGenres).toEqual(['Shoegaze'])
      expect(data.suggestedDecades).toEqual(['1990s'])
    })

    it('reads Plex, never the cache, so both flows offer one list', async () => {
      configured()
      let cache_asked = false
      server.use(
        http.get('/api/library/stats/cached', () => {
          cache_asked = true
          return HttpResponse.json({
            total_tracks: 0,
            genres: [{ name: 'Normalised', count: 1 }],
            decades: [],
          })
        }),
      )
      stocked()
      writePlaylistFlow(SEED)

      const data = (await loadFilters(asked('seed'))) as FiltersData

      expect(cache_asked).toBe(false)
      expect(data.suggestedGenres).toEqual(['Shoegaze'])
    })

    it('keeps the step usable when the configuration cannot be read', async () => {
      stocked()
      server.use(
        http.get('/api/config', () =>
          HttpResponse.json({ detail: 'no' }, { status: 500 }),
        ),
      )
      writePlaylistFlow(SEED)

      const data = (await loadFilters(asked('seed'))) as FiltersData

      expect(data.ceiling).toBe(3500)
    })
  })
})

import { http, HttpResponse } from 'msw'
import { beforeEach, describe, expect, it } from 'vitest'

import { server } from '@test'
import type { AlbumFlow } from '../albumStore/albumStore.ts'
import { forgetAlbumFlow, writeAlbumFlow } from '../albumStore/albumStore.ts'
import { loadAlbumRefine } from '../loadAlbumRefine/loadAlbumRefine.ts'
import { loadAlbumResults } from '../loadAlbumResults/loadAlbumResults.ts'
import type { AlbumFiltersData } from './loadAlbumFilters.ts'
import { loadAlbumFilters } from './loadAlbumFilters.ts'

const ANSWERED: AlbumFlow = {
  id: 'f-1',
  sessionId: 's-1',
  prompt: 'rainy Sunday',
  questions: [],
  answers: [],
  answerTexts: [],
  mode: 'library',
  familiarity: 'comfort',
}

/** The loader as the router calls it. */
function asked(): { request: Request } {
  return { request: new Request('http://localhost/recommend/filters') }
}

/** What Plex reports, holding two genres and one decade. */
function stocked(): void {
  server.use(
    http.get('/api/library/stats', () =>
      HttpResponse.json({
        total_tracks: 5000,
        genres: [
          { name: 'Jazz', count: 400 },
          { name: 'Rock', count: 900 },
        ],
        decades: [{ name: '1970s', count: 30 }],
      }),
    ),
  )
}

/** A configuration read, so the ceiling is not the fallback. */
function configured(ceiling = 35_000): void {
  server.use(
    http.get('/api/config', () =>
      HttpResponse.json({ max_albums_to_ai: ceiling }),
    ),
  )
}

describe('loadAlbumFilters', () => {
  beforeEach(forgetAlbumFlow)

  it('sends a deep link with no record behind it back to step one', async () => {
    const answer = await loadAlbumFilters(asked())

    expect((answer as Response).headers.get('Location')).toBe('/recommend')
  })

  it('sends a flow whose questions are unanswered back to the refine step', async () => {
    writeAlbumFlow({ ...ANSWERED, answers: undefined })

    const answer = await loadAlbumFilters(asked())

    expect((answer as Response).headers.get('Location')).toBe(
      '/recommend/refine',
    )
  })

  it('starts from the suggestion the prompt earned, and says so', async () => {
    stocked()
    configured()
    writeAlbumFlow({
      ...ANSWERED,
      suggested: { genres: ['Jazz'], decades: [], reasoning: '' },
    })

    const data = (await loadAlbumFilters(asked())) as AlbumFiltersData

    expect(data.selectedGenres).toEqual(['Jazz'])
    expect(data.selectedDecades).toEqual([])
    expect(data.fromPrompt).toBe(true)
    expect(data.familiarity).toBe('comfort')
  })

  it('starts from everything where the analysis never landed', async () => {
    stocked()
    configured()
    writeAlbumFlow(ANSWERED)

    const data = (await loadAlbumFilters(asked())) as AlbumFiltersData

    expect(data.selectedGenres).toEqual(['Jazz', 'Rock'])
    expect(data.selectedDecades).toEqual(['1970s'])
    expect(data.fromPrompt).toBe(false)
  })

  it('reads Plex, not the cache, so it offers what the analysis saw', async () => {
    let cacheAsked = false
    server.use(
      http.get('/api/library/stats/cached', () => {
        cacheAsked = true
        return HttpResponse.json({ total_tracks: 0, genres: [], decades: [] })
      }),
    )
    stocked()
    configured()
    writeAlbumFlow(ANSWERED)

    await loadAlbumFilters(asked())

    expect(cacheAsked).toBe(false)
  })

  it('keeps the step usable when the configuration cannot be read', async () => {
    stocked()
    server.use(
      http.get('/api/config', () =>
        HttpResponse.json({ detail: 'no' }, { status: 500 }),
      ),
    )
    writeAlbumFlow(ANSWERED)

    const data = (await loadAlbumFilters(asked())) as AlbumFiltersData

    expect(data.ceiling).toBe(2500)
  })
})

describe('loadAlbumRefine', () => {
  beforeEach(forgetAlbumFlow)

  it('answers the record it was given', () => {
    writeAlbumFlow(ANSWERED)

    expect(loadAlbumRefine()).toEqual(ANSWERED)
  })

  it('sends a deep link with nothing behind it back to step one', () => {
    expect((loadAlbumRefine() as Response).headers.get('Location')).toBe(
      '/recommend',
    )
  })
})

describe('loadAlbumResults', () => {
  beforeEach(forgetAlbumFlow)

  it('sends a flow with no filters back to the step that chooses them', () => {
    writeAlbumFlow(ANSWERED)

    expect((loadAlbumResults() as Response).headers.get('Location')).toBe(
      '/recommend/filters',
    )
  })

  it('answers a flow that has been through the filters step', () => {
    const ready = {
      ...ANSWERED,
      filters: { genres: [], decades: [], max_albums: 2500 },
    }
    writeAlbumFlow(ready)

    expect(loadAlbumResults()).toEqual(ready)
  })
})

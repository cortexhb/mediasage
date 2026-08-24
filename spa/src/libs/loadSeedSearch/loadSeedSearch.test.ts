import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { server } from '@test'
import { loadSeedSearch } from './loadSeedSearch.ts'

const TRACK = {
  rating_key: '99',
  title: 'Fake Plastic Trees',
  artist: 'Radiohead',
  album: 'The Bends',
  duration_ms: 290_000,
}

/** The loader as the router calls it, with the query in the URL. */
function asked(url: string): { request: Request } {
  return { request: new Request(`http://localhost${url}`) }
}

describe('loadSeedSearch', () => {
  it('answers the tracks Plex found', async () => {
    server.use(
      http.get('/api/library/search', () => HttpResponse.json([TRACK])),
    )

    const found = await loadSeedSearch(asked('/playlist/seed?q=radiohead'))

    expect(found.tracks).toEqual([TRACK])
    expect(found.query).toBe('radiohead')
  })

  it('asks for nothing without a query', async () => {
    let asked_for = false
    server.use(
      http.get('/api/library/search', () => {
        asked_for = true
        return HttpResponse.json([])
      }),
    )

    const found = await loadSeedSearch(asked('/playlist/seed'))

    expect(asked_for).toBe(false)
    expect(found.tracks).toEqual([])
  })

  it('sends the query as typed, so Plex sees the whole phrase', async () => {
    let sent: string | null = null
    server.use(
      http.get('/api/library/search', ({ request }) => {
        sent = new URL(request.url).searchParams.get('q')
        return HttpResponse.json([])
      }),
    )

    await loadSeedSearch(asked('/playlist/seed?q=r.e.m.%20%26%20friends'))

    expect(sent).toBe('r.e.m. & friends')
  })

  it('keeps the step usable when the search failed', async () => {
    server.use(
      http.get('/api/library/search', () =>
        HttpResponse.json({ detail: 'Not connected' }, { status: 502 }),
      ),
    )

    const found = await loadSeedSearch(asked('/playlist/seed?q=jazz'))

    expect(found.error).toBeTruthy()
    expect(found.query).toBe('jazz')
  })
})

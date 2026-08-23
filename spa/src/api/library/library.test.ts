import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { server } from '@test'
import { ApiError } from '../request/request.ts'
import {
  readCachedLibraryStats,
  readLibraryStats,
  readLibraryStatus,
} from './library.ts'

/** A signal no test aborts, for the cases that are not about cancellation. */
function live(): AbortSignal {
  return new AbortController().signal
}

describe('readCachedLibraryStats', () => {
  it('answers the breakdowns the cache holds', async () => {
    server.use(
      http.get('/api/library/stats/cached', () =>
        HttpResponse.json({
          total_tracks: 0,
          genres: [{ name: 'Rock', count: 900 }],
          decades: [],
        }),
      ),
    )

    const stats = await readCachedLibraryStats(live())

    expect(stats.genres).toEqual([{ name: 'Rock', count: 900 }])
  })

  it('reads the cache, never the live endpoint', async () => {
    let live_asked = false
    server.use(
      http.get('/api/library/stats', () => {
        live_asked = true
        return HttpResponse.json({ total_tracks: 1, genres: [], decades: [] })
      }),
      http.get('/api/library/stats/cached', () =>
        HttpResponse.json({ total_tracks: 0, genres: [], decades: [] }),
      ),
    )

    await readCachedLibraryStats(live())

    expect(live_asked).toBe(false)
  })
})

describe('readLibraryStats', () => {
  it('answers what Plex reported', async () => {
    server.use(
      http.get('/api/library/stats', () =>
        HttpResponse.json({ total_tracks: 80038, genres: [], decades: [] }),
      ),
    )

    expect((await readLibraryStats(live())).total_tracks).toBe(80038)
  })

  it('raises a disconnected server rather than reporting an empty library', async () => {
    server.use(
      http.get('/api/library/stats', () =>
        HttpResponse.json({ detail: 'Not connected' }, { status: 502 }),
      ),
    )

    await expect(readLibraryStats(live())).rejects.toBeInstanceOf(ApiError)
  })
})

describe('readLibraryStatus', () => {
  it('answers what the last sync recorded', async () => {
    server.use(
      http.get('/api/library/status', () =>
        HttpResponse.json({
          track_count: 52341,
          synced_at: '2026-08-01T00:00:00Z',
          is_syncing: false,
          plex_connected: true,
        }),
      ),
    )

    expect((await readLibraryStatus(live())).track_count).toBe(52341)
  })
})

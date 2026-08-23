import { http, HttpResponse } from 'msw'
import type { LoaderFunctionArgs } from 'react-router'
import { describe, expect, it } from 'vitest'

import { server } from '@test'
import { loadStats } from './loadStats.ts'

/** The breakdowns, which the cached endpoint reports with no total. */
const STATS = {
  total_tracks: 0,
  genres: [{ name: 'Rock', count: 900 }],
  decades: [{ name: '1980s', count: 620 }],
}

/** What the cache knows about the last sync. */
const STATUS = {
  track_count: 52341,
  synced_at: '2026-08-01T00:00:00Z',
  is_syncing: false,
  plex_connected: true,
}

/** The loader's argument, which only ever reads `request`. */
function args(connected = true): LoaderFunctionArgs {
  const request = new Request(
    `http://localhost/settings/stats?connected=${String(connected)}`,
  )
  return {
    request,
    url: new URL(request.url),
    pattern: '/settings/stats',
    params: {},
    context: undefined as never,
  }
}

/** Answer both cache reads with a synced library. */
function cache() {
  server.use(
    http.get('/api/library/stats/cached', () => HttpResponse.json(STATS)),
    http.get('/api/library/status', () => HttpResponse.json(STATUS)),
  )
}

describe('loadStats', () => {
  it('takes the total from the sync, which the breakdowns omit', async () => {
    cache()

    const stats = await loadStats(args())

    expect(stats?.total_tracks).toBe(52341)
    expect(stats?.genres).toEqual([{ name: 'Rock', count: 900 }])
  })

  it('never asks Plex once a sync has run, which costs seconds', async () => {
    let asked = false
    cache()
    server.use(
      http.get('/api/library/stats', () => {
        asked = true
        return HttpResponse.json(STATS)
      }),
    )

    await loadStats(args())

    expect(asked).toBe(false)
  })

  it('falls back to Plex when no sync has run, since nothing else knows', async () => {
    cache()
    server.use(
      http.get('/api/library/status', () =>
        HttpResponse.json({ ...STATUS, track_count: 0, synced_at: null }),
      ),
      http.get('/api/library/stats', () =>
        HttpResponse.json({ ...STATS, total_tracks: 80038 }),
      ),
    )

    expect((await loadStats(args()))?.total_tracks).toBe(80038)
  })

  it('asks nothing of a server that is not connected', async () => {
    let asked = false
    cache()
    server.use(
      http.get('/api/library/status', () =>
        HttpResponse.json({ ...STATUS, track_count: 0, synced_at: null }),
      ),
      http.get('/api/library/stats', () => {
        asked = true
        return HttpResponse.json(STATS)
      }),
    )

    expect(await loadStats(args(false))).toBeNull()
    expect(asked).toBe(false)
  })

  it('answers nothing rather than faulting when the read fails', async () => {
    server.use(
      http.get('/api/library/stats/cached', () =>
        HttpResponse.json({ detail: 'Cache unreadable' }, { status: 503 }),
      ),
      http.get('/api/library/status', () => HttpResponse.json(STATUS)),
    )

    expect(await loadStats(args())).toBeNull()
  })
})

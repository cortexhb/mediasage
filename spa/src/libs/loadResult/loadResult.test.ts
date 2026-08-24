import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { server } from '@test'
import { loadResult } from './loadResult.ts'

/**
 * The loader's argument, as the router hands it over.
 *
 * Takes the whole `params`, not an id: a default parameter would swallow the
 * one case worth testing, since `args(undefined)` falls back to the default.
 */
function args(
  params: Record<string, string | undefined> = { resultId: 'r-1' },
) {
  return {
    request: new Request('http://localhost/result/r-1'),
    params,
    context: undefined as never,
  }
}

const SAVED = {
  id: 'r-1',
  title: 'Rainy Sunday',
  prompt: 'rain',
  track_count: 1,
  created_at: '2026-08-01T10:00:00Z',
  type: 'prompt_playlist',
  snapshot: { tracks: [], token_count: 1, estimated_cost: 0 },
}

describe('loadResult', () => {
  it('answers the saved result with its snapshot', async () => {
    server.use(http.get('/api/results/r-1', () => HttpResponse.json(SAVED)))

    expect(await loadResult(args())).toMatchObject({
      id: 'r-1',
      type: 'prompt_playlist',
    })
  })

  it('says a deleted result is gone rather than crashing', async () => {
    server.use(
      http.get('/api/results/r-1', () =>
        HttpResponse.json({ detail: 'Result not found' }, { status: 404 }),
      ),
    )

    await expect(loadResult(args())).rejects.toThrow(
      'This result is no longer available.',
    )
  })

  it('says the same of a snapshot too old to draw', async () => {
    server.use(
      http.get('/api/results/r-1', () =>
        HttpResponse.json(
          { detail: 'saved by an earlier version' },
          { status: 422 },
        ),
      ),
    )

    await expect(loadResult(args())).rejects.toThrow(
      'This result is no longer available.',
    )
  })

  it('lets a server failure say what it was, rather than calling it missing', async () => {
    server.use(
      http.get('/api/results/r-1', () =>
        HttpResponse.json(
          { detail: 'the database is on fire' },
          { status: 500 },
        ),
      ),
    )

    await expect(loadResult(args())).rejects.toThrow('the database is on fire')
  })

  it('refuses a route with no id rather than asking for one', async () => {
    await expect(loadResult(args({}))).rejects.toThrow(
      'This result is no longer available.',
    )
  })
})

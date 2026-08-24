import { http, HttpResponse } from 'msw'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { server } from '@test'
import { forgetRound } from '../albumRun/albumRun.ts'
import type { AlbumFlow } from '../albumStore/albumStore.ts'
import {
  forgetAlbumFlow,
  readAlbumFlow,
  writeAlbumFlow,
} from '../albumStore/albumStore.ts'
import type { AlbumResultAction } from './actOnRecommendation.ts'
import { actOnRecommendation } from './actOnRecommendation.ts'

const READY: AlbumFlow = {
  id: 'f-1',
  sessionId: 's-1',
  prompt: 'rainy Sunday',
  questions: [],
  answers: [],
  answerTexts: [],
  mode: 'library',
  familiarity: 'any',
  filters: { genres: [], decades: [], max_albums: 2500 },
}

/** The action as the router calls it. */
function acting(fields: Record<string, string[]>): { request: Request } {
  const form = new FormData()
  for (const [name, values] of Object.entries(fields))
    for (const value of values) form.append(name, value)
  return {
    request: new Request('http://localhost/recommend/results', {
      method: 'POST',
      body: form,
    }),
  }
}

/** The generate stream and the configuration the deadline is read from. */
function generating(): () => number {
  let asked = 0
  server.use(
    http.get('/api/config', () => HttpResponse.json({})),
    http.post('/api/recommend/generate', () => {
      asked += 1
      return new HttpResponse(
        'event: result\ndata: {"recommendations":[]}\n\n',
        { headers: { 'Content-Type': 'text/event-stream' } },
      )
    }),
  )
  return () => asked
}

describe('actOnRecommendation', () => {
  beforeEach(forgetAlbumFlow)
  afterEach(forgetRound)

  describe('save', () => {
    it('names the playlist as `frontend/app.js:5022` names it', async () => {
      let sent: unknown
      server.use(
        http.post('/api/playlist', async ({ request }) => {
          sent = await request.json()
          return HttpResponse.json({ success: true, tracks_added: 9 })
        }),
      )
      writeAlbumFlow(READY)

      const answer = (await actOnRecommendation(
        acting({
          intent: ['save'],
          album: ['Pink Moon'],
          artist: ['Nick Drake'],
          pitch: ['the whole pitch'],
          rating_keys: ['1', '2'],
        }),
      )) as AlbumResultAction

      expect(answer.saved).toBe('Saved "Pink Moon" to playlist')
      expect(sent).toMatchObject({
        name: 'Recommended: Pink Moon - Nick Drake',
        rating_keys: ['1', '2'],
        description: 'the whole pitch',
      })
    })

    it('refuses an album with no tracks in the library', async () => {
      writeAlbumFlow(READY)

      const answer = (await actOnRecommendation(
        acting({ intent: ['save'], album: ['X'], artist: ['Y'] }),
      )) as AlbumResultAction

      expect(answer.error).toBe('That album has no tracks in your library')
    })

    it('reports what the backend refused with', async () => {
      server.use(
        http.post('/api/playlist', () =>
          HttpResponse.json({ success: false, error: 'Plex is down' }),
        ),
      )
      writeAlbumFlow(READY)

      const answer = (await actOnRecommendation(
        acting({
          intent: ['save'],
          album: ['X'],
          artist: ['Y'],
          rating_keys: ['1'],
        }),
      )) as AlbumResultAction

      expect(answer.error).toBe('Plex is down')
    })
  })

  describe('again', () => {
    it('starts another round on the same session', async () => {
      const asked = generating()
      writeAlbumFlow(READY)

      const answer = await actOnRecommendation(acting({ intent: ['again'] }))

      expect((answer as Response).headers.get('Location')).toBe(
        '/recommend/results',
      )
      await new Promise((resolve) => setTimeout(resolve, 0))
      expect(asked()).toBe(1)
    })
  })

  describe('discovery', () => {
    it('takes the new session id and generates from it', async () => {
      let sent: unknown
      const asked = generating()
      server.use(
        http.post('/api/recommend/switch-mode', async ({ request }) => {
          sent = await request.json()
          return HttpResponse.json({ session_id: 's-2' })
        }),
      )
      writeAlbumFlow(READY)

      await actOnRecommendation(acting({ intent: ['discovery'] }))

      expect(sent).toEqual({ session_id: 's-1', mode: 'discovery' })
      const flow = readAlbumFlow()
      expect(flow?.sessionId).toBe('s-2')
      expect(flow?.mode).toBe('discovery')
      await new Promise((resolve) => setTimeout(resolve, 0))
      expect(asked()).toBe(1)
    })

    it('reports an expired session rather than generating on it', async () => {
      server.use(
        http.post('/api/recommend/switch-mode', () =>
          HttpResponse.json(
            { detail: 'Session not found or expired' },
            { status: 404 },
          ),
        ),
      )
      writeAlbumFlow(READY)

      const answer = (await actOnRecommendation(
        acting({ intent: ['discovery'] }),
      )) as AlbumResultAction

      expect(answer.error).toBe('Session not found or expired')
      expect(readAlbumFlow()?.mode).toBe('library')
    })
  })

  it('sends a deep link with no record behind it back to step one', async () => {
    const answer = await actOnRecommendation(acting({ intent: ['again'] }))

    expect((answer as Response).headers.get('Location')).toBe('/recommend')
  })
})

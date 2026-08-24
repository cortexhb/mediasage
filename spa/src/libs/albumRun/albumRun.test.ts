import { http, HttpResponse } from 'msw'
import { afterEach, describe, expect, it } from 'vitest'

import { server } from '@test'
import type { RecommendGenerateRequest } from '../../api/generated/types.gen.ts'
import { forgetAlbumFlow, writeAlbumFlow } from '../albumStore/albumStore.ts'
import { forgetRound, readRound, startRound, watchRound } from './albumRun.ts'

const BODY: RecommendGenerateRequest = {
  session_id: 's-1',
  answers: [],
  answer_texts: [],
  mode: 'library',
  genres: [],
  decades: [],
  familiarity_pref: 'any',
  max_albums: 2500,
}

/** A finished stream, as the backend frames one. */
function finished(album: string): string {
  const result = {
    recommendations: [{ rank: 'primary', album, artist: 'Nick Drake' }],
    token_count: 12,
    estimated_cost: 0,
    result_id: 'r-1',
  }
  return [
    'event: progress\ndata: {"step":"writing","message":"..."}\n\n',
    `event: result\ndata: ${JSON.stringify(result)}\n\n`,
  ].join('')
}

/** Serve one round, counting how many times it was asked for. */
function serving(...bodies: string[]): () => number {
  let asked = 0
  server.use(
    http.post('/api/recommend/generate', () => {
      const body = bodies[Math.min(asked, bodies.length - 1)] ?? ''
      asked += 1
      return new HttpResponse(body, {
        headers: { 'Content-Type': 'text/event-stream' },
      })
    }),
  )
  return () => asked
}

/** Resolve once the round stops, so an assertion is not racing the stream. */
function settled(): Promise<void> {
  return new Promise((resolve) => {
    const stop = watchRound(() => {
      if (readRound().running) return
      stop()
      resolve()
    })
  })
}

describe('startRound', () => {
  afterEach(() => {
    forgetRound()
    forgetAlbumFlow()
  })

  it('ends on `result`, which is this stream and not the playlist one', async () => {
    serving(finished('Pink Moon'))
    const done = settled()

    startRound(BODY, 1000)
    await done

    expect(readRound().result?.recommendations[0]?.album).toBe('Pink Moon')
    expect(readRound().stage).toBe(6)
  })

  it('keeps the round in the record, so a reload redraws it', async () => {
    writeAlbumFlow({
      id: 'f-1',
      sessionId: 's-1',
      prompt: 'rainy',
      questions: [],
      mode: 'library',
      familiarity: 'any',
    })
    serving(finished('Pink Moon'))
    const done = settled()

    startRound(BODY, 1000)
    await done

    expect(readRound().result?.result_id).toBe('r-1')
  })

  it('generates again when the same session asks twice', async () => {
    const asked = serving(finished('First'), finished('Second'))

    const first = settled()
    startRound(BODY, 1000)
    await first

    const second = settled()
    startRound(BODY, 1000)
    await second

    expect(asked()).toBe(2)
    expect(readRound().result?.recommendations[0]?.album).toBe('Second')
  })

  it('reports a round that came back with nothing in it', async () => {
    serving('event: result\ndata: {"recommendations":[]}\n\n')
    const done = settled()

    startRound(BODY, 1000)
    await done

    expect(readRound().failure).toBe(
      'No recommendations were received. Please try again.',
    )
  })

  it('reports an error frame in the words the backend sent', async () => {
    serving(
      'event: error\ndata: {"message":"Session not found or expired"}\n\n',
    )
    const done = settled()

    startRound(BODY, 1000)
    await done

    expect(readRound().failure).toBe('Session not found or expired')
  })

  it('reports an expired session, which is a status before any frame', async () => {
    server.use(
      http.post('/api/recommend/generate', () =>
        HttpResponse.json(
          { detail: 'Session not found or expired' },
          { status: 404 },
        ),
      ),
    )
    const done = settled()

    startRound(BODY, 1000)
    await done

    expect(readRound().failure).toBe('Session not found or expired')
  })

  it('says so when the stream ended before the round did', async () => {
    serving('event: progress\ndata: {"step":"writing"}\n\n')
    const done = settled()

    startRound(BODY, 1000)
    await done

    expect(readRound().failure).toBe(
      'The stream ended before the recommendation did.',
    )
  })
})

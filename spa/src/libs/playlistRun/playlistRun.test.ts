import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { server } from '@test'
import type { GenerateRequest } from '../../api/generated/types.gen.ts'
import { forgetPlaylistFlow } from '../flowStore/flowStore.ts'
import { forgetRun, readRun, startRun, watchRun } from './playlistRun.ts'

const BODY: GenerateRequest = {
  prompt: 'moody jazz',
  genres: [],
  decades: [],
  track_count: 25,
  exclude_live: true,
  min_rating: 0,
  max_tracks_to_ai: 500,
}

/** A finished stream, as the backend frames one. */
function finished(title: string): string {
  return [
    'event: progress\ndata: {"step":"matching","message":"..."}\n\n',
    `event: narrative\ndata: {"playlist_title":${JSON.stringify(title)},"narrative":"n","track_reasons":{},"user_request":"x"}\n\n`,
    'event: complete\ndata: {"track_count":0,"token_count":1,"estimated_cost":0,"playlist_title":"","narrative":"","track_reasons":{},"result_id":"r"}\n\n',
  ].join('')
}

/** Serve one generation, counting how many times it was asked for. */
function serving(...bodies: string[]): () => number {
  let asked = 0
  server.use(
    http.post('/api/generate/stream', () => {
      const body = bodies[Math.min(asked, bodies.length - 1)] ?? ''
      asked += 1
      return new HttpResponse(body, {
        headers: { 'Content-Type': 'text/event-stream' },
      })
    }),
  )
  return () => asked
}

/** Resolve once the run stops, so an assertion is not racing the stream. */
function settled(): Promise<void> {
  return new Promise((resolve) => {
    const stop = watchRun(() => {
      if (readRun().running) return
      stop()
      resolve()
    })
  })
}

describe('startRun', () => {
  it('generates and publishes what came back', async () => {
    serving(finished('Rainstorm Reverie'))
    const done = settled()

    startRun(BODY, 1000)
    await done

    expect(readRun().title).toBe('Rainstorm Reverie')
    forgetRun()
    forgetPlaylistFlow()
  })

  it('generates again when the same filters are submitted twice', async () => {
    // Keying a run on its request body made a repeat a no-op.
    const asked = serving(finished('First'), finished('Second'))

    const first = settled()
    startRun(BODY, 1000)
    await first

    const second = settled()
    startRun(BODY, 1000)
    await second

    expect(asked()).toBe(2)
    expect(readRun().title).toBe('Second')
    forgetRun()
    forgetPlaylistFlow()
  })
})

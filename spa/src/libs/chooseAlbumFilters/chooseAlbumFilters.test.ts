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
import { chooseAlbumFilters } from './chooseAlbumFilters.ts'

const ANSWERED: AlbumFlow = {
  id: 'f-1',
  sessionId: 's-1',
  prompt: 'rainy Sunday',
  questions: [],
  answers: [],
  answerTexts: [],
  mode: 'library',
  familiarity: 'any',
}

/** The action as the router calls it, with the form the step submits. */
function submitting(fields: Record<string, string[]>): { request: Request } {
  const form = new FormData()
  for (const [name, values] of Object.entries(fields))
    for (const value of values) form.append(name, value)
  return {
    request: new Request('http://localhost/recommend/filters', {
      method: 'POST',
      body: form,
    }),
  }
}

/** The generate stream and the configuration the deadline is read from. */
function serving(): () => unknown {
  let sent: unknown
  server.use(
    http.get('/api/config', () => HttpResponse.json({})),
    http.post('/api/recommend/generate', async ({ request }) => {
      sent = await request.json()
      return new HttpResponse(
        'event: result\ndata: {"recommendations":[]}\n\n',
        {
          headers: { 'Content-Type': 'text/event-stream' },
        },
      )
    }),
  )
  return () => sent
}

const CHOSEN = {
  genres: ['Jazz'],
  decades: ['1970s'],
  genre_total: ['2'],
  decade_total: ['2'],
  max_albums: ['5000'],
  mode: ['discovery'],
  familiarity: ['rediscover'],
}

describe('chooseAlbumFilters', () => {
  beforeEach(() => {
    forgetAlbumFlow()
    localStorage.clear()
  })
  afterEach(forgetRound)

  it('keeps what was chosen and moves on to the results', async () => {
    serving()
    writeAlbumFlow(ANSWERED)

    const answer = await chooseAlbumFilters(submitting(CHOSEN))

    expect(answer.headers.get('Location')).toBe('/recommend/results')
    const flow = readAlbumFlow()
    expect(flow?.filters).toEqual({
      genres: ['Jazz'],
      decades: ['1970s'],
      max_albums: 5000,
    })
    expect(flow?.mode).toBe('discovery')
  })

  it('sends nothing where everything was selected', async () => {
    const sent = serving()
    writeAlbumFlow(ANSWERED)

    await chooseAlbumFilters(
      submitting({ ...CHOSEN, genre_total: ['1'], decade_total: ['1'] }),
    )

    expect(readAlbumFlow()?.filters?.genres).toEqual([])
    // The stream is started, not awaited, by the action.
    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(sent()).toMatchObject({ genres: [], decades: [] })
  })

  it('remembers the play-history preference across flows', async () => {
    serving()
    writeAlbumFlow(ANSWERED)

    await chooseAlbumFilters(submitting(CHOSEN))

    expect(localStorage.getItem('mediasage-familiarity-pref')).toBe(
      'rediscover',
    )
  })

  it('drops the round a previous selection produced', async () => {
    serving()
    writeAlbumFlow({
      ...ANSWERED,
      result: { recommendations: [], result_id: 'r-1' },
    })

    await chooseAlbumFilters(submitting(CHOSEN))

    expect(readAlbumFlow()?.result).toBeUndefined()
  })

  it('sends a deep link with no record behind it back to step one', async () => {
    const answer = await chooseAlbumFilters(submitting(CHOSEN))

    expect(answer.headers.get('Location')).toBe('/recommend')
  })
})

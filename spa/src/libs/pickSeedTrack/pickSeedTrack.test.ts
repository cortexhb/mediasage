import { http, HttpResponse } from 'msw'
import { beforeEach, describe, expect, it } from 'vitest'

import { server } from '@test'
import { forgetPlaylistFlow, readPlaylistFlow } from '../flowStore/flowStore.ts'
import { pickSeedTrack } from './pickSeedTrack.ts'

const TRACK = {
  rating_key: '99',
  title: 'Fake Plastic Trees',
  artist: 'Radiohead',
  album: 'The Bends',
  duration_ms: 290_000,
}

const DIMENSIONS = [
  { id: 'mood', label: 'Mood', description: 'How it feels' },
  { id: 'era', label: 'Era', description: 'When it is from' },
]

/** The action as the router calls it, with the picked key in the body. */
function picking(ratingKey: string): { request: Request } {
  const form = new FormData()
  form.set('rating_key', ratingKey)
  return {
    request: new Request('http://localhost/playlist/seed', {
      method: 'POST',
      body: form,
    }),
  }
}

/** One analysis, capturing what was asked of it. */
function analysing(): () => { rating_key: string; flow_id: string } | null {
  let sent: { rating_key: string; flow_id: string } | null = null
  server.use(
    http.post('/api/analyze/track', async ({ request }) => {
      sent = (await request.json()) as { rating_key: string; flow_id: string }
      return HttpResponse.json({ track: TRACK, dimensions: DIMENSIONS })
    }),
  )
  return () => sent
}

describe('pickSeedTrack', () => {
  beforeEach(forgetPlaylistFlow)

  it('starts a seed flow from what the analysis answered', async () => {
    analysing()

    const answer = await pickSeedTrack(picking('99'))

    expect(answer).toBeInstanceOf(Response)
    const flow = readPlaylistFlow()
    expect(flow?.mode).toBe('seed')
    expect(flow?.mode === 'seed' && flow.track).toEqual(TRACK)
    expect(flow?.mode === 'seed' && flow.dimensions).toEqual(DIMENSIONS)
  })

  it('goes on to the dimensions step', async () => {
    analysing()

    const answer = await pickSeedTrack(picking('99'))

    expect((answer as Response).headers.get('Location')).toBe(
      '/playlist/seed/dimensions',
    )
  })

  it('mints a flow id and traces the analysis under it', async () => {
    const sent = analysing()

    await pickSeedTrack(picking('99'))

    expect(sent()?.flow_id).toMatch(/^[0-9a-f]{32}$/)
    expect(sent()?.flow_id).toBe(readPlaylistFlow()?.id)
  })

  it('reports a failed analysis rather than starting a flow', async () => {
    server.use(
      http.post('/api/analyze/track', () =>
        HttpResponse.json({ detail: 'Track not found' }, { status: 404 }),
      ),
    )

    const answer = await pickSeedTrack(picking('missing'))

    expect(answer).not.toBeInstanceOf(Response)
    expect(readPlaylistFlow()).toBeUndefined()
  })

  it('spends nothing when no track was picked', async () => {
    let asked = false
    server.use(
      http.post('/api/analyze/track', () => {
        asked = true
        return HttpResponse.json({ track: TRACK, dimensions: [] })
      }),
    )

    const answer = await pickSeedTrack(picking(''))

    expect(asked).toBe(false)
    expect(answer).not.toBeInstanceOf(Response)
  })
})

import { beforeEach, describe, expect, it } from 'vitest'

import type { SeedFlow } from '../flowStore/flowStore.ts'
import {
  forgetPlaylistFlow,
  readPlaylistFlow,
  writePlaylistFlow,
} from '../flowStore/flowStore.ts'
import { chooseDimensions } from './chooseDimensions.ts'
import { loadDimensions } from '../loadDimensions/loadDimensions.ts'

const SEED: SeedFlow = {
  mode: 'seed',
  id: 'f-1',
  track: {
    rating_key: '99',
    title: 'Fake Plastic Trees',
    artist: 'Radiohead',
    album: 'The Bends',
    duration_ms: 290_000,
  },
  dimensions: [
    { id: 'mood', label: 'Mood', description: 'How it feels' },
    { id: 'era', label: 'Era', description: 'When it is from' },
  ],
}

/** The action as the router calls it, with the chosen ids and the notes. */
function choosing(ids: string[], notes = ''): { request: Request } {
  const form = new FormData()
  for (const id of ids) form.append('dimensions', id)
  form.set('notes', notes)
  return {
    request: new Request('http://localhost/playlist/seed/dimensions', {
      method: 'POST',
      body: form,
    }),
  }
}

describe('chooseDimensions', () => {
  beforeEach(forgetPlaylistFlow)

  it('keeps what was chosen and moves on to the filters', async () => {
    writePlaylistFlow(SEED)

    const answer = await chooseDimensions(choosing(['mood'], ' loud please '))

    expect((answer as Response).headers.get('Location')).toBe(
      '/playlist/seed/filters',
    )
    const flow = readPlaylistFlow()
    expect(flow?.mode === 'seed' && flow.selectedDimensions).toEqual(['mood'])
    expect(flow?.mode === 'seed' && flow.notes).toBe('loud please')
  })

  it('refuses an empty selection rather than generating from none', async () => {
    writePlaylistFlow(SEED)

    const answer = await chooseDimensions(choosing([]))

    expect(answer).not.toBeInstanceOf(Response)
    const flow = readPlaylistFlow()
    expect(flow?.mode === 'seed' && flow.selectedDimensions).toBeUndefined()
  })

  it('sends a flow that is not a seed back to step one', async () => {
    const answer = await chooseDimensions(choosing(['mood']))

    expect((answer as Response).headers.get('Location')).toBe('/playlist/seed')
  })
})

describe('loadDimensions', () => {
  beforeEach(forgetPlaylistFlow)

  it('answers the seed record it was given', () => {
    writePlaylistFlow(SEED)

    expect(loadDimensions()).toEqual(SEED)
  })

  it('sends a deep link with nothing behind it back to step one', () => {
    const answer = loadDimensions()

    expect((answer as Response).headers.get('Location')).toBe('/playlist/seed')
  })

  it('sends a prompt flow to its own step two', () => {
    writePlaylistFlow({
      mode: 'prompt',
      id: 'f-2',
      prompt: 'moody jazz',
      questions: [],
    })

    expect((loadDimensions() as Response).headers.get('Location')).toBe(
      '/playlist/seed',
    )
  })
})

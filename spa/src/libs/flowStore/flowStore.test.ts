import { describe, expect, it } from 'vitest'

import type { PlaylistFlow } from './flowStore.ts'
import {
  forgetPlaylistFlow,
  readPlaylistFlow,
  writePlaylistFlow,
} from './flowStore.ts'

const FLOW: PlaylistFlow = {
  mode: 'prompt',
  id: 'f-1',
  prompt: 'moody jazz',
  questions: [],
}

const SEED: PlaylistFlow = {
  mode: 'seed',
  id: 'f-2',
  track: {
    rating_key: '99',
    title: 'Fake Plastic Trees',
    artist: 'Radiohead',
    album: 'The Bends',
    duration_ms: 290_000,
  },
  dimensions: [{ id: 'mood', label: 'Mood', description: 'How it feels' }],
}

describe('the flow record', () => {
  it('reads back what was written', () => {
    writePlaylistFlow(FLOW)

    expect(readPlaylistFlow()).toEqual(FLOW)
  })

  it('answers nothing once forgotten', () => {
    writePlaylistFlow(FLOW)
    forgetPlaylistFlow()

    expect(readPlaylistFlow()).toBeUndefined()
  })

  it('discards a record written under an older version', () => {
    sessionStorage.setItem(
      'mediasage.flow.playlist',
      JSON.stringify({ version: 0, flow: FLOW }),
    )

    expect(readPlaylistFlow()).toBeUndefined()
  })

  it('discards a body that will not parse', () => {
    sessionStorage.setItem('mediasage.flow.playlist', 'not json')

    expect(readPlaylistFlow()).toBeUndefined()
  })

  it('reads a seed record back with its track and dimensions', () => {
    writePlaylistFlow(SEED)

    expect(readPlaylistFlow()).toEqual(SEED)
  })

  it('holds one flow, so starting a seed abandons a prompt', () => {
    writePlaylistFlow(FLOW)
    writePlaylistFlow(SEED)

    expect(readPlaylistFlow()?.mode).toBe('seed')
  })
})

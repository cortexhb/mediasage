import { describe, expect, it } from 'vitest'

import type { PlaylistFlow } from '../flowStore/flowStore.ts'
import { playlistName } from './playlistName.ts'

const ON = new Date('2026-08-24T12:00:00')

const PROMPT: PlaylistFlow = {
  mode: 'prompt',
  id: 'f-1',
  prompt: 'moody jazz for a rainy evening',
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
  dimensions: [],
}

describe('playlistName', () => {
  it('opens a prompt flow with its first three words', () => {
    expect(playlistName(PROMPT, ON)).toBe('moody jazz for... (Aug 24)')
  })

  it('names a seed flow after the track it started from', () => {
    expect(playlistName(SEED, ON)).toBe('Like Fake Plastic Trees (Aug 24)')
  })
})

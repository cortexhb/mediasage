import { describe, expect, it } from 'vitest'

import type { ChosenFilters, PlaylistFlow } from '../flowStore/flowStore.ts'
import { generateBody } from './generateBody.ts'

const FILTERS: ChosenFilters = {
  genres: ['Rock'],
  decades: [],
  track_count: 25,
  exclude_live: true,
  min_rating: 0,
  max_tracks_to_ai: 500,
}

const PROMPT: PlaylistFlow = {
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
  dimensions: [],
  selectedDimensions: ['mood', 'era'],
}

describe('generateBody', () => {
  it('carries the flow id, so the run traces under the flow', () => {
    expect(generateBody(PROMPT, FILTERS).flow_id).toBe('f-1')
  })

  it('sends the filters as they were narrowed', () => {
    const body = generateBody(PROMPT, FILTERS)

    expect(body.genres).toEqual(['Rock'])
    expect(body.decades).toEqual([])
    expect(body.max_tracks_to_ai).toBe(500)
  })

  describe('a prompt flow', () => {
    it('asks with the sentence that was typed', () => {
      const body = generateBody(PROMPT, FILTERS)

      expect(body.prompt).toBe('moody jazz')
      expect(body.seed_track).toBeUndefined()
    })

    it('sends the answers positionally, blanks included', () => {
      const answered = { ...PROMPT, refinementAnswers: ['fast', null] }

      expect(generateBody(answered, FILTERS).refinement_answers).toEqual([
        'fast',
        null,
      ])
    })

    it('omits the answers where none were given', () => {
      expect(generateBody(PROMPT, FILTERS).refinement_answers).toBeUndefined()
    })
  })

  describe('a seed flow', () => {
    it('asks with the track and the dimensions to explore', () => {
      const body = generateBody(SEED, FILTERS)

      expect(body.seed_track).toEqual({
        rating_key: '99',
        selected_dimensions: ['mood', 'era'],
      })
      expect(body.prompt).toBeUndefined()
    })

    it('sends the notes only where some were written', () => {
      expect(generateBody(SEED, FILTERS).additional_notes).toBeUndefined()
      expect(
        generateBody({ ...SEED, notes: 'no ballads' }, FILTERS)
          .additional_notes,
      ).toBe('no ballads')
    })
  })
})

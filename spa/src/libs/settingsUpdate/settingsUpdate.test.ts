import { describe, expect, it } from 'vitest'

import { settingsUpdate } from './settingsUpdate.ts'

/** A submitted form, from the pairs a field set would produce. */
function submitted(fields: Record<string, string>): FormData {
  const form = new FormData()
  for (const [name, value] of Object.entries(fields)) form.append(name, value)
  return form
}

describe('settingsUpdate', () => {
  it('carries the fields that were filled in', () => {
    const update = settingsUpdate(
      submitted({ plex_url: 'http://plex:32400', music_library: 'Music' }),
    )

    expect(update).toEqual({
      plex_url: 'http://plex:32400',
      music_library: 'Music',
    })
  })

  it('trims what was typed', () => {
    const update = settingsUpdate(submitted({ plex_url: '  http://plex  ' }))

    expect(update).toEqual({ plex_url: 'http://plex' })
  })

  describe('leaving fields out', () => {
    it('drops an empty field entirely', () => {
      // A present key is a change: blank would erase the stored token.
      const update = settingsUpdate(
        submitted({ plex_token: '', plex_url: 'http://plex' }),
      )

      expect(update).not.toHaveProperty('plex_token')
    })

    it('drops a field of only whitespace', () => {
      const update = settingsUpdate(submitted({ plex_token: '   ' }))

      expect(update).toEqual({})
    })

    it('answers an empty update when nothing was filled in', () => {
      const update = settingsUpdate(submitted({ plex_url: '', plex_token: '' }))

      expect(update).toEqual({})
    })
  })

  describe('numbers', () => {
    it('sends a context window as a number, not a string', () => {
      const update = settingsUpdate(submitted({ context_window: '32768' }))

      expect(update).toEqual({ context_window: 32768 })
    })

    it.each([
      'cost_analysis_input',
      'cost_analysis_output',
      'cost_generation_input',
      'cost_generation_output',
    ])('sends %s as a number', (name) => {
      expect(settingsUpdate(submitted({ [name]: '1.25' }))).toEqual({
        [name]: 1.25,
      })
    })

    it('keeps a zero cost', () => {
      // `ConfigUpdate.changes()` filters on presence, so zero must survive.
      const update = settingsUpdate(submitted({ cost_analysis_input: '0' }))

      expect(update).toEqual({ cost_analysis_input: 0 })
    })

    it('leaves a string field a string even when it looks numeric', () => {
      const update = settingsUpdate(submitted({ model_analysis: '4' }))

      expect(update).toEqual({ model_analysis: '4' })
    })
  })

  describe('a custom provider', () => {
    it('sends its one model as both models', () => {
      const update = settingsUpdate(
        submitted({ llm_provider: 'custom', model_analysis: 'qwen3' }),
      )

      expect(update).toMatchObject({
        model_analysis: 'qwen3',
        model_generation: 'qwen3',
      })
    })

    it('sends neither when the model was left blank', () => {
      const update = settingsUpdate(
        submitted({ llm_provider: 'custom', model_analysis: '' }),
      )

      expect(update).toEqual({ llm_provider: 'custom' })
    })
  })

  describe('any other provider', () => {
    it('leaves the two models as they were submitted', () => {
      const update = settingsUpdate(
        submitted({
          llm_provider: 'ollama',
          model_analysis: 'big',
          model_generation: 'small',
        }),
      )

      expect(update).toMatchObject({
        model_analysis: 'big',
        model_generation: 'small',
      })
    })
  })

  describe('smart_generation', () => {
    it.each([
      ['true', true],
      ['false', false],
    ])('sends %s as a boolean, not the string', (carried, expected) => {
      // The API types it as a boolean; a form carries only strings.
      const update = settingsUpdate(submitted({ smart_generation: carried }))

      expect(update.smart_generation).toBe(expected)
    })
  })
})

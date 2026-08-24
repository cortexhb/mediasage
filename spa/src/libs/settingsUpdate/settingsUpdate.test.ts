import { describe, expect, it } from 'vitest'

import type { PatchKind } from '../patchFields/patchFields.ts'
import { settingsUpdate } from './settingsUpdate.ts'

/**
 * What the schema says about the fields these tests submit.
 *
 * Hand-written here rather than read from `/openapi.json`: this is a unit over
 * the coercion rules, and `patchFields` is what proves the map is built right.
 */
const KINDS: ReadonlyMap<string, PatchKind> = new Map<string, PatchKind>([
  ['llm.provider', 'text'],
  ['llm.api_key', 'password'],
  ['llm.model_analysis', 'text'],
  ['llm.model_generation', 'text'],
  ['llm.endpoint_url', 'text'],
  ['llm.context_window', 'number'],
  ['llm.smart_generation', 'boolean'],
  ['llm.cost_analysis_input', 'number'],
  ['llm.cost_analysis_output', 'number'],
  ['llm.cost_generation_input', 'number'],
  ['llm.cost_generation_output', 'number'],
  ['plex.music_library', 'text'],
  ['plex.retry_backoff', 'list'],
  ['library.live_keywords', 'list'],
])

/** A submitted form, from the pairs a field set would produce. */
function submitted(fields: Record<string, string>): FormData {
  const form = new FormData()
  for (const [name, value] of Object.entries(fields)) form.append(name, value)
  return form
}

/** The update those fields produce, under the kinds above. */
function updateFrom(fields: Record<string, string>) {
  return settingsUpdate(submitted(fields), KINDS)
}

describe('settingsUpdate', () => {
  it('groups each field under the section its name begins with', () => {
    const update = updateFrom({
      'llm.endpoint_url': 'http://ollama:11434',
      'plex.music_library': 'Music',
    })

    expect(update).toEqual({
      llm: { endpoint_url: 'http://ollama:11434' },
      plex: { music_library: 'Music' },
    })
  })

  it('trims what was typed', () => {
    expect(updateFrom({ 'llm.endpoint_url': '  http://ollama  ' })).toEqual({
      llm: { endpoint_url: 'http://ollama' },
    })
  })

  it('drops a name that carries no section, since there is nowhere to put it', () => {
    expect(updateFrom({ music_library: 'Music' })).toEqual({})
  })

  describe('leaving fields out', () => {
    it('drops an empty field entirely', () => {
      // A present key is a change: blank would erase the stored key.
      const update = updateFrom({
        'llm.api_key': '',
        'plex.music_library': 'Music',
      })

      expect(update.llm).toBeUndefined()
    })

    it('drops a field of only whitespace', () => {
      expect(updateFrom({ 'llm.api_key': '   ' })).toEqual({})
    })

    it('answers an empty update when nothing was filled in', () => {
      expect(
        updateFrom({ 'plex.music_library': '', 'llm.api_key': '' }),
      ).toEqual({})
    })
  })

  describe('numbers', () => {
    it('sends a context window as a number, not a string', () => {
      expect(updateFrom({ 'llm.context_window': '32768' })).toEqual({
        llm: { context_window: 32768 },
      })
    })

    it.each([
      'cost_analysis_input',
      'cost_analysis_output',
      'cost_generation_input',
      'cost_generation_output',
    ])('sends %s as a number', (field) => {
      expect(updateFrom({ [`llm.${field}`]: '1.25' })).toEqual({
        llm: { [field]: 1.25 },
      })
    })

    it('keeps a zero cost', () => {
      // `ConfigUpdate.changes()` filters on presence, so zero must survive.
      expect(updateFrom({ 'llm.cost_analysis_input': '0' })).toEqual({
        llm: { cost_analysis_input: 0 },
      })
    })

    it('leaves a string field a string even when it looks numeric', () => {
      expect(updateFrom({ 'llm.model_analysis': '4' })).toEqual({
        llm: { model_analysis: '4' },
      })
    })
  })

  describe('lists', () => {
    it('splits a comma-separated field into an array', () => {
      expect(
        updateFrom({ 'library.live_keywords': 'live, concert, sbd' }),
      ).toEqual({ library: { live_keywords: ['live', 'concert', 'sbd'] } })
    })

    it('drops the gaps a trailing comma leaves', () => {
      expect(
        updateFrom({ 'library.live_keywords': 'live, ,concert,' }),
      ).toEqual({
        library: { live_keywords: ['live', 'concert'] },
      })
    })

    it('leaves the items as text, since the API coerces them', () => {
      // `retry_backoff` is `list[float]`; pydantic reads "1.0" as 1.0.
      expect(updateFrom({ 'plex.retry_backoff': '1.0, 3.0' })).toEqual({
        plex: { retry_backoff: ['1.0', '3.0'] },
      })
    })
  })

  describe('a custom provider', () => {
    it('sends its one model as both models', () => {
      const update = updateFrom({
        'llm.provider': 'custom',
        'llm.model_analysis': 'qwen3',
      })

      expect(update.llm).toMatchObject({
        model_analysis: 'qwen3',
        model_generation: 'qwen3',
      })
    })

    it('sends neither when the model was left blank', () => {
      expect(
        updateFrom({ 'llm.provider': 'custom', 'llm.model_analysis': '' }),
      ).toEqual({ llm: { provider: 'custom' } })
    })
  })

  describe('any other provider', () => {
    it('leaves the two models as they were submitted', () => {
      const update = updateFrom({
        'llm.provider': 'ollama',
        'llm.model_analysis': 'big',
        'llm.model_generation': 'small',
      })

      expect(update.llm).toMatchObject({
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
      const update = updateFrom({ 'llm.smart_generation': carried })

      expect(update.llm?.smart_generation).toBe(expected)
    })
  })

  it('coerces a name the schema does not know to text, rather than dropping it', () => {
    // `extra="forbid"` on the patch means the API rejects it, loudly.
    expect(updateFrom({ 'llm.invented': 'x' })).toEqual({
      llm: { invented: 'x' },
    })
  })
})

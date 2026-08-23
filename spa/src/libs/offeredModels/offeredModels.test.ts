import { describe, expect, it } from 'vitest'

import { offeredModels } from './offeredModels.ts'

const HELD = ['qwen3:8b', 'llama3:70b']

describe('offeredModels', () => {
  it('keeps a saved model the server holds', () => {
    expect(offeredModels(HELD, 'llama3:70b', 'qwen3:8b')).toEqual({
      analysis: 'llama3:70b',
      generation: 'qwen3:8b',
    })
  })

  it('empties a saved model the server lacks, rather than replacing it', () => {
    // A replacement would be saved over the real configuration.
    expect(offeredModels(HELD, 'gone', 'qwen3:8b')).toEqual({
      analysis: '',
      generation: 'qwen3:8b',
    })
  })

  it('falls back to the first model only when neither survived', () => {
    expect(offeredModels(HELD, 'gone', 'also-gone')).toEqual({
      analysis: 'qwen3:8b',
      generation: 'qwen3:8b',
    })
  })

  it('offers the first model to a configuration with none', () => {
    expect(offeredModels(HELD, '', '')).toEqual({
      analysis: 'qwen3:8b',
      generation: 'qwen3:8b',
    })
  })

  it('offers nothing for a server holding nothing', () => {
    expect(offeredModels([], 'qwen3:8b', 'qwen3:8b')).toEqual({
      analysis: '',
      generation: '',
    })
  })
})

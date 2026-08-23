import { describe, expect, it } from 'vitest'

import { explainError } from './explainError.ts'

describe('explainError', () => {
  it('reads the message off an Error', () => {
    expect(explainError(new Error('Plex refused the token'))).toBe(
      'Plex refused the token',
    )
  })

  it('reads the status line off a route error response', () => {
    // What the router hands the boundary after a loader throws a Response.
    const thrown = {
      status: 503,
      statusText: 'No API',
      internal: false,
      data: null,
    }

    expect(explainError(thrown)).toBe('503 No API')
  })

  it('falls back for something thrown that explains nothing', () => {
    expect(explainError('a bare string')).toBe('The page could not be loaded.')
    expect(explainError(undefined)).toBe('The page could not be loaded.')
  })
})

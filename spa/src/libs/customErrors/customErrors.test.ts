import { describe, expect, it } from 'vitest'

import { customErrors } from './customErrors.ts'

describe('customErrors', () => {
  describe('the endpoint', () => {
    it.each([
      'http://localhost:5000/v1',
      'https://openrouter.ai/api/v1',
      'http://192.168.1.10:8080/v1',
    ])('accepts %s', (url) => {
      expect(customErrors(url, '32768').url).toBeUndefined()
    })

    it('says nothing about an empty field, which `required` already covers', () => {
      expect(customErrors('', '32768').url).toBeUndefined()
      expect(customErrors('   ', '32768').url).toBeUndefined()
    })

    it('rejects something that is not an address', () => {
      expect(customErrors('nonsense', '32768').url).toBe('Invalid URL format')
    })

    it('rejects a bare host, which parses as its own scheme', () => {
      // `new URL('localhost:5000')` succeeds with protocol `localhost:`.
      expect(customErrors('localhost:5000', '32768').url).toBe(
        'Must use http or https protocol',
      )
    })

    it.each(['ftp://host/v1', 'file:///models'])(
      'rejects %s, which fetch cannot use',
      (url) => {
        expect(customErrors(url, '32768').url).toBe(
          'Must use http or https protocol',
        )
      },
    )
  })

  describe('the context window', () => {
    it('accepts a window a server could have', () => {
      expect(customErrors('http://h/v1', '32768').contextWindow).toBeUndefined()
    })

    it('accepts the smallest one that fits the instructions', () => {
      expect(customErrors('http://h/v1', '512').contextWindow).toBeUndefined()
    })

    it.each(['511', '0', '-1'])('rejects %s as too small', (window) => {
      expect(customErrors('http://h/v1', window).contextWindow).toBe(
        'Must be at least 512 tokens',
      )
    })

    it('rejects a blank field, since the API requires the value', () => {
      expect(customErrors('http://h/v1', '').contextWindow).toBe(
        'Must be at least 512 tokens',
      )
    })

    it('rejects a figure no server has, which is a typo', () => {
      expect(customErrors('http://h/v1', '20000000').contextWindow).toBe(
        'Cannot exceed 2,000,000 tokens',
      )
    })

    it('accepts the largest one', () => {
      expect(
        customErrors('http://h/v1', '2000000').contextWindow,
      ).toBeUndefined()
    })
  })

  it('judges the two fields independently', () => {
    expect(customErrors('nonsense', '10')).toEqual({
      url: 'Invalid URL format',
      contextWindow: 'Must be at least 512 tokens',
    })
  })
})

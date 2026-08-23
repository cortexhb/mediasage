import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useDebounced } from './useDebounced.ts'

describe('useDebounced', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('reports the first value immediately, so nothing renders empty', () => {
    const { result } = renderHook(() => useDebounced('http://localhost:11434'))

    expect(result.current).toBe('http://localhost:11434')
  })

  it('holds a new value back until it stops changing', () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebounced(value),
      {
        initialProps: { value: 'a' },
      },
    )

    rerender({ value: 'ab' })
    expect(result.current).toBe('a')

    act(() => {
      vi.advanceTimersByTime(500)
    })
    expect(result.current).toBe('ab')
  })

  it('reports only the last of a burst', () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebounced(value),
      {
        initialProps: { value: 'h' },
      },
    )

    for (const value of ['ht', 'htt', 'http']) {
      rerender({ value })
      act(() => {
        vi.advanceTimersByTime(400)
      })
    }
    expect(result.current).toBe('h')

    act(() => {
      vi.advanceTimersByTime(500)
    })
    expect(result.current).toBe('http')
  })

  it('takes a delay, for a caller that needs a different one', () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebounced(value, 50),
      { initialProps: { value: 'a' } },
    )

    rerender({ value: 'b' })
    act(() => {
      vi.advanceTimersByTime(50)
    })

    expect(result.current).toBe('b')
  })
})

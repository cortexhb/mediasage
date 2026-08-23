/**
 * A value that settles before anyone reads it.
 *
 * Exists so a probe fires once for a typed URL rather than once per
 * keystroke. The delay matches `frontend/app.js:2732`.
 */
import { useEffect, useState } from 'react'

/** Long enough to finish typing a hostname, short enough to feel immediate. */
const SETTLE = 500

export function useDebounced<T>(value: T, delay: number = SETTLE): T {
  const [settled, setSettled] = useState(value)

  useEffect(() => {
    const timer = setTimeout(() => {
      setSettled(value)
    }, delay)
    return () => {
      clearTimeout(timer)
    }
  }, [value, delay])

  return settled
}

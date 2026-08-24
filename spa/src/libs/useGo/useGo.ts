/**
 * Navigating from a click handler, without the promise it answers.
 *
 * `useNavigate` returns `void | Promise<void>` on the overload every page
 * uses, so each caller wrapped it in `Promise.resolve(...).catch()` to satisfy
 * the no-floating-promises rule. Six pages wrote the same three lines.
 *
 * The rejection is dropped deliberately: a navigation that fails has already
 * been handled by the router's error boundary.
 */
import { useCallback } from 'react'
import { useNavigate } from 'react-router'

export function useGo(): (to: string) => void {
  const navigate = useNavigate()

  return useCallback(
    (to: string) => {
      Promise.resolve(navigate(to)).catch(() => undefined)
    },
    [navigate],
  )
}

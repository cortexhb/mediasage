/**
 * Paces a `StepProgress` from its first stage to its last.
 *
 * The backend answers once and reports nothing in between, so the stages are
 * paced rather than observed -- `frontend/app.js:4594` used the same fixed
 * interval. It stops on the last stage rather than wrapping: pretending to
 * start over would be a lie about a request that is still running.
 *
 * Counts from the mount, which is what makes a second wait start over: the
 * caller unmounts it between runs rather than resetting it.
 */
import { useEffect, useState } from 'react'

/** Milliseconds a stage is shown before the next takes over. */
const EVERY = 2000

export function useStepTicker(count: number): number {
  const [stage, setStage] = useState(0)

  useEffect(() => {
    const timer = setInterval(() => {
      setStage((at) => Math.min(at + 1, count - 1))
    }, EVERY)
    return () => {
      clearInterval(timer)
    }
  }, [count])

  return stage
}

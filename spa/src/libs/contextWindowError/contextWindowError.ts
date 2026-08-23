/**
 * What is wrong with a typed context window, if anything.
 *
 * Its own module because every provider needs it and none of them can be told
 * it by a server: hosted providers publish no limits endpoint, and a table of
 * per-model windows in the code would go stale. The bounds match
 * `backend/config/models.py:46-47`, so the field refuses what the API would.
 */

/** Below this a window cannot hold the instructions, let alone a library. */
export const SMALLEST = 512

/** Above this the value is a typo, not a window any server has. */
export const LARGEST = 2_000_000

export function contextWindowError(value: string): string | undefined {
  const tokens = Number.parseInt(value, 10)
  if (Number.isNaN(tokens) || tokens < SMALLEST) {
    return `Must be at least ${String(SMALLEST)} tokens`
  }
  if (tokens > LARGEST) {
    return `Cannot exceed ${LARGEST.toLocaleString()} tokens`
  }
  return undefined
}

/**
 * Roughly how many library tracks a context window holds.
 *
 * Measured against this repository's prompts, so it is a module constant
 * rather than configuration: 90% of the window, less 1000 tokens of
 * instructions, at ~50 tokens a track. Ported from `frontend/app.js:1890`.
 *
 * The floor of 100 is the legacy behaviour: a window too small to hold
 * anything still reports a number the form can show.
 */
const USABLE = 0.9
const INSTRUCTIONS = 1000
const PER_TRACK = 50
const FLOOR = 100

export function tracksThatFit(contextWindow: number): number {
  const forTracks = contextWindow * USABLE - INSTRUCTIONS
  return Math.max(FLOOR, Math.floor(forTracks / PER_TRACK))
}

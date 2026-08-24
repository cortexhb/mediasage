/**
 * The play-history preference, remembered across flows.
 *
 * `localStorage`, not the flow record: `frontend/app.js:4791` restores it on
 * every visit and `resetRecState` deliberately preserves it. It says how the
 * reader likes to be recommended to, which does not belong to one session.
 *
 * An unreadable or unrecognised value falls back to `any`, which is what the
 * backend defaults to.
 */
import type { Familiarity } from '../albumStore/albumStore.ts'

const KEY = 'mediasage-familiarity-pref'

/** The four the backend accepts, in the order the legacy drew them. */
export const FAMILIARITIES: readonly {
  readonly value: Familiarity
  readonly label: string
}[] = [
  { value: 'any', label: 'Any' },
  { value: 'comfort', label: 'Comfort picks' },
  { value: 'rediscover', label: 'Rediscover' },
  { value: 'hidden_gems', label: 'Hidden gems' },
]

/** The remembered preference, or `any`. */
export function readFamiliarity(): Familiarity {
  let saved: string | null
  try {
    saved = localStorage.getItem(KEY)
  } catch {
    return 'any'
  }
  const known = FAMILIARITIES.find((each) => each.value === saved)
  return known?.value ?? 'any'
}

/** Remember it, or do nothing where storage refuses. */
export function keepFamiliarity(preference: Familiarity): void {
  try {
    localStorage.setItem(KEY, preference)
  } catch {
    // Private browsing denies writes; the round still uses what was chosen.
  }
}

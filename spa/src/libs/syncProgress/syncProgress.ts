/**
 * A sync's progress, as a percentage and a line of text.
 *
 * Every phase is measurable, so the rule is the denominator, not the phase:
 * a total above zero gives a percentage, and anything else is indeterminate.
 * `frontend/app.js:2258` drew the fetching phases as an empty bar instead,
 * which is indistinguishable from a sync that has stalled.
 *
 * The phases count different things — albums, then genres, then tracks — so
 * the bar restarts between them. The text is what says why.
 */
import type { SyncProgress } from '../../api/generated/types.gen.ts'

/**
 * What each phase is doing, and the unit it counts.
 *
 * The genre phase fetches nothing new: it runs one album search per genre and
 * fills in a field on albums already read (`PlexLibrary._attach_genres`).
 */
const PHASES = {
  fetching_albums: { doing: 'Reading albums from Plex', unit: 'albums' },
  fetching_genres: { doing: 'Enriching albums with genres', unit: 'genres' },
  fetching: { doing: 'Reading tracks from Plex', unit: 'tracks' },
  processing: { doing: 'Saving tracks', unit: 'tracks' },
}

export interface SyncReport {
  /** 0 to 100, or null where nothing can be measured yet. */
  readonly percent: number | null
  readonly text: string
}

export function syncProgress(progress: SyncProgress | null): SyncReport {
  const phase = progress?.phase
  if (!phase) return { percent: null, text: 'Syncing…' }

  const { doing, unit } = PHASES[phase]
  const current = progress.current ?? 0
  const total = progress.total ?? 0
  if (total <= 0) return { percent: null, text: `${doing}…` }

  return {
    percent: (current / total) * 100,
    text: `${doing}: ${current.toLocaleString()} / ${total.toLocaleString()} ${unit}`,
  }
}

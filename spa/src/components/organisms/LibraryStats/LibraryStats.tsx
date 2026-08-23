/**
 * What the library holds, from `frontend/app.js:3223`.
 *
 * Sits inside the Plex card rather than a card of its own: the counts are
 * what the configured server and library resolved to, so they read as the
 * answer to those fields.
 *
 * Loaded through a fetcher rather than the page loader, so a settings save is
 * never held behind a stats read. Nothing here may call `setState` on the
 * success path of the load — see `organisms/OllamaSettings`.
 */
import { useEffect } from 'react'
import { useFetcher } from 'react-router'

import type { LibraryStatsResponse } from '../../../api/generated/types.gen.ts'
import { Text } from '../../atoms/Text/Text.tsx'
import { Counts } from '../../molecules/Counts/Counts.tsx'

/** The resource route in `routes.ts` that answers with the counts. */
const STATS = '/settings/stats'

/** Shown while the counts are in flight; a live read takes seconds. */
const WAITING = 'Getting library statistics, hold tight…'

/** Neither source answered, which is worth saying rather than hiding. */
const UNAVAILABLE = 'Library statistics are unavailable.'

export interface LibraryStatsProps {
  /** Whether Plex answers, which decides if a live read is worth trying. */
  readonly connected: boolean
}

export function LibraryStats({ connected }: LibraryStatsProps) {
  const counts = useFetcher<LibraryStatsResponse | null>()
  const { load: read } = counts

  useEffect(() => {
    const asked = new URLSearchParams({ connected: String(connected) })
    read(`${STATS}?${asked.toString()}`).catch(() => undefined)
  }, [connected, read])

  // Idle with no data is the tick before the effect runs.
  if (counts.state !== 'idle' || counts.data === undefined) {
    return <Text tone="muted">{WAITING}</Text>
  }

  if (counts.data === null) return <Text tone="muted">{UNAVAILABLE}</Text>

  return <Counts stats={counts.data} />
}

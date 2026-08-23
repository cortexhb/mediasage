/**
 * The library counts, on a route of their own.
 *
 * Not part of `loadSettings`, and the reason is not tidiness. Loader data
 * commits inside a transition, and React holds a whole transition until every
 * suspended boundary in it resolves — so a stats promise revalidated by a save
 * made the save appear to take as long as a stats read. A fetcher keeps this
 * off the navigation entirely.
 *
 * Read by `components/organisms/LibraryStats`.
 */
import type { LoaderFunctionArgs } from 'react-router'

import type { LibraryStatsResponse } from '../../api/generated/types.gen.ts'
import {
  readCachedLibraryStats,
  readLibraryStats,
  readLibraryStatus,
} from '../../api/library/library.ts'

/**
 * The counts out of SQLite, or nothing.
 *
 * Two cheap reads: the cached endpoint knows the breakdowns but reports no
 * total, and the sync status holds the total it recorded.
 */
async function cachedStats(
  signal: AbortSignal,
): Promise<LibraryStatsResponse | null> {
  const [counts, status] = await Promise.all([
    readCachedLibraryStats(signal),
    readLibraryStatus(signal),
  ])
  // An unsynced cache reports zeroes, which say less than nothing at all.
  if (status.track_count === 0) return null
  return { ...counts, total_tracks: status.track_count }
}

/**
 * `GET /settings/stats` — the counts, from whichever source can answer.
 *
 * The cache first, since it costs one index scan. Plex only when no sync has
 * run yet, because there the same answer costs three round-trips. A failure
 * answers null: the counts are informational and must not fault the page.
 */
export async function loadStats({
  request,
}: LoaderFunctionArgs): Promise<LibraryStatsResponse | null> {
  const connected =
    new URL(request.url).searchParams.get('connected') === 'true'

  try {
    const cached = await cachedStats(request.signal)
    if (cached) return cached
    if (!connected) return null
    return await readLibraryStats(request.signal)
  } catch {
    return null
  }
}

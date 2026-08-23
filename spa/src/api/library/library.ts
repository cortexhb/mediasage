/**
 * The library endpoints, paired with their generated types.
 *
 * Only what Settings reports today. Sync and status arrive with their own
 * page rather than ahead of it.
 */
import type {
  LibraryCacheStatusResponse,
  LibraryStatsResponse,
} from '../generated/types.gen.ts'
import { request } from '../request/request.ts'

/**
 * `GET /api/library/stats/cached` — the counts, out of SQLite.
 *
 * The live sibling at `/api/library/stats` costs three Plex round-trips and
 * takes seconds on a large library. `total_tracks` comes back zero here; the
 * cache status carries the real figure.
 */
export function readCachedLibraryStats(
  signal: AbortSignal,
): Promise<LibraryStatsResponse> {
  return request<LibraryStatsResponse>('/api/library/stats/cached', { signal })
}

/**
 * `GET /api/library/stats` — the counts, read live from Plex.
 *
 * Three Plex round-trips, seconds on a large library. Only worth asking when
 * no sync has run, since the cache cannot answer until one has.
 */
export function readLibraryStats(
  signal: AbortSignal,
): Promise<LibraryStatsResponse> {
  return request<LibraryStatsResponse>('/api/library/stats', { signal })
}

/** `GET /api/library/status` — what the last sync left behind. */
export function readLibraryStatus(
  signal: AbortSignal,
): Promise<LibraryCacheStatusResponse> {
  return request<LibraryCacheStatusResponse>('/api/library/status', { signal })
}

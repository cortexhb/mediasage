/** The library endpoints, paired with their generated types. */
import type {
  LibraryCacheStatusResponse,
  LibraryStatsResponse,
  SyncTriggerResponse,
  Track,
} from '../generated/types.gen.ts'
import { request } from '../request/request.ts'

/**
 * `GET /api/library/search` — tracks matching a query, read live from Plex.
 *
 * Plex, not the cache, so it answers before a sync has ever run. The backend
 * straightens the curly quotes iOS substitutes (`library/search.py:13`).
 */
export function searchTracks(
  query: string,
  signal: AbortSignal,
): Promise<Track[]> {
  return request<Track[]>(
    `/api/library/search?q=${encodeURIComponent(query)}`,
    { signal },
  )
}

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

/**
 * `POST /api/library/sync` — start a sync and return immediately.
 *
 * Always backgrounded, so progress comes from `readLibraryStatus` rather than
 * from this call. Answers 409 when one is already running.
 */
export function syncLibrary(signal: AbortSignal): Promise<SyncTriggerResponse> {
  return request<SyncTriggerResponse>('/api/library/sync', {
    method: 'POST',
    signal,
  })
}

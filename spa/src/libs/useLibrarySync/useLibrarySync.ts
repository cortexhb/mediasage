/**
 * The library sync, as one poller.
 *
 * `frontend/app.js` ran two: a 1s interval in `startSyncPolling` (:2389) and a
 * separate pass in `checkLibraryStatus` (:2333) that re-read the same endpoint
 * to decide whether to open a modal. Both read `GET /api/library/status`, and
 * both could be running at once. Here one chain of timeouts owns the endpoint
 * and every caller reads its state.
 *
 * The chain is timeouts rather than an interval: an interval fires again while
 * the previous request is still open, and a slow status read would queue polls
 * behind each other.
 *
 * **Nothing starts a sync on its own.** `checkLibraryStatus` did, on an empty
 * library, which made opening the page spend hours of somebody's Plex server
 * without being asked. A sync is always a click.
 *
 * The legacy `needs_resync` branch is not ported either.
 * `LibraryCacheStatusResponse` (`backend/models.py:480`) has no such field, so
 * that branch was already dead.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from 'react'

import type { LibraryCacheStatusResponse } from '../../api/generated/types.gen.ts'
import { readLibraryStatus, syncLibrary } from '../../api/library/library.ts'
import { ApiError } from '../../api/request/request.ts'

/** Milliseconds between polls while a sync runs. The legacy cadence. */
const POLL_MS = 1000

/** Already running. Not a failure: the next poll shows it. */
const IN_PROGRESS = 409

const UNREACHABLE = 'Could not reach the server.'

export interface LibrarySync {
  /** What the last poll reported, or nothing before the first one lands. */
  readonly status: LibraryCacheStatusResponse | undefined
  /**
   * Whether the running sync is the one that makes the app usable at all.
   *
   * With no tracks and no previous sync there is nothing to build a playlist
   * from, so the UI reports it in full rather than in the status bar.
   */
  readonly blocking: boolean
  /** Whether a sync has never run and a server is there to run one against. */
  readonly unsynced: boolean
  readonly error: string
  /** Start a sync, or do nothing if one is already running. */
  readonly start: () => void
}

export function useLibrarySync(): LibrarySync {
  const [status, setStatus] = useState<LibraryCacheStatusResponse>()
  const [error, setError] = useState('')
  // Bumped to restart the poll after a sync this tab asked for.
  const [pulse, setPulse] = useState(0)

  useEffect(() => {
    const aborter = new AbortController()
    let timer = 0

    const ask = async (): Promise<void> => {
      const now = await readLibraryStatus(aborter.signal)
      setStatus(now)
      // A request a second: only worth it while a sync runs.
      if (now.is_syncing) timer = window.setTimeout(poll, POLL_MS)
    }

    /** `ask` reports its own failures; the promise still has to be consumed. */
    const poll = (): void => {
      ask().catch((failure: unknown) => {
        if (aborter.signal.aborted) return
        setError(failure instanceof ApiError ? failure.message : UNREACHABLE)
      })
    }

    poll()
    return () => {
      aborter.abort()
      clearTimeout(timer)
    }
  }, [pulse])

  const start = useCallback((): void => {
    // Not aborted on unmount: the sync is server-side and outlives the page.
    const aborter = new AbortController()
    setError('')

    const resume = (): void => {
      setPulse((count) => count + 1)
    }

    syncLibrary(aborter.signal).then(resume, (failure: unknown) => {
      if (failure instanceof ApiError && failure.status === IN_PROGRESS) {
        resume()
        return
      }
      setError(failure instanceof ApiError ? failure.message : UNREACHABLE)
    })
  }, [])

  const empty = status?.track_count === 0 && !status.synced_at

  return {
    status,
    blocking: empty && status.is_syncing,
    unsynced: empty && !status.is_syncing && status.plex_connected,
    error: error || (status?.error ?? ''),
    start,
  }
}

/**
 * The one poller, shared. `LibrarySyncProvider` is what fills it.
 *
 * Null until then, so a component that reads it outside the shell fails
 * loudly rather than quietly starting a second poller of its own.
 */
export const LibrarySyncContext = createContext<LibrarySync | null>(null)

/** The shell's sync state. Throws where no provider is above the caller. */
export function useSharedLibrarySync(): LibrarySync {
  const shared = useContext(LibrarySyncContext)
  if (!shared)
    throw new Error('useSharedLibrarySync needs a LibrarySyncProvider')
  return shared
}

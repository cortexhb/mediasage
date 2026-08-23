/**
 * Holds the single `useLibrarySync` poller for everything under it.
 *
 * Two components ask about the sync -- the status bar and the Plex settings
 * card -- and each calling the hook would mean two pollers. Worse than the
 * duplicate requests: a sync started from one would never be seen by the
 * other, which only re-polls while it already believes a sync is running.
 *
 * Renders nothing. It exists so tests can mount a consumer on its own.
 */
import type { ReactNode } from 'react'

import {
  LibrarySyncContext,
  useLibrarySync,
} from '../../../libs/useLibrarySync/useLibrarySync.ts'

export interface LibrarySyncProviderProps {
  readonly children: ReactNode
}

export function LibrarySyncProvider({ children }: LibrarySyncProviderProps) {
  const sync = useLibrarySync()

  return <LibrarySyncContext value={sync}>{children}</LibrarySyncContext>
}

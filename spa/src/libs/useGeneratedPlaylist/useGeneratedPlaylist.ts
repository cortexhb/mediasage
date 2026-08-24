/**
 * The running generation, as React state.
 *
 * `useSyncExternalStore` rather than an effect that sets state: the run
 * outlives the component, and a second subscriber has to see the frames that
 * already arrived. Starting is a separate call, so a reader of the run is
 * never the thing that begins one.
 */
import { useSyncExternalStore } from 'react'

import type { PlaylistRun } from '../playlistRun/playlistRun.ts'
import { readRun, watchRun } from '../playlistRun/playlistRun.ts'

export function useGeneratedPlaylist(): PlaylistRun {
  return useSyncExternalStore(watchRun, readRun)
}

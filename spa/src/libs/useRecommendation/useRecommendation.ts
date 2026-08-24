/**
 * The running round, as React state.
 *
 * `useSyncExternalStore` rather than an effect that sets state: the round
 * outlives the component, and a second subscriber has to see the frames that
 * already arrived. Starting is a separate call, so a reader of the round is
 * never the thing that begins one.
 */
import { useSyncExternalStore } from 'react'

import type { AlbumRun } from '../albumRun/albumRun.ts'
import { readRound, watchRound } from '../albumRun/albumRun.ts'

export function useRecommendation(): AlbumRun {
  return useSyncExternalStore(watchRound, readRound)
}

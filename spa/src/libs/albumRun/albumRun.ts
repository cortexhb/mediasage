/**
 * One recommendation round, held outside React.
 *
 * `POST /api/recommend/generate` spends several LLM calls, so **only a click
 * ever starts one**: the filters submit, "Show Me Another", or switching to
 * discovery. Nothing here is called from an effect, or a reload would buy a
 * round every time.
 *
 * A finished round is kept in the flow record, so a reload shows the albums
 * that were paid for. `restoreRound` is how the page reads it back.
 *
 * Nothing aborts on unmount: the work is server-side and outlives the page.
 * `forgetRound` is the deliberate discard, and it aborts.
 *
 * The token, the listeners and the abort are `libs/streamStore`; what is here
 * is what a round is made of. Read it with `useRecommendation`.
 */
import { useSyncExternalStore } from 'react'

import type {
  RecommendGenerateRequest,
  RecommendResultFrame,
} from '../../api/generated/types.gen.ts'
import { generateRecommendations } from '../../api/recommend/recommend.ts'
import type { AlbumFrame } from '../albumFrames/albumFrames.ts'
import { albumFrame } from '../albumFrames/albumFrames.ts'
import { readAlbumFlow, writeAlbumFlow } from '../albumStore/albumStore.ts'
import { streamStore } from '../streamStore/streamStore.ts'

/** The seven stages a reader is shown, from `frontend/app.js:4393`. */
export const ROUND_STEPS = [
  'Choosing albums from your library...',
  'Researching an album...',
  'Looking up additional picks...',
  'Analyzing research sources...',
  'Writing the pitch...',
  'Fact-checking the pitch...',
  'Refining the pitch...',
]

/** Backend step names onto those seven. Same order, same names. */
const STAGE_OF: Record<string, number> = {
  selecting: 0,
  researching_primary: 1,
  researching_secondary: 2,
  extracting_facts: 3,
  writing: 4,
  validating: 5,
  rewriting: 6,
}

export interface AlbumRun {
  /** Index into `ROUND_STEPS`, as the last `progress` frame reported. */
  readonly stage: number
  /** The round's albums and totals, and the only signal that it finished. */
  readonly result: RecommendResultFrame | null
  readonly failure: string
  readonly running: boolean
}

const EMPTY: AlbumRun = {
  stage: 0,
  result: null,
  failure: '',
  running: false,
}

const TRUNCATED = 'The stream ended before the recommendation did.'

/** `frontend/app.js:4494`, word for word. */
const NOTHING = 'No recommendations were received. Please try again.'

/** One frame folded into the round. */
function applied(at: AlbumRun, frame: AlbumFrame): AlbumRun {
  switch (frame.event) {
    case 'progress':
      return { ...at, stage: STAGE_OF[frame.data.step] ?? at.stage }
    case 'result':
      // An empty round is a failure, not a result.
      if (!frame.data.recommendations.length)
        return { ...at, running: false, failure: NOTHING }
      return {
        ...at,
        result: frame.data,
        stage: ROUND_STEPS.length - 1,
        running: false,
      }
    case 'error':
      return { ...at, running: false, failure: frame.data.message }
  }
}

/** Keep a finished round, so a reload redraws it instead of buying another. */
function keep(finished: AlbumRun): void {
  const flow = readAlbumFlow()
  if (!flow || !finished.result) return
  writeAlbumFlow({ ...flow, result: finished.result })
}

const store = streamStore<AlbumRun, RecommendGenerateRequest, AlbumFrame>({
  empty: EMPTY,
  open: generateRecommendations,
  narrow: albumFrame,
  applied,
  finished: (at) => at.result !== null,
  keep,
  truncated: TRUNCATED,
})

export const readRound = store.read

export const watchRound = store.watch

/**
 * Drop the round, and the result kept from it.
 *
 * The request is aborted, which is what tells the backend to stop.
 */
export const forgetRound = store.forget

/**
 * Show a round that was already generated, without generating one.
 *
 * A reload loses the module state but not the flow record, so this is what a
 * refreshed results page draws from. Ignored while a round of its own is live.
 */
export function restoreRound(saved: RecommendResultFrame): void {
  const round = store.read()
  if (round.running || round.result) return
  store.publish({
    stage: ROUND_STEPS.length - 1,
    result: saved,
    failure: '',
    running: false,
  })
}

/** Generate. Only ever from a click, and every click is a round of its own. */
export const startRound = store.start

/**
 * The running round, as React state.
 *
 * `useSyncExternalStore` rather than an effect that sets state: the round
 * outlives the component, and a second subscriber has to see the frames that
 * already arrived. Starting is a separate call, so a reader of the round is
 * never the thing that begins one.
 */
export function useRecommendation(): AlbumRun {
  return useSyncExternalStore(watchRound, readRound)
}

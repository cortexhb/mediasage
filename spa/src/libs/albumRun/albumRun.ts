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
 * Read it with `useRecommendation`.
 */
import type {
  RecommendGenerateRequest,
  RecommendResultFrame,
} from '../../api/generated/types.gen.ts'
import { readEventStream } from '../../api/readEventStream/readEventStream.ts'
import { generateRecommendations } from '../../api/recommend/recommend.ts'
import type { AlbumFrame } from '../albumFrames/albumFrames.ts'
import { albumFrame } from '../albumFrames/albumFrames.ts'
import { readAlbumFlow, writeAlbumFlow } from '../albumStore/albumStore.ts'
import { explainError } from '../explainError/explainError.ts'

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

/**
 * Which round's frames are the current ones.
 *
 * Not the request body: "Show Me Another" sends the same body twice, and
 * identifying rounds by what they asked for made the repeat a no-op.
 */
let token = 0
let round: AlbumRun = EMPTY
let aborter: AbortController | null = null
const listeners = new Set<() => void>()

function publish(next: AlbumRun): void {
  round = next
  for (const listener of listeners) listener()
}

export function readRound(): AlbumRun {
  return round
}

export function watchRound(listener: () => void): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

/**
 * Drop the round, and the result kept from it.
 *
 * The request is aborted, which is what tells the backend to stop: the call in
 * flight cannot be recalled, but nothing after it is spent.
 */
export function forgetRound(): void {
  // Bumped, so the frames of the round being dropped are ignored.
  token += 1
  aborter?.abort()
  aborter = null
  publish(EMPTY)
}

/**
 * Show a round that was already generated, without generating one.
 *
 * A reload loses the module state but not the flow record, so this is what a
 * refreshed results page draws from. Ignored while a round of its own is live.
 */
export function restoreRound(saved: RecommendResultFrame): void {
  if (round.running || round.result) return
  publish({
    stage: ROUND_STEPS.length - 1,
    result: saved,
    failure: '',
    running: false,
  })
}

/**
 * Generate. Only ever from a click, and every click is a round of its own.
 *
 * `staleAfterMs` is `llm.stream_idle_timeout` in milliseconds: how long the
 * deployment's hardware may be silent between frames before it counts as gone.
 */
export function startRound(
  body: RecommendGenerateRequest,
  staleAfterMs: number,
): void {
  const mine = ++token
  // The previous round has no reader left.
  aborter?.abort()
  publish({ ...EMPTY, running: true })
  // `consume` publishes its own failures; the promise still has to be taken.
  consume(body, staleAfterMs, mine).catch(() => undefined)
}

async function consume(
  body: RecommendGenerateRequest,
  staleAfterMs: number,
  mine: number,
): Promise<void> {
  try {
    const own = new AbortController()
    aborter = own
    const stream = await generateRecommendations(body, own.signal)
    for await (const raw of readEventStream(stream, { staleAfterMs })) {
      // A newer request owns the round; this one's frames are stale.
      if (token !== mine) return
      const frame = albumFrame(raw)
      if (frame) publish(applied(round, frame))
    }
    if (token !== mine) return
    if (round.result) keep(round.result)
    else if (!round.failure)
      publish({ ...round, running: false, failure: TRUNCATED })
  } catch (error) {
    if (token === mine)
      publish({ ...round, running: false, failure: explainError(error) })
  }
}

/** Keep a finished round, so a reload redraws it instead of buying another. */
function keep(finished: RecommendResultFrame): void {
  const flow = readAlbumFlow()
  if (!flow) return
  writeAlbumFlow({ ...flow, result: finished })
}

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

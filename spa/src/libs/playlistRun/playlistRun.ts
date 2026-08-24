/**
 * One generation, held outside React.
 *
 * `POST /api/generate/stream` spends two LLM calls, so **only a click ever
 * starts one**: the filters submit, or the footer's Regenerate. Nothing here
 * is called from an effect, or a reload would buy a playlist every time.
 *
 * A finished run is kept in the flow record, so a reload shows the playlist
 * that was paid for rather than generating another. `restoreRun` is how the
 * page reads it back.
 *
 * Nothing aborts on unmount, for the same reason `useLibrarySync.start` does
 * not -- the work is server-side and outlives the page. `forgetRun` is the
 * deliberate discard, and it aborts.
 *
 * Read it with `useGeneratedPlaylist`.
 */
import type {
  GenerateRequest,
  PlaylistCompleteFrame,
  Track,
} from '../../api/generated/types.gen.ts'
import { generatePlaylist } from '../../api/playlists/playlists.ts'
import { readEventStream } from '../../api/readEventStream/readEventStream.ts'
import { explainError } from '../explainError/explainError.ts'
import type { SavedPlaylist } from '../flowStore/flowStore.ts'
import { readPlaylistFlow, writePlaylistFlow } from '../flowStore/flowStore.ts'
import type { PlaylistFrame } from '../playlistFrames/playlistFrames.ts'
import { playlistFrame } from '../playlistFrames/playlistFrames.ts'

/** The four stages a reader is shown, from `frontend/app.js:4533`. */
export const GENERATION_STEPS = [
  'Preparing your library...',
  'AI is curating your playlist...',
  'Matching tracks to your library...',
  'Writing playlist story...',
]

/** Backend step names onto those four. `frontend/app.js:4523`. */
const STAGE_OF: Record<string, number> = {
  fetching: 0,
  filtering: 0,
  preparing: 0,
  ai_working: 1,
  parsing: 2,
  matching: 2,
  narrative: 3,
}

export interface PlaylistRun {
  /** Index into `GENERATION_STEPS`, as the last `progress` frame reported. */
  readonly stage: number
  readonly tracks: readonly Track[]
  readonly title: string
  readonly narrative: string
  readonly reasons: Readonly<Record<string, string>>
  /** The run's totals, and the only signal that it finished. */
  readonly totals: PlaylistCompleteFrame | null
  readonly failure: string
  readonly running: boolean
}

const EMPTY: PlaylistRun = {
  stage: 0,
  tracks: [],
  title: '',
  narrative: '',
  reasons: {},
  totals: null,
  failure: '',
  running: false,
}

/**
 * Which run's frames are the current ones.
 *
 * Not the request body: submitting the same filters twice is a second run,
 * and identifying runs by what they asked for made the repeat a no-op.
 */
let token = 0
let run: PlaylistRun = EMPTY
let aborter: AbortController | null = null
const listeners = new Set<() => void>()

function publish(next: PlaylistRun): void {
  run = next
  for (const listener of listeners) listener()
}

export function readRun(): PlaylistRun {
  return run
}

export function watchRun(listener: () => void): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

/**
 * Drop the run, and the playlist kept from it, so a new one may be generated.
 *
 * The request is aborted, which is what tells the backend to stop: the call in
 * flight cannot be recalled, but nothing after it is spent.
 */
export function forgetRun(): void {
  // Bumped, so the frames of the run being dropped are ignored.
  token += 1
  aborter?.abort()
  aborter = null

  const flow = readPlaylistFlow()
  // Left in place, the page would restore the playlist being replaced.
  if (flow?.playlist) writePlaylistFlow({ ...flow, playlist: undefined })

  publish(EMPTY)
}

/**
 * Show a playlist that was already generated, without generating one.
 *
 * A reload loses the module state but not the flow record, so this is what a
 * refreshed results page draws from. Ignored while a run of its own is live.
 */
export function restoreRun(saved: SavedPlaylist): void {
  if (run.running || run.tracks.length) return
  publish({
    stage: GENERATION_STEPS.length - 1,
    tracks: saved.tracks,
    title: saved.title,
    narrative: saved.narrative,
    reasons: saved.reasons,
    totals: saved.totals,
    failure: '',
    running: false,
  })
}

/**
 * Generate. Only ever from a click, and every click is a run of its own.
 *
 * Returning to the filters step and submitting the same selection generates
 * again: the reader asked twice, and the library may have changed between.
 *
 * `staleAfterMs` is `llm.stream_idle_timeout` in milliseconds: how long the
 * deployment's hardware may be silent between frames before it counts as gone.
 */
export function startRun(body: GenerateRequest, staleAfterMs: number): void {
  const mine = ++token
  // The previous run has no reader left, as `frontend/app.js:323` had it.
  aborter?.abort()
  publish({ ...EMPTY, running: true })
  // `consume` publishes its own failures; the promise still has to be taken.
  consume(body, staleAfterMs, mine).catch(() => undefined)
}

async function consume(
  body: GenerateRequest,
  staleAfterMs: number,
  mine: number,
): Promise<void> {
  try {
    const own = new AbortController()
    aborter = own
    const stream = await generatePlaylist(body, own.signal)
    for await (const raw of readEventStream(stream, { staleAfterMs })) {
      // A newer request owns the run; this one's frames are stale.
      if (token !== mine) return
      const frame = playlistFrame(raw)
      if (frame) publish(applied(run, frame))
    }
    if (token !== mine) return
    if (run.totals) keep(run)
    // Ended with no `complete` frame: the totals never arrived.
    else publish({ ...run, running: false, failure: TRUNCATED })
  } catch (error) {
    if (token === mine)
      publish({ ...run, running: false, failure: explainError(error) })
  }
}

const TRUNCATED = 'The stream ended before the playlist did.'

/** Keep a finished run, so a reload redraws it instead of buying another. */
function keep(finished: PlaylistRun): void {
  const flow = readPlaylistFlow()
  if (!flow || !finished.totals) return
  writePlaylistFlow({
    ...flow,
    playlist: {
      tracks: finished.tracks,
      title: finished.title,
      narrative: finished.narrative,
      reasons: finished.reasons,
      totals: finished.totals,
    },
  })
}

/** One frame folded into the run. */
function applied(at: PlaylistRun, frame: PlaylistFrame): PlaylistRun {
  switch (frame.event) {
    case 'progress':
      return { ...at, stage: STAGE_OF[frame.data.step] ?? at.stage }
    case 'narrative':
      return {
        ...at,
        title: frame.data.playlist_title,
        narrative: frame.data.narrative,
        reasons: frame.data.track_reasons,
      }
    case 'tracks':
      return { ...at, tracks: [...at.tracks, ...frame.data.batch] }
    case 'complete':
      return {
        ...at,
        // The narrative frame carries the same three, but not on every run.
        title: frame.data.playlist_title || at.title,
        narrative: frame.data.narrative || at.narrative,
        reasons: frame.data.track_reasons,
        totals: frame.data,
        stage: GENERATION_STEPS.length - 1,
        running: false,
      }
    case 'error':
      return { ...at, running: false, failure: frame.data.message }
  }
}

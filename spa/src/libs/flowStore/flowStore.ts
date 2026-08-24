/**
 * What a flow's earlier steps produced, held across a reload.
 *
 * The prompt analysis costs two LLM calls and the recommend session is held
 * on the server. Neither can be recomputed for free, so a refresh on step two
 * must not send the reader back to step one — but a deep link with nothing
 * behind it must, which is why every step's loader reads this.
 *
 * `sessionStorage`, not `localStorage`: a flow belongs to the tab it was
 * started in, and two tabs mid-flow must not overwrite each other.
 *
 * Versioned, because the record's shape will change while old tabs still hold
 * the previous one. A version that does not match is discarded rather than
 * migrated: the cost is one re-analysis, and a migration path for a record
 * that lives minutes is not worth maintaining.
 */
import type {
  AnalyzePromptResponse,
  ClarifyingQuestion,
  Dimension,
  PlaylistCompleteFrame,
  Track,
} from '../../api/generated/types.gen.ts'

/** Bump on any change to `PlaylistFlow`. Mismatched records are dropped. */
const VERSION = 3

const KEY = 'mediasage.flow.playlist'

/** Which of the two ways into a playlist a record was started by. */
export type FlowMode = 'prompt' | 'seed'

/** What both flows carry, whichever way they were started. */
interface FlowBase {
  /** Groups this flow's LLM calls into one Langfuse session. */
  readonly id: string
  readonly filters?: ChosenFilters | undefined
  readonly playlist?: SavedPlaylist | undefined
}

/** A flow started from a sentence the reader typed. */
export interface PromptFlow extends FlowBase {
  readonly mode: 'prompt'
  readonly prompt: string
  readonly questions: readonly ClarifyingQuestion[]
  /** One per question, positional; null where it was skipped. */
  readonly refinementAnswers?: readonly (string | null)[] | undefined
  readonly analysis?: AnalyzePromptResponse | undefined
}

/** A flow started from a track the reader picked out of the library. */
export interface SeedFlow extends FlowBase {
  readonly mode: 'seed'
  readonly track: Track
  readonly dimensions: readonly Dimension[]
  /** Which of them to explore; empty until the dimensions step is left. */
  readonly selectedDimensions?: readonly string[] | undefined
  readonly notes?: string | undefined
}

/**
 * What each step of a playlist flow leaves for the next.
 *
 * One record, not one per mode: the legacy held a single `state.mode`
 * (`frontend/app.js:72`) and starting either flow abandons the other.
 */
export type PlaylistFlow = PromptFlow | SeedFlow

/**
 * What a finished run produced.
 *
 * Kept because a reload would otherwise throw away a playlist that has been
 * paid for, and generating is never something a reload may do on its own.
 */
export interface SavedPlaylist {
  readonly tracks: readonly Track[]
  readonly title: string
  readonly narrative: string
  readonly reasons: Readonly<Record<string, string>>
  readonly totals: PlaylistCompleteFrame
}

/** What the filters step chose, in the shape the generate request wants. */
export interface ChosenFilters {
  readonly genres: readonly string[]
  readonly decades: readonly string[]
  readonly track_count: number
  readonly exclude_live: boolean
  readonly min_rating: number
  readonly max_tracks_to_ai: number
}

/** The stored shape: the record, and the version it was written under. */
interface Stored {
  readonly version: number
  readonly flow: PlaylistFlow
}

/**
 * The playlist flow's record, or nothing.
 *
 * Answers nothing for a missing record, a version that does not match, and a
 * body that will not parse — a step cannot act on any of the three, and
 * telling them apart would only give the caller a choice it does not have.
 *
 * Storage itself can throw: Safari's private mode denies access outright.
 */
export function readPlaylistFlow(): PlaylistFlow | undefined {
  let raw: string | null
  try {
    raw = sessionStorage.getItem(KEY)
  } catch {
    return undefined
  }
  if (raw === null) return undefined

  try {
    const stored = JSON.parse(raw) as Stored
    return stored.version === VERSION ? stored.flow : undefined
  } catch {
    return undefined
  }
}

/** Keep the flow, or do nothing where storage refuses. */
export function writePlaylistFlow(flow: PlaylistFlow): void {
  const stored: Stored = { version: VERSION, flow }
  try {
    sessionStorage.setItem(KEY, JSON.stringify(stored))
  } catch {
    // Refused storage costs a re-analysis, not a broken flow.
  }
}

/** Drop the record, once its flow has reached a saved result. */
export function forgetPlaylistFlow(): void {
  try {
    sessionStorage.removeItem(KEY)
  } catch {
    // Nothing to do: the next write replaces it anyway.
  }
}

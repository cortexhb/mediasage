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
  PlaylistCompleteFrame,
  Track,
} from '../../api/generated/types.gen.ts'

/** Bump on any change to `PlaylistFlow`. Mismatched records are dropped. */
const VERSION = 2

const KEY = 'mediasage.flow.playlist'

/** What each step of the playlist flow leaves for the next. */
export interface PlaylistFlow {
  /** Groups this flow's LLM calls into one Langfuse session. */
  readonly id: string
  readonly prompt: string
  readonly questions: readonly ClarifyingQuestion[]
  /** One per question, positional; null where it was skipped. */
  readonly refinementAnswers?: readonly (string | null)[] | undefined
  readonly analysis?: AnalyzePromptResponse | undefined
  readonly filters?: ChosenFilters | undefined
  readonly playlist?: SavedPlaylist | undefined
}

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
 * An id for a flow about to start.
 *
 * `crypto.randomUUID` is secure-context only, and MediaSage is normally
 * reached over plain HTTP on a LAN, where it is undefined. `getRandomValues`
 * carries no such restriction.
 */
export function newFlowId(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(16))
  return [...bytes].map((byte) => byte.toString(16).padStart(2, '0')).join('')
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

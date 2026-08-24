/**
 * What a flow's earlier steps produced, held across a reload.
 *
 * The prompt analysis costs two LLM calls and the recommend session is held
 * on the server. Neither can be recomputed for free, so a refresh on step two
 * must not send the reader back to step one — but a deep link with nothing
 * behind it must, which is why every step's loader reads this.
 *
 * Storage, versioning and the read that answers nothing rather than a broken
 * record are `libs/sessionRecord`, which the album flow keeps its own record
 * with. What is here is the shape of a playlist flow.
 */
import type {
  AnalyzePromptResponse,
  ClarifyingQuestion,
  Dimension,
  PlaylistCompleteFrame,
  Track,
} from '../../api/generated/types.gen.ts'
import { sessionRecord } from '../sessionRecord/sessionRecord.ts'

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

const record = sessionRecord<PlaylistFlow>(KEY, VERSION)

/** The playlist flow's record, or nothing. */
export const readPlaylistFlow = record.read

/** Keep the flow, or do nothing where storage refuses. */
export const writePlaylistFlow = record.write

/** Drop the record, once its flow has reached a saved result. */
export const forgetPlaylistFlow = record.forget

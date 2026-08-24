/**
 * What the album flow's earlier steps produced, held across a reload.
 *
 * The session itself is the reason this exists: `POST /api/recommend/questions`
 * opens one on the server and everything after it is addressed by
 * `session_id`. Losing that id on a refresh would strand a paid-for session
 * with no way to reach it, so the id is kept here and every step's loader
 * reads it.
 *
 * A record of its own, not the playlist flow's: `frontend/app.js:72` held
 * `state.rec` beside `state`, and starting one flow never cleared the other.
 *
 * `sessionStorage` and the versioning work as `libs/flowStore` describes them.
 */
import type {
  ClarifyingQuestion,
  FilterSuggestion,
  RecommendResultFrame,
} from '../../api/generated/types.gen.ts'

/** Bump on any change to `AlbumFlow`. Mismatched records are dropped. */
const VERSION = 1

const KEY = 'mediasage.flow.album'

/** Where a round draws its albums from. */
export type RecommendMode = 'library' | 'discovery'

/** How much weight a round gives to what has already been played. */
export type Familiarity = 'any' | 'comfort' | 'rediscover' | 'hidden_gems'

/** What the filters step chose, in the shape the generate request wants. */
export interface ChosenAlbumFilters {
  readonly genres: readonly string[]
  readonly decades: readonly string[]
  readonly max_albums: number
}

/** What each step of the album flow leaves for the next. */
export interface AlbumFlow {
  /** Groups this flow's LLM calls into one Langfuse session. */
  readonly id: string
  /** The server-held session every later call is addressed by. */
  readonly sessionId: string
  readonly prompt: string
  readonly questions: readonly ClarifyingQuestion[]
  /** One per question, positional; null where it was skipped. */
  readonly answers?: readonly (string | null)[] | undefined
  /** The reader's own detail per question, sent alongside the answers. */
  readonly answerTexts?: readonly string[] | undefined
  /**
   * What the prompt implied, once it landed.
   *
   * Absent where the analysis failed, which is not an error: the filters step
   * then starts with nothing selected and says nothing about a suggestion.
   */
  readonly suggested?: FilterSuggestion | undefined
  readonly mode: RecommendMode
  readonly familiarity: Familiarity
  readonly filters?: ChosenAlbumFilters | undefined
  /** What the last finished round produced, so a reload redraws it. */
  readonly result?: RecommendResultFrame | undefined
}

/** The stored shape: the record, and the version it was written under. */
interface Stored {
  readonly version: number
  readonly flow: AlbumFlow
}

/**
 * The album flow's record, or nothing.
 *
 * Answers nothing for a missing record, a version that does not match, and a
 * body that will not parse, exactly as `libs/flowStore` does.
 */
export function readAlbumFlow(): AlbumFlow | undefined {
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
export function writeAlbumFlow(flow: AlbumFlow): void {
  const stored: Stored = { version: VERSION, flow }
  try {
    sessionStorage.setItem(KEY, JSON.stringify(stored))
  } catch {
    // Refused storage costs the session on reload, not the round in flight.
  }
}

/** Drop the record, once its flow has been started over. */
export function forgetAlbumFlow(): void {
  try {
    sessionStorage.removeItem(KEY)
  } catch {
    // Nothing to do: the next write replaces it anyway.
  }
}

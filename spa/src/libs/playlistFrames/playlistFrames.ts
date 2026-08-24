/**
 * Narrowing for the frames `POST /api/generate/stream` sends.
 *
 * `readEventStream` is frame-agnostic, so `data` reaches a caller as
 * `unknown`. This turns one frame into a member of the union the schema
 * declares (`GeneratePlaylistResponses[200]`), or into nothing at all: a frame
 * this build does not know is skipped rather than thrown on, so a backend that
 * adds one does not break a running page.
 *
 * The stream also carries `: heartbeat` comment frames
 * (`backend/generator/playlists.py:236`); those never reach here, as a comment
 * dispatches no event.
 */
import type {
  ErrorFrame,
  NarrativeFrame,
  PlaylistCompleteFrame,
  ProgressFrame,
  TracksFrame,
} from '../../api/generated/types.gen.ts'
import type { StreamFrame } from '../../api/readEventStream/readEventStream.ts'

export type PlaylistFrame =
  | { readonly event: 'progress'; readonly data: ProgressFrame }
  | { readonly event: 'narrative'; readonly data: NarrativeFrame }
  | { readonly event: 'tracks'; readonly data: TracksFrame }
  | { readonly event: 'complete'; readonly data: PlaylistCompleteFrame }
  | { readonly event: 'error'; readonly data: ErrorFrame }

const KNOWN = ['progress', 'narrative', 'tracks', 'complete', 'error']

/** One frame as its declared shape, or `undefined` where it is not one. */
export function playlistFrame(frame: StreamFrame): PlaylistFrame | undefined {
  if (!KNOWN.includes(frame.event)) return undefined
  if (typeof frame.data !== 'object' || frame.data === null) return undefined
  // The event name is the discriminant the backend already sends.
  return { event: frame.event, data: frame.data } as PlaylistFrame
}

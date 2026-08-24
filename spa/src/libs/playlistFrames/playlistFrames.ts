/**
 * The frames `POST /api/generate/stream` sends, as a union.
 *
 * The narrowing itself is `libs/narrowFrame`, which both streams share; what
 * is declared here is which events this one carries
 * (`GeneratePlaylistResponses[200]`).
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
import { knownFrame } from '../knownFrame/knownFrame.ts'

export type PlaylistFrame =
  | { readonly event: 'progress'; readonly data: ProgressFrame }
  | { readonly event: 'narrative'; readonly data: NarrativeFrame }
  | { readonly event: 'tracks'; readonly data: TracksFrame }
  | { readonly event: 'complete'; readonly data: PlaylistCompleteFrame }
  | { readonly event: 'error'; readonly data: ErrorFrame }

const KNOWN = ['progress', 'narrative', 'tracks', 'complete', 'error']

/** One frame as its declared shape, or `undefined` where it is not one. */
export function playlistFrame(frame: StreamFrame): PlaylistFrame | undefined {
  return knownFrame(KNOWN, frame) as PlaylistFrame | undefined
}

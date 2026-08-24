/**
 * The frames `POST /api/recommend/generate` sends, as a union.
 *
 * The terminal frame is `result`, not `complete`: this stream and the playlist
 * one disagree (`backend/api/routes/recommend/generate.py:156`), which is why
 * `readEventStream` ends on the body rather than on a frame name.
 *
 * The narrowing itself is `libs/narrowFrame`, which both streams share.
 */
import type {
  ErrorFrame,
  ProgressFrame,
  RecommendResultFrame,
} from '../../api/generated/types.gen.ts'
import type { StreamFrame } from '../../api/readEventStream/readEventStream.ts'
import { knownFrame } from '../knownFrame/knownFrame.ts'

export type AlbumFrame =
  | { readonly event: 'progress'; readonly data: ProgressFrame }
  | { readonly event: 'result'; readonly data: RecommendResultFrame }
  | { readonly event: 'error'; readonly data: ErrorFrame }

const KNOWN = ['progress', 'result', 'error']

/** One frame as its declared shape, or `undefined` where it is not one. */
export function albumFrame(frame: StreamFrame): AlbumFrame | undefined {
  return knownFrame(KNOWN, frame) as AlbumFrame | undefined
}

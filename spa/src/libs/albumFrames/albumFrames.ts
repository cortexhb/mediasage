/**
 * Narrowing for the frames `POST /api/recommend/generate` sends.
 *
 * The terminal frame is `result`, not `complete`: this stream and the playlist
 * one disagree (`backend/api/routes/recommend/generate.py:156`), which is why
 * `readEventStream` ends on the body rather than on a frame name.
 *
 * A frame this build does not know is skipped rather than thrown on, so a
 * backend that adds one does not break a running page.
 */
import type {
  ErrorFrame,
  ProgressFrame,
  RecommendResultFrame,
} from '../../api/generated/types.gen.ts'
import type { StreamFrame } from '../../api/readEventStream/readEventStream.ts'

export type AlbumFrame =
  | { readonly event: 'progress'; readonly data: ProgressFrame }
  | { readonly event: 'result'; readonly data: RecommendResultFrame }
  | { readonly event: 'error'; readonly data: ErrorFrame }

const KNOWN = ['progress', 'result', 'error']

/** One frame as its declared shape, or `undefined` where it is not one. */
export function albumFrame(frame: StreamFrame): AlbumFrame | undefined {
  if (!KNOWN.includes(frame.event)) return undefined
  if (typeof frame.data !== 'object' || frame.data === null) return undefined
  // The event name is the discriminant the backend already sends.
  return { event: frame.event, data: frame.data } as AlbumFrame
}

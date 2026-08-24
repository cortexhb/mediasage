/**
 * The check both SSE streams run over a raw frame before narrowing it.
 *
 * `readEventStream` is frame-agnostic, so `data` reaches a caller as
 * `unknown`. A frame this build does not know is skipped rather than thrown
 * on, so a backend that adds one does not break a running page, and so is one
 * whose payload is not an object at all.
 *
 * Which union the frame then belongs to is the caller's to declare: the event
 * name is the discriminant the backend already sends, and nothing at runtime
 * can check that without restating the schema.
 */
import type { StreamFrame } from '../../api/readEventStream/readEventStream.ts'

/** The frame, where its event is one of `known` and its payload an object. */
export function knownFrame(
  known: readonly string[],
  frame: StreamFrame,
): { readonly event: string; readonly data: object } | undefined {
  if (!known.includes(frame.event)) return undefined
  if (typeof frame.data !== 'object' || frame.data === null) return undefined

  return { event: frame.event, data: frame.data }
}

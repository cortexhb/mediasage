/**
 * The one SSE reader, as an async generator.
 *
 * Frame-agnostic by design. The two streams disagree on their terminal frame
 * -- `backend/generator/playlists.py:266` emits `complete`,
 * `backend/api/routes/recommend/generate.py:156` emits `result` -- so this
 * ends when the body ends and each caller declares its own terminator.
 *
 * Takes a `ReadableStream` rather than a `Response`, so cancellation is the
 * caller's `AbortSignal` on the `fetch` and a test can drive it with real
 * bytes. Leaving the loop for any reason cancels the body.
 *
 * Framing lives in `libs/parseSse`; this adds decoding, the stale-chunk
 * timeout, and cleanup.
 */
import { parseSse } from '../../libs/parseSse/parseSse.ts'

/** One frame, with its payload decoded. Narrowing `data` is the caller's job. */
export interface StreamFrame {
  readonly event: string
  readonly data: unknown
}

export interface EventStreamOptions {
  /**
   * Abort if no chunk arrives for this long, in milliseconds.
   *
   * A stream can be legitimately silent for minutes while a model works, so
   * the deadline is per chunk rather than per stream, and every caller sets
   * its own. Omit it and the read waits as long as the connection lives.
   */
  readonly staleAfterMs?: number | undefined
}

/** The stream went quiet for longer than its caller allows. */
export class StreamStalledError extends Error {
  constructor(afterMs: number) {
    super(`The stream sent nothing for ${String(afterMs)}ms`)
    this.name = 'StreamStalledError'
  }
}

/** A frame arrived that is not the JSON every event on these streams carries. */
export class FrameDecodeError extends Error {
  constructor(event: string, cause: unknown) {
    super(`The '${event}' frame did not contain JSON`, { cause })
    this.name = 'FrameDecodeError'
  }
}

type Chunk = Uint8Array

/**
 * Yield each frame as it completes, until the body ends.
 *
 * Throws `StreamStalledError` past `staleAfterMs`, `FrameDecodeError` on a
 * payload that is not JSON, and whatever the body rejects with otherwise --
 * an `AbortError` when the caller aborts the request.
 */
export async function* readEventStream(
  body: ReadableStream<Uint8Array>,
  options: EventStreamOptions = {},
): AsyncGenerator<StreamFrame, void, void> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    for (;;) {
      const chunk = await nextChunk(reader, options.staleAfterMs)
      if (chunk === null) break

      buffer += decoder.decode(chunk, { stream: true })
      const { frames, rest } = parseSse(buffer)
      buffer = rest

      for (const frame of frames) {
        yield { event: frame.event, data: decode(frame.event, frame.data) }
      }
    }
    // A leftover buffer is a truncated frame, which the spec discards.
    // The caller learns of it from the terminator that never arrived.
  } finally {
    await reader.cancel()
  }
}

/** The next chunk, or `null` once the body is done. */
async function nextChunk(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  staleAfterMs: number | undefined,
): Promise<Chunk | null> {
  const read = reader.read()

  if (staleAfterMs === undefined) {
    const { done, value } = await read
    return done ? null : value
  }

  let timer: ReturnType<typeof setTimeout> | undefined
  const stalled = new Promise<never>((_resolve, reject) => {
    timer = setTimeout(() => {
      reject(new StreamStalledError(staleAfterMs))
    }, staleAfterMs)
  })

  try {
    const { done, value } = await Promise.race([read, stalled])
    return done ? null : value
  } finally {
    clearTimeout(timer)
  }
}

/** A frame's payload, or a named failure instead of a silent drop. */
function decode(event: string, data: string): unknown {
  try {
    return JSON.parse(data) as unknown
  } catch (error) {
    throw new FrameDecodeError(event, error)
  }
}

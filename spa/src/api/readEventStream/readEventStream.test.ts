import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  FrameDecodeError,
  readEventStream,
  StreamStalledError,
  type StreamFrame,
} from './readEventStream.ts'

const encoder = new TextEncoder()

/** A body that delivers the given chunks and then ends. */
function bodyOf(...chunks: readonly (string | Uint8Array)[]) {
  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(
          typeof chunk === 'string' ? encoder.encode(chunk) : chunk,
        )
      }
      controller.close()
    },
  })
}

/** A body that delivers nothing and never ends. */
function silentBody() {
  return new ReadableStream<Uint8Array>({ start: () => undefined })
}

async function collect(
  frames: AsyncGenerator<StreamFrame, void, void>,
): Promise<StreamFrame[]> {
  const seen: StreamFrame[] = []
  for await (const frame of frames) seen.push(frame)
  return seen
}

const PROGRESS = 'event: progress\ndata: {"step":"filtering"}\n\n'
const COMPLETE = 'event: complete\ndata: {"track_count":12}\n\n'

describe('readEventStream', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('yields each frame with its payload decoded', async () => {
    const frames = await collect(readEventStream(bodyOf(PROGRESS, COMPLETE)))

    expect(frames).toEqual([
      { event: 'progress', data: { step: 'filtering' } },
      { event: 'complete', data: { track_count: 12 } },
    ])
  })

  it('ends when the body ends, with no terminator of its own', async () => {
    // The two streams disagree on which frame is last.
    const frames = await collect(readEventStream(bodyOf(PROGRESS)))

    expect(frames).toHaveLength(1)
  })

  it('yields nothing for an empty body', async () => {
    expect(await collect(readEventStream(bodyOf()))).toEqual([])
  })

  it('reassembles a frame split across two chunks', async () => {
    const body = bodyOf('event: complete\ndata: {"track_', 'count":12}\n\n')

    const frames = await collect(readEventStream(body))

    expect(frames).toEqual([{ event: 'complete', data: { track_count: 12 } }])
  })

  it('reassembles a multi-byte character split across two chunks', async () => {
    // The é occupies bytes 19 and 20; decoding per chunk yields U+FFFD.
    const bytes = encoder.encode('event: a\ndata: "café"\n\n')

    const body = bodyOf(bytes.slice(0, 20), bytes.slice(20))
    const frames = await collect(readEventStream(body))

    expect(frames).toEqual([{ event: 'a', data: 'café' }])
  })

  it('does not yield a comment frame', async () => {
    const frames = await collect(
      readEventStream(bodyOf(': heartbeat\n\n', PROGRESS)),
    )

    expect(frames).toEqual([{ event: 'progress', data: { step: 'filtering' } }])
  })

  it('drops a frame the body was cut off part-way through', async () => {
    const body = bodyOf(PROGRESS, 'event: complete\ndata: {"track_')

    const frames = await collect(readEventStream(body))

    expect(frames).toHaveLength(1)
  })

  it('reports a payload that is not JSON rather than skipping it', async () => {
    const body = bodyOf('event: complete\ndata: not json\n\n')

    await expect(collect(readEventStream(body))).rejects.toThrow(
      FrameDecodeError,
    )
  })

  it('names the event on a payload it cannot decode', async () => {
    const body = bodyOf('event: narrative\ndata: {oops\n\n')

    await expect(collect(readEventStream(body))).rejects.toThrow(/'narrative'/)
  })

  it('keeps the underlying parse failure as the cause', async () => {
    const body = bodyOf('event: a\ndata: {oops\n\n')

    const failure = await collect(readEventStream(body)).catch(
      (error: unknown) => error,
    )

    expect(failure).toBeInstanceOf(FrameDecodeError)
    expect((failure as FrameDecodeError).cause).toBeInstanceOf(SyntaxError)
  })

  describe('the stale-chunk deadline', () => {
    it('throws once nothing has arrived for long enough', async () => {
      vi.useFakeTimers()

      const reading = collect(
        readEventStream(silentBody(), { staleAfterMs: 120_000 }),
      )
      const failure = reading.catch((error: unknown) => error)
      await vi.advanceTimersByTimeAsync(120_000)

      expect(await failure).toBeInstanceOf(StreamStalledError)
    })

    it('says how long it waited', async () => {
      vi.useFakeTimers()

      const reading = collect(
        readEventStream(silentBody(), { staleAfterMs: 300_000 }),
      )
      const failure = reading.catch((error: unknown) => error)
      await vi.advanceTimersByTimeAsync(300_000)

      expect(await failure).toHaveProperty(
        'message',
        expect.stringContaining('300000'),
      )
    })

    it('restarts the deadline on every chunk', async () => {
      vi.useFakeTimers()
      const pipe = new TransformStream<Uint8Array, Uint8Array>()
      const writer = pipe.writable.getWriter()

      // Each gap is under the 100ms deadline, but 270ms passes in total.
      const frames = collect(
        readEventStream(pipe.readable, { staleAfterMs: 100 }),
      )
      for (const chunk of [PROGRESS, PROGRESS, COMPLETE]) {
        await vi.advanceTimersByTimeAsync(90)
        await writer.write(encoder.encode(chunk))
      }
      await writer.close()

      expect(await frames).toHaveLength(3)
    })

    it('throws when one gap alone is too long', async () => {
      vi.useFakeTimers()
      const pipe = new TransformStream<Uint8Array, Uint8Array>()
      const writer = pipe.writable.getWriter()

      const reading = collect(
        readEventStream(pipe.readable, { staleAfterMs: 50 }),
      )
      const failure = reading.catch((error: unknown) => error)
      await vi.advanceTimersByTimeAsync(90)
      await writer.write(encoder.encode(PROGRESS)).catch(() => undefined)

      expect(await failure).toBeInstanceOf(StreamStalledError)
    })

    it('waits indefinitely when no deadline is given', async () => {
      vi.useFakeTimers()
      const pipe = new TransformStream<Uint8Array, Uint8Array>()
      const writer = pipe.writable.getWriter()

      const frames = collect(readEventStream(pipe.readable))
      await vi.advanceTimersByTimeAsync(3_600_000)
      await writer.write(encoder.encode(PROGRESS))
      await writer.close()

      expect(await frames).toHaveLength(1)
    })
  })

  it('cancels the body when the caller stops reading early', async () => {
    const cancelled = vi.fn()
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode(PROGRESS))
        controller.enqueue(encoder.encode(COMPLETE))
      },
      cancel: cancelled,
    })

    for await (const frame of readEventStream(body)) {
      expect(frame.event).toBe('progress')
      break
    }

    expect(cancelled).toHaveBeenCalled()
  })

  it('cancels the body when a frame fails to decode', async () => {
    const cancelled = vi.fn()
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode('event: a\ndata: {oops\n\n'))
      },
      cancel: cancelled,
    })

    await expect(collect(readEventStream(body))).rejects.toThrow(
      FrameDecodeError,
    )
    expect(cancelled).toHaveBeenCalled()
  })

  it('surfaces what the body itself rejects with', async () => {
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.error(new Error('network gone'))
      },
    })

    await expect(collect(readEventStream(body))).rejects.toThrow('network gone')
  })
})

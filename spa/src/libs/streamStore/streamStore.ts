/**
 * One streaming run, held outside React, whichever stream it reads.
 *
 * `libs/playlistRun` and `libs/albumRun` differ in their request, their frames
 * and their state; everything around those is the same and lives here -- the
 * listener set a `useSyncExternalStore` reads, the run token that makes a
 * superseded run's frames ignorable, and the abort a deliberate discard
 * performs.
 *
 * **Nothing here starts a run on its own.** `start` is called from a click,
 * because every run spends LLM calls, and an effect would spend them again on
 * every reload.
 */
import type { StreamFrame } from '../../api/readEventStream/readEventStream.ts'
import { readEventStream } from '../../api/readEventStream/readEventStream.ts'
import { explainError } from '../explainError/explainError.ts'

/** What every run reports, whatever else it carries. */
export interface RunState {
  readonly running: boolean
  readonly failure: string
}

/** What one kind of run does that the bookkeeping cannot do for it. */
export interface StreamSpec<S extends RunState, B, F> {
  readonly empty: S
  readonly open: (
    body: B,
    signal: AbortSignal,
  ) => Promise<ReadableStream<Uint8Array>>
  /** One raw frame as its declared shape, or nothing where it is unknown. */
  readonly narrow: (frame: StreamFrame) => F | undefined
  readonly applied: (at: S, frame: F) => S
  /** Whether the run reached the terminal frame its stream ends on. */
  readonly finished: (at: S) => boolean
  /** Keep a finished run, so a reload redraws it instead of buying another. */
  readonly keep: (finished: S) => void
  /** Said where the stream ended before the run did. */
  readonly truncated: string
}

export interface StreamStore<S extends RunState, B> {
  readonly read: () => S
  readonly watch: (listener: () => void) => () => void
  /** Publish a state the caller assembled, for a restore or a reset. */
  readonly publish: (next: S) => void
  /**
   * Drop the run.
   *
   * The request is aborted, which is what tells the backend to stop: the call
   * in flight cannot be recalled, but nothing after it is spent.
   */
  readonly forget: () => void
  /**
   * Generate. Only ever from a click, and every click is a run of its own.
   *
   * `staleAfterMs` is `llm.stream_idle_timeout` in milliseconds: how long the
   * deployment's hardware may be silent between frames before it counts as
   * gone.
   */
  readonly start: (body: B, staleAfterMs: number) => void
}

export function streamStore<S extends RunState, B, F>(
  spec: StreamSpec<S, B, F>,
): StreamStore<S, B> {
  /**
   * Which run's frames are the current ones.
   *
   * Not the request body: the same body sent twice is a second run, and
   * identifying runs by what they asked for made the repeat a no-op.
   */
  let token = 0
  let run: S = spec.empty
  let aborter: AbortController | null = null
  const listeners = new Set<() => void>()

  const publish = (next: S): void => {
    run = next
    for (const listener of listeners) listener()
  }

  /** The run, stopped, with what stopped it. */
  const stopped = (failure: string): S => ({ ...run, running: false, failure })

  const consume = async (
    body: B,
    staleAfterMs: number,
    mine: number,
  ): Promise<void> => {
    try {
      const own = new AbortController()
      aborter = own
      const stream = await spec.open(body, own.signal)
      for await (const raw of readEventStream(stream, { staleAfterMs })) {
        // A newer request owns the run; this one's frames are stale.
        if (token !== mine) return
        const frame = spec.narrow(raw)
        if (frame) publish(spec.applied(run, frame))
      }
      if (token !== mine) return
      if (spec.finished(run)) spec.keep(run)
      // Ended with no terminal frame, and no frame that said why.
      else if (!run.failure) publish(stopped(spec.truncated))
    } catch (error) {
      if (token === mine) publish(stopped(explainError(error)))
    }
  }

  return {
    read: () => run,
    watch: (listener) => {
      listeners.add(listener)
      return () => {
        listeners.delete(listener)
      }
    },
    publish,
    forget: () => {
      // Bumped, so the frames of the run being dropped are ignored.
      token += 1
      aborter?.abort()
      aborter = null
      publish(spec.empty)
    },
    start: (body, staleAfterMs) => {
      const mine = ++token
      // The previous run has no reader left, as `frontend/app.js:323` had it.
      aborter?.abort()
      publish({ ...spec.empty, running: true })
      // `consume` publishes its own failures; the promise still has to be taken.
      consume(body, staleAfterMs, mine).catch(() => undefined)
    },
  }
}

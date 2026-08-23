/**
 * Framing for `text/event-stream`, as text.
 *
 * Pure and stateless: given everything received so far, it returns the frames
 * that are complete and the tail that is not one yet. The caller appends the
 * next chunk to that tail and calls again.
 *
 * Statelessness is the point. The legacy reader kept its `event`/`data`
 * accumulator in a variable re-initialised on every chunk
 * (`frontend/app.js:382`), so a frame split at a line boundary lost its
 * `event:` line and was dropped. Here an incomplete frame stays in `rest`
 * whole, including the lines already read.
 *
 * Follows the WHATWG event-stream parse rules -- see Sources in
 * `spa/docs/migration.md`. Payloads are left as text; decoding them is the
 * caller's business.
 */

/** One dispatched event: its type, and its `data` lines joined by newlines. */
export interface SseFrame {
  readonly event: string
  readonly data: string
}

/** Complete frames, and the tail that is not a complete frame yet. */
export interface SseSplit {
  readonly frames: readonly SseFrame[]
  readonly rest: string
}

/** CRLF, LF and CR are all line terminators in an event stream. */
const TERMINATOR = /\r\n|\n|\r/

/** An event with no type of its own is a `message`. */
const DEFAULT_EVENT = 'message'

/**
 * Split a receive buffer into whole frames and an unfinished remainder.
 *
 * `rest` is safe to prepend to the next chunk and pass straight back in.
 */
export function parseSse(buffer: string): SseSplit {
  // A trailing CR may be half of a split CRLF.
  const held = buffer.endsWith('\r') ? '\r' : ''
  const lines = (held ? buffer.slice(0, -1) : buffer).split(TERMINATOR)

  const frames: SseFrame[] = []
  let event = ''
  let data = ''
  // The first line not yet accounted for by a dispatched frame.
  let restFrom = 0

  // The final element has no terminator, so it is incomplete.
  for (let i = 0; i < lines.length - 1; i += 1) {
    const line = lines[i] ?? ''

    if (line === '') {
      // A blank line dispatches, unless nothing was accumulated.
      if (data !== '') {
        frames.push({
          event: event === '' ? DEFAULT_EVENT : event,
          // Every `data` field appended a newline; the last one is not part
          // of the payload.
          data: data.slice(0, -1),
        })
      }
      event = ''
      data = ''
      restFrom = i + 1
      continue
    }

    // A comment. The playlist stream sends `: heartbeat` to flush proxies.
    if (line.startsWith(':')) continue

    const colon = line.indexOf(':')
    const field = colon === -1 ? line : line.slice(0, colon)
    const raw = colon === -1 ? '' : line.slice(colon + 1)
    // One space after the colon is framing, not value.
    const value = raw.startsWith(' ') ? raw.slice(1) : raw

    if (field === 'event') {
      event = value
    } else if (field === 'data') {
      data += `${value}\n`
    }
    // `id` and `retry` are ignored: nothing here reconnects.
  }

  return { frames, rest: lines.slice(restFrom).join('\n') + held }
}

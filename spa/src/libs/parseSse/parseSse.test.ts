import { describe, expect, it } from 'vitest'

import { parseSse } from './parseSse.ts'

/** Feed a stream one chunk at a time, the way the reader does. */
function feed(...chunks: readonly string[]) {
  let buffer = ''
  const frames = []

  for (const chunk of chunks) {
    buffer += chunk
    const split = parseSse(buffer)
    buffer = split.rest
    frames.push(...split.frames)
  }

  return { frames, rest: buffer }
}

describe('parseSse', () => {
  it('finds nothing in an empty buffer', () => {
    expect(parseSse('')).toEqual({ frames: [], rest: '' })
  })

  it('reads one frame', () => {
    const { frames, rest } = parseSse('event: progress\ndata: {"step":1}\n\n')

    expect(frames).toEqual([{ event: 'progress', data: '{"step":1}' }])
    expect(rest).toBe('')
  })

  it('reads several frames from one buffer', () => {
    const { frames } = parseSse(
      'event: a\ndata: 1\n\nevent: b\ndata: 2\n\nevent: c\ndata: 3\n\n',
    )

    expect(frames.map((frame) => frame.event)).toEqual(['a', 'b', 'c'])
    expect(frames.map((frame) => frame.data)).toEqual(['1', '2', '3'])
  })

  it('joins repeated data fields with newlines', () => {
    const { frames } = parseSse('event: note\ndata: one\ndata: two\n\n')

    expect(frames).toEqual([{ event: 'note', data: 'one\ntwo' }])
  })

  it('calls a frame with no event type a message', () => {
    const { frames } = parseSse('data: bare\n\n')

    expect(frames).toEqual([{ event: 'message', data: 'bare' }])
  })

  it('accepts a data field with no space after the colon', () => {
    const { frames } = parseSse('event:tick\ndata:1\n\n')

    expect(frames).toEqual([{ event: 'tick', data: '1' }])
  })

  it('keeps every space after the first', () => {
    const { frames } = parseSse('data:   padded\n\n')

    expect(frames).toEqual([{ event: 'message', data: '  padded' }])
  })

  it('dispatches a data field that is empty', () => {
    const { frames } = parseSse('event: ping\ndata:\n\n')

    expect(frames).toEqual([{ event: 'ping', data: '' }])
  })

  it('dispatches nothing for a frame that carried no data', () => {
    const { frames, rest } = parseSse('event: lonely\n\n')

    expect(frames).toEqual([])
    expect(rest).toBe('')
  })

  it('ignores a comment frame', () => {
    const { frames } = parseSse(': heartbeat\n\n')

    expect(frames).toEqual([])
  })

  it('ignores a heartbeat between two frames', () => {
    const { frames } = parseSse(
      'event: a\ndata: 1\n\n: heartbeat\n\nevent: b\ndata: 2\n\n',
    )

    expect(frames.map((frame) => frame.event)).toEqual(['a', 'b'])
  })

  it('ignores fields it has no use for', () => {
    const { frames } = parseSse('id: 7\nretry: 2000\nevent: a\ndata: 1\n\n')

    expect(frames).toEqual([{ event: 'a', data: '1' }])
  })

  it('ignores a line with no colon at all', () => {
    const { frames } = parseSse('event: a\nnonsense\ndata: 1\n\n')

    expect(frames).toEqual([{ event: 'a', data: '1' }])
  })

  describe('chunk boundaries', () => {
    it('holds back a partial line', () => {
      const { frames, rest } = parseSse('event: a\ndata: {"half"')

      expect(frames).toEqual([])
      expect(rest).toBe('event: a\ndata: {"half"')
    })

    it('holds back a whole frame that has no blank line yet', () => {
      const { frames, rest } = parseSse('event: a\ndata: 1\n')

      expect(frames).toEqual([])
      expect(rest).toBe('event: a\ndata: 1\n')
    })

    it('keeps the event type of a frame split at a line boundary', () => {
      // The legacy reader re-initialised its accumulator per chunk
      // (`frontend/app.js:382`), so this frame arrived typed as undefined.
      const { frames } = feed('event: narrative\n', 'data: {"a":1}\n\n')

      expect(frames).toEqual([{ event: 'narrative', data: '{"a":1}' }])
    })

    it('reassembles a payload split mid-token', () => {
      const { frames } = feed('event: tracks\ndata: {"bat', 'ch":[1,2]}\n\n')

      expect(frames).toEqual([{ event: 'tracks', data: '{"batch":[1,2]}' }])
    })

    it('reassembles a frame delivered one character at a time', () => {
      const wire = 'event: a\ndata: 1\n\n'

      const { frames, rest } = feed(...wire.split(''))

      expect(frames).toEqual([{ event: 'a', data: '1' }])
      expect(rest).toBe('')
    })

    it('emits the first frame while the second is still arriving', () => {
      const { frames, rest } = parseSse('event: a\ndata: 1\n\nevent: b\ndata: ')

      expect(frames).toEqual([{ event: 'a', data: '1' }])
      expect(rest).toBe('event: b\ndata: ')
    })

    it('leaves a trailing partial frame in rest when the stream stops', () => {
      const { frames, rest } = feed('event: a\ndata: 1\n\nevent: b\ndata: {"c"')

      expect(frames).toEqual([{ event: 'a', data: '1' }])
      expect(rest).toBe('event: b\ndata: {"c"')
    })
  })

  describe('line terminators', () => {
    it('reads CRLF', () => {
      const { frames } = parseSse('event: a\r\ndata: 1\r\n\r\n')

      expect(frames).toEqual([{ event: 'a', data: '1' }])
    })

    it('reads a bare CR', () => {
      const { frames, rest } = parseSse('event: a\rdata: 1\r\rnext')

      expect(frames).toEqual([{ event: 'a', data: '1' }])
      expect(rest).toBe('next')
    })

    it('defers a frame whose buffer ends on a CR until one more byte', () => {
      // Held back because the CR may be half of a CRLF.
      const held = parseSse('event: a\rdata: 1\r\r')
      expect(held.frames).toEqual([])

      const { frames } = feed('event: a\rdata: 1\r\r', 'x')
      expect(frames).toEqual([{ event: 'a', data: '1' }])
    })

    it('keeps a frame whole when a CRLF pair is split around it', () => {
      // Without the hold-back the stray LF would end the frame early and
      // deliver its two data lines as two frames.
      const { frames } = feed('data: 1\r', '\ndata: 2\r\n\r\n')

      expect(frames).toEqual([{ event: 'message', data: '1\n2' }])
    })

    it('does not treat a trailing CR as a finished line', () => {
      // It may be half of a CRLF the boundary split.
      const { frames, rest } = parseSse('event: a\r\ndata: 1\r')

      expect(frames).toEqual([])
      expect(rest).toBe('event: a\ndata: 1\r')
    })

    it('reassembles a CRLF split across two chunks', () => {
      const { frames } = feed('event: a\r\ndata: 1\r', '\n\r\n')

      expect(frames).toEqual([{ event: 'a', data: '1' }])
    })
  })
})

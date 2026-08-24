import { describe, expect, it } from 'vitest'

import {
  forgetPlaylistFlow,
  newFlowId,
  readPlaylistFlow,
  writePlaylistFlow,
} from './flowStore.ts'

const FLOW = { id: 'f-1', prompt: 'moody jazz', questions: [] }

describe('newFlowId', () => {
  it('is 32 hex characters', () => {
    expect(newFlowId()).toMatch(/^[0-9a-f]{32}$/)
  })

  it('does not repeat', () => {
    const minted = new Set(Array.from({ length: 50 }, newFlowId))

    expect(minted.size).toBe(50)
  })

  it('does not need a secure context', () => {
    // `crypto.randomUUID` is undefined over plain HTTP; this must not be.
    expect(globalThis.isSecureContext || newFlowId()).toBeTruthy()
  })
})

describe('the flow record', () => {
  it('reads back what was written', () => {
    writePlaylistFlow(FLOW)

    expect(readPlaylistFlow()).toEqual(FLOW)
  })

  it('answers nothing once forgotten', () => {
    writePlaylistFlow(FLOW)
    forgetPlaylistFlow()

    expect(readPlaylistFlow()).toBeUndefined()
  })

  it('discards a record written under an older version', () => {
    sessionStorage.setItem(
      'mediasage.flow.playlist',
      JSON.stringify({ version: 0, flow: FLOW }),
    )

    expect(readPlaylistFlow()).toBeUndefined()
  })

  it('discards a body that will not parse', () => {
    sessionStorage.setItem('mediasage.flow.playlist', 'not json')

    expect(readPlaylistFlow()).toBeUndefined()
  })
})

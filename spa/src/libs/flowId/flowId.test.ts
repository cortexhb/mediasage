import { describe, expect, it } from 'vitest'

import { newFlowId } from './flowId.ts'

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

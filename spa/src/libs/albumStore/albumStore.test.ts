import { beforeEach, describe, expect, it } from 'vitest'

import type { AlbumFlow } from './albumStore.ts'
import { forgetAlbumFlow, readAlbumFlow, writeAlbumFlow } from './albumStore.ts'

const FLOW: AlbumFlow = {
  id: 'f-1',
  sessionId: 's-1',
  prompt: 'something for a rainy Sunday',
  questions: [],
  mode: 'library',
  familiarity: 'any',
}

describe('the album flow record', () => {
  beforeEach(forgetAlbumFlow)

  it('reads back what was written', () => {
    writeAlbumFlow(FLOW)

    expect(readAlbumFlow()).toEqual(FLOW)
  })

  it('answers nothing when nothing was written', () => {
    expect(readAlbumFlow()).toBeUndefined()
  })

  it('keeps its own key, so a playlist flow does not overwrite it', () => {
    writeAlbumFlow(FLOW)
    sessionStorage.setItem('mediasage.flow.playlist', 'anything')

    expect(readAlbumFlow()?.sessionId).toBe('s-1')
  })

  it('drops a record written under another version', () => {
    sessionStorage.setItem(
      'mediasage.flow.album',
      JSON.stringify({ version: 0, flow: FLOW }),
    )

    expect(readAlbumFlow()).toBeUndefined()
  })

  it('drops a body that will not parse', () => {
    sessionStorage.setItem('mediasage.flow.album', '{')

    expect(readAlbumFlow()).toBeUndefined()
  })
})

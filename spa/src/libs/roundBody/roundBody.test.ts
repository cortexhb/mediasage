import { describe, expect, it } from 'vitest'

import type { AlbumFlow } from '../albumStore/albumStore.ts'
import { roundBody } from './roundBody.ts'

const READY: AlbumFlow = {
  id: 'f-1',
  sessionId: 's-1',
  prompt: 'rainy Sunday',
  questions: [],
  answers: ['Quiet', null],
  answerTexts: ['', 'no drums'],
  mode: 'library',
  familiarity: 'comfort',
  filters: { genres: ['Jazz'], decades: [], max_albums: 2500 },
}

describe('roundBody', () => {
  it('sends the session, the answers and the selection', () => {
    expect(roundBody(READY)).toEqual({
      session_id: 's-1',
      answers: ['Quiet', null],
      answer_texts: ['', 'no drums'],
      mode: 'library',
      genres: ['Jazz'],
      decades: [],
      familiarity_pref: 'comfort',
      max_albums: 2500,
    })
  })

  it('answers nothing before the filters step has been left', () => {
    expect(roundBody({ ...READY, filters: undefined })).toBeUndefined()
  })

  it('answers nothing before the questions have been answered', () => {
    expect(roundBody({ ...READY, answers: undefined })).toBeUndefined()
  })
})

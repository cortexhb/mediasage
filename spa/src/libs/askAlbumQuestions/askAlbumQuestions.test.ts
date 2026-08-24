import { http, HttpResponse } from 'msw'
import { beforeEach, describe, expect, it } from 'vitest'

import { server } from '@test'
import { forgetAlbumFlow, readAlbumFlow } from '../albumStore/albumStore.ts'
import { answerAlbumQuestions } from '../answerAlbumQuestions/answerAlbumQuestions.ts'
import { forgetSuggestion } from '../suggestionCache/suggestionCache.ts'
import type { AlbumPromptResult } from './askAlbumQuestions.ts'
import { askAlbumQuestions } from './askAlbumQuestions.ts'

const QUESTION = {
  dimension: 'mood',
  question_text: 'How heavy?',
  options: ['Light', 'Heavy'],
}

/** The action as the router calls it, with one named field. */
function submitting(url: string, fields: Record<string, string>) {
  const form = new FormData()
  for (const [name, value] of Object.entries(fields)) form.set(name, value)
  return {
    request: new Request(`http://localhost${url}`, {
      method: 'POST',
      body: form,
    }),
  }
}

/** The questions endpoint, and the two reads the suggestion needs. */
function serving(): void {
  server.use(
    http.post('/api/recommend/questions', () =>
      HttpResponse.json({
        questions: [QUESTION],
        session_id: 's-1',
        token_count: 12,
        estimated_cost: 0,
      }),
    ),
    http.get('/api/library/stats', () =>
      HttpResponse.json({ total_tracks: 1, genres: [], decades: [] }),
    ),
    http.post('/api/recommend/analyze-prompt', () =>
      HttpResponse.json({ genres: ['Jazz'], decades: [], reasoning: '' }),
    ),
  )
}

describe('askAlbumQuestions', () => {
  beforeEach(() => {
    forgetAlbumFlow()
    forgetSuggestion()
    localStorage.clear()
  })

  it('opens the session and moves on to the refine step', async () => {
    serving()

    const answer = await askAlbumQuestions(
      submitting('/recommend', { prompt: '  rainy Sunday  ' }),
    )

    expect((answer as Response).headers.get('Location')).toBe(
      '/recommend/refine',
    )
    const flow = readAlbumFlow()
    expect(flow?.sessionId).toBe('s-1')
    expect(flow?.prompt).toBe('rainy Sunday')
    expect(flow?.mode).toBe('library')
  })

  it('refuses an empty prompt rather than spending a call', async () => {
    const answer = await askAlbumQuestions(
      submitting('/recommend', { prompt: '   ' }),
    )

    expect((answer as AlbumPromptResult).error).toBe('Please enter a prompt')
    expect(readAlbumFlow()).toBeUndefined()
  })

  it('reports what the backend refused with', async () => {
    server.use(
      http.post('/api/recommend/questions', () =>
        HttpResponse.json({ detail: 'LLM not configured' }, { status: 503 }),
      ),
      http.get('/api/library/stats', () =>
        HttpResponse.json({ total_tracks: 0, genres: [], decades: [] }),
      ),
      http.post('/api/recommend/analyze-prompt', () =>
        HttpResponse.json({ genres: [], decades: [], reasoning: '' }),
      ),
    )

    const answer = await askAlbumQuestions(
      submitting('/recommend', { prompt: 'rainy' }),
    )

    expect((answer as AlbumPromptResult).error).toBe('LLM not configured')
  })
})

describe('answerAlbumQuestions', () => {
  beforeEach(() => {
    forgetAlbumFlow()
    forgetSuggestion()
    localStorage.clear()
  })

  it('keeps the option and the detail apart, as the backend reads them', async () => {
    serving()
    await askAlbumQuestions(submitting('/recommend', { prompt: 'rainy' }))

    const answer = await answerAlbumQuestions(
      submitting('/recommend/refine', {
        'option-0': 'Heavy',
        'detail-0': '  no drums  ',
      }),
    )

    expect(answer.headers.get('Location')).toBe('/recommend/filters')
    const flow = readAlbumFlow()
    expect(flow?.answers).toEqual(['Heavy'])
    expect(flow?.answerTexts).toEqual(['no drums'])
  })

  it('sends null for a question that was skipped', async () => {
    serving()
    await askAlbumQuestions(submitting('/recommend', { prompt: 'rainy' }))

    await answerAlbumQuestions(
      submitting('/recommend/refine', { 'option-0': '', 'detail-0': '' }),
    )

    expect(readAlbumFlow()?.answers).toEqual([null])
  })

  it('collects the suggestion the prompt step started', async () => {
    serving()
    await askAlbumQuestions(submitting('/recommend', { prompt: 'rainy' }))

    await answerAlbumQuestions(submitting('/recommend/refine', {}))

    expect(readAlbumFlow()?.suggested?.genres).toEqual(['Jazz'])
  })

  it('sends a deep link with no record behind it back to step one', async () => {
    const answer = await answerAlbumQuestions(
      submitting('/recommend/refine', {}),
    )

    expect(answer.headers.get('Location')).toBe('/recommend')
  })
})

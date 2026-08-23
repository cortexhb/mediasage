import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { server } from '@test'
import { ApiError } from '../request/request.ts'
import { forgetResult, listResults } from './results.ts'

/** A signal no test aborts, for the cases that are not about cancellation. */
function live(): AbortSignal {
  return new AbortController().signal
}

describe('listResults', () => {
  it('answers the page and the total behind it', async () => {
    server.use(
      http.get('/api/results', () =>
        HttpResponse.json({
          results: [{ id: 'a', title: 'One', type: 'prompt_playlist' }],
          total: 41,
        }),
      ),
    )

    const page = await listResults(20, 0, live())

    expect(page.total).toBe(41)
    expect(page.results).toHaveLength(1)
  })

  it('sends the window as query parameters', async () => {
    let asked = ''
    server.use(
      http.get('/api/results', ({ request }) => {
        asked = new URL(request.url).search
        return HttpResponse.json({ results: [], total: 0 })
      }),
    )

    await listResults(20, 40, live())

    expect(asked).toBe('?limit=20&offset=40')
  })

  it('never asks the server to filter, since the chips filter the page', async () => {
    let asked = ''
    server.use(
      http.get('/api/results', ({ request }) => {
        asked = new URL(request.url).search
        return HttpResponse.json({ results: [], total: 0 })
      }),
    )

    await listResults(20, 0, live())

    expect(asked).not.toContain('type')
  })

  it('raises a failed read rather than reporting an empty history', async () => {
    server.use(
      http.get('/api/results', () =>
        HttpResponse.json({ detail: 'database is locked' }, { status: 500 }),
      ),
    )

    await expect(listResults(20, 0, live())).rejects.toBeInstanceOf(ApiError)
  })

  it('drops the read when the caller aborts', async () => {
    const aborter = new AbortController()
    server.use(http.get('/api/results', () => HttpResponse.json({})))
    const reading = listResults(20, 0, aborter.signal)

    aborter.abort()

    await expect(reading).rejects.toThrow()
  })
})

describe('forgetResult', () => {
  it('deletes the one it was given', async () => {
    let path = ''
    server.use(
      http.delete('/api/results/:id', ({ request }) => {
        path = new URL(request.url).pathname
        return new HttpResponse(null, { status: 204 })
      }),
    )

    await forgetResult('p1', live())

    expect(path).toBe('/api/results/p1')
  })

  it('escapes an id that would otherwise reshape the path', async () => {
    let path = ''
    server.use(
      http.delete('/api/results/:id', ({ request }) => {
        path = new URL(request.url).pathname
        return new HttpResponse(null, { status: 204 })
      }),
    )

    await forgetResult('a/b', live())

    expect(path).toBe('/api/results/a%2Fb')
  })

  it('answers nothing, since 204 carries no body', async () => {
    server.use(
      http.delete(
        '/api/results/:id',
        () => new HttpResponse(null, { status: 204 }),
      ),
    )

    await expect(forgetResult('p1', live())).resolves.toBeUndefined()
  })

  it('raises a refusal that is not "already gone"', async () => {
    server.use(
      http.delete('/api/results/:id', () =>
        HttpResponse.json({ detail: 'read-only' }, { status: 500 }),
      ),
    )

    await expect(forgetResult('p1', live())).rejects.toBeInstanceOf(ApiError)
  })
})

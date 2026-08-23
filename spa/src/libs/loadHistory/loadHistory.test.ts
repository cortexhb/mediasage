import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { server } from '@test'
import { loadHistory } from './loadHistory.ts'

/** The loader's argument, as the router hands it over. */
function args(url = 'http://localhost/') {
  return {
    request: new Request(url),
    params: {},
    context: undefined as never,
  }
}

describe('loadHistory', () => {
  it('returns the first page and the total behind it', async () => {
    server.use(
      http.get('/api/results', () =>
        HttpResponse.json({
          results: [{ id: 'a', title: 'One', type: 'prompt_playlist' }],
          total: 41,
        }),
      ),
    )

    const page = await loadHistory(args())

    expect(page).toMatchObject({ total: 41, failed: false })
    expect(page.items).toHaveLength(1)
  })

  it('asks for twenty from the start', async () => {
    let asked = ''
    server.use(
      http.get('/api/results', ({ request }) => {
        asked = new URL(request.url).search
        return HttpResponse.json({ results: [], total: 0 })
      }),
    )

    await loadHistory(args())

    expect(asked).toBe('?limit=20&offset=0')
  })

  it('treats a body with neither field as an empty page', async () => {
    server.use(http.get('/api/results', () => HttpResponse.json({})))

    expect(await loadHistory(args())).toEqual({
      items: [],
      total: 0,
      failed: false,
    })
  })

  it('says it failed rather than throwing, so Home still renders', async () => {
    // Faulting the route would take the greeting and cards down too.
    server.use(
      http.get('/api/results', () =>
        HttpResponse.json({ detail: 'nope' }, { status: 500 }),
      ),
    )

    expect(await loadHistory(args())).toEqual({
      items: [],
      total: 0,
      failed: true,
    })
  })
})

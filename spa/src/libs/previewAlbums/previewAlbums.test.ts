import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { server } from '@test'
import { previewAlbums } from './previewAlbums.ts'

/** The loader as the fetcher calls it, with a query string. */
function asked(query: string): { request: Request } {
  return {
    request: new Request(`http://localhost/recommend/albums/preview?${query}`),
  }
}

/** The preview endpoint, reporting back what it was asked. */
function counting(): () => URLSearchParams {
  let sent = new URLSearchParams()
  server.use(
    http.get('/api/recommend/albums/preview', ({ request }) => {
      sent = new URL(request.url).searchParams
      return HttpResponse.json({ matching_albums: 900, albums_to_send: 500 })
    }),
  )
  return () => sent
}

describe('previewAlbums', () => {
  it('answers the counts', async () => {
    counting()

    expect(await previewAlbums(asked('max_albums=500'))).toEqual({
      matching_albums: 900,
      albums_to_send: 500,
    })
  })

  it('forwards only the filters it was given', async () => {
    const sent = counting()

    await previewAlbums(asked('genres=Jazz&max_albums=500'))

    expect(sent().get('genres')).toBe('Jazz')
    expect(sent().has('decades')).toBe(false)
  })

  it('answers nothing rather than faulting the step', async () => {
    server.use(
      http.get('/api/recommend/albums/preview', () =>
        HttpResponse.json({ detail: 'no' }, { status: 500 }),
      ),
    )

    expect(await previewAlbums(asked('max_albums=500'))).toBeNull()
  })
})

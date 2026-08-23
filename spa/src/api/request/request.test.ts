import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { server } from '@test'
import { ApiError, request, stream } from './request.ts'

/** A signal no test aborts, for the cases that are not about cancellation. */
function live(): AbortSignal {
  return new AbortController().signal
}

describe('request', () => {
  it('returns the parsed body', async () => {
    server.use(
      http.get('/api/health', () => HttpResponse.json({ status: 'healthy' })),
    )

    const body = await request<{ status: string }>('/api/health', {
      signal: live(),
    })

    expect(body).toEqual({ status: 'healthy' })
  })

  it('defaults to GET and sends no body', async () => {
    let sent: { method: string; body: string } | undefined
    server.use(
      http.get('/api/health', async ({ request: sentRequest }) => {
        sent = {
          method: sentRequest.method,
          body: await sentRequest.text(),
        }
        return HttpResponse.json({})
      }),
    )

    await request('/api/health', { signal: live() })

    expect(sent).toEqual({ method: 'GET', body: '' })
  })

  it('sends a body as JSON with its content type', async () => {
    let sent: { type: string | null; body: unknown } | undefined
    server.use(
      http.post('/api/config', async ({ request: sentRequest }) => {
        sent = {
          type: sentRequest.headers.get('Content-Type'),
          body: await sentRequest.json(),
        }
        return HttpResponse.json({})
      }),
    )

    await request('/api/config', {
      method: 'POST',
      body: { llm_provider: 'ollama' },
      signal: live(),
    })

    expect(sent).toEqual({
      type: 'application/json',
      body: { llm_provider: 'ollama' },
    })
  })

  it('answers undefined for a 204', async () => {
    server.use(
      http.delete(
        '/api/results/:id',
        () => new HttpResponse(null, { status: 204 }),
      ),
    )

    const body = await request('/api/results/{result_id}', {
      method: 'DELETE',
      path: { result_id: 'abc' },
      signal: live(),
    })

    expect(body).toBeUndefined()
  })

  describe('addressing', () => {
    it('fills a path placeholder', async () => {
      server.use(
        http.get('/api/art/:key', ({ params }) =>
          HttpResponse.json({ key: params.key }),
        ),
      )

      const body = await request<{ key: string }>('/api/art/{rating_key}', {
        path: { rating_key: '12345' },
        signal: live(),
      })

      expect(body).toEqual({ key: '12345' })
    })

    it('escapes a path value', async () => {
      let seen = ''
      server.use(
        http.get('/api/art/*', ({ request: sentRequest }) => {
          seen = new URL(sentRequest.url).pathname
          return HttpResponse.json({})
        }),
      )

      await request('/api/art/{rating_key}', {
        path: { rating_key: 'a/b c' },
        signal: live(),
      })

      expect(seen).toBe('/api/art/a%2Fb%20c')
    })

    it('appends a query string', async () => {
      let seen = ''
      server.use(
        http.get('/api/results', ({ request: sentRequest }) => {
          seen = new URL(sentRequest.url).search
          return HttpResponse.json({})
        }),
      )

      await request('/api/results', {
        query: { limit: 5, offset: 10 },
        signal: live(),
      })

      expect(seen).toBe('?limit=5&offset=10')
    })

    it('leaves out a query value that is undefined', async () => {
      let seen = ''
      server.use(
        http.get('/api/results', ({ request: sentRequest }) => {
          seen = new URL(sentRequest.url).search
          return HttpResponse.json({})
        }),
      )

      await request('/api/results', {
        query: { limit: 5, type: undefined },
        signal: live(),
      })

      expect(seen).toBe('?limit=5')
    })

    it('sends no question mark when there is nothing to ask', async () => {
      let seen = ''
      server.use(
        http.get('/api/health', ({ request: sentRequest }) => {
          seen = new URL(sentRequest.url).search
          return HttpResponse.json({})
        }),
      )

      await request('/api/health', { query: {}, signal: live() })

      expect(seen).toBe('')
    })
  })

  describe('refusals', () => {
    it('throws ApiError carrying the status', async () => {
      server.use(
        http.get('/api/health', () =>
          HttpResponse.json({ detail: 'Nope' }, { status: 503 }),
        ),
      )

      const failure = await request('/api/health', { signal: live() }).catch(
        (error: unknown) => error,
      )

      expect(failure).toBeInstanceOf(ApiError)
      expect(failure).toHaveProperty('status', 503)
    })

    it('reads a string detail as the message', async () => {
      server.use(
        http.get('/api/health', () =>
          HttpResponse.json({ detail: 'Result not found' }, { status: 404 }),
        ),
      )

      await expect(request('/api/health', { signal: live() })).rejects.toThrow(
        'Result not found',
      )
    })

    it('joins the per-field problems of a 422', async () => {
      server.use(
        http.post('/api/config', () =>
          HttpResponse.json(
            {
              detail: [
                {
                  loc: ['body', 'context_window'],
                  msg: 'too small',
                  type: 'x',
                },
                { loc: ['body', 'endpoint_url'], msg: 'not a url', type: 'y' },
              ],
            },
            { status: 422 },
          ),
        ),
      )

      await expect(
        request('/api/config', { method: 'POST', body: {}, signal: live() }),
      ).rejects.toThrow('too small; not a url')
    })

    it('keeps the whole body for a caller that needs the fields', async () => {
      const detail = [{ loc: ['body', 'x'], msg: 'bad', type: 'y' }]
      server.use(
        http.post('/api/config', () =>
          HttpResponse.json({ detail }, { status: 422 }),
        ),
      )

      const failure = await request('/api/config', {
        method: 'POST',
        body: {},
        signal: live(),
      }).catch((error: unknown) => error)

      expect(failure).toHaveProperty('body', { detail })
    })

    it('falls back to the status line when the body explains nothing', async () => {
      server.use(
        http.get(
          '/api/health',
          () => new HttpResponse('<html>502</html>', { status: 502 }),
        ),
      )

      const failure = await request('/api/health', { signal: live() }).catch(
        (error: unknown) => error,
      )

      expect((failure as ApiError).message).toContain('502')
    })

    it('does not throw ApiError when the network itself fails', async () => {
      server.use(http.get('/api/health', () => HttpResponse.error()))

      const failure = await request('/api/health', { signal: live() }).catch(
        (error: unknown) => error,
      )

      // A server that is down is not a refusal.
      expect(failure).toBeInstanceOf(Error)
      expect(failure).not.toBeInstanceOf(ApiError)
    })
  })

  describe('cancellation', () => {
    it('passes the signal to fetch', async () => {
      server.use(
        http.get('/api/health', () => HttpResponse.json({ status: 'healthy' })),
      )
      const aborter = new AbortController()
      aborter.abort()

      const failure = await request('/api/health', {
        signal: aborter.signal,
      }).catch((error: unknown) => error)

      expect(failure).toHaveProperty('name', 'AbortError')
    })

    it('lets an abort through rather than dressing it as a refusal', async () => {
      server.use(
        http.get('/api/health', () => HttpResponse.json({ status: 'healthy' })),
      )
      const aborter = new AbortController()
      aborter.abort()

      const failure = await request('/api/health', {
        signal: aborter.signal,
      }).catch((error: unknown) => error)

      expect(failure).toBeInstanceOf(Error)
      expect(failure).not.toBeInstanceOf(ApiError)
    })
  })
})

describe('stream', () => {
  it('hands back the body unread', async () => {
    server.use(
      http.post('/api/generate/stream', () =>
        HttpResponse.text('event: progress\ndata: {}\n\n', {
          headers: { 'Content-Type': 'text/event-stream' },
        }),
      ),
    )

    const body = await stream('/api/generate/stream', {
      method: 'POST',
      body: { prompt: 'rainy monday' },
      signal: live(),
    })

    expect(body).toBeInstanceOf(ReadableStream)
  })

  it('refuses before the first frame when the request is rejected', async () => {
    server.use(
      http.post('/api/generate/stream', () =>
        HttpResponse.json({ detail: 'No tracks match' }, { status: 400 }),
      ),
    )

    await expect(
      stream('/api/generate/stream', {
        method: 'POST',
        body: {},
        signal: live(),
      }),
    ).rejects.toThrow('No tracks match')
  })
})

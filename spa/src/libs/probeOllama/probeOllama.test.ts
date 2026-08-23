import { http, HttpResponse } from 'msw'
import type { LoaderFunctionArgs } from 'react-router'
import { describe, expect, it } from 'vitest'

import { server } from '@test'
import { probeOllama } from './probeOllama.ts'

/** The loader's argument, carrying whatever the form asked about. */
function args(query: string): LoaderFunctionArgs {
  const request = new Request(`http://localhost/settings/ollama?${query}`)
  return {
    request,
    url: new URL(request.url),
    pattern: '/settings/ollama',
    params: {},
    context: undefined as never,
  }
}

/** A server holding `models`, each with the same context window. */
function ollama(models: string[], contextWindow = 8192) {
  server.use(
    http.get('/api/ollama/status', () =>
      HttpResponse.json({ connected: true, model_count: models.length }),
    ),
    http.get('/api/ollama/models', () =>
      HttpResponse.json({ models: models.map((name) => ({ name })) }),
    ),
    http.get('/api/ollama/model-info', ({ request }) =>
      HttpResponse.json({
        name: new URL(request.url).searchParams.get('model'),
        context_window: contextWindow,
      }),
    ),
  )
}

describe('probeOllama', () => {
  it('asks nothing when no address was given', async () => {
    const probe = await probeOllama(args('url='))

    expect(probe).toEqual({
      connected: false,
      message: '',
      models: [],
      contextWindow: undefined,
    })
  })

  describe('given an address', () => {
    it('reports the server and what it holds', async () => {
      ollama(['qwen3:8b', 'llama3:70b'])

      const probe = await probeOllama(args('url=http://box:11434'))

      expect(probe.connected).toBe(true)
      expect(probe.message).toBe('Connected (2 models)')
      expect(probe.models).toEqual(['qwen3:8b', 'llama3:70b'])
    })

    it('passes the address through rather than using the saved one', async () => {
      let asked: string | null = null
      server.use(
        http.get('/api/ollama/status', ({ request }) => {
          asked = new URL(request.url).searchParams.get('url')
          return HttpResponse.json({ connected: true, model_count: 1 })
        }),
        http.get('/api/ollama/models', () =>
          HttpResponse.json({ models: [{ name: 'qwen3:8b' }] }),
        ),
        http.get('/api/ollama/model-info', () =>
          HttpResponse.json({ name: 'qwen3:8b', context_window: 8192 }),
        ),
      )

      await probeOllama(args('url=http://box:11434'))

      expect(asked).toBe('http://box:11434')
    })

    it('reports why a server refused', async () => {
      server.use(
        http.get('/api/ollama/status', () =>
          HttpResponse.json({ connected: false, error: 'connection refused' }),
        ),
      )

      const probe = await probeOllama(args('url=http://box:11434'))

      expect(probe).toMatchObject({
        connected: false,
        message: 'connection refused',
        models: [],
      })
    })

    it('does not list models a refused server cannot have', async () => {
      let listed = false
      server.use(
        http.get('/api/ollama/status', () =>
          HttpResponse.json({ connected: false, error: 'down' }),
        ),
        http.get('/api/ollama/models', () => {
          listed = true
          return HttpResponse.json({ models: [] })
        }),
      )

      await probeOllama(args('url=http://box:11434'))

      expect(listed).toBe(false)
    })

    it('treats a server with nothing pulled as unusable', async () => {
      server.use(
        http.get('/api/ollama/status', () =>
          HttpResponse.json({ connected: true, model_count: 0 }),
        ),
      )

      const probe = await probeOllama(args('url=http://box:11434'))

      expect(probe.connected).toBe(false)
      expect(probe.message).toBe('No models installed')
    })

    it('reports a failed request rather than throwing it at the boundary', async () => {
      // A half-typed address must not replace the settings form.
      server.use(http.get('/api/ollama/status', () => HttpResponse.error()))

      const probe = await probeOllama(args('url=http://ba'))

      expect(probe).toMatchObject({
        connected: false,
        message: 'Connection failed',
      })
    })
  })

  describe('the context window', () => {
    it('is reported for the model asked about', async () => {
      let asked: string | null = null
      ollama(['qwen3:8b', 'llama3:70b'])
      server.use(
        http.get('/api/ollama/model-info', ({ request }) => {
          asked = new URL(request.url).searchParams.get('model')
          return HttpResponse.json({ name: asked, context_window: 40960 })
        }),
      )

      const probe = await probeOllama(
        args('url=http://box:11434&want=llama3:70b'),
      )

      expect(asked).toBe('llama3:70b')
      expect(probe.contextWindow).toBe(40960)
    })

    it('describes nothing when only the generation model survived', async () => {
      // The analysis select is left empty, so no window is in force.
      let asked = false
      ollama(['llama3:70b'])
      server.use(
        http.get('/api/ollama/model-info', () => {
          asked = true
          return HttpResponse.json({
            name: 'llama3:70b',
            context_window: 40960,
          })
        }),
      )

      const probe = await probeOllama(
        args('url=http://box:11434&want=gone&alt=llama3:70b'),
      )

      expect(asked).toBe(false)
      expect(probe.described).toBeUndefined()
      expect(probe.contextWindow).toBeUndefined()
    })

    it.each([
      ['nothing is configured', 'want=&alt='],
      ['neither saved model survived', 'want=gone&alt=also-gone'],
    ])('describes the first model when %s', async (_case, asked) => {
      ollama(['llama3:70b'], 40960)

      const probe = await probeOllama(args(`url=http://box:11434&${asked}`))

      expect(probe.described).toBe('llama3:70b')
      expect(probe.contextWindow).toBe(40960)
    })

    it('is absent for a model the server cannot describe', async () => {
      ollama(['qwen3:8b'])
      server.use(
        http.get('/api/ollama/model-info', () =>
          HttpResponse.json({ name: 'qwen3:8b', context_window: null }),
        ),
      )

      const probe = await probeOllama(
        args('url=http://box:11434&want=qwen3:8b'),
      )

      expect(probe.contextWindow).toBeUndefined()
    })

    it('does not cost the models a server did answer for', async () => {
      // The endpoint stays usable; only the discovered figure is lost.
      ollama(['qwen3:8b'])
      server.use(
        http.get('/api/ollama/model-info', () =>
          HttpResponse.json({ detail: 'Model not found' }, { status: 404 }),
        ),
      )

      const probe = await probeOllama(
        args('url=http://box:11434&want=qwen3:8b'),
      )

      expect(probe.contextWindow).toBeUndefined()
      expect(probe.connected).toBe(true)
      expect(probe.models).toEqual(['qwen3:8b'])
    })
  })
})

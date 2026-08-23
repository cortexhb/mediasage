import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { server } from '@test'
import { ApiError } from '../request/request.ts'
import {
  listOllamaModels,
  readConfig,
  readOllamaModelInfo,
  readOllamaStatus,
  readSetupStatus,
  saveConfig,
} from './config.ts'

/** A signal no test aborts, for the cases that are not about cancellation. */
function live(): AbortSignal {
  return new AbortController().signal
}

describe('readConfig', () => {
  it('answers the settings the API reports', async () => {
    server.use(
      http.get('/api/config', () =>
        HttpResponse.json({ plex_url: 'http://plex:32400' }),
      ),
    )

    const config = await readConfig(live())

    expect(config).toHaveProperty('plex_url', 'http://plex:32400')
  })
})

describe('saveConfig', () => {
  it('posts the changes as JSON', async () => {
    let sent: unknown
    server.use(
      http.post('/api/config', async ({ request }) => {
        sent = await request.json()
        return HttpResponse.json({})
      }),
    )

    await saveConfig({ llm_provider: 'ollama', context_window: 32768 }, live())

    expect(sent).toEqual({ llm_provider: 'ollama', context_window: 32768 })
  })

  it('sends a zero rather than dropping it', async () => {
    // `changes()` filters on presence, so a zero cost must survive the wire.
    let sent: unknown
    server.use(
      http.post('/api/config', async ({ request }) => {
        sent = await request.json()
        return HttpResponse.json({})
      }),
    )

    await saveConfig({ cost_analysis_input: 0 }, live())

    expect(sent).toEqual({ cost_analysis_input: 0 })
  })

  it('raises the refusal a probe reported', async () => {
    server.use(
      http.post('/api/config', () =>
        HttpResponse.json(
          { detail: 'Model not found on the server' },
          { status: 422 },
        ),
      ),
    )

    const failure = await saveConfig({ model_analysis: 'nope' }, live()).catch(
      (error: unknown) => error,
    )

    expect(failure).toBeInstanceOf(ApiError)
    expect(failure).toHaveProperty('status', 422)
    expect((failure as ApiError).message).toBe('Model not found on the server')
  })
})

describe('readSetupStatus', () => {
  it('answers what settings needs and /api/config does not carry', async () => {
    server.use(
      http.get('/api/setup/status', () =>
        HttpResponse.json({
          data_dir_writable: true,
          plex_connected: true,
          llm_configured: true,
          library_synced: true,
          music_libraries: ['Music', 'Vinyl'],
          llm_from_env: true,
        }),
      ),
    )

    const status = await readSetupStatus(live())

    expect(status.music_libraries).toEqual(['Music', 'Vinyl'])
    expect(status.llm_from_env).toBe(true)
  })
})

describe('the ollama endpoints', () => {
  it('probes a url that has not been saved', async () => {
    let seen = ''
    server.use(
      http.get('/api/ollama/status', ({ request }) => {
        seen = new URL(request.url).searchParams.get('url') ?? ''
        return HttpResponse.json({ connected: true, model_count: 3 })
      }),
    )

    const status = await readOllamaStatus('http://box:11434', live())

    expect(seen).toBe('http://box:11434')
    expect(status.connected).toBe(true)
  })

  it('falls back to the configured endpoint on an empty url', async () => {
    let seen: string | null = 'unset'
    server.use(
      http.get('/api/ollama/status', ({ request }) => {
        seen = new URL(request.url).searchParams.get('url')
        return HttpResponse.json({ connected: false })
      }),
    )

    await readOllamaStatus('', live())

    expect(seen).toBe('')
  })

  it('lists what the server has pulled', async () => {
    server.use(
      http.get('/api/ollama/models', () =>
        HttpResponse.json({ models: [{ name: 'qwen3:8b' }] }),
      ),
    )

    const listed = await listOllamaModels('http://box:11434', live())

    expect(listed.models).toEqual([{ name: 'qwen3:8b' }])
  })

  it('reports a listing failure in the body rather than as a refusal', async () => {
    // A server that is down is a 200 carrying an error string.
    server.use(
      http.get('/api/ollama/models', () =>
        HttpResponse.json({ models: [], error: 'connection refused' }),
      ),
    )

    const listed = await listOllamaModels('http://box:11434', live())

    expect(listed.error).toBe('connection refused')
  })

  it('asks for one model by name', async () => {
    let seen: Record<string, string> = {}
    server.use(
      http.get('/api/ollama/model-info', ({ request }) => {
        seen = Object.fromEntries(new URL(request.url).searchParams)
        return HttpResponse.json({ name: 'qwen3:8b', context_window: 40960 })
      }),
    )

    const info = await readOllamaModelInfo(
      'http://box:11434',
      'qwen3:8b',
      live(),
    )

    expect(seen).toEqual({ url: 'http://box:11434', model: 'qwen3:8b' })
    expect(info.context_window).toBe(40960)
  })

  it('raises for a model the server does not have', async () => {
    server.use(
      http.get('/api/ollama/model-info', () =>
        HttpResponse.json(
          { detail: "Model 'gone' not found" },
          { status: 404 },
        ),
      ),
    )

    const failure = await readOllamaModelInfo('', 'gone', live()).catch(
      (error: unknown) => error,
    )

    expect(failure).toBeInstanceOf(ApiError)
    expect(failure).toHaveProperty('status', 404)
  })
})

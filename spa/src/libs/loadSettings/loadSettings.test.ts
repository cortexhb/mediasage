import { http, HttpResponse } from 'msw'
import type { LoaderFunctionArgs } from 'react-router'
import { describe, expect, it } from 'vitest'

import { server } from '@test'
import { loadSettings } from './loadSettings.ts'

/** The settings a backend with nothing unusual about it reports. */
const CONFIG = {
  version: '1.0.0',
  plex_url: 'http://plex:32400',
  plex_connected: true,
  plex_token_set: true,
  music_library: 'Music',
  llm_provider: 'anthropic',
  llm_configured: true,
  llm_api_key_set: true,
  model_analysis: 'claude',
  model_generation: 'claude',
  max_tracks_to_ai: 500,
  max_albums_to_ai: 100,
  defaults: { track_count: 25 },
  context_window: 200000,
}

const SETUP = {
  data_dir_writable: true,
  plex_connected: true,
  llm_configured: true,
  library_synced: true,
  music_libraries: ['Music'],
}

/** The loader's argument, which only ever reads `request`. */
function args(): LoaderFunctionArgs {
  const request = new Request('http://localhost/settings')
  return {
    request,
    url: new URL(request.url),
    pattern: '/settings',
    params: {},
    context: undefined as never,
  }
}

/** Answer every read a load makes, with optional overrides. */
function backend(config: object = {}, setup: object = {}) {
  server.use(
    http.get('/api/config', () => HttpResponse.json({ ...CONFIG, ...config })),
    http.get('/api/setup/status', () =>
      HttpResponse.json({ ...SETUP, ...setup }),
    ),
  )
}

describe('loadSettings', () => {
  it('reads the settings and the setup status together', async () => {
    backend()

    const data = await loadSettings(args())

    expect(data.config.plex_url).toBe('http://plex:32400')
    expect(data.setup.music_libraries).toEqual(['Music'])
  })

  it('reads both at once rather than one after the other', async () => {
    let open = 0
    let overlapped = false
    server.use(
      http.get('/api/config', async () => {
        open += 1
        await new Promise((resolve) => setTimeout(resolve, 5))
        overlapped ||= open > 1
        open -= 1
        return HttpResponse.json(CONFIG)
      }),
      http.get('/api/setup/status', () => {
        open += 1
        overlapped ||= open > 1
        open -= 1
        return HttpResponse.json(SETUP)
      }),
    )

    await loadSettings(args())

    expect(overlapped).toBe(true)
  })

  it('leaves the library counts to their own route, so a save never waits', async () => {
    let asked = false
    backend()
    server.use(
      http.get('/api/library/stats/cached', () => {
        asked = true
        return HttpResponse.json({ total_tracks: 0, genres: [], decades: [] })
      }),
    )

    await loadSettings(args())

    expect(asked).toBe(false)
  })

  it('asks no Ollama server anything, whoever the provider is', async () => {
    // The form probes the endpoint in the field, not the saved one.
    let asked = false
    backend({ llm_provider: 'ollama' })
    server.use(
      http.get('/api/ollama/models', () => {
        asked = true
        return HttpResponse.json({ models: [] })
      }),
      http.get('/api/ollama/status', () => {
        asked = true
        return HttpResponse.json({ connected: true })
      }),
    )

    const data = await loadSettings(args())

    expect(asked).toBe(false)
    expect(data.config.llm_provider).toBe('ollama')
  })

  it('lets a failed read reach the error boundary', async () => {
    server.use(
      http.get('/api/config', () =>
        HttpResponse.json({ detail: 'No API' }, { status: 503 }),
      ),
      http.get('/api/setup/status', () => HttpResponse.json(SETUP)),
    )

    await expect(loadSettings(args())).rejects.toThrow('No API')
  })
})

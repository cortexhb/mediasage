import { http, HttpResponse } from 'msw'
import type { LoaderFunctionArgs } from 'react-router'
import { describe, expect, it } from 'vitest'

import { CONFIG, SETUP, configWith, server } from '@test'
import { loadSettings } from './loadSettings.ts'

/** Enough of the document for the loader to read fields out of it. */
const SCHEMA = {
  components: {
    schemas: {
      BudgetPatch: {
        properties: {
          tokens_per_track: {
            anyOf: [{ type: 'integer', exclusiveMinimum: 0 }, { type: 'null' }],
            title: 'Tokens Per Track',
          },
        },
      },
    },
  },
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

/** Answer every read a load makes, with an optional replacement config. */
function backend(config: object = CONFIG, setup: object = {}) {
  server.use(
    http.get('/api/config', () => HttpResponse.json(config)),
    http.get('/api/setup/status', () =>
      HttpResponse.json({ ...SETUP, ...setup }),
    ),
    http.get('/openapi.json', () => HttpResponse.json(SCHEMA)),
  )
}

describe('loadSettings', () => {
  it('reads the settings and the setup status together', async () => {
    backend()

    const data = await loadSettings(args())

    expect(data.config.sections.plex?.server_name).toBe('Living Room')
    expect(data.setup.music_libraries).toEqual(['Music'])
  })

  it('reads the fields the form draws out of the API schema', async () => {
    backend()

    const data = await loadSettings(args())

    expect(data.fields).toContainEqual(
      expect.objectContaining({
        name: 'budget.tokens_per_track',
        kind: 'number',
      }),
    )
  })

  it('reads them all at once rather than one after another', async () => {
    let open = 0
    let overlapped = false
    const count = async <T>(answer: T): Promise<T> => {
      open += 1
      await new Promise((resolve) => setTimeout(resolve, 5))
      overlapped ||= open > 1
      open -= 1
      return answer
    }
    server.use(
      http.get('/api/config', async () =>
        HttpResponse.json(await count(CONFIG)),
      ),
      http.get('/api/setup/status', async () =>
        HttpResponse.json(await count(SETUP)),
      ),
      http.get('/openapi.json', async () =>
        HttpResponse.json(await count(SCHEMA)),
      ),
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
    backend(
      configWith({
        llm: {
          provider: 'ollama',
          endpoint_url: 'http://ollama:11434',
          context_window: 32768,
        },
      }),
    )
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
    expect(data.config.sections.llm.provider).toBe('ollama')
  })

  it('lets a failed read reach the error boundary', async () => {
    server.use(
      http.get('/api/config', () =>
        HttpResponse.json({ detail: 'No API' }, { status: 503 }),
      ),
      http.get('/api/setup/status', () => HttpResponse.json(SETUP)),
      http.get('/openapi.json', () => HttpResponse.json(SCHEMA)),
    )

    await expect(loadSettings(args())).rejects.toThrow('No API')
  })
})

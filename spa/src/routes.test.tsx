import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { beforeEach, describe, expect, it } from 'vitest'

import { server } from '@test'
import { routes } from './routes.ts'

/** A synced library, for the footer the shell carries on every route. */
const SYNCED = {
  track_count: 1200,
  synced_at: '2026-08-23T09:00:00Z',
  is_syncing: false,
  plex_connected: true,
}

/** Enough of `/api/config` for the settings page to render. */
const CONFIG = {
  version: '1.0.0',
  plex_connected: true,
  plex_linked: true,
  plex_server_name: 'Living Room',
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

/** The real route table, entered at a path. */
function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  return render(<RouterProvider router={router} />)
}

describe('routes', () => {
  beforeEach(() => {
    server.use(
      http.get('/api/library/status', () => HttpResponse.json(SYNCED)),
      http.get('/api/results', () =>
        HttpResponse.json({ results: [], total: 0 }),
      ),
    )
  })

  it('answers an unmatched path with the not-found page', () => {
    renderAt('/nowhere')

    expect(
      screen.getByRole('heading', { name: 'Page not found' }),
    ).toBeVisible()
  })

  it('keeps the shell around a not-found page', () => {
    // The header is how a wrong address is recoverable without the back
    // button.
    renderAt('/nowhere')

    expect(
      screen.getByRole('navigation', { name: 'Main navigation' }),
    ).toBeVisible()
  })

  it('loads settings from the API and renders them', async () => {
    server.use(
      http.get('/api/config', () => HttpResponse.json(CONFIG)),
      http.get('/api/setup/status', () => HttpResponse.json(SETUP)),
      http.get('/api/library/stats/cached', () =>
        HttpResponse.json({ total_tracks: 0, genres: [], decades: [] }),
      ),
      http.get('/api/library/status', () =>
        HttpResponse.json({
          track_count: 12,
          is_syncing: false,
          plex_connected: true,
        }),
      ),
    )

    renderAt('/settings')

    expect(await screen.findByText('Connected to Living Room')).toBeVisible()
  })

  it('keeps the shell when a page loader fails', async () => {
    // The boundary sits on the shell, so the header survives the failure.
    server.use(
      http.get('/api/config', () =>
        HttpResponse.json({ detail: 'No API' }, { status: 503 }),
      ),
      http.get('/api/setup/status', () => HttpResponse.json(SETUP)),
    )

    renderAt('/settings')

    expect(await screen.findByRole('alert')).toHaveTextContent('No API')
    expect(
      screen.getByRole('navigation', { name: 'Main navigation' }),
    ).toBeVisible()
  })

  it('finishes a save without waiting on the library counts', async () => {
    // A navigation awaits its revalidating fetchers, so a counts read left
    // revalidating held the button on "Saving…" for as long as Plex took.
    const user = userEvent.setup()
    let reads = 0
    server.use(
      http.get('/api/config', () => HttpResponse.json(CONFIG)),
      http.post('/api/config', () => HttpResponse.json(CONFIG)),
      http.get('/api/setup/status', () => HttpResponse.json(SETUP)),
      http.get('/api/library/stats/cached', () => {
        reads += 1
        return HttpResponse.json({ total_tracks: 0, genres: [], decades: [] })
      }),
      http.get('/api/library/status', () =>
        HttpResponse.json({
          track_count: 12,
          is_syncing: false,
          plex_connected: true,
        }),
      ),
    )

    renderAt('/settings')
    await user.click(
      await screen.findByRole('button', { name: 'Save Settings' }),
    )

    expect(
      await screen.findByRole('button', { name: 'Save Settings' }),
    ).toBeEnabled()
    expect(reads).toBe(1)
  })

  it('probes an Ollama endpoint the settings form has not saved', async () => {
    // Reached through a fetcher; the route has no page.
    server.use(
      http.get('/api/config', () =>
        HttpResponse.json({ ...CONFIG, llm_provider: 'ollama' }),
      ),
      http.get('/api/setup/status', () => HttpResponse.json(SETUP)),
      http.get('/api/library/stats/cached', () =>
        HttpResponse.json({ total_tracks: 0, genres: [], decades: [] }),
      ),
      http.get('/api/library/status', () =>
        HttpResponse.json({
          track_count: 12,
          is_syncing: false,
          plex_connected: true,
        }),
      ),
      http.get('/api/ollama/status', () =>
        HttpResponse.json({ connected: true, model_count: 1 }),
      ),
      http.get('/api/ollama/models', () =>
        HttpResponse.json({ models: [{ name: 'qwen3:8b' }] }),
      ),
      http.get('/api/ollama/model-info', () =>
        HttpResponse.json({ name: 'qwen3:8b', context_window: 40960 }),
      ),
    )

    renderAt('/settings')

    expect(await screen.findByText(/Connected \(1 models\)/)).toBeVisible()
    expect(await screen.findByText(/40,960 tokens/)).toBeVisible()
  })
})

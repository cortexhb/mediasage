import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { describe, expect, it } from 'vitest'

import { server } from '@test'
import type { SettingsData } from '../../libs/loadSettings/loadSettings.ts'
import { Settings } from './Settings.tsx'

/** What a configured deployment loads. */
const DATA: SettingsData = {
  config: {
    version: '1.0.0',
    plex_connected: true,
    plex_linked: true,
    plex_server_name: 'Living Room',
    plex_server_id: 'abc123',
    music_library: 'Music',
    llm_provider: 'anthropic',
    llm_configured: true,
    llm_api_key_set: true,
    model_analysis: 'claude-opus',
    model_generation: 'claude-haiku',
    max_tracks_to_ai: 500,
    max_albums_to_ai: 100,
    defaults: { track_count: 25 },
    context_window: 200000,
  },
  setup: {
    data_dir_writable: true,
    plex_connected: true,
    llm_configured: true,
    library_synced: true,
    music_libraries: ['Music'],
  },
}

/** What a synced library reports, on the route the Plex card fetches. */
const STATS = {
  total_tracks: 52341,
  genres: [{ name: 'Rock', count: 900 }],
  decades: [{ name: '1980s', count: 620 }],
}

/** The page on its own route, with the loader stubbed. */
function renderPage(data: SettingsData = DATA) {
  const router = createMemoryRouter([
    { path: '/', Component: Settings, loader: () => data },
    { path: 'settings/stats', loader: () => STATS },
  ])
  return render(<RouterProvider router={router} />)
}

/** Answer the save and the status re-read that follows it. */
function backend(config: object = {}, setup: object = {}) {
  server.use(
    http.post('/api/config', () =>
      HttpResponse.json({ ...DATA.config, ...config }),
    ),
    http.get('/api/setup/status', () =>
      HttpResponse.json({ ...DATA.setup, ...setup }),
    ),
  )
}

/** Click Save, once the page has painted. */
async function saveWith(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole('button', { name: 'Save Settings' }))
}

describe('Settings', () => {
  it('titles itself under the shell heading', async () => {
    renderPage()

    expect(
      await screen.findByRole('heading', { level: 2, name: 'Settings' }),
    ).toBeVisible()
  })

  it('shows both halves of the configuration', async () => {
    renderPage()

    expect(
      await screen.findByRole('heading', { name: 'Plex Connection' }),
    ).toBeVisible()
    expect(screen.getByRole('heading', { name: 'LLM Provider' })).toBeVisible()
  })

  it('says nothing about storage when the directory is writable', async () => {
    renderPage()

    await screen.findByRole('button', { name: 'Save Settings' })
    expect(
      screen.queryByRole('heading', { name: 'Storage' }),
    ).not.toBeInTheDocument()
  })

  it('warns when it is not', async () => {
    renderPage({
      ...DATA,
      setup: {
        ...DATA.setup,
        data_dir_writable: false,
        data_dir: '/data',
        process_uid: 1000,
        process_gid: 1000,
      },
    })

    expect(await screen.findByRole('alert')).toHaveTextContent(
      '/data is not writable',
    )
  })

  describe('saving', () => {
    it('posts the whole form, not just what changed on screen', async () => {
      const user = userEvent.setup()
      let sent: unknown
      server.use(
        http.post('/api/config', async ({ request }) => {
          sent = await request.json()
          return HttpResponse.json(DATA.config)
        }),
        http.get('/api/setup/status', () => HttpResponse.json(DATA.setup)),
      )

      renderPage()
      await saveWith(user)

      await screen.findByText('Settings saved')
      expect(sent).toMatchObject({ music_library: 'Music' })
    })

    it('navigates nowhere, so nothing else reloads with it', async () => {
      // A route action would be a navigation, and a navigation waits on
      // every active fetcher before it goes idle.
      const user = userEvent.setup()
      let reads = 0
      backend()
      server.use(
        http.get('/api/library/stats/cached', () => {
          reads += 1
          return HttpResponse.json({ total_tracks: 0, genres: [], decades: [] })
        }),
      )

      renderPage()
      await saveWith(user)

      await screen.findByText('Settings saved')
      expect(reads).toBe(0)
    })

    it('reports a refusal as an error, not as a save', async () => {
      const user = userEvent.setup()
      server.use(
        http.post('/api/config', () =>
          HttpResponse.json({ detail: 'Model not found' }, { status: 422 }),
        ),
      )

      renderPage()
      await saveWith(user)

      expect(await screen.findByRole('alert')).toHaveTextContent(
        'Model not found',
      )
    })

    it('says nothing about a save before one is made', async () => {
      renderPage()

      await screen.findByRole('button', { name: 'Save Settings' })
      expect(screen.queryByText('Settings saved')).not.toBeInTheDocument()
    })

    it('blocks a second submit while the first is in flight', async () => {
      const user = userEvent.setup()
      let release!: () => void
      const held = new Promise<void>((resolve) => {
        release = resolve
      })
      server.use(
        http.post('/api/config', async () => {
          await held
          return HttpResponse.json(DATA.config)
        }),
      )

      renderPage()
      await saveWith(user)

      expect(
        await screen.findByRole('button', { name: 'Saving…' }),
      ).toBeDisabled()
      release()
    })

    it('says what the wait is for, since the button is below the fold', async () => {
      const user = userEvent.setup()
      let release!: () => void
      const held = new Promise<void>((resolve) => {
        release = resolve
      })
      server.use(
        http.post('/api/config', async () => {
          await held
          return HttpResponse.json(DATA.config)
        }),
      )

      renderPage()
      await saveWith(user)

      // By text: the Plex and provider cards carry statuses too.
      expect(
        await screen.findByText(/Checking Plex and the provider/),
      ).toBeVisible()
      release()
    })

    it('marks the form busy, so the fields read as out of reach', async () => {
      const user = userEvent.setup()
      let release!: () => void
      const held = new Promise<void>((resolve) => {
        release = resolve
      })
      server.use(
        http.post('/api/config', async () => {
          await held
          return HttpResponse.json(DATA.config)
        }),
      )

      renderPage()
      await saveWith(user)

      expect(await screen.findByRole('form')).toHaveAttribute(
        'aria-busy',
        'true',
      )
      release()
    })

    it('clears the stored credentials, so a later save cannot resend them', async () => {
      const user = userEvent.setup()
      backend()

      renderPage()
      const key = await screen.findByLabelText('API Key')
      await user.type(key, 'sk-a-real-key')
      await saveWith(user)

      await screen.findByText('Settings saved')
      expect(key).toHaveValue('')
    })

    it('adopts what was kept, so the library list follows a Plex change', async () => {
      const user = userEvent.setup()
      backend({}, { music_libraries: ['Music', 'Vinyl'] })

      renderPage()
      await saveWith(user)

      await screen.findByText('Settings saved')
      expect(
        await screen.findByRole('option', { name: 'Vinyl' }),
      ).toBeInTheDocument()
    })
  })
})

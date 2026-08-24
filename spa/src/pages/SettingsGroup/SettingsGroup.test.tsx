import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { createMemoryRouter, Outlet, RouterProvider } from 'react-router'
import { describe, expect, it } from 'vitest'

import { CONFIG, FIELDS, SETUP, server } from '@test'
import { LibrarySyncProvider } from '../../components/organisms/LibrarySyncProvider/LibrarySyncProvider.tsx'
import type { SettingsData } from '../../libs/loadSettings/loadSettings.ts'
import type { PatchField } from '../../libs/patchFields/patchFields.ts'
import { SettingsGroup } from './SettingsGroup.tsx'

/** What a configured deployment loads. */
const DATA: SettingsData = { config: CONFIG, setup: SETUP, fields: FIELDS }

/** What a synced library reports, on the route the Plex card fetches. */
const STATS = {
  total_tracks: 52341,
  genres: [{ name: 'Rock', count: 900 }],
  decades: [{ name: '1980s', count: 620 }],
}

/**
 * One group on its own route, under a parent that hands down the load.
 *
 * The provider stands in for the shell, which owns the sync poller the Plex
 * card's sync button reads.
 */
function renderGroup(slug = 'ai', data: SettingsData = DATA) {
  server.use(
    http.get('/api/library/status', () =>
      HttpResponse.json({
        track_count: STATS.total_tracks,
        synced_at: '2026-01-01T00:00:00Z',
        is_syncing: false,
        plex_connected: true,
      }),
    ),
  )
  const router = createMemoryRouter(
    [
      {
        path: '/settings',
        Component: () => (
          <LibrarySyncProvider>
            <Outlet context={data} />
          </LibrarySyncProvider>
        ),
        children: [{ path: ':group', Component: SettingsGroup }],
      },
      { path: '/settings/stats', loader: () => STATS },
    ],
    { initialEntries: [`/settings/${slug}`] },
  )
  return render(<RouterProvider router={router} />)
}

/** Answer the save and the status re-read that follows it. */
function backend(config: object = {}, setup: object = {}) {
  server.use(
    http.post('/api/config', () => HttpResponse.json({ ...CONFIG, ...config })),
    http.get('/api/setup/status', () =>
      HttpResponse.json({ ...SETUP, ...setup }),
    ),
  )
}

/** Click the group's save button, once the pane has painted. */
async function saveWith(
  user: ReturnType<typeof userEvent.setup>,
  name = 'Save AI Provider',
) {
  await user.click(await screen.findByRole('button', { name }))
}

/** A save that does not answer until the returned release is called. */
function held(): () => void {
  let release!: () => void
  const answer = new Promise<void>((resolve) => {
    release = resolve
  })
  server.use(
    http.post('/api/config', async () => {
      await answer
      return HttpResponse.json(CONFIG)
    }),
  )
  return release
}

describe('SettingsGroup', () => {
  it('names the group it is showing', async () => {
    renderGroup()

    expect(
      await screen.findByRole('heading', { level: 3, name: 'AI Provider' }),
    ).toBeVisible()
  })

  it('saves that group alone, so the button says which', async () => {
    renderGroup('plex')

    expect(
      await screen.findByRole('button', { name: 'Save Plex' }),
    ).toBeVisible()
  })

  it('draws the hand-written organism the group asks for', async () => {
    renderGroup('plex')

    expect(
      await screen.findByRole('heading', { name: 'Plex Connection' }),
    ).toBeVisible()
  })

  it('is a 404 for a group the rail does not offer', async () => {
    renderGroup('nonesuch')

    expect(
      await screen.findByRole('heading', { name: 'Page not found' }),
    ).toBeVisible()
  })

  describe('the fields the schema declares', () => {
    /** One field in a section no organism draws. */
    const COUNT: PatchField = {
      section: 'defaults',
      field: 'track_count',
      name: 'defaults.track_count',
      label: 'Track Count',
      kind: 'number',
      hint: 'How many tracks a playlist asks for.',
      min: 1,
      max: 200,
      step: 1,
    }

    it('renders one input per field, filled from the held settings', async () => {
      renderGroup('recommend', { ...DATA, fields: [COUNT] })

      expect(await screen.findByLabelText('Track Count')).toHaveValue(25)
    })

    it('carries the hint, which is the only documentation on the page', async () => {
      renderGroup('recommend', { ...DATA, fields: [COUNT] })

      expect(
        await screen.findByText('How many tracks a playlist asks for.'),
      ).toBeVisible()
    })

    it('leaves out what an organism above it already draws', async () => {
      // `plex.music_library` is bespoke, so the generated pass must skip it.
      renderGroup('plex')

      expect(await screen.findAllByLabelText('Music Library')).toHaveLength(1)
    })
  })

  describe('saving', () => {
    it('posts the whole group, not just what changed on screen', async () => {
      const user = userEvent.setup()
      let sent: unknown
      server.use(
        http.post('/api/config', async ({ request }) => {
          sent = await request.json()
          return HttpResponse.json(CONFIG)
        }),
        http.get('/api/setup/status', () => HttpResponse.json(SETUP)),
      )

      renderGroup('plex')
      await saveWith(user, 'Save Plex')

      await screen.findByText('Settings saved')
      expect(sent).toMatchObject({ plex: { music_library: 'Music' } })
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

      renderGroup()
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

      renderGroup()
      await saveWith(user)

      expect(await screen.findByRole('alert')).toHaveTextContent(
        'Model not found',
      )
    })

    it('says nothing about a save before one is made', async () => {
      renderGroup()

      await screen.findByRole('button', { name: 'Save AI Provider' })
      expect(screen.queryByText('Settings saved')).not.toBeInTheDocument()
    })

    it('blocks a second submit while the first is in flight', async () => {
      const user = userEvent.setup()
      const release = held()

      renderGroup()
      await saveWith(user)

      expect(
        await screen.findByRole('button', { name: 'Saving…' }),
      ).toBeDisabled()
      release()
    })

    it('says what the wait is for, since the button is below the fold', async () => {
      const user = userEvent.setup()
      const release = held()

      renderGroup()
      await saveWith(user)

      expect(
        await screen.findByText(/Checking what the change touches/),
      ).toBeVisible()
      release()
    })

    it('marks the form busy, so the fields read as out of reach', async () => {
      const user = userEvent.setup()
      const release = held()

      renderGroup()
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

      renderGroup()
      const key = await screen.findByLabelText('API Key')
      await user.type(key, 'sk-a-real-key')
      await saveWith(user)

      await screen.findByText('Settings saved')
      expect(key).toHaveValue('')
    })

    it('adopts what was kept, so the library list follows a Plex change', async () => {
      const user = userEvent.setup()
      backend({}, { music_libraries: ['Music', 'Vinyl'] })

      renderGroup('plex')
      await saveWith(user, 'Save Plex')

      await screen.findByText('Settings saved')
      expect(
        await screen.findByRole('option', { name: 'Vinyl' }),
      ).toBeInTheDocument()
    })
  })
})

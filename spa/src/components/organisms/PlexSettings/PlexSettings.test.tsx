import { render as mount, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { server } from '@test'
import type { PlexSettingsProps } from './PlexSettings.tsx'
import { PlexSettings } from './PlexSettings.tsx'

/** A signed-in account with a connected server behind it. */
const PROPS: PlexSettingsProps = {
  library: 'Music',
  connected: true,
  linked: true,
  serverName: 'Living Room',
  serverId: 'abc123',
  libraries: ['Music'],
}

/** What a signed-out card is rendered with. */
const SIGNED_OUT: Partial<PlexSettingsProps> = {
  linked: false,
  connected: false,
  serverName: '',
  serverId: '',
}

/** What a synced library reports, on the route the card's counts fetch. */
const STATS = {
  total_tracks: 52341,
  genres: [{ name: 'Rock', count: 900 }],
  decades: [{ name: '1980s', count: 620 }],
}

const PIN = {
  pin_id: 42,
  code: 'WXYZ',
  url: 'https://app.plex.tv/auth/#!?code=WXYZ',
  expires_in: 900,
}

const SERVERS = [
  { id: 'abc123', name: 'Living Room', owned: true },
  { id: 'def456', name: 'A Friend', owned: false },
]

/** The card inside a router, since its counts come from a resource route. */
function render(props: Partial<PlexSettingsProps> = {}) {
  const router = createMemoryRouter([
    { index: true, Component: () => <PlexSettings {...PROPS} {...props} /> },
    { path: 'settings/stats', loader: () => STATS },
  ])
  return mount(<RouterProvider router={router} />)
}

/** Script the pin exchange: a pin, then the poll answers it takes. */
function signIn(...polls: object[]) {
  const answers = [...polls]
  server.use(
    http.post('/api/plex/link', () => HttpResponse.json(PIN)),
    http.get('/api/plex/link/:pin', () =>
      HttpResponse.json(answers.length > 1 ? answers.shift() : answers[0]),
    ),
  )
}

/** Sign in and get as far as the server picker. */
async function toPicker() {
  signIn({ state: 'linked', servers: SERVERS })
  render(SIGNED_OUT)
  await userEvent.click(screen.getByRole('button', { name: 'Sign in to Plex' }))
  return screen.findByRole('combobox', { name: 'Plex Server' })
}

describe('PlexSettings', () => {
  /** The tab the card opens; a blocked popup is what `null` stands for. */
  let opened = vi.fn().mockReturnValue(null)

  beforeEach(() => {
    opened = vi.fn().mockReturnValue(null)
    vi.stubGlobal('open', opened)
    // A signed-in card lists its servers on mount.
    server.use(
      http.get('/api/plex/servers', () =>
        HttpResponse.json({ state: 'linked', servers: SERVERS }),
      ),
    )
  })

  describe('when nobody has signed in', () => {
    it('says so rather than showing an empty server name', () => {
      render(SIGNED_OUT)

      expect(screen.getByRole('status')).toHaveTextContent('Not signed in')
    })

    it('offers the sign-in and nothing else', () => {
      render(SIGNED_OUT)

      expect(
        screen.getByRole('button', { name: 'Sign in to Plex' }),
      ).toBeVisible()
      expect(
        screen.queryByRole('button', { name: 'Sign out' }),
      ).not.toBeInTheDocument()
    })

    it('has no server or token field, since neither is typed any more', () => {
      render(SIGNED_OUT)

      expect(
        screen.queryByRole('textbox', { name: 'Plex Server URL' }),
      ).not.toBeInTheDocument()
      expect(screen.queryByLabelText('Plex Token')).not.toBeInTheDocument()
    })
  })

  describe('when a server is connected', () => {
    it('names it, so it is clear which one is in force', () => {
      render()

      expect(screen.getByRole('status')).toHaveTextContent(
        'Connected to Living Room',
      )
    })

    it('names it as the failure when it stops answering', () => {
      render({ connected: false })

      expect(screen.getByRole('status')).toHaveTextContent(
        'Living Room is not answering',
      )
    })

    it('says a server is still unchosen rather than blaming one', () => {
      render({ connected: false, serverName: '' })

      expect(screen.getByRole('status')).toHaveTextContent(
        'Signed in, but no server is chosen',
      )
    })

    it('leaves the library to LibraryField', () => {
      render({ libraries: ['Music', 'Vinyl'] })

      expect(
        screen.getByRole('combobox', { name: 'Music Library' }),
      ).toHaveValue('Music')
    })

    it('reports the counts here, under the fields that decide them', async () => {
      render()

      expect(await screen.findByText('Total Tracks')).toBeVisible()
      expect(screen.getByText('52,341')).toBeVisible()
    })
  })

  describe('signing in', () => {
    it('shows the code the user has to approve', async () => {
      signIn({ state: 'pending' })
      render(SIGNED_OUT)

      await userEvent.click(
        screen.getByRole('button', { name: 'Sign in to Plex' }),
      )

      expect(await screen.findByText('WXYZ')).toBeVisible()
    })

    it('offers the approval address, in case the tab was blocked', async () => {
      signIn({ state: 'pending' })
      render(SIGNED_OUT)

      await userEvent.click(
        screen.getByRole('button', { name: 'Sign in to Plex' }),
      )

      expect(await screen.findByRole('link')).toHaveAttribute('href', PIN.url)
    })

    it('opens the tab in the click, since a later popup is blocked', async () => {
      signIn({ state: 'pending' })
      render(SIGNED_OUT)

      await userEvent.click(
        screen.getByRole('button', { name: 'Sign in to Plex' }),
      )

      expect(opened).toHaveBeenCalledWith('', '_blank')
    })

    it('offers the servers once the pin comes back approved', async () => {
      signIn({ state: 'linked', servers: SERVERS })
      render(SIGNED_OUT)

      await userEvent.click(
        screen.getByRole('button', { name: 'Sign in to Plex' }),
      )

      expect(
        await screen.findByRole('combobox', { name: 'Plex Server' }),
      ).toBeVisible()
    })

    it('marks a shared server, since it is not the account owner’s own', async () => {
      signIn({ state: 'linked', servers: SERVERS })
      render(SIGNED_OUT)

      await userEvent.click(
        screen.getByRole('button', { name: 'Sign in to Plex' }),
      )
      await screen.findByRole('combobox', { name: 'Plex Server' })

      expect(
        screen.getByRole('option', { name: 'A Friend (shared)' }),
      ).toBeVisible()
    })

    it('abandons the pin when cancelled', async () => {
      signIn({ state: 'pending' })
      render(SIGNED_OUT)

      await userEvent.click(
        screen.getByRole('button', { name: 'Sign in to Plex' }),
      )
      await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))

      expect(
        screen.getByRole('button', { name: 'Sign in to Plex' }),
      ).toBeVisible()
    })

    it('reports a refusal from plex.tv rather than waiting forever', async () => {
      server.use(
        http.post('/api/plex/link', () =>
          HttpResponse.json(
            { detail: 'Could not reach plex.tv' },
            { status: 502 },
          ),
        ),
      )
      render(SIGNED_OUT)

      await userEvent.click(
        screen.getByRole('button', { name: 'Sign in to Plex' }),
      )

      expect(await screen.findByRole('alert')).toHaveTextContent(
        'Could not reach plex.tv',
      )
    })
  })

  describe('never calling a signed-in account signed out', () => {
    it('says it is working while the pin is being created', async () => {
      let release = () => {
        // Replaced by the promise's own resolve, below.
      }
      const held = new Promise<void>((resolve) => {
        release = resolve
      })
      server.use(
        http.post('/api/plex/link', async () => {
          await held
          return HttpResponse.json(PIN)
        }),
      )
      render(SIGNED_OUT)

      await userEvent.click(
        screen.getByRole('button', { name: 'Sign in to Plex' }),
      )

      await waitFor(() => {
        expect(screen.getByRole('status')).toHaveTextContent('Talking to Plex')
      })
      release()
    })

    it('stays signed in while a chosen server is being resolved', async () => {
      const picker = await toPicker()
      let release = () => {
        // Replaced by the promise's own resolve, below.
      }
      const held = new Promise<void>((resolve) => {
        release = resolve
      })
      server.use(
        http.post('/api/plex/server', async () => {
          await held
          return HttpResponse.json({ linked: true, connected: true })
        }),
      )

      await userEvent.selectOptions(picker, 'abc123')

      await waitFor(() => {
        expect(screen.getByRole('status')).toHaveTextContent('Talking to Plex')
      })
      expect(screen.queryByText('Not signed in')).not.toBeInTheDocument()
      release()
    })

    it('does not fall back to signed out when the picker is left', async () => {
      // The loaded config predates the sign-in and still says signed out.
      await toPicker()
      server.use(
        http.post('/api/plex/server', () =>
          HttpResponse.json({ detail: 'nope' }, { status: 422 }),
        ),
      )

      expect(screen.queryByText('Not signed in')).not.toBeInTheDocument()
    })
  })

  describe('choosing a server', () => {
    it('starts on no server, since one has not been chosen yet', async () => {
      const picker = await toPicker()

      expect(picker).toHaveValue('')
    })

    it('adopts what the choice reported, without reloading the page', async () => {
      const picker = await toPicker()
      server.use(
        http.post('/api/plex/server', () =>
          HttpResponse.json({
            linked: true,
            connected: true,
            server_name: 'A Friend',
            server_id: 'def456',
            music_libraries: ['Shared Music'],
          }),
        ),
      )

      await userEvent.selectOptions(picker, 'def456')

      await waitFor(() => {
        expect(screen.getByRole('status')).toHaveTextContent(
          'Connected to A Friend',
        )
      })
      expect(
        screen.getByRole('combobox', { name: 'Music Library' }),
      ).toHaveValue('Shared Music')
    })

    it('stays on the picker when the chosen server will not answer', async () => {
      const picker = await toPicker()
      server.use(
        http.post('/api/plex/server', () =>
          HttpResponse.json(
            { detail: 'Plex listed no address for that server' },
            { status: 422 },
          ),
        ),
      )

      await userEvent.selectOptions(picker, 'abc123')

      expect(await screen.findByRole('alert')).toHaveTextContent('no address')
      expect(
        screen.getByRole('combobox', { name: 'Plex Server' }),
      ).toBeVisible()
    })
  })

  describe('changing server once one is chosen', () => {
    /** A card already signed in, whose servers load on mount. */
    function listed(...servers: object[]) {
      server.use(
        http.get('/api/plex/servers', () =>
          HttpResponse.json({ state: 'linked', servers }),
        ),
      )
      return render()
    }

    it('offers the choice upfront, not behind a button', async () => {
      listed(...SERVERS)

      expect(
        await screen.findByRole('combobox', { name: 'Plex Server' }),
      ).toBeVisible()
      expect(
        screen.queryByRole('button', { name: 'Change server' }),
      ).not.toBeInTheDocument()
    })

    it('marks the server already in force', async () => {
      listed(...SERVERS)

      expect(
        await screen.findByRole('combobox', { name: 'Plex Server' }),
      ).toHaveValue('abc123')
    })

    it('switches on the selection alone, with nothing to confirm', async () => {
      listed(...SERVERS)
      server.use(
        http.post('/api/plex/server', () =>
          HttpResponse.json({
            linked: true,
            connected: true,
            server_name: 'A Friend',
            server_id: 'def456',
            music_libraries: ['Shared Music'],
          }),
        ),
      )

      await userEvent.selectOptions(
        await screen.findByRole('combobox', { name: 'Plex Server' }),
        'def456',
      )

      expect(await screen.findByText('Connected to A Friend')).toBeVisible()
    })

    it('still names the server when plex.tv will not list them', async () => {
      // Losing the dropdown must not lose which server is in force.
      server.use(http.get('/api/plex/servers', () => HttpResponse.error()))
      render()

      // Awaited: unmounting on a listing still in flight aborts it, and msw
      // reports that abort as an unhandled rejection.
      expect(await screen.findByRole('status')).toHaveTextContent(
        'Connected to Living Room',
      )
      expect(
        screen.queryByRole('combobox', { name: 'Plex Server' }),
      ).not.toBeInTheDocument()
    })
  })

  describe('signing out', () => {
    it('goes back to the sign-in, with no server named', async () => {
      server.use(
        http.delete('/api/plex/link', () =>
          HttpResponse.json({ linked: false, connected: false }),
        ),
      )
      render()

      await userEvent.click(screen.getByRole('button', { name: 'Sign out' }))

      expect(
        await screen.findByRole('button', { name: 'Sign in to Plex' }),
      ).toBeVisible()
    })

    it('reports a failure and stays signed in', async () => {
      server.use(
        http.delete('/api/plex/link', () =>
          HttpResponse.json({ detail: 'disk full' }, { status: 500 }),
        ),
      )
      render()

      await userEvent.click(screen.getByRole('button', { name: 'Sign out' }))

      expect(await screen.findByRole('alert')).toHaveTextContent('disk full')
      expect(screen.getByRole('status')).toHaveTextContent(
        'Connected to Living Room',
      )
    })
  })
})

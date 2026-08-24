import { render as mount, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { beforeEach, describe, expect, it } from 'vitest'

import { server } from '@test'
import { LibrarySyncProvider } from '../LibrarySyncProvider/LibrarySyncProvider.tsx'
import { Footer } from './Footer.tsx'

/**
 * The bar reads the shell's poller, so it needs one above it.
 *
 * A data router too: the version and model come through a fetcher, which
 * answers nothing here — this file is about the library half of the bar.
 */
function render() {
  const router = createMemoryRouter([
    {
      index: true,
      Component: () => (
        <LibrarySyncProvider>
          <Footer />
        </LibrarySyncProvider>
      ),
    },
    { path: 'footer', loader: () => null },
  ])
  return mount(<RouterProvider router={router} />)
}

/** A library that has been synced and is sitting idle. */
const IDLE = {
  track_count: 80058,
  synced_at: new Date().toISOString(),
  is_syncing: false,
  plex_connected: true,
}

/** Answer the status poll with `status`, once and thereafter. */
function reporting(status: object) {
  server.use(http.get('/api/library/status', () => HttpResponse.json(status)))
}

describe('Footer', () => {
  beforeEach(() => {
    reporting(IDLE)
  })

  it('says how much the library holds', async () => {
    render()

    expect(await screen.findByText('80,058 tracks')).toBeVisible()
  })

  it('says when it last synced', async () => {
    render()

    expect(await screen.findByText('Just now')).toBeVisible()
  })

  it('says nothing at all before the first poll answers', () => {
    render()

    expect(screen.queryByText(/tracks/)).not.toBeInTheDocument()
  })

  describe('before anything is synced', () => {
    const UNSYNCED = {
      track_count: 0,
      synced_at: null,
      is_syncing: false,
      plex_connected: true,
    }

    it('offers the sync rather than starting one', async () => {
      // `frontend/app.js:2352` started it unasked, spending someone's Plex
      // server for as long as their library takes.
      let started = false
      server.use(
        http.post('/api/library/sync', () => {
          started = true
          return HttpResponse.json({ started: true, blocking: false })
        }),
      )
      reporting(UNSYNCED)
      render()

      expect(
        await screen.findByRole('button', { name: 'Sync now' }),
      ).toBeVisible()
      expect(started).toBe(false)
    })

    it('says so, rather than reporting zero tracks', async () => {
      reporting(UNSYNCED)
      render()

      expect(await screen.findByText('Library not synced')).toBeVisible()
      expect(screen.queryByText('0 tracks')).not.toBeInTheDocument()
    })

    it('stays quiet with no Plex to sync from', async () => {
      reporting({ ...UNSYNCED, plex_connected: false })
      render()

      await waitFor(() => {
        expect(screen.queryByText('Library not synced')).not.toBeInTheDocument()
      })
    })
  })

  describe('while a sync runs', () => {
    it('reports the percentage once there is one', async () => {
      reporting({
        ...IDLE,
        is_syncing: true,
        sync_progress: { phase: 'processing', current: 40, total: 200 },
      })
      render()

      expect(await screen.findByText('Syncing 20%')).toBeVisible()
    })

    it('says only that it is syncing where nothing is measurable', async () => {
      // A percentage would sit at 0 and read as a hang.
      reporting({
        ...IDLE,
        is_syncing: true,
        sync_progress: { phase: 'fetching_albums', current: 0, total: 0 },
      })
      render()

      expect(await screen.findByText('Syncing…')).toBeVisible()
    })

    it('refuses a second sync while one is in flight', async () => {
      reporting({ ...IDLE, is_syncing: true })
      render()

      expect(
        await screen.findByRole('button', { name: 'Refresh' }),
      ).toBeDisabled()
    })
  })

  describe('the progress dialog', () => {
    const RESYNC = { ...IDLE, is_syncing: true }

    it('does not open itself over a library that is already usable', async () => {
      reporting(RESYNC)
      render()

      await screen.findByRole('button', { name: /Syncing/ })
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })

    it('offers the progress text as the way back in', async () => {
      // `frontend/app.js:2244` hid it with no way back, leaving only the bar.
      // What a click does is asserted in `Footer.browser.test.tsx`.
      reporting(RESYNC)
      render()

      expect(
        await screen.findByRole('button', { name: /Syncing/ }),
      ).toBeEnabled()
    })

    it('offers nothing to open once the sync is done', async () => {
      reporting(IDLE)
      render()

      expect(await screen.findByText('Just now')).toBeVisible()
      expect(
        screen.queryByRole('button', { name: /Syncing/ }),
      ).not.toBeInTheDocument()
    })
  })

  describe('starting one', () => {
    it('asks the server, then goes back to polling', async () => {
      let started = false
      server.use(
        http.post('/api/library/sync', () => {
          started = true
          return HttpResponse.json({ started: true, blocking: false })
        }),
      )
      render()

      await userEvent.click(
        await screen.findByRole('button', { name: 'Refresh' }),
      )

      await waitFor(() => {
        expect(started).toBe(true)
      })
    })

    it('treats "already running" as the outcome asked for', async () => {
      server.use(
        http.post('/api/library/sync', () =>
          HttpResponse.json(
            { detail: 'Sync already in progress' },
            { status: 409 },
          ),
        ),
      )
      render()

      await userEvent.click(
        await screen.findByRole('button', { name: 'Refresh' }),
      )

      await waitFor(() => {
        expect(screen.queryByRole('alert')).not.toBeInTheDocument()
      })
    })

    it('reports a refusal it cannot explain away', async () => {
      server.use(
        http.post('/api/library/sync', () =>
          HttpResponse.json(
            { detail: 'Plex is not connected' },
            { status: 503 },
          ),
        ),
      )
      render()

      await userEvent.click(
        await screen.findByRole('button', { name: 'Refresh' }),
      )

      expect(await screen.findByRole('alert')).toHaveTextContent(
        'Plex is not connected',
      )
    })
  })

  it('surfaces what a failed sync left behind', async () => {
    reporting({ ...IDLE, error: 'Plex went away mid-sync' })
    render()

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Plex went away mid-sync',
    )
  })
})
